"""Pruebas unitarias de Medallotel. Ejecutar: python -m unittest test_suite -v"""
import os
import tempfile
import unittest

import db
import services as svc
from services import NotFoundError, ValidationError


class BaseTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db.DB_PATH = self.path
        db.init_db(seed_defaults=False)

    def tearDown(self):
        os.remove(self.path)

    def make_reservation(self, nights=3, rate=100000.0, consumptions=()):
        room = svc.create_room("101", rate)
        res = svc.create_reservation("Ana Pérez", room["id"], "2026-11-01", f"2026-11-{1 + nights:02d}")
        for i, (name, qty, price) in enumerate(consumptions):
            s = svc.create_service(f"{name}{i}", price)
            svc.add_consumption(res["id"], s["id"], qty)
        return res["id"]


class TestReservationsAndServices(BaseTest):
    def test_overlap_rejected(self):
        room = svc.create_room("201", 80000)
        svc.create_reservation("A", room["id"], "2026-11-01", "2026-11-05")
        with self.assertRaises(ValidationError):
            svc.create_reservation("B", room["id"], "2026-11-04", "2026-11-06")
        svc.create_reservation("C", room["id"], "2026-11-05", "2026-11-07")  # contiguas: ok

    def test_consumption_keeps_historical_price(self):
        rid = self.make_reservation()
        s = svc.create_service("Spa", 50000)
        svc.add_consumption(rid, s["id"], 1)
        with db.get_connection() as c:
            c.execute("UPDATE services SET price = 99999 WHERE id = ?", (s["id"],))
        self.assertEqual(svc.list_consumptions(rid)[-1]["unit_price"], 50000.0)

    def test_invalid_quantity(self):
        rid = self.make_reservation()
        s = svc.create_service("Cena", 30000)
        with self.assertRaises(ValidationError):
            svc.add_consumption(rid, s["id"], 0)


class TestInvoicing(BaseTest):
    def test_invoice_calculation(self):
        rid = self.make_reservation(3, 100000.0, [("Desayuno", 2, 15000.0), ("Lavandería", 1, 20000.0)])
        inv = svc.generate_invoice(rid)
        self.assertEqual(inv["total_lodging"], 300000.0)
        self.assertEqual(inv["total_services"], 50000.0)
        self.assertEqual(inv["grand_total"], 350000.0)
        self.assertEqual(inv["paid_amount"], 0.0)
        self.assertEqual(inv["balance"], 350000.0)
        self.assertEqual(inv["status"], "PENDIENTE")
        self.assertRegex(inv["invoice_number"], r"^FAC-\d{8}-\d{4}$")
        self.assertEqual(len(inv["items"]["services"]), 2)
        self.assertEqual(inv["items"]["lodging"]["nights"], 3)

    def test_duplicate_invoice_raises_conflict(self):
        rid = self.make_reservation()
        inv1 = svc.generate_invoice(rid)
        self.assertIsNotNone(inv1)
        with self.assertRaises(svc.ConflictError):
            svc.generate_invoice(rid)

    def test_invoice_unknown_reservation(self):
        with self.assertRaises(NotFoundError):
            svc.generate_invoice(99999)

    def test_get_invoice_by_reservation(self):
        rid = self.make_reservation()
        inv = svc.generate_invoice(rid)
        self.assertEqual(svc.get_invoice_detail(reservation_id=rid)["id"], inv["id"])

    def test_list_invoices(self):
        self.assertEqual(svc.list_invoices(), [])
        rid = self.make_reservation()
        inv = svc.generate_invoice(rid)
        listed = svc.list_invoices()
        self.assertEqual([i["id"] for i in listed], [inv["id"]])
        self.assertEqual(listed[0]["reservation_id"], rid)

    def test_valid_payment(self):
        inv = svc.generate_invoice(self.make_reservation(2, 100000.0))
        res = svc.register_payment(inv["id"], 50000.0, "EFECTIVO", "recibo 1")
        self.assertEqual(res["paid_amount"], 50000.0)
        self.assertEqual(res["balance"], 150000.0)
        self.assertEqual(len(res["payments"]), 1)
        self.assertEqual(res["payments"][0]["reference"], "recibo 1")

    def test_reject_non_positive_amount(self):
        inv = svc.generate_invoice(self.make_reservation())
        for bad in (0, -10, "abc", None, True):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                svc.register_payment(inv["id"], bad, "EFECTIVO", None)

    def test_reject_invalid_method(self):
        inv = svc.generate_invoice(self.make_reservation())
        with self.assertRaises(ValidationError):
            svc.register_payment(inv["id"], 1000, "CHEQUE", None)

    def test_reject_overpayment(self):
        inv = svc.generate_invoice(self.make_reservation(1, 100000.0))
        with self.assertRaises(ValidationError):
            svc.register_payment(inv["id"], 100000.01, "TARJETA", None)
        detail = svc.get_invoice_detail(invoice_id=inv["id"])
        self.assertEqual(detail["paid_amount"], 0.0)
        self.assertEqual(detail["payments"], [])

    def test_status_transitions(self):
        inv = svc.generate_invoice(self.make_reservation(2, 100000.0))
        self.assertEqual(inv["status"], "PENDIENTE")
        r1 = svc.register_payment(inv["id"], 80000.0, "TARJETA", card_last4="4321", auth_number="AUT-1")
        self.assertEqual(r1["status"], "PARCIALMENTE_PAGADA")
        r2 = svc.register_payment(inv["id"], 120000.0, "TRANSFERENCIA", reference="TRX-999")
        self.assertEqual(r2["status"], "PAGADA")
        self.assertEqual(r2["balance"], 0.0)
        self.assertEqual(len(r2["payments"]), 2)
        with self.assertRaises(ValidationError):  # ya saldada
            svc.register_payment(inv["id"], 1, "EFECTIVO", None)

    def test_no_consumption_after_invoice(self):
        rid = self.make_reservation()
        svc.generate_invoice(rid)
        s = svc.create_service("Minibar", 5000)
        with self.assertRaises(ValidationError):
            svc.add_consumption(rid, s["id"], 1)


class TestPermissionsAndAudit(BaseTest):
    def setUp(self):
        super().setUp()
        # Inicializar usuarios
        db.init_db(seed_defaults=True)

    def test_auth_login_and_roles(self):
        admin_auth = svc.authenticate_user("admin", "admin123")
        self.assertEqual(admin_auth["user"]["role"], "ADMINISTRADOR")
        self.assertIsNotNone(admin_auth["token"])

        recep_auth = svc.authenticate_user("recepcion", "recep123")
        self.assertEqual(recep_auth["user"]["role"], "RECEPCIONISTA")

        # Credenciales incorrectas
        with self.assertRaises(svc.AuthenticationError):
            svc.authenticate_user("admin", "clave_erronea")

    def test_permission_denied_for_non_admin(self):
        recep_user = svc.authenticate_user("recepcion", "recep123")["user"]
        # Recepcionista no puede crear servicios (exclusivo Administrador)
        with self.assertRaises(svc.PermissionDeniedError):
            svc.require_role(recep_user, ["ADMINISTRADOR"])

        admin_user = svc.authenticate_user("admin", "admin123")["user"]
        # Administrador sí tiene permiso
        svc.require_role(admin_user, ["ADMINISTRADOR"])

    def test_audit_logs_recorded(self):
        admin_auth = svc.authenticate_user("admin", "admin123")
        room = svc.create_room("901", 100000.0)
        res = svc.create_reservation("Invitado Audit", room["id"], "2026-11-20", "2026-11-22", user=admin_auth["user"])

        with db.get_connection() as c:
            logs = c.execute("SELECT * FROM audit_logs WHERE action = 'CREATE_RESERVATION' AND entity_id = ?", (res["id"],)).fetchall()
            self.assertTrue(len(logs) >= 1)
            self.assertEqual(logs[0]["action"], "CREATE_RESERVATION")
            self.assertEqual(logs[0]["user_id"], admin_auth["user"]["id"])

    def test_reservation_not_confirmed_if_audit_fails(self):
        room = svc.create_room("902", 100000.0)
        # Provocar fallo en audit_logs eliminando la tabla temporalmente para verificar rollback
        with db.get_connection() as c:
            c.execute("DROP TABLE audit_logs")

        with self.assertRaises(svc.AuditError):
            svc.create_reservation("Test Falla", room["id"], "2026-11-20", "2026-11-22")

        # Verificar que la reserva NO fue creada en la base de datos
        with db.get_connection() as c:
            r = c.execute("SELECT 1 FROM reservations WHERE guest_name = 'Test Falla'").fetchone()
            self.assertIsNone(r)


class TestRoomsAndAvailability(BaseTest):
    def test_room_out_of_service_not_available_and_cannot_reserve(self):
        room = svc.create_room("903", 100000.0, status="MANTENIMIENTO")
        # No debe aparecer en list_rooms con fechas
        available = svc.list_rooms(check_in="2026-11-20", check_out="2026-11-25")
        self.assertNotIn(room["id"], [r["id"] for r in available])

        # Intentar reservar habitación fuera de servicio debe fallar
        with self.assertRaises(ValidationError):
            svc.create_reservation("Huesped Fallo", room["id"], "2026-11-20", "2026-11-25")

    def test_invalid_dates_rejected(self):
        room = svc.create_room("904", 100000.0)
        # Salida antes de entrada
        with self.assertRaises(ValidationError):
            svc.create_reservation("Fechas Mal", room["id"], "2026-11-25", "2026-11-20")
        # Salida igual a entrada
        with self.assertRaises(ValidationError):
            svc.create_reservation("Fechas Mal", room["id"], "2026-11-20", "2026-11-20")


class TestPaymentsValidation(BaseTest):
    def test_card_payment_requires_last4_and_auth(self):
        rid = self.make_reservation()
        inv = svc.generate_invoice(rid)

        # Sin last4 o auth_number
        with self.assertRaises(ValidationError):
            svc.register_payment(inv["id"], 50000.0, "TARJETA", reference="REF")

        with self.assertRaises(ValidationError):
            svc.register_payment(inv["id"], 50000.0, "TARJETA", card_last4="12", auth_number="AUTH-1")

        # Válido
        paid = svc.register_payment(inv["id"], 50000.0, "TARJETA", card_last4="4321", auth_number="AUTH-999")
        self.assertEqual(paid["payments"][-1]["card_last4"], "4321")
        self.assertEqual(paid["payments"][-1]["auth_number"], "AUTH-999")

    def test_transfer_payment_requires_voucher(self):
        rid = self.make_reservation()
        inv = svc.generate_invoice(rid)

        with self.assertRaises(ValidationError):
            svc.register_payment(inv["id"], 50000.0, "TRANSFERENCIA", reference="")

        paid = svc.register_payment(inv["id"], 50000.0, "TRANSFERENCIA", reference="TRX-123456")
        self.assertEqual(paid["payments"][-1]["reference"], "TRX-123456")


if __name__ == "__main__":
    unittest.main(verbosity=2)

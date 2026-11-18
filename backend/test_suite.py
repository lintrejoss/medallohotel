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
        db.init_db()

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

    def test_generate_invoice_is_idempotent(self):
        rid = self.make_reservation()
        a, b = svc.generate_invoice(rid), svc.generate_invoice(rid)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(a["invoice_number"], b["invoice_number"])

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
        r1 = svc.register_payment(inv["id"], 80000.0, "TARJETA", "AUT-1")
        self.assertEqual(r1["status"], "PARCIALMENTE_PAGADA")
        r2 = svc.register_payment(inv["id"], 120000.0, "TRANSFERENCIA", "TRX-9")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)

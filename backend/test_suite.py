"""
Script de pruebas unitarias y de validación de negocio para Medallotel Etapa 1.
"""
import unittest
import os
import sys

# Agregar la raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.db import init_db, get_db_connection
from backend.services import (
    BusinessError,
    validate_dates,
    find_guest_by_doc,
    get_available_rooms,
    create_reservation,
    get_active_reservations,
    get_reservation_detail
)

class TestMedallotelEtapa1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_find_guest_valid_and_invalid(self):
        # Huésped existente (semilla)
        guest = find_guest_by_doc('1020304050')
        self.assertIsNotNone(guest)
        self.assertEqual(guest['first_name'], 'Carlos')

        # Huésped inexistente
        guest_none = find_guest_by_doc('999999999999')
        self.assertIsNone(guest_none)

    def test_case_2_reject_invalid_dates(self):
        # Caso 2 solicitado por el usuario: rechazar fechas inválidas (check-in posterior o igual a check-out)
        with self.assertRaises(BusinessError) as ctx:
            validate_dates('2026-12-10', '2026-12-05')
        self.assertIn("estrictamente anterior", ctx.exception.message)

        with self.assertRaises(BusinessError) as ctx2:
            validate_dates('2026-12-10', '2026-12-10')
        self.assertIn("estrictamente anterior", ctx2.exception.message)

    def test_out_of_service_room_not_available(self):
        # La habitación 302 está FUERA_DE_SERVICIO
        rooms = get_available_rooms('2026-12-10', '2026-12-15')
        room_numbers = [r['room_number'] for r in rooms]
        self.assertNotIn('302', room_numbers)

    def test_case_3_reject_overlapping_reservation(self):
        # En el seeder existe una reserva activa para habitación 101 del 2026-12-01 al 2026-12-05
        # Consultar disponibilidad en ese rango no debe incluir la habitación 101
        rooms = get_available_rooms('2026-12-02', '2026-12-04')
        room_numbers = [r['room_number'] for r in rooms]
        self.assertNotIn('101', room_numbers)

        # Intentar crear reserva forzadamente para la 101 en fechas cruzadas debe lanzar BusinessError
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM rooms WHERE room_number = '101'")
        room_101_id = c.fetchone()['id']
        c.execute("SELECT id FROM guests WHERE doc_number = '1020304050'")
        guest_id = c.fetchone()['id']
        conn.close()

        with self.assertRaises(BusinessError) as ctx:
            create_reservation(guest_id, room_101_id, '2026-12-03', '2026-12-06')
        self.assertIn("ya tiene la reserva activa", ctx.exception.message)

    def test_case_1_create_valid_reservation(self):
        # Caso 1 solicitado: crear una reserva válida sin solapamientos
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM rooms WHERE room_number = '201'")
        room_201_id = c.fetchone()['id']
        c.execute("SELECT id FROM guests WHERE doc_number = '9876543210'")
        guest_id = c.fetchone()['id']
        conn.close()

        res = create_reservation(guest_id, room_201_id, '2026-12-10', '2026-12-14')
        self.assertIsNotNone(res)
        self.assertEqual(res['room_number'], '201')
        self.assertEqual(res['total_nights'], 4)
        self.assertEqual(res['nightly_rate'], 230000.0)
        self.assertEqual(res['total_lodging'], 920000.0)
        self.assertEqual(res['status'], 'ACTIVA')

        # Verificar que aparezca en reservas activas
        active = get_active_reservations()
        res_codes = [r['code'] for r in active]
        self.assertIn(res['code'], res_codes)

if __name__ == '__main__':
    unittest.main()

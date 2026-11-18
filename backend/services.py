"""
Capa de lógica y reglas de negocio para Medallotel.
"""
from datetime import datetime, date
import uuid
from backend.db import get_db_connection

class BusinessError(Exception):
    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field

def validate_dates(check_in_str, check_out_str):
    if not check_in_str:
        raise BusinessError("La fecha de entrada es obligatoria.", field="check_in_date")
    if not check_out_str:
        raise BusinessError("La fecha de salida es obligatoria.", field="check_out_date")

    try:
        check_in = datetime.strptime(check_in_str, "%Y-%m-%d").date()
    except ValueError:
        raise BusinessError("Formato de fecha de entrada inválido (debe ser AAAA-MM-DD).", field="check_in_date")

    try:
        check_out = datetime.strptime(check_out_str, "%Y-%m-%d").date()
    except ValueError:
        raise BusinessError("Formato de fecha de salida inválido (debe ser AAAA-MM-DD).", field="check_out_date")

    if check_in >= check_out:
        raise BusinessError("La fecha de entrada debe ser estrictamente anterior a la fecha de salida (mínimo 1 noche).", field="check_out_date")

    nights = (check_out - check_in).days
    return check_in_str, check_out_str, nights

def find_guest_by_doc(doc_number):
    if not doc_number or not doc_number.strip():
        raise BusinessError("Ingrese un número de documento.", field="doc_number")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, doc_type, doc_number, first_name, last_name, phone, email
    FROM guests
    WHERE doc_number = ?
    """, (doc_number.strip(),))
    guest = cursor.fetchone()
    conn.close()

    if not guest:
        return None
    return dict(guest)

def get_available_rooms(check_in_str, check_out_str):
    validate_dates(check_in_str, check_out_str)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Una habitación está disponible si:
    # 1. Su estado es 'DISPONIBLE' (no está FUERA_DE_SERVICIO).
    # 2. No existe ninguna reserva 'ACTIVA' cuyo intervalo de fechas se cruce:
    #    (check_in_reserva < fecha_salida_solicitada) Y (check_out_reserva > fecha_entrada_solicitada)
    query = """
    SELECT r.id, r.room_number, r.room_type, r.capacity, r.price_per_night, r.status
    FROM rooms r
    WHERE r.status = 'DISPONIBLE'
      AND r.id NOT IN (
          SELECT res.room_id
          FROM reservations res
          WHERE res.status = 'ACTIVA'
            AND res.check_in_date < ?
            AND res.check_out_date > ?
      )
    ORDER BY r.room_number ASC
    """
    cursor.execute(query, (check_out_str, check_in_str))
    rooms = cursor.fetchall()
    conn.close()

    return [dict(r) for r in rooms]

def create_reservation(guest_id, room_id, check_in_str, check_out_str):
    check_in, check_out, nights = validate_dates(check_in_str, check_out_str)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Validar que el huésped exista
    cursor.execute("SELECT id, first_name, last_name FROM guests WHERE id = ?", (guest_id,))
    guest = cursor.fetchone()
    if not guest:
        conn.close()
        raise BusinessError("El huésped especificado no existe.", field="guest_id")

    # Validar habitación y disponibilidad
    cursor.execute("SELECT id, room_number, room_type, price_per_night, status FROM rooms WHERE id = ?", (room_id,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        raise BusinessError("La habitación especificada no existe.", field="room_id")

    if room['status'] != 'DISPONIBLE':
        conn.close()
        raise BusinessError(f"La habitación {room['room_number']} no está disponible (estado: {room['status']}).", field="room_id")

    # Validar cruce de reservas activas
    cursor.execute("""
    SELECT code, check_in_date, check_out_date FROM reservations
    WHERE room_id = ?
      AND status = 'ACTIVA'
      AND check_in_date < ?
      AND check_out_date > ?
    """, (room_id, check_out_str, check_in_str))
    conflict = cursor.fetchone()

    if conflict:
        conn.close()
        raise BusinessError(
            f"La habitación {room['room_number']} ya tiene la reserva activa {conflict['code']} entre el {conflict['check_in_date']} y {conflict['check_out_date']}.",
            field="room_id"
        )

    # Calcular tarifas y código único
    rate = room['price_per_night']
    total_lodging = rate * nights
    unique_code = f"RES-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

    cursor.execute("""
    INSERT INTO reservations (code, guest_id, room_id, check_in_date, check_out_date, total_nights, nightly_rate, total_lodging, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVA')
    """, (unique_code, guest_id, room_id, check_in_str, check_out_str, nights, rate, total_lodging))

    reservation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return get_reservation_detail(reservation_id)

def get_active_reservations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT res.id, res.code, res.check_in_date, res.check_out_date, res.total_nights,
           res.nightly_rate, res.total_lodging, res.status, res.created_at,
           g.id as guest_id, g.doc_type, g.doc_number, g.first_name, g.last_name, g.phone, g.email,
           r.id as room_id, r.room_number, r.room_type, r.capacity
    FROM reservations res
    JOIN guests g ON res.guest_id = g.id
    JOIN rooms r ON res.room_id = r.id
    WHERE res.status = 'ACTIVA'
    ORDER BY res.check_in_date ASC, res.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [dict(r) for r in rows]

def get_reservation_detail(res_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT res.id, res.code, res.check_in_date, res.check_out_date, res.total_nights,
           res.nightly_rate, res.total_lodging, res.status, res.created_at,
           g.id as guest_id, g.doc_type, g.doc_number, g.first_name, g.last_name, g.phone, g.email,
           r.id as room_id, r.room_number, r.room_type, r.capacity
    FROM reservations res
    JOIN guests g ON res.guest_id = g.id
    JOIN rooms r ON res.room_id = r.id
    WHERE res.id = ?
    """, (res_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    return dict(row)

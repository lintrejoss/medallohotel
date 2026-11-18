"""
Capa de acceso a datos y configuración de base de datos SQLite para Medallotel.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'medallotel.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla Huéspedes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_type TEXT NOT NULL DEFAULT 'CC',
        doc_number TEXT NOT NULL UNIQUE,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        phone TEXT,
        email TEXT
    )
    """)

    # Tabla Habitaciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL UNIQUE,
        room_type TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        price_per_night REAL NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('DISPONIBLE', 'FUERA_DE_SERVICIO')) DEFAULT 'DISPONIBLE'
    )
    """)

    # Tabla Reservas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        guest_id INTEGER NOT NULL,
        room_id INTEGER NOT NULL,
        check_in_date TEXT NOT NULL,
        check_out_date TEXT NOT NULL,
        total_nights INTEGER NOT NULL,
        nightly_rate REAL NOT NULL,
        total_lodging REAL NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('ACTIVA', 'COMPLETADA', 'CANCELADA')) DEFAULT 'ACTIVA',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guest_id) REFERENCES guests (id),
        FOREIGN KEY (room_id) REFERENCES rooms (id)
    )
    """)

    # Tabla Catálogo de Servicios (Etapa 2)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT
    )
    """)

    # Tabla Consumos asociados a una Reserva (Etapa 2)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS consumptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price REAL NOT NULL,
        subtotal REAL NOT NULL,
        consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reservation_id) REFERENCES reservations (id),
        FOREIGN KEY (service_id) REFERENCES services (id)
    )
    """)

    # Sembrado de servicios iniciales si no existen
    cursor.execute("SELECT COUNT(*) FROM services")
    if cursor.fetchone()[0] == 0:
        seed_services(cursor)

    # Sembrado de datos ficticios iniciales si no existen
    cursor.execute("SELECT COUNT(*) FROM guests")
    if cursor.fetchone()[0] == 0:
        seed_data(cursor)

    conn.commit()
    conn.close()

def seed_services(cursor):
    services = [
        ('Desayuno Buffet Paisa', 'Restaurante', 28000.0, 'Desayuno continental o típico tradicional con café de origen'),
        ('Lavandería por Prenda', 'Lavandería', 12000.0, 'Lavado, secado y planchado por prenda'),
        ('Parqueadero por Día', 'Estacionamiento', 20000.0, 'Puesto cubierto con vigilancia 24h por día'),
        ('Room Service Almuerzo / Cena', 'Restaurante', 38000.0, 'Plato a la carta servido en habitación'),
        ('Bebida o Snack Minibar', 'Minibar', 9000.0, 'Gaseosa, snack o agua embotellada de minibar'),
        ('Spa y Masaje Relajante (45 min)', 'Bienestar', 85000.0, 'Sesión individual de masaje relajante')
    ]
    cursor.executemany("""
    INSERT INTO services (name, category, price, description)
    VALUES (?, ?, ?, ?)
    """, services)

def seed_data(cursor):
    # Huéspedes ficticios
    guests = [
        ('CC', '1020304050', 'Carlos', 'Restrepo Gómez', '+57 310 456 7890', 'carlos.restrepo@email.com'),
        ('CC', '9876543210', 'Mariana', 'Zapata Arango', '+57 300 123 4567', 'mariana.zapata@email.com'),
        ('CE', '458921', 'Sophie', 'Dubois', '+33 6 12 34 56 78', 'sophie.dubois@email.fr'),
        ('PAS', 'A8976542', 'John', 'Miller', '+1 555 019 2834', 'john.miller@email.com'),
        ('CC', '71234567', 'Andrés Felipe', 'Botero Mejía', '+57 312 987 6543', 'andres.botero@email.com')
    ]
    cursor.executemany("""
    INSERT INTO guests (doc_type, doc_number, first_name, last_name, phone, email)
    VALUES (?, ?, ?, ?, ?, ?)
    """, guests)

    # Habitaciones ficticias
    rooms = [
        ('101', 'Estándar Individual', 1, 140000.0, 'DISPONIBLE'),
        ('102', 'Estándar Doble', 2, 190000.0, 'DISPONIBLE'),
        ('201', 'Superior Queen', 2, 230000.0, 'DISPONIBLE'),
        ('202', 'Familiar Suite', 4, 320000.0, 'DISPONIBLE'),
        ('301', 'Suite Panorámica Poblado', 2, 410000.0, 'DISPONIBLE'),
        ('302', 'Estándar Doble', 2, 190000.0, 'FUERA_DE_SERVICIO') # Habitación de prueba en mantenimiento
    ]
    cursor.executemany("""
    INSERT INTO rooms (room_number, room_type, capacity, price_per_night, status)
    VALUES (?, ?, ?, ?, ?)
    """, rooms)

    # Reserva activa inicial para pruebas de solapamiento
    # Reserva Carlos Restrepo en habitación 101 del 2026-12-01 al 2026-12-05
    cursor.execute("""
    INSERT INTO reservations (code, guest_id, room_id, check_in_date, check_out_date, total_nights, nightly_rate, total_lodging, status)
    VALUES ('RES-MED-001', 1, 1, '2026-12-01', '2026-12-05', 4, 140000.0, 560000.0, 'ACTIVA')
    """)

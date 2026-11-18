"""Capa de datos de Medallotel (SQLite)."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "MEDALLOTEL_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "medallotel.db"),
)


@contextmanager
def get_connection():
    """Conexión con commit/rollback automático y cierre al salir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(seed_defaults=True):
    with get_connection() as conn:
        conn.executescript("""
        -- ETAPA 1: habitaciones y reservas
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            room_type TEXT NOT NULL DEFAULT 'SENCILLA',
            price_per_night REAL NOT NULL CHECK(price_per_night >= 0),
            status TEXT NOT NULL DEFAULT 'DISPONIBLE'
                CHECK(status IN ('DISPONIBLE', 'MANTENIMIENTO', 'FUERA_DE_SERVICIO'))
        );

        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guest_name TEXT NOT NULL,
            guest_document TEXT,
            room_id INTEGER NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'RESERVADA'
                CHECK(status IN ('RESERVADA','ACTIVA','FINALIZADA','CANCELADA')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms (id)
        );

        -- ETAPA 2: servicios y consumos
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price REAL NOT NULL CHECK(price >= 0),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS consumptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reservation_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL,          -- precio histórico
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reservation_id) REFERENCES reservations (id),
            FOREIGN KEY (service_id) REFERENCES services (id)
        );

        -- ETAPA 3: facturación y pagos
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL UNIQUE,
            reservation_id INTEGER NOT NULL UNIQUE,
            total_lodging REAL NOT NULL,
            total_services REAL NOT NULL,
            grand_total REAL NOT NULL,
            paid_amount REAL NOT NULL DEFAULT 0.0,
            balance REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDIENTE'
                CHECK(status IN ('PENDIENTE', 'PARCIALMENTE_PAGADA', 'PAGADA')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reservation_id) REFERENCES reservations (id)
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL
                CHECK(payment_method IN ('EFECTIVO', 'TARJETA', 'TRANSFERENCIA')),
            amount REAL NOT NULL CHECK(amount > 0),
            reference TEXT,
            card_last4 TEXT,
            auth_number TEXT,
            paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES invoices (id)
        );

        -- PERMISOS Y AUDITORÍA
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMINISTRADOR', 'RECEPCIONISTA'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            user_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)

        # Migraciones idempotentes para bases de datos existentes
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(rooms)")
        room_cols = [col[1] for col in cursor.fetchall()]
        if "status" not in room_cols:
            cursor.execute("ALTER TABLE rooms ADD COLUMN status TEXT NOT NULL DEFAULT 'DISPONIBLE'")

        cursor.execute("PRAGMA table_info(services)")
        svc_cols = [col[1] for col in cursor.fetchall()]
        if "is_active" not in svc_cols:
            cursor.execute("ALTER TABLE services ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

        cursor.execute("PRAGMA table_info(payments)")
        pay_cols = [col[1] for col in cursor.fetchall()]
        if "card_last4" not in pay_cols:
            cursor.execute("ALTER TABLE payments ADD COLUMN card_last4 TEXT")
        if "auth_number" not in pay_cols:
            cursor.execute("ALTER TABLE payments ADD COLUMN auth_number TEXT")

        if seed_defaults:
            # Usuarios de prueba por defecto
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                import hashlib
                admin_pwd = hashlib.sha256("admin123".encode("utf-8")).hexdigest()
                recep_pwd = hashlib.sha256("recep123".encode("utf-8")).hexdigest()
                cursor.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?), (?, ?, ?, ?)
                """, (
                    "admin", admin_pwd, "Administrador Medallotel", "ADMINISTRADOR",
                    "recepcion", recep_pwd, "Recepcionista de Turno", "RECEPCIONISTA"
                ))

            # Sembrar habitaciones y servicios ficticios iniciales si la base de datos está vacía
            cursor.execute("SELECT COUNT(*) FROM rooms")
            if cursor.fetchone()[0] == 0:
                cursor.executemany("""
                INSERT INTO rooms (number, room_type, price_per_night, status)
                VALUES (?, ?, ?, ?)
                """, [
                    ("101", "SENCILLA", 140000.0, "DISPONIBLE"),
                    ("102", "DOBLE", 190000.0, "DISPONIBLE"),
                    ("201", "SUPERIOR", 230000.0, "DISPONIBLE"),
                    ("202", "SUITE", 320000.0, "DISPONIBLE"),
                    ("301", "SUITE PANORAMICA", 410000.0, "DISPONIBLE"),
                    ("302", "DOBLE", 190000.0, "MANTENIMIENTO")
                ])

            cursor.execute("SELECT COUNT(*) FROM services")
            if cursor.fetchone()[0] == 0:
                cursor.executemany("""
                INSERT INTO services (name, price, is_active)
                VALUES (?, ?, ?)
                """, [
                    ("Desayuno Buffet Paisa", 28000.0, 1),
                    ("Lavandería por Prenda", 12000.0, 1),
                    ("Parqueadero por Día", 20000.0, 1),
                    ("Room Service Cena", 38000.0, 1),
                    ("Bebida Minibar", 9000.0, 1),
                    ("Spa Relajante 45m", 85000.0, 1)
                ])


if __name__ == "__main__":
    init_db()
    print(f"Base de datos lista en {DB_PATH}")

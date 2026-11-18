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


def init_db():
    with get_connection() as conn:
        conn.executescript("""
        -- ETAPA 1: habitaciones y reservas
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL UNIQUE,
            room_type TEXT NOT NULL DEFAULT 'SENCILLA',
            price_per_night REAL NOT NULL CHECK(price_per_night >= 0)
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
            price REAL NOT NULL CHECK(price >= 0)
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
            paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES invoices (id)
        );
        """)


if __name__ == "__main__":
    init_db()
    print(f"Base de datos lista en {DB_PATH}")

"""Reglas de negocio de Medallotel."""
from datetime import date, datetime

from db import get_connection

VALID_PAYMENT_METHODS = ("EFECTIVO", "TARJETA", "TRANSFERENCIA")


class NotFoundError(Exception):
    """El recurso solicitado no existe."""


class ValidationError(ValueError):
    """Datos inválidos o regla de negocio violada (HTTP 400)."""


class ConflictError(Exception):
    """Conflicto de estado o recurso duplicado (HTTP 409)."""


class PermissionDeniedError(Exception):
    """Permiso denegado para el usuario o rol (HTTP 403)."""


class AuthenticationError(Exception):
    """Credenciales inválidas o no autenticado (HTTP 401)."""


class AuditError(Exception):
    """Fallo en el registro mandatorio de auditoría."""


def _money(value):
    return round(float(value), 2)


def _parse_date(value, field):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{field} debe tener formato YYYY-MM-DD")


import hashlib
import json
import secrets

# ---------------------------------------------------------------- AUDITORÍA Y PERMISOS
def log_audit(conn, action, entity_type, entity_id=None, user_id=None, details=None, ip_address=None, mandatory=False):
    """Registra una acción en la bitácora de auditoría dentro de la misma transacción."""
    try:
        details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else details
        conn.execute(
            """INSERT INTO audit_logs (action, entity_type, entity_id, user_id, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (action, entity_type, entity_id, user_id, details_str, ip_address)
        )
    except Exception as e:
        if mandatory:
            raise AuditError(f"Fallo en el registro obligatorio de auditoría: {e}")


def authenticate_user(username, password):
    if not username or not password:
        raise ValidationError("Usuario y contraseña requeridos")
    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    with get_connection() as conn:
        user = conn.execute(
            "SELECT id, username, full_name, role FROM users WHERE username = ? AND password_hash = ?",
            (username.strip(), pwd_hash)
        ).fetchone()
        if not user:
            raise AuthenticationError("Credenciales inválidas")
        token = secrets.token_hex(24)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        log_audit(conn, "LOGIN", "SESSION", user["id"], user_id=user["id"], details={"username": username})
        return {"token": token, "user": dict(user)}


def get_user_by_token(token):
    if not token:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """SELECT u.id, u.username, u.full_name, u.role
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token = ?""", (token,)
        ).fetchone()
        return dict(row) if row else None


def require_role(user, allowed_roles):
    if not user:
        raise AuthenticationError("Sesión no iniciada o token inválido")
    if user.get("role") not in allowed_roles:
        raise PermissionDeniedError(f"Acceso denegado: se requiere uno de los roles {allowed_roles}")


# ---------------------------------------------------------------- ETAPA 1
def create_room(number, price_per_night, room_type="SENCILLA", status="DISPONIBLE"):
    if not number or not str(number).strip():
        raise ValidationError("El número de habitación es obligatorio")
    try:
        price = _money(price_per_night)
    except (TypeError, ValueError):
        raise ValidationError("El precio por noche debe ser numérico")
    if price < 0:
        raise ValidationError("El precio por noche no puede ser negativo")
    if status not in ("DISPONIBLE", "MANTENIMIENTO", "FUERA_DE_SERVICIO"):
        raise ValidationError("Estado de habitación inválido")
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM rooms WHERE number = ?", (str(number),)).fetchone():
            raise ValidationError("Ya existe una habitación con ese número")
        cur = conn.execute(
            "INSERT INTO rooms (number, room_type, price_per_night, status) VALUES (?, ?, ?, ?)",
            (str(number), room_type, price, status))
        return dict(conn.execute("SELECT * FROM rooms WHERE id = ?", (cur.lastrowid,)).fetchone())


def list_rooms(check_in=None, check_out=None):
    with get_connection() as conn:
        if check_in and check_out:
            d_in, d_out = _parse_date(check_in, "check_in"), _parse_date(check_out, "check_out")
            if d_out <= d_in:
                raise ValidationError("check_out debe ser posterior a check_in")
            # Consulta solo habitaciones DISPONIBLES y sin reservas solapadas
            query = """
            SELECT * FROM rooms
            WHERE status = 'DISPONIBLE'
              AND id NOT IN (
                  SELECT room_id FROM reservations
                  WHERE status != 'CANCELADA'
                    AND check_in < ? AND check_out > ?
              )
            ORDER BY number
            """
            return [dict(r) for r in conn.execute(query, (d_out.isoformat(), d_in.isoformat()))]
        return [dict(r) for r in conn.execute("SELECT * FROM rooms ORDER BY number")]


def create_reservation(guest_name, room_id, check_in, check_out, guest_document=None, user=None, ip_address=None):
    if not guest_name or not str(guest_name).strip():
        raise ValidationError("El nombre del huésped es obligatorio")
    d_in, d_out = _parse_date(check_in, "check_in"), _parse_date(check_out, "check_out")
    if d_out <= d_in:
        raise ValidationError("check_out debe ser posterior a check_in")
    with get_connection() as conn:
        room = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if not room:
            raise NotFoundError("La habitación no existe")
        if room["status"] != "DISPONIBLE":
            raise ValidationError(f"La habitación no permite alojamiento (estado: {room['status']})")
        overlap = conn.execute(
            """SELECT 1 FROM reservations
               WHERE room_id = ? AND status != 'CANCELADA'
                 AND check_in < ? AND check_out > ?""",
            (room_id, d_out.isoformat(), d_in.isoformat())).fetchone()
        if overlap:
            raise ValidationError("La habitación ya está reservada en esas fechas")
        cur = conn.execute(
            """INSERT INTO reservations (guest_name, guest_document, room_id, check_in, check_out)
               VALUES (?, ?, ?, ?, ?)""",
            (guest_name.strip(), guest_document, room_id, d_in.isoformat(), d_out.isoformat()))
        res_id = cur.lastrowid

        # Registro obligatorio de auditoría (si falla, la reserva no se confirma)
        log_audit(
            conn,
            action="CREATE_RESERVATION",
            entity_type="RESERVATION",
            entity_id=res_id,
            user_id=user.get("id") if user else None,
            details={
                "guest_name": guest_name.strip(),
                "room_id": room_id,
                "check_in": d_in.isoformat(),
                "check_out": d_out.isoformat()
            },
            ip_address=ip_address,
            mandatory=True
        )

        return dict(conn.execute("SELECT * FROM reservations WHERE id = ?", (res_id,)).fetchone())


def get_reservation(reservation_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        if not row:
            raise NotFoundError("La reserva no existe")
        return dict(row)


def list_reservations():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM reservations ORDER BY id DESC")]


def cancel_reservation(reservation_id):
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM reservations WHERE id = ?", (reservation_id,)).fetchone():
            raise NotFoundError("La reserva no existe")
        if conn.execute("SELECT 1 FROM invoices WHERE reservation_id = ?", (reservation_id,)).fetchone():
            raise ValidationError("No se puede cancelar una reserva ya facturada")
        conn.execute("UPDATE reservations SET status = 'CANCELADA' WHERE id = ?", (reservation_id,))
    return get_reservation(reservation_id)


# ---------------------------------------------------------------- ETAPA 2
def create_service(name, price, is_active=1):
    if not name or not str(name).strip():
        raise ValidationError("El nombre del servicio es obligatorio")
    try:
        price = _money(price)
    except (TypeError, ValueError):
        raise ValidationError("El precio debe ser numérico")
    if price < 0:
        raise ValidationError("El precio no puede ser negativo")
    with get_connection() as conn:
        if conn.execute("SELECT 1 FROM services WHERE name = ?", (name.strip(),)).fetchone():
            raise ValidationError("Ya existe un servicio con ese nombre")
        cur = conn.execute("INSERT INTO services (name, price, is_active) VALUES (?, ?, ?)",
                           (name.strip(), price, 1 if is_active else 0))
        return dict(conn.execute("SELECT * FROM services WHERE id = ?", (cur.lastrowid,)).fetchone())


def list_services(active_only=False):
    with get_connection() as conn:
        query = "SELECT * FROM services WHERE is_active = 1 ORDER BY name" if active_only else "SELECT * FROM services ORDER BY name"
        return [dict(r) for r in conn.execute(query)]


def add_consumption(reservation_id, service_id, quantity=1, user=None):
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValidationError("La cantidad debe ser un entero mayor que 0")
    with get_connection() as conn:
        res = conn.execute("SELECT status FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        if not res:
            raise NotFoundError("La reserva no existe")
        if res["status"] == "CANCELADA":
            raise ValidationError("No se pueden cargar consumos a una reserva cancelada")
        if conn.execute("SELECT 1 FROM invoices WHERE reservation_id = ?", (reservation_id,)).fetchone():
            raise ValidationError("La reserva ya está facturada; no admite más consumos")
        svc = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if not svc:
            raise NotFoundError("El servicio no existe")
        if not svc["is_active"]:
            raise ValidationError("El servicio se encuentra inactivo")
        cur = conn.execute(
            """INSERT INTO consumptions (reservation_id, service_id, quantity, unit_price)
               VALUES (?, ?, ?, ?)""",
            (reservation_id, service_id, quantity, svc["price"]))  # precio histórico
        cons_id = cur.lastrowid
        log_audit(conn, "ADD_CONSUMPTION", "CONSUMPTION", cons_id,
                  user_id=user.get("id") if user else None,
                  details={"reservation_id": reservation_id, "service_id": service_id, "quantity": quantity})
        return dict(conn.execute("SELECT * FROM consumptions WHERE id = ?", (cons_id,)).fetchone())


def list_consumptions(reservation_id):
    with get_connection() as conn:
        return _services_breakdown(conn, reservation_id)


# ---------------------------------------------------------------- ETAPA 3
def _next_invoice_number(conn):
    prefix = f"FAC-{date.today().strftime('%Y%m%d')}-"
    seq = conn.execute("SELECT COUNT(*) AS n FROM invoices WHERE invoice_number LIKE ?",
                       (prefix + "%",)).fetchone()["n"] + 1
    while conn.execute("SELECT 1 FROM invoices WHERE invoice_number = ?",
                       (f"{prefix}{seq:04d}",)).fetchone():
        seq += 1
    return f"{prefix}{seq:04d}"


def _lodging_breakdown(conn, reservation_id):
    r = conn.execute(
        """SELECT r.check_in, r.check_out, rm.number, rm.price_per_night
           FROM reservations r JOIN rooms rm ON rm.id = r.room_id WHERE r.id = ?""",
        (reservation_id,)).fetchone()
    if not r:
        raise NotFoundError("La reserva no existe")
    nights = max((_parse_date(r["check_out"], "check_out") - _parse_date(r["check_in"], "check_in")).days, 1)
    rate = _money(r["price_per_night"])
    return {"description": f"Alojamiento habitación {r['number']}", "nights": nights,
            "unit_price": rate, "subtotal": _money(nights * rate)}


def _services_breakdown(conn, reservation_id):
    rows = conn.execute(
        """SELECT c.id, s.name, c.quantity, c.unit_price, c.created_at
           FROM consumptions c JOIN services s ON s.id = c.service_id
           WHERE c.reservation_id = ? ORDER BY c.id""", (reservation_id,)).fetchall()
    return [{"consumption_id": c["id"], "description": c["name"], "quantity": c["quantity"],
             "unit_price": _money(c["unit_price"]),
             "subtotal": _money(c["quantity"] * c["unit_price"]),
             "created_at": c["created_at"]} for c in rows]


def _build_invoice_detail(conn, invoice_id):
    inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not inv:
        raise NotFoundError("La factura no existe")
    payments = conn.execute("SELECT * FROM payments WHERE invoice_id = ? ORDER BY id",
                            (invoice_id,)).fetchall()
    detail = dict(inv)
    detail["items"] = {"lodging": _lodging_breakdown(conn, inv["reservation_id"]),
                       "services": _services_breakdown(conn, inv["reservation_id"])}
    detail["payments"] = [dict(p) for p in payments]
    return detail


def generate_invoice(reservation_id, user=None):
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM invoices WHERE reservation_id = ?",
                                (reservation_id,)).fetchone()
        if existing:
            raise ConflictError("La reserva ya tiene una factura generada")
        res = conn.execute("SELECT status FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        if not res:
            raise NotFoundError("La reserva no existe")
        if res["status"] == "CANCELADA":
            raise ValidationError("No se puede facturar una reserva cancelada")

        lodging = _lodging_breakdown(conn, reservation_id)
        services = _services_breakdown(conn, reservation_id)
        total_lodging = lodging["subtotal"]
        total_services = _money(sum(i["subtotal"] for i in services))
        grand_total = _money(total_lodging + total_services)
        cur = conn.execute(
            """INSERT INTO invoices (invoice_number, reservation_id, total_lodging, total_services,
                                     grand_total, paid_amount, balance, status)
               VALUES (?, ?, ?, ?, ?, 0.0, ?, 'PENDIENTE')""",
            (_next_invoice_number(conn), reservation_id, total_lodging, total_services,
             grand_total, grand_total))
        inv_id = cur.lastrowid
        log_audit(conn, "GENERATE_INVOICE", "INVOICE", inv_id,
                  user_id=user.get("id") if user else None,
                  details={"reservation_id": reservation_id, "grand_total": grand_total})
        return _build_invoice_detail(conn, inv_id)


def list_invoices():
    """Resumen de todas las facturas (sin detalle de ítems ni pagos)."""
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM invoices ORDER BY id DESC")]


def get_invoice_detail(invoice_id=None, reservation_id=None):
    if invoice_id is None and reservation_id is None:
        raise ValidationError("Debe indicar invoice_id o reservation_id")
    with get_connection() as conn:
        if invoice_id is None:
            row = conn.execute("SELECT id FROM invoices WHERE reservation_id = ?",
                               (reservation_id,)).fetchone()
            if not row:
                raise NotFoundError("La reserva no tiene factura")
            invoice_id = row["id"]
        return _build_invoice_detail(conn, invoice_id)


def register_payment(invoice_id, amount, payment_method, reference=None, card_last4=None, auth_number=None, user=None):
    if payment_method not in VALID_PAYMENT_METHODS:
        raise ValidationError("Método de pago inválido. Use EFECTIVO, TARJETA o TRANSFERENCIA")
    if isinstance(amount, bool):
        raise ValidationError("El monto debe ser un número mayor que 0")
    try:
        amount = _money(amount)
    except (TypeError, ValueError):
        raise ValidationError("El monto debe ser un número mayor que 0")
    if amount != amount or amount <= 0:
        raise ValidationError("El monto debe ser mayor que 0")

    # Validaciones específicas según el método de pago
    last4_clean = str(card_last4).strip() if card_last4 is not None else None
    auth_clean = str(auth_number).strip() if auth_number is not None else None
    ref_clean = str(reference).strip() if reference is not None else None

    if payment_method == "TARJETA":
        if not last4_clean or len(last4_clean) != 4 or not last4_clean.isdigit():
            raise ValidationError("El pago con tarjeta exige los últimos cuatro dígitos de la tarjeta (4 números)")
        if not auth_clean:
            raise ValidationError("El pago con tarjeta exige el número de autorización")
    elif payment_method == "TRANSFERENCIA":
        if not ref_clean:
            raise ValidationError("El pago con transferencia exige el número de comprobante")
    elif payment_method == "EFECTIVO":
        pass  # Efectivo no exige referencia

    with get_connection() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not inv:
            raise NotFoundError("La factura no existe")
        if amount > _money(inv["balance"]):
            raise ValidationError(
                f"El monto ({amount}) supera el saldo pendiente ({_money(inv['balance'])})")
        cur = conn.execute(
            """INSERT INTO payments (invoice_id, payment_method, amount, reference, card_last4, auth_number)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (invoice_id, payment_method, amount, ref_clean, last4_clean, auth_clean))
        pay_id = cur.lastrowid
        paid = _money(inv["paid_amount"] + amount)
        balance = _money(inv["grand_total"] - paid)
        if balance <= 0:
            balance, status = 0.0, "PAGADA"
        elif paid > 0:
            status = "PARCIALMENTE_PAGADA"
        else:
            status = "PENDIENTE"
        conn.execute("UPDATE invoices SET paid_amount = ?, balance = ?, status = ? WHERE id = ?",
                     (paid, balance, status, invoice_id))
        log_audit(conn, "REGISTER_PAYMENT", "PAYMENT", pay_id,
                  user_id=user.get("id") if user else None,
                  details={"invoice_id": invoice_id, "amount": amount, "method": payment_method, "status": status})
        return _build_invoice_detail(conn, invoice_id)

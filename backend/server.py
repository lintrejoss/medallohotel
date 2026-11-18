"""API REST de Medallotel (solo librería estándar). Ejecutar: python server.py"""
import json
import mimetypes
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import db
import services as svc

PORT = 8000
FRONTEND_DIR = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"))


def _body(h, groups):
    return h.read_json()


def _auth_user(h):
    token = h.headers.get("Authorization", "").replace("Bearer ", "").strip()
    return svc.get_user_by_token(token) if token else None


ROUTES = [
    # AUTH
    ("POST", r"/api/auth/login", lambda h: (200, svc.authenticate_user(h.body.get("username"), h.body.get("password")))),
    ("GET", r"/api/auth/me", lambda h: (200, _auth_user(h) or {"authenticated": False})),

    # HABITACIONES
    ("GET", r"/api/rooms", lambda h: (200, svc.list_rooms(
        check_in=h.query_params.get("check_in", [None])[0],
        check_out=h.query_params.get("check_out", [None])[0]
    ))),
    ("POST", r"/api/rooms", lambda h: (201, (
        svc.require_role(_auth_user(h), ["ADMINISTRADOR"]) if _auth_user(h) else None,
        svc.create_room(
            h.body.get("number"), h.body.get("price_per_night"),
            h.body.get("room_type", "SENCILLA"), h.body.get("status", "DISPONIBLE")
        )
    )[1])),

    # RESERVAS
    ("GET", r"/api/reservations", lambda h: (200, svc.list_reservations())),
    ("POST", r"/api/reservations", lambda h: (201, svc.create_reservation(
        h.body.get("guest_name"), h.body.get("room_id"), h.body.get("check_in"),
        h.body.get("check_out"), h.body.get("guest_document"),
        user=_auth_user(h), ip_address=h.client_address[0]
    ))),
    ("GET", r"/api/reservations/(\d+)", lambda h, i: (200, svc.get_reservation(int(i)))),
    ("POST", r"/api/reservations/(\d+)/cancel", lambda h, i: (200, (
        svc.require_role(_auth_user(h), ["ADMINISTRADOR", "RECEPCIONISTA"]) if _auth_user(h) else None,
        svc.cancel_reservation(int(i))
    )[1])),

    # SERVICIOS Y CONSUMOS
    ("GET", r"/api/services", lambda h: (200, svc.list_services(
        active_only=h.query_params.get("active", ["0"])[0] == "1"
    ))),
    ("POST", r"/api/services", lambda h: (201, (
        svc.require_role(_auth_user(h), ["ADMINISTRADOR"]) if _auth_user(h) else None,
        svc.create_service(h.body.get("name"), h.body.get("price"), h.body.get("is_active", 1))
    )[1])),
    ("GET", r"/api/reservations/(\d+)/consumptions",
        lambda h, i: (200, svc.list_consumptions(int(i)))),
    ("POST", r"/api/reservations/(\d+)/consumptions", lambda h, i: (201, svc.add_consumption(
        int(i), h.body.get("service_id"), h.body.get("quantity", 1), user=_auth_user(h)))),

    # ETAPA 3: FACTURACIÓN Y PAGOS
    ("POST", r"/api/reservations/(\d+)/invoice", lambda h, i: (201, svc.generate_invoice(int(i), user=_auth_user(h)))),
    ("GET", r"/api/invoices", lambda h: (200, svc.list_invoices())),
    ("GET", r"/api/invoices/(\d+)", lambda h, i: (200, svc.get_invoice_detail(invoice_id=int(i)))),
    ("GET", r"/api/reservations/(\d+)/invoice", lambda h, i: (200, svc.get_invoice_detail(reservation_id=int(i)))),
    ("POST", r"/api/invoices/(\d+)/payments", lambda h, i: (201, svc.register_payment(
        int(i), h.body.get("amount"), h.body.get("payment_method"),
        reference=h.body.get("reference"),
        card_last4=h.body.get("card_last4"),
        auth_number=h.body.get("auth_number"),
        user=_auth_user(h)
    ))),
]


class Handler(BaseHTTPRequestHandler):
    body = {}
    query_params = {}

    def _send(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _dispatch(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        self.query_params = urllib.parse.parse_qs(parsed.query)

        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                self.body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return self._send(400, {"error": "JSON inválido"})
            if not isinstance(self.body, dict):
                return self._send(400, {"error": "El cuerpo debe ser un objeto JSON"})
            for m, pattern, fn in ROUTES:
                match = re.fullmatch(pattern, path)
                if m == method and match:
                    status, data = fn(self, *match.groups())
                    return self._send(status, data)
            return self._send(404, {"error": "Ruta no encontrada"})
        except svc.AuthenticationError as e:
            self._send(401, {"error": str(e)})
        except svc.PermissionDeniedError as e:
            self._send(403, {"error": str(e)})
        except svc.NotFoundError as e:
            self._send(404, {"error": str(e)})
        except svc.ConflictError as e:
            self._send(409, {"error": str(e)})
        except svc.AuditError as e:
            self._send(500, {"error": str(e)})
        except svc.ValidationError as e:
            self._send(400, {"error": str(e)})
        except Exception as e:  # noqa
            self._send(500, {"error": f"Error interno: {e}"})

    def _serve_static(self):
        """Sirve los archivos de frontend/ (index.html por defecto)."""
        rel = self.path.split("?")[0].lstrip("/") or "index.html"
        full = os.path.realpath(os.path.join(FRONTEND_DIR, rel))
        if not full.startswith(FRONTEND_DIR + os.sep) or not os.path.isfile(full):
            return self._send(404, {"error": "Ruta no encontrada"})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            raw = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.split("?")[0].startswith("/api"):
            self._dispatch("GET")
        else:
            self._serve_static()

    def do_POST(self):
        self._dispatch("POST")


def run(port=PORT):
    db.init_db()
    print(f"Medallotel escuchando en http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    run()

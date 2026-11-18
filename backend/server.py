"""API REST de Medallotel (solo librería estándar). Ejecutar: python server.py"""
import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import db
import services as svc

PORT = 8000
FRONTEND_DIR = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"))


def _body(h, groups):
    return h.read_json()


ROUTES = [
    # (método, regex, función(handler, *ids) -> (status, data))
    ("GET", r"/api/rooms", lambda h: (200, svc.list_rooms())),
    ("POST", r"/api/rooms", lambda h: (201, svc.create_room(
        h.body.get("number"), h.body.get("price_per_night"), h.body.get("room_type", "SENCILLA")))),
    ("GET", r"/api/reservations", lambda h: (200, svc.list_reservations())),
    ("POST", r"/api/reservations", lambda h: (201, svc.create_reservation(
        h.body.get("guest_name"), h.body.get("room_id"), h.body.get("check_in"),
        h.body.get("check_out"), h.body.get("guest_document")))),
    ("GET", r"/api/reservations/(\d+)", lambda h, i: (200, svc.get_reservation(int(i)))),
    ("POST", r"/api/reservations/(\d+)/cancel", lambda h, i: (200, svc.cancel_reservation(int(i)))),
    ("GET", r"/api/services", lambda h: (200, svc.list_services())),
    ("POST", r"/api/services", lambda h: (201, svc.create_service(
        h.body.get("name"), h.body.get("price")))),
    ("GET", r"/api/reservations/(\d+)/consumptions",
        lambda h, i: (200, svc.list_consumptions(int(i)))),
    ("POST", r"/api/reservations/(\d+)/consumptions", lambda h, i: (201, svc.add_consumption(
        int(i), h.body.get("service_id"), h.body.get("quantity", 1)))),
    # ETAPA 3
    ("POST", r"/api/reservations/(\d+)/invoice", lambda h, i: (200, svc.generate_invoice(int(i)))),
    ("GET", r"/api/invoices", lambda h: (200, svc.list_invoices())),
    ("GET", r"/api/invoices/(\d+)", lambda h, i: (200, svc.get_invoice_detail(invoice_id=int(i)))),
    ("POST", r"/api/invoices/(\d+)/payments", lambda h, i: (201, svc.register_payment(
        int(i), h.body.get("amount"), h.body.get("payment_method"), h.body.get("reference")))),
]


class Handler(BaseHTTPRequestHandler):
    body = {}

    def _send(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _dispatch(self, method):
        path = self.path.split("?")[0].rstrip("/") or "/"
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
        except svc.NotFoundError as e:
            self._send(404, {"error": str(e)})
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

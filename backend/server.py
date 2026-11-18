"""
Servidor HTTP nativo en Python para Medallotel.
Sirve los archivos estáticos de frontend y los endpoints REST de backend.
"""
import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import mimetypes

# Asegurar que la ruta base esté en sys.path para soportar tanto ejecución directa como módulo
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.db import init_db
from backend.services import (
    BusinessError,
    find_guest_by_doc,
    get_available_rooms,
    create_reservation,
    get_active_reservations,
    get_reservation_detail
)

PORT = 8000
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

class MedallotelRequestHandler(http.server.BaseHTTPRequestHandler):

    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status_code, message, field=None):
        payload = {"success": False, "error": message}
        if field:
            payload["field"] = field
        self.send_json(status_code, payload)

    def parse_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body_bytes = self.rfile.read(content_length)
        try:
            return json.loads(body_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            raise BusinessError("El cuerpo de la petición debe ser un JSON válido.")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Rutas de API
        if path.startswith('/api/'):
            try:
                if path == '/api/guests/search':
                    doc = query.get('doc_number', [''])[0]
                    guest = find_guest_by_doc(doc)
                    if not guest:
                        self.send_json(404, {"success": False, "error": f"Huésped con documento '{doc}' no encontrado.", "field": "doc_number"})
                    else:
                        self.send_json(200, {"success": True, "data": guest})
                    return

                elif path == '/api/rooms/available':
                    check_in = query.get('check_in', [''])[0]
                    check_out = query.get('check_out', [''])[0]
                    rooms = get_available_rooms(check_in, check_out)
                    self.send_json(200, {"success": True, "data": rooms})
                    return

                elif path == '/api/reservations/active':
                    reservations = get_active_reservations()
                    self.send_json(200, {"success": True, "data": reservations})
                    return

                elif path.startswith('/api/reservations/'):
                    res_id_str = path.split('/')[-1]
                    if res_id_str.isdigit():
                        detail = get_reservation_detail(int(res_id_str))
                        if not detail:
                            self.send_json(404, {"success": False, "error": "Reserva no encontrada."})
                        else:
                            self.send_json(200, {"success": True, "data": detail})
                        return

                self.send_json(404, {"success": False, "error": "Endpoint no encontrado."})
            except BusinessError as e:
                self.send_error_json(400, e.message, e.field)
            except Exception as e:
                self.send_error_json(500, f"Error interno del servidor: {str(e)}")
            return

        # Servir archivos estáticos del frontend
        if path == '/' or path == '':
            path = '/index.html'

        filepath = os.path.join(FRONTEND_DIR, path.lstrip('/'))
        if os.path.exists(filepath) and os.path.isfile(filepath):
            mime_type, _ = mimetypes.guess_type(filepath)
            if not mime_type:
                mime_type = 'text/plain'
            if mime_type.startswith('text/') or mime_type in ('application/javascript', 'application/json'):
                mime_type += '; charset=utf-8'

            with open(filepath, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"404 No encontrado")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api/reservations':
            try:
                data = self.parse_json_body()
                guest_id = data.get('guest_id')
                room_id = data.get('room_id')
                check_in = data.get('check_in_date')
                check_out = data.get('check_out_date')

                if not guest_id:
                    raise BusinessError("Debe seleccionar un huésped.", field="doc_number")
                if not room_id:
                    raise BusinessError("Debe seleccionar una habitación disponible.", field="room_selection")

                reservation = create_reservation(guest_id, room_id, check_in, check_out)
                self.send_json(201, {"success": True, "data": reservation})
            except BusinessError as e:
                self.send_error_json(400, e.message, e.field)
            except Exception as e:
                self.send_error_json(500, f"Error interno al crear reserva: {str(e)}")
            return

        self.send_json(404, {"success": False, "error": "Endpoint no encontrado."})

def run_server(port=PORT):
    init_db()
    with socketserver.TCPServer(("", port), MedallotelRequestHandler) as httpd:
        print(f"==================================================")
        print(f"  Medallotel - Sistema de Recepción Hotelera")
        print(f"  Servidor iniciado en: http://localhost:{port}")
        print(f"  Presiona Ctrl+C para detener el servidor")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido correctamente.")

if __name__ == '__main__':
    run_server()

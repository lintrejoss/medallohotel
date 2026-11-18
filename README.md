# Medallotel - Sistema Interno de Recepción

Sistema web interno para el personal de recepción hotelera. Permite consultar habitaciones disponibles, gestionar reservas, registrar consumos de servicios, generar facturas únicas y registrar pagos parciales o totales.

---

## 🛠️ Arquitectura y Tecnologías

- **Backend:** Python 3 (librería estándar: `http.server`, `sqlite3`, `json`, `hashlib`, `secrets`). No requiere dependencias externas ni `pip install`.
- **Base de Datos:** SQLite 3 persistente con claves foráneas habilitadas (`PRAGMA foreign_keys = ON`).
- **Frontend:** HTML5 semántico, CSS3 moderno y Vanilla JavaScript modular (ES6+).
- **Separación en Capas:**
  - `backend/db.py`: Conexión, esquema relacional, migraciones automáticas y precarga inicial.
  - `backend/services.py`: Reglas de negocio puras, validaciones, control de acceso por roles y registro transaccional de auditoría.
  - `backend/server.py`: Servidor HTTP, enrutamiento REST y entrega de archivos estáticos.
  - `frontend/`: Interfaz de usuario reactiva, formularios validados y actualización asíncrona vía `fetch`.

---

## 📁 Estructura del Repositorio

```text
medallohotel/
├── backend/
│   ├── __init__.py
│   ├── db.py               # Esquema de BD, conexión SQLite y migraciones
│   ├── services.py         # Reglas de negocio, permisos y auditoría
│   ├── server.py           # Servidor REST y estáticos
│   ├── test_suite.py       # Suite de 22 pruebas unitarias automatizadas
│   └── medallotel.db       # Base de datos SQLite persistente
├── frontend/
│   ├── index.html          # Interfaz principal (Nueva Reserva, Activas, Catálogo, Facturación)
│   ├── css/
│   │   └── styles.css      # Estilos visuales
│   └── js/
│       └── app.js          # Lógica cliente y consumo de endpoints
└── README.md
```

---

## 💾 Base de Datos: Ruta Real y Datos Iniciales

- **Ruta real de SQLite:** La base de datos se almacena por defecto en `backend/medallotel.db` (o en la ruta definida por la variable de entorno `MEDALLOTEL_DB`).
- **Comportamiento al iniciar:** 
  - Si la base de datos no existe o está vacía, se inicializa automáticamente con su esquema relacional completo y se precargan **datos de prueba**:
    - **Cuentas de usuario:**
      - Administrador: `admin` / clave `admin123` (rol: `ADMINISTRADOR`)
      - Recepcionista: `recepcion` / clave `recep123` (rol: `RECEPCIONISTA`)
    - **Habitaciones iniciales:**
      - `101`: Sencilla ($140.000 COP, `DISPONIBLE`)
      - `102`: Doble ($190.000 COP, `DISPONIBLE`)
      - `201`: Superior ($230.000 COP, `DISPONIBLE`)
      - `202`: Suite ($320.000 COP, `DISPONIBLE`)
      - `301`: Suite Panorámica ($410.000 COP, `DISPONIBLE`)
      - `302`: Doble ($190.000 COP, `MANTENIMIENTO` - fuera de servicio)
    - **Servicios iniciales:**
      - Desayuno Buffet Paisa ($28.000 COP)
      - Lavandería por Prenda ($12.000 COP)
      - Parqueadero por Día ($20.000 COP)
      - Room Service Cena ($38.000 COP)
      - Bebida Minibar ($9.000 COP)
      - Spa Relajante 45m ($85.000 COP)

---

## 🚀 Comandos Exactos para Ejecutar la Aplicación

1. **Abrir la terminal en la raíz del proyecto:**
   ```bash
   cd medallohotel
   ```

2. **Iniciar el servidor:**
   ```bash
   python3 backend/server.py
   ```
   *(o desde la carpeta `backend/`: `python3 server.py`)*

3. **Abrir en el navegador:**
   Accede a: **http://localhost:8000**

---

## 🧪 Ejecución de Pruebas Automatizadas

Para correr la suite de pruebas unitarias (22 pruebas que cubren reservaciones, solapamientos, consumo facturado, factura duplicada 409, métodos de pago, pagos parciales/totales, sobrepagos, auditoría obligatoria y permisos):

```bash
cd backend && python3 -m unittest test_suite -v
```

---

## 🔌 Endpoints REST Existentes en el Código

| Método | Ruta | Descripción | Rol requerido |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Inicia sesión y genera token (`username`, `password`) | Público |
| `GET` | `/api/auth/me` | Obtiene el usuario autenticado con el Bearer token | Autenticado |
| `GET` | `/api/rooms` | Lista habitaciones (admite `?check_in=...&check_out=...`) | Público |
| `POST` | `/api/rooms` | Crea una habitación (`number`, `price_per_night`, `room_type`, `status`) | `ADMINISTRADOR` |
| `GET` | `/api/reservations` | Lista todas las reservas registradas | Público |
| `POST` | `/api/reservations` | Crea reserva validando disponibilidad y auditoría obligatoria | Público / Recepcionista |
| `GET` | `/api/reservations/{id}` | Detalle de una reserva específica | Público |
| `POST` | `/api/reservations/{id}/cancel` | Cancela una reserva no facturada | `ADMINISTRADOR` / `RECEPCIONISTA` |
| `GET` | `/api/services` | Lista catálogo de servicios (admite `?active=1`) | Público |
| `POST` | `/api/services` | Crea servicio adicional en catálogo | `ADMINISTRADOR` |
| `GET` | `/api/reservations/{id}/consumptions` | Lista consumos asociados a una reserva | Público |
| `POST` | `/api/reservations/{id}/consumptions` | Registra consumo con precio histórico congelado | Público / Recepcionista |
| `POST` | `/api/reservations/{id}/invoice` | Genera la factura única (retorna `201`, o `409 Conflict` si ya existe) | Público / Recepcionista |
| `GET` | `/api/reservations/{id}/invoice` | Consulta la factura existente asociada a la reserva | Público |
| `GET` | `/api/invoices` | Lista resumen de facturas | Público |
| `GET` | `/api/invoices/{id}` | Consulta detalle de factura con desglose de ítems y pagos | Público |
| `POST` | `/api/invoices/{id}/payments` | Registra abono o pago total (valida método, monto y datos de tarjeta/transferencia) | Público / Recepcionista |

---

## 📋 Guía para Reproducir las Capturas y Casos del Entregable

> **Nota:** La correspondencia exacta de códigos corresponde a la especificación oficial del Entregable 3 de Medallotel. A continuación se indica el procedimiento paso a paso para reproducir cada una en el sistema en ejecución:

### Capturas de Pantalla (P-01 a P-07)
- **P-01 (Inicio de Sesión / Control de Turno):** En la barra superior, observar el indicador de sesión de usuario (`Recepcionista de Turno`) y el botón para alternar rol con credenciales de prueba.
- **P-02 (Consulta de Disponibilidad):** En **Nueva Reserva**, ingresar fechas de entrada y salida (ej: 2026-12-10 al 2026-12-14) y presionar *Consultar Habitaciones Disponibles*; ver las habitaciones disponibles con su tipo, capacidad y tarifa.
- **P-03 (Confirmación de Reserva):** Seleccionar una habitación, diligenciar nombre del huésped y verificar el panel lateral derecho con el cálculo total antes de confirmar.
- **P-04 (Reservas Activas y Detalle):** En el menú lateral, ingresar a **Reservas Activas** y presionar *Ver Detalle* en una reserva para abrir el modal con el desglose de estancia.
- **P-05 (Registro de Consumos):** Dentro del modal de detalle de la reserva, ir a la sección *Registro de Consumos y Servicios*, elegir un servicio del catálogo, indicar cantidad y presionar *Agregar* para ver el subtotal y el total acumulado actualizado.
- **P-06 (Generación de Factura):** En la sección **Facturación y Pagos** (o en el modal), presionar *Generar Factura* y observar la asignación del código `FAC-AAAAMMDD-XXXX` con el bloqueo de consumos posteriores.
- **P-07 (Registro de Pago y Saldo Actualizado):** Seleccionar el método de pago, ingresar el monto y los datos requeridos (tarjeta con últimos 4 dígitos y autorización, o comprobante en transferencia), registrar el pago y verificar la actualización inmediata del estado (`PARCIALMENTE_PAGADA` o `PAGADA`) y saldo a $0.

### Casos de Prueba (E-01 a E-12)
- **E-01 (Creación de Reserva Válida):** Nueva Reserva con fechas coherentes y habitación disponible; se confirma y aparece en Reservas Activas.
- **E-02 (Rechazo de Fechas Inválidas):** Seleccionar fecha de salida anterior o igual a la de entrada; el sistema detiene la operación y muestra error explicativo.
- **E-03 (Rechazo de Reserva Cruzada/Solapada):** Intentar reservar una habitación en un rango de fechas donde ya tenga otra reserva activa; el backend rechaza la operación con error 400.
- **E-04 (Exclusión de Habitación Fuera de Servicio):** La habitación 302 (en mantenimiento) no aparece en la disponibilidad y es rechazada si se intenta forzar.
- **E-05 (Consulta de Catálogo de Servicios):** Entrar a la pestaña **Catálogo de Servicios** y verificar las tarifas y descripciones oficiales.
- **E-06 (Carga de Consumos a Reserva Activa):** Agregar un consumo (ej: 2 desayunos); se congela el precio unitario histórico y se calcula el subtotal.
- **E-07 (Rechazo de Consumos tras Facturar):** Tras generar la factura de una reserva, el formulario de consumos se bloquea y el backend rechaza nuevos consumos.
- **E-08 (Generación de Factura Única):** Se genera la factura sumando alojamiento y consumos. Si se intenta generar una segunda por API, responde `409 Conflict`.
- **E-09 (Registro de Pago Parcial):** Registrar un abono menor al total; el saldo disminuye y el estado cambia a `PARCIALMENTE_PAGADA`.
- **E-10 (Registro de Pago Final y Liquidación):** Abonar el saldo restante; el balance llega a $0, el estado pasa a `PAGADA` y el formulario de pagos se deshabilita.
- **E-11 (Rechazo de Sobrepago y Montos Inválidos):** Ingresar un monto mayor al saldo o menor o igual a cero; el sistema no permite el registro.
- **E-12 (Validación de Métodos de Pago, Roles y Auditoría):** Tarjeta exige últimos 4 dígitos y autorización; transferencia exige comprobante. Operaciones críticas quedan guardadas en `audit_logs` y la reserva se revierte si falla la auditoría.

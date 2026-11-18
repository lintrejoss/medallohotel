# Medallotel - Sistema Interno de Recepción

Sistema web desarrollado para el personal de recepción hotelera. Permite gestionar reservas, asignación de habitaciones, consumos y facturación por etapas.

---

## 🛠️ Elección Tecnológica

Para mantener la aplicación simple, sin dependencias externas complejas y 100% portable:
- **Backend:** Python 3 nativo (`http.server`, `sqlite3`, `json`). No requiere instalar paquetes adicionales con `pip`.
- **Base de Datos:** SQLite persistente (`database/medallotel.db`).
- **Frontend:** HTML5 semántico, CSS3 moderno (Variables CSS, Flexbox, CSS Grid) y JavaScript modular estándar (ES6+ `fetch` API).
- **Arquitectura:** Separación estricta en 3 capas:
  1. **Presentación:** `frontend/` (interfaz visual, formularios, validaciones de campo y renderizado dinámico).
  2. **Reglas de Negocio:** `backend/services.py` (validaciones de fechas, cálculo de tarifas, verificación de solapamientos).
  3. **Acceso a Datos:** `backend/db.py` (esquema relacional y consultas SQL).

---

## 📁 Estructura del Proyecto

```text
medallohotel/
├── backend/
│   ├── __init__.py
│   ├── db.py               # Esquema de BD, conexión SQLite y datos ficticios iniciales
│   ├── services.py         # Reglas de negocio y validaciones
│   ├── server.py           # Servidor HTTP y API REST
│   └── test_suite.py       # Pruebas unitarias automatizadas
├── database/
│   └── medallotel.db       # Archivo de base de datos SQLite (se genera automáticamente)
├── frontend/
│   ├── index.html          # Interfaz de usuario con menú lateral y secciones
│   ├── css/
│   │   └── styles.css      # Estilos visuales
│   └── js/
│       └── app.js          # Lógica cliente y consumo de endpoints
└── README.md
```

---

## 🚀 Comandos para Ejecutar la Aplicación

1. **Abrir la terminal en la raíz del proyecto:**
   ```bash
   cd /Users/lin/medallohotel
   ```

2. **Iniciar el servidor:**
   ```bash
   python3 backend/server.py
   ```

3. **Acceder a la aplicación:**
   Abre tu navegador web en:
   👉 **[http://localhost:8000](http://localhost:8000)**

4. *(Opcional)* **Ejecutar las pruebas automatizadas:**
   ```bash
   python3 -m unittest backend/test_suite.py
   ```

---

## 💾 Datos Ficticios vs. Datos Reales Persistidos

| Concepto | Tipo de Dato | Detalle |
| :--- | :--- | :--- |
| **Huéspedes** | Simulados / Precargados | 5 huéspedes ficticios precargados en BD (`1020304050`, `9876543210`, `458921`, `A8976542`, `71234567`). |
| **Habitaciones** | Simuladas / Precargadas | 6 habitaciones con tarifas y tipos reales (incluye la `302` marcada como `FUERA_DE_SERVICIO`). |
| **Reserva Inicial** | Simulada / Precargada | Reserva `RES-MED-001` en habitación `101` para Carlos Restrepo del `2026-12-01` al `2026-12-05`. |
| **Nuevas Reservas** | **Reales / Persistidos** | Se almacenan de forma permanente en la base de datos `medallotel.db` con código único, noches y tarifas calculadas. |

---

## 🧪 Instrucciones para Probar los 3 Casos Solicitados

### Caso 1: Crear una reserva válida
1. En la sección **"Nueva Reserva"**, ingresa el documento `1020304050` en el Paso 1 y haz clic en **"Buscar Huésped"**. Verás los datos de *Carlos Restrepo Gómez*.
2. En el Paso 2, selecciona las fechas:
   - **Entrada:** `2026-12-10`
   - **Salida:** `2026-12-14`
3. Haz clic en **"Consultar Habitaciones Disponibles"**. Se listarán las habitaciones libres y la cantidad de noches (4 noches).
4. Haz clic sobre la **Habitación 201 (Superior Queen)**.
5. Revisa el panel derecho **"Resumen de Reserva"**: verás el desglose de 4 noches y el total de `$920.000 COP`.
6. Haz clic en **"✅ Confirmar y Registrar Reserva"**. El sistema confirmará la creación con un código de reserva generado.
7. Dirígete a la pestaña **"Reservas Activas"** en el menú lateral y haz clic en **"Ver Detalle"** para consultar el desglose completo.

---

### Caso 2: Rechazar fechas inválidas
1. En el Paso 2 de **"Nueva Reserva"**, selecciona una fecha de entrada posterior o igual a la de salida:
   - **Entrada:** `2026-12-15`
   - **Salida:** `2026-12-10` (o `2026-12-15`)
2. Haz clic en **"Consultar Habitaciones Disponibles"**.
3. **Resultado:** El sistema rechaza la consulta de inmediato mostrando el mensaje de error junto al campo: *"La fecha de salida debe ser posterior a la fecha de entrada."* (tanto en la interfaz como en la validación estricta del backend).

---

### Caso 3: Rechazar una reserva que se cruce con otra para la misma habitación
1. En la base de datos ya existe una reserva activa para la **Habitación 101** del **`2026-12-01` al `2026-12-05`**.
2. En el Paso 2, ingresa un rango de fechas que se solape con ella, por ejemplo:
   - **Entrada:** `2026-12-03`
   - **Salida:** `2026-12-06`
3. Haz clic en **"Consultar Habitaciones Disponibles"**.
4. **Resultado en la búsqueda:** La **Habitación 101** no aparecerá en la lista de disponibles (tampoco la `302` por estar fuera de servicio).
5. Si un cliente o petición externa intenta forzar la reserva para la habitación `101` en ese rango, el backend rechaza la transacción con el error: *"La habitación 101 ya tiene la reserva activa RES-MED-001 entre el 2026-12-01 y 2026-12-05"*.

---

## 💳 Etapa 3: Facturación y Pagos (interfaz)

En el menú lateral, **"Facturación y Pagos"** abre la sección *Facturación y Cobros*: lista las reservas vigentes pendientes de pago (sin factura, `PENDIENTE` o `PARCIALMENTE_PAGADA`) y muestra la ficha de factura tipo recibo. La misma ficha aparece en **Reservas Activas → Ver Detalle → Facturación y Saldo**.

- **📄 Generar / Consultar Factura:** genera la factura (`FAC-AAAAMMDD-NNNN`) o la consulta si ya existe. Al facturar, la reserva ya no admite más consumos.
- **💳 Registrar Pago:** método (Efectivo, Tarjeta, Transferencia), monto (validado en vivo: > 0 y ≤ saldo) y referencia opcional. El saldo, el estado y el historial se actualizan sin recargar la página.
- Con saldo `$0` el formulario se deshabilita y se muestra *"Factura Pagada en su totalidad"*.

Endpoints usados: `POST /api/reservations/{id}/invoice`, `GET /api/invoices`, `GET /api/invoices/{id}`, `POST /api/invoices/{id}/payments`.

> **Nota:** el servidor ahora sirve `frontend/` directamente en `http://localhost:8000`. La base de datos (`backend/medallotel.db`) se crea vacía; para probar, crea habitaciones y servicios con la API, por ejemplo:
> ```bash
> curl -X POST localhost:8000/api/rooms -H 'Content-Type: application/json' -d '{"number":"101","price_per_night":150000,"room_type":"SENCILLA"}'
> curl -X POST localhost:8000/api/services -H 'Content-Type: application/json' -d '{"name":"Desayuno","price":15000}'
> ```

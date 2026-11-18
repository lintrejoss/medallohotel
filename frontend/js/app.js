/**
 * Controlador de Frontend para Medallotel - Etapas 1, 2 y 3
 * (reservas, consumos, facturación y pagos)
 */

// Estado global de la vista
const state = {
  checkIn: null,
  checkOut: null,
  nights: 0,
  availableRooms: [],
  selectedRoom: null,
  servicesCatalog: [],
  currentModalReservationId: null,
  billingSelectedId: null
};

const ACTIVE_STATUSES = ['RESERVADA', 'ACTIVA'];

const PAYMENT_METHODS = [
  { value: 'EFECTIVO', label: 'Efectivo' },
  { value: 'TARJETA', label: 'Tarjeta' },
  { value: 'TRANSFERENCIA', label: 'Transferencia' }
];

const PAGE_TITLES = {
  'new-reservation': 'Gestión de Reservas',
  'active-reservations': 'Gestión de Reservas',
  'services-catalog': 'Catálogo de Servicios',
  'billing': 'Facturación y Pagos'
};

// ==========================================
// UTILIDADES
// ==========================================

// Formato de moneda COP
const formatCOP = (val) => {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0
  }).format(val || 0);
};

// Escapa texto ingresado por el usuario antes de insertarlo como HTML
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

// SQLite guarda CURRENT_TIMESTAMP en UTC ("YYYY-MM-DD HH:MM:SS")
function formatDateTime(ts) {
  if (!ts) return '-';
  const d = new Date(String(ts).replace(' ', 'T') + 'Z');
  if (isNaN(d)) return esc(ts);
  return d.toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' });
}

function reservationCode(id) {
  return `RES-${String(id).padStart(4, '0')}`;
}

function nightsBetween(checkIn, checkOut) {
  const nights = Math.round((Date.parse(checkOut) - Date.parse(checkIn)) / 86400000);
  return Math.max(nights, 1);
}

// Cliente HTTP: normaliza las respuestas del backend ({...} o {"error": "..."})
async function api(path, options = {}) {
  const init = { method: options.method || 'GET' };
  if (options.body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(options.body);
  }
  try {
    const res = await fetch(path, init);
    let data = null;
    try { data = await res.json(); } catch (e) { /* respuesta sin cuerpo JSON */ }
    if (!res.ok) {
      return { ok: false, status: res.status, error: (data && data.error) || `Error ${res.status}` };
    }
    return { ok: true, status: res.status, data };
  } catch (err) {
    return { ok: false, status: 0, error: 'No fue posible conectar con el servidor.' };
  }
}

// Limpieza de mensajes de error (solo del formulario de Nueva Reserva)
function clearErrors() {
  document.querySelectorAll('#section-new-reservation .field-error').forEach(el => el.textContent = '');
  const errBox = document.getElementById('confirm-error-message');
  errBox.classList.add('hidden');
  errBox.textContent = '';
  const succBox = document.getElementById('confirm-success-message');
  succBox.classList.add('hidden');
  succBox.textContent = '';
}

function setError(elementId, message) {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = message;
  }
}

// Inicialización de la aplicación
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupGuestInputs();
  setupAvailabilityCheck();
  setupConfirmation();
  setupActiveReservations();
  setupModal();
  setupBillingSection();

  // Fechas por defecto sugeridas: hoy y mañana
  const today = new Date();
  const tomorrow = new Date();
  tomorrow.setDate(today.getDate() + 1);

  const formatDate = d => d.toISOString().split('T')[0];
  document.getElementById('check-in-date').value = formatDate(today);
  document.getElementById('check-out-date').value = formatDate(tomorrow);
});

// Navegación de pestañas laterales
function setupNavigation() {
  const navItems = document.querySelectorAll('.sidebar-nav .nav-item:not(.disabled)');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      navItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      const targetSection = item.dataset.section;
      document.querySelectorAll('.content-section').forEach(sec => sec.classList.remove('active'));
      const activeSec = document.getElementById(`section-${targetSection}`);
      if (activeSec) activeSec.classList.add('active');
      document.getElementById('page-title').textContent = PAGE_TITLES[targetSection] || 'Medallotel';

      if (targetSection === 'active-reservations') {
        loadActiveReservations();
      } else if (targetSection === 'services-catalog') {
        loadServicesCatalog();
      } else if (targetSection === 'billing') {
        loadBillingList();
      }
    });
  });
}

// ==========================================
// ETAPA 1: NUEVA RESERVA
// ==========================================

// Datos del huésped titular (el backend recibe nombre y documento directamente)
function setupGuestInputs() {
  document.getElementById('guest-name-input').addEventListener('input', updateSummary);
  document.getElementById('guest-doc-input').addEventListener('input', updateSummary);
}

function getGuestData() {
  return {
    name: document.getElementById('guest-name-input').value.trim(),
    doc: document.getElementById('guest-doc-input').value.trim()
  };
}

// Consulta de Disponibilidad de Habitaciones
function setupAvailabilityCheck() {
  const btnCheck = document.getElementById('btn-check-availability');

  btnCheck.addEventListener('click', async () => {
    clearErrors();
    const checkIn = document.getElementById('check-in-date').value;
    const checkOut = document.getElementById('check-out-date').value;

    let hasClientError = false;
    if (!checkIn) {
      setError('error-check-in', 'Selecciona la fecha de entrada.');
      hasClientError = true;
    }
    if (!checkOut) {
      setError('error-check-out', 'Selecciona la fecha de salida.');
      hasClientError = true;
    }
    if (checkIn && checkOut && checkIn >= checkOut) {
      setError('error-check-out', 'La fecha de salida debe ser posterior a la fecha de entrada.');
      hasClientError = true;
    }

    if (hasClientError) {
      document.getElementById('rooms-results-container').classList.add('hidden');
      state.selectedRoom = null;
      updateSummary();
      return;
    }

    const [rooms, reservations] = await Promise.all([api('/api/rooms'), api('/api/reservations')]);
    if (!rooms.ok || !reservations.ok) {
      setError('error-availability-general', (!rooms.ok ? rooms.error : reservations.error) || 'Error al consultar disponibilidad.');
      document.getElementById('rooms-results-container').classList.add('hidden');
      state.selectedRoom = null;
      updateSummary();
      return;
    }

    // Misma regla de solapamiento que aplica el backend
    const busyRoomIds = new Set(
      reservations.data
        .filter(r => r.status !== 'CANCELADA' && r.check_in < checkOut && r.check_out > checkIn)
        .map(r => r.room_id)
    );

    state.checkIn = checkIn;
    state.checkOut = checkOut;
    state.nights = nightsBetween(checkIn, checkOut);
    state.availableRooms = rooms.data.filter(r => !busyRoomIds.has(r.id));
    state.selectedRoom = null; // Reiniciar selección al cambiar fechas

    renderAvailableRooms();
    updateSummary();
  });
}

function renderAvailableRooms() {
  const container = document.getElementById('rooms-results-container');
  const grid = document.getElementById('rooms-grid');
  const nightsTag = document.getElementById('nights-tag');
  const title = document.getElementById('rooms-count-title');

  container.classList.remove('hidden');
  grid.innerHTML = '';
  nightsTag.textContent = `${state.nights} ${state.nights === 1 ? 'noche' : 'noches'}`;
  title.textContent = `${state.availableRooms.length} ${state.availableRooms.length === 1 ? 'habitación disponible' : 'habitaciones disponibles'}`;

  if (state.availableRooms.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1/-1; padding: 1.5rem; text-align: center; color: var(--text-muted); background: #f8fafc; border-radius: 8px;">
        No hay habitaciones disponibles para el rango de fechas seleccionado.
      </div>
    `;
    return;
  }

  state.availableRooms.forEach(room => {
    const card = document.createElement('div');
    card.className = 'room-card';
    card.dataset.roomId = room.id;
    card.innerHTML = `
      <div class="room-card-number">Habitación ${esc(room.number)}</div>
      <div class="room-card-type">${esc(room.room_type)}</div>
      <div class="room-card-price">${formatCOP(room.price_per_night)} <small>/ noche</small></div>
    `;

    card.addEventListener('click', () => {
      document.querySelectorAll('.room-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      state.selectedRoom = room;
      clearErrors();
      updateSummary();
    });

    grid.appendChild(card);
  });
}

// Actualización en vivo del resumen lateral
function updateSummary() {
  const summaryGuest = document.getElementById('summary-guest');
  const summaryRoom = document.getElementById('summary-room');
  const summaryRoomType = document.getElementById('summary-room-type');
  const summaryDates = document.getElementById('summary-dates');
  const summaryNights = document.getElementById('summary-nights');
  const summaryRate = document.getElementById('summary-rate');
  const summaryTotal = document.getElementById('summary-total');
  const btnConfirm = document.getElementById('btn-confirm-reservation');

  const guest = getGuestData();
  if (guest.name) {
    summaryGuest.textContent = guest.doc ? `${guest.name} (${guest.doc})` : guest.name;
  } else {
    summaryGuest.textContent = 'No seleccionado';
  }

  if (state.selectedRoom) {
    summaryRoom.textContent = `Habitación ${state.selectedRoom.number}`;
    summaryRoomType.textContent = state.selectedRoom.room_type;
    summaryRate.textContent = `${formatCOP(state.selectedRoom.price_per_night)}`;
  } else {
    summaryRoom.textContent = 'No seleccionada';
    summaryRoomType.textContent = '-';
    summaryRate.textContent = '$0 COP';
  }

  if (state.checkIn && state.checkOut && state.nights > 0) {
    summaryDates.textContent = `${state.checkIn} al ${state.checkOut}`;
    summaryNights.textContent = `${state.nights}`;
  } else {
    summaryDates.textContent = '-';
    summaryNights.textContent = '0';
  }

  if (state.selectedRoom && state.nights > 0) {
    summaryTotal.textContent = formatCOP(state.selectedRoom.price_per_night * state.nights);
  } else {
    summaryTotal.textContent = '$0 COP';
  }

  // Activar botón de confirmación únicamente si todos los datos están completos
  const canConfirm = Boolean(guest.name && state.selectedRoom && state.checkIn && state.checkOut && state.nights > 0);
  btnConfirm.disabled = !canConfirm;
}

// Confirmación de la Reserva
function setupConfirmation() {
  const btnConfirm = document.getElementById('btn-confirm-reservation');
  const errBox = document.getElementById('confirm-error-message');
  const succBox = document.getElementById('confirm-success-message');
  const label = '✅ Confirmar y Registrar Reserva';

  btnConfirm.addEventListener('click', async () => {
    clearErrors();
    const guest = getGuestData();
    if (!guest.name) {
      setError('error-guest-name', 'Ingresa el nombre del huésped.');
      return;
    }
    btnConfirm.disabled = true;
    btnConfirm.textContent = '⏳ Registrando reserva...';

    const result = await api('/api/reservations', {
      method: 'POST',
      body: {
        guest_name: guest.name,
        guest_document: guest.doc || null,
        room_id: state.selectedRoom.id,
        check_in: state.checkIn,
        check_out: state.checkOut
      }
    });

    if (!result.ok) {
      errBox.textContent = `❌ ${result.error || 'No se pudo crear la reserva.'}`;
      errBox.classList.remove('hidden');
      btnConfirm.disabled = false;
      btnConfirm.textContent = label;
      return;
    }

    const r = result.data;
    succBox.innerHTML = `
      <strong>🎉 ¡Reserva confirmada con éxito!</strong><br>
      Código: <strong>${reservationCode(r.id)}</strong><br>
      Habitación: <strong>${esc(state.selectedRoom.number)}</strong> (${esc(state.selectedRoom.room_type)})<br>
      Huésped: ${esc(r.guest_name)}
    `;
    succBox.classList.remove('hidden');

    // Limpiar selección para evitar duplicados accidentales (la habitación ya no está libre)
    state.selectedRoom = null;
    state.availableRooms = [];
    document.getElementById('rooms-results-container').classList.add('hidden');
    document.getElementById('guest-name-input').value = '';
    document.getElementById('guest-doc-input').value = '';
    updateSummary();
    btnConfirm.textContent = label;
  });
}

// ==========================================
// RESERVAS ACTIVAS Y MODAL DE DETALLE
// ==========================================

async function loadActiveReservations() {
  const tbody = document.getElementById('reservations-tbody');
  const emptyMsg = document.getElementById('no-reservations-msg');
  tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 2rem;">Cargando reservas activas...</td></tr>';
  emptyMsg.classList.add('hidden');

  const [resp, rooms] = await Promise.all([api('/api/reservations'), api('/api/rooms')]);
  if (!resp.ok || !rooms.ok) {
    tbody.innerHTML = `<tr><td colspan="10" style="color: red; text-align: center;">Error al cargar reservas: ${esc(resp.error || rooms.error)}</td></tr>`;
    return;
  }

  const roomsById = Object.fromEntries(rooms.data.map(r => [r.id, r]));
  const reservations = resp.data.filter(r => ACTIVE_STATUSES.includes(r.status));
  if (reservations.length === 0) {
    tbody.innerHTML = '';
    emptyMsg.classList.remove('hidden');
    return;
  }

  tbody.innerHTML = '';
  reservations.forEach(r => {
    const room = roomsById[r.room_id] || {};
    const nights = nightsBetween(r.check_in, r.check_out);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${reservationCode(r.id)}</strong></td>
      <td>${esc(r.guest_name)}</td>
      <td><small>${esc(r.guest_document || '-')}</small></td>
      <td><strong>Hab. ${esc(room.number || r.room_id)}</strong><br><small style="color:var(--text-muted)">${esc(room.room_type || '')}</small></td>
      <td>${esc(r.check_in)}</td>
      <td>${esc(r.check_out)}</td>
      <td>${nights} n</td>
      <td><strong>${formatCOP(nights * (room.price_per_night || 0))}</strong></td>
      <td><span class="badge-status badge-activa">${esc(r.status)}</span></td>
      <td>
        <button class="btn btn-secondary btn-sm btn-view-res" data-id="${r.id}">
          Ver Detalle
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll('.btn-view-res').forEach(btn => {
    btn.addEventListener('click', () => openReservationModal(btn.dataset.id));
  });
}

function setupActiveReservations() {
  document.getElementById('btn-refresh-reservations').addEventListener('click', loadActiveReservations);
}

// Modal de Detalle de Reserva
function setupModal() {
  const modal = document.getElementById('detail-modal');
  const btnClose = document.getElementById('btn-close-modal');
  const btnCloseAction = document.getElementById('btn-modal-close-action');

  const closeModal = () => {
    modal.classList.add('hidden');
    state.currentModalReservationId = null;
  };
  btnClose.addEventListener('click', closeModal);
  btnCloseAction.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });
}

// ==========================================
// ETAPA 2: CATÁLOGO DE SERVICIOS Y CONSUMOS
// ==========================================

async function loadServicesCatalog() {
  const grid = document.getElementById('services-catalog-grid');
  grid.innerHTML = '<p style="color: var(--text-muted); padding: 1rem;">Cargando catálogo de servicios...</p>';

  const result = await api('/api/services');
  if (!result.ok) {
    grid.innerHTML = `<p style="color: red;">Error al cargar catálogo: ${esc(result.error)}</p>`;
    return;
  }

  state.servicesCatalog = result.data;
  if (state.servicesCatalog.length === 0) {
    grid.innerHTML = '<p style="color: var(--text-muted); padding: 1rem;">Aún no hay servicios en el catálogo.</p>';
    return;
  }
  grid.innerHTML = '';
  state.servicesCatalog.forEach(s => {
    const card = document.createElement('div');
    card.className = 'service-card';
    card.innerHTML = `
      <h4 class="service-name">${esc(s.name)}</h4>
      <p class="service-description">Servicio hotelero oficial</p>
      <div class="service-price">${formatCOP(s.price)}</div>
    `;
    grid.appendChild(card);
  });
}

async function fetchServicesCatalogIfNeeded() {
  if (state.servicesCatalog.length === 0) {
    const result = await api('/api/services');
    if (result.ok) state.servicesCatalog = result.data;
  }
}

async function openReservationModal(resId) {
  state.currentModalReservationId = resId;
  const modal = document.getElementById('detail-modal');
  const content = document.getElementById('modal-content');
  content.innerHTML = '<p style="text-align: center; padding: 1.5rem;">Cargando información y consumos de la reserva...</p>';
  modal.classList.remove('hidden');

  await fetchServicesCatalogIfNeeded();
  await reloadReservationDetail(resId);
}

// Carga reserva + habitación + consumos y dibuja el detalle
async function reloadReservationDetail(resId) {
  const content = document.getElementById('modal-content');
  const [resp, cons, rooms] = await Promise.all([
    api(`/api/reservations/${resId}`),
    api(`/api/reservations/${resId}/consumptions`),
    api('/api/rooms')
  ]);

  const failed = [resp, cons, rooms].find(r => !r.ok);
  if (failed) {
    content.innerHTML = `<p style="color: red; padding: 1rem;">Error: ${esc(failed.error)}</p>`;
    return;
  }

  const room = rooms.data.find(r => r.id === resp.data.room_id) || {};
  renderReservationDetailContent(resp.data, room, cons.data);
}

function renderReservationDetailContent(d, room, consumptions) {
  const content = document.getElementById('modal-content');
  const nights = nightsBetween(d.check_in, d.check_out);
  const rate = room.price_per_night || 0;
  const totalLodging = nights * rate;
  const totalConsumptions = consumptions.reduce((acc, c) => acc + c.subtotal, 0);

  // Renderizar filas de consumos existentes
  let consumptionsTableRows = '';
  if (consumptions.length === 0) {
    consumptionsTableRows = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1rem;">
          No hay consumos registrados para esta reserva.
        </td>
      </tr>
    `;
  } else {
    consumptionsTableRows = consumptions.map(c => `
      <tr>
        <td><strong>${esc(c.description)}</strong></td>
        <td>${c.quantity}</td>
        <td>${formatCOP(c.unit_price)}</td>
        <td><strong>${formatCOP(c.subtotal)}</strong></td>
        <td><small style="color:var(--text-muted)">${formatDateTime(c.created_at)}</small></td>
      </tr>
    `).join('');
  }

  // Opciones de servicios para el selector
  const serviceOptions = state.servicesCatalog.map(s => `
    <option value="${s.id}">${esc(s.name)} - ${formatCOP(s.price)}</option>
  `).join('');

  content.innerHTML = `
    <!-- Datos de la Estancia -->
    <div class="modal-detail-grid">
      <div class="detail-item">
        <span class="lbl">Código de Reserva</span>
        <span class="val" style="color: var(--primary); font-size: 1.1rem;">${reservationCode(d.id)}</span>
      </div>
      <div class="detail-item">
        <span class="lbl">Estado Actual</span>
        <span class="val"><span class="badge-status badge-activa">${esc(d.status)}</span></span>
      </div>
      <div class="detail-item">
        <span class="lbl">Huésped Titular</span>
        <span class="val">${esc(d.guest_name)}${d.guest_document ? ` (${esc(d.guest_document)})` : ''}</span>
      </div>
      <div class="detail-item">
        <span class="lbl">Habitación Asignada</span>
        <span class="val">Hab. ${esc(room.number || d.room_id)} (${esc(room.room_type || '-')})</span>
      </div>
      <div class="detail-item">
        <span class="lbl">Fechas de Estancia</span>
        <span class="val">${esc(d.check_in)} al ${esc(d.check_out)} (${nights} ${nights === 1 ? 'noche' : 'noches'})</span>
      </div>
      <div class="detail-item">
        <span class="lbl">Tarifa Alojamiento</span>
        <span class="val">${formatCOP(rate)} / noche</span>
      </div>
    </div>

    <!-- Sección Etapa 2: Consumos y Servicios -->
    <div class="consumptions-section">
      <h4>🛒 Registro de Consumos y Servicios</h4>
      <p class="helper-text" style="margin-bottom: 0.75rem;">Agrega consumos de restaurante, lavandería u otros servicios del catálogo a esta estancia.</p>

      <div class="consumption-form-box">
        <div id="consumption-lock-notice" class="alert-box alert-info hidden">
          🔒 La reserva ya está facturada: no admite más consumos.
        </div>
        <form id="form-add-consumption" onsubmit="event.preventDefault(); handleAddConsumption(${d.id});">
          <fieldset id="consumption-fieldset" class="plain-fieldset">
            <div class="consumption-form-grid">
              <div class="form-group" style="margin-bottom: 0;">
                <label for="select-service">Servicio del Catálogo</label>
                <select id="select-service" required>
                  <option value="">-- Selecciona un servicio --</option>
                  ${serviceOptions}
                </select>
                <span class="field-error" id="error-consumption-service"></span>
              </div>

              <div class="form-group" style="margin-bottom: 0;">
                <label for="input-qty">Cantidad</label>
                <input type="number" id="input-qty" min="1" value="1" required style="padding: 0.65rem 0.85rem;">
                <span class="field-error" id="error-consumption-qty"></span>
              </div>

              <button type="submit" id="btn-submit-consumption" class="btn btn-primary" style="height: 42px;">
                ➕ Agregar
              </button>
            </div>
            <span class="field-error" id="error-consumption-general"></span>
          </fieldset>
        </form>
      </div>

      <!-- Tabla de consumos registrados -->
      <h5 style="font-size: 0.95rem; font-weight: 600; margin-bottom: 0.5rem; color: #334155;">Consumos Registrados en la Estancia</h5>
      <div class="table-wrapper">
        <table class="data-table" style="font-size: 0.825rem;">
          <thead>
            <tr>
              <th>Servicio</th>
              <th>Cantidad</th>
              <th>Precio Aplicado</th>
              <th>Subtotal</th>
              <th>Fecha/Hora</th>
            </tr>
          </thead>
          <tbody>
            ${consumptionsTableRows}
          </tbody>
        </table>
      </div>

      <!-- Totales Acumulados -->
      <div class="consumption-totals-box">
        <div class="totals-row">
          <span>Subtotal Alojamiento (${nights} ${nights === 1 ? 'noche' : 'noches'}):</span>
          <span>${formatCOP(totalLodging)}</span>
        </div>
        <div class="totals-row">
          <span>Subtotal Servicios y Consumos:</span>
          <span style="font-weight: 600; color: #0f172a;">${formatCOP(totalConsumptions)}</span>
        </div>
        <div class="totals-row grand-total">
          <span>Total Acumulado a Facturar:</span>
          <span>${formatCOP(totalLodging + totalConsumptions)}</span>
        </div>
      </div>
    </div>

    <!-- Sección Etapa 3: Facturación y Saldo -->
    <div class="billing-modal-section">
      <h4>🧾 Facturación y Saldo</h4>
      <div id="modal-billing"></div>
    </div>
  `;

  mountBillingPanel(document.getElementById('modal-billing'), d.id, {
    scope: 'modal',
    onInvoice: (invoice) => setConsumptionsLocked(Boolean(invoice))
  });
}

// Bloquea el formulario de consumos cuando la reserva ya fue facturada
function setConsumptionsLocked(locked) {
  const fieldset = document.getElementById('consumption-fieldset');
  const notice = document.getElementById('consumption-lock-notice');
  if (!fieldset || !notice) return;
  fieldset.disabled = locked;
  notice.classList.toggle('hidden', !locked);
}

// Acción de agregar consumo
window.handleAddConsumption = async function(reservationId) {
  const serviceSelect = document.getElementById('select-service');
  const qtyInput = document.getElementById('input-qty');
  const btnSubmit = document.getElementById('btn-submit-consumption');
  const errService = document.getElementById('error-consumption-service');
  const errQty = document.getElementById('error-consumption-qty');
  const errGeneral = document.getElementById('error-consumption-general');

  errService.textContent = '';
  errQty.textContent = '';
  errGeneral.textContent = '';

  const serviceId = serviceSelect.value;
  const quantity = parseInt(qtyInput.value, 10);

  if (!serviceId) {
    errService.textContent = 'Selecciona un servicio.';
    return;
  }
  if (!quantity || quantity <= 0) {
    errQty.textContent = 'Cantidad inválida.';
    return;
  }

  btnSubmit.disabled = true;
  btnSubmit.textContent = 'Guardando...';

  const result = await api(`/api/reservations/${reservationId}/consumptions`, {
    method: 'POST',
    body: { service_id: parseInt(serviceId, 10), quantity: quantity }
  });

  if (!result.ok) {
    if (/cantidad/i.test(result.error)) errQty.textContent = result.error;
    else if (/servicio/i.test(result.error)) errService.textContent = result.error;
    else errGeneral.textContent = result.error || 'Error al agregar consumo.';
    btnSubmit.disabled = false;
    btnSubmit.textContent = '➕ Agregar';
    return;
  }

  // Recargar el detalle de la reserva con los nuevos consumos calculados
  await reloadReservationDetail(reservationId);
};

// ==========================================
// ETAPA 3: FACTURACIÓN Y PAGOS
// ==========================================

function invoiceBadge(status) {
  const labels = { SIN_FACTURAR: 'SIN FACTURAR' };
  return `<span class="badge-status badge-inv badge-inv-${status.toLowerCase()}" data-status="${status}">${labels[status] || status}</span>`;
}

// Devuelve { invoice } (null si aún no existe) o { error }
async function fetchInvoiceForReservation(reservationId) {
  const list = await api('/api/invoices');
  if (!list.ok) return { error: list.error };
  const hit = list.data.find(i => String(i.reservation_id) === String(reservationId));
  if (!hit) return { invoice: null };
  const detail = await api(`/api/invoices/${hit.id}`);
  return detail.ok ? { invoice: detail.data } : { error: detail.error };
}

/**
 * Panel de facturación reutilizable (modal de reserva y sección Facturación y Cobros).
 * opts: { scope: 'modal' | 'billing', context?: {...}, onInvoice?(invoice), onChange?(invoice) }
 */
async function mountBillingPanel(container, reservationId, opts = {}) {
  const token = container._billingToken = (container._billingToken || 0) + 1;
  container.innerHTML = '<p class="helper-text">Consultando factura...</p>';

  const found = await fetchInvoiceForReservation(reservationId);
  if (container._billingToken !== token) return; // se eligió otra reserva mientras cargaba

  if (found.error) {
    container.innerHTML = `<div class="alert-box alert-error">❌ ${esc(found.error)}</div>`;
    return;
  }
  renderBillingPanel(container, reservationId, found.invoice, opts);
}

function renderBillingPanel(container, reservationId, invoice, opts) {
  const scope = opts.scope || 'modal';

  container.innerHTML = `
    <div class="billing-panel ${scope === 'billing' ? 'billing-panel-receipt' : ''}">
      ${receiptHeader(scope, opts.context)}
      <div class="billing-panel-head">
        <div>
          ${invoice
            ? `<span class="invoice-number" data-testid="invoice-number">${esc(invoice.invoice_number)}</span>
               <span class="invoice-date">Emitida: ${formatDateTime(invoice.created_at)}</span>`
            : `<span class="invoice-number invoice-none">Sin factura generada</span>`}
        </div>
        <div class="billing-panel-actions">
          ${invoice ? invoiceBadge(invoice.status) : ''}
          <button type="button" class="btn btn-primary btn-sm" id="${scope}-btn-invoice">📄 Generar / Consultar Factura</button>
        </div>
      </div>
      <div class="field-error" id="${scope}-err-invoice"></div>
      ${invoice ? invoiceBody(invoice, scope, opts) : `
        <p class="helper-text">Genera la factura para congelar alojamiento y consumos y habilitar el registro de pagos. Después de facturar no se podrán agregar más consumos.</p>`}
    </div>
  `;

  container.querySelector(`#${scope}-btn-invoice`).addEventListener('click', () =>
    handleInvoiceButton(container, reservationId, invoice, opts));

  if (invoice) {
    wirePaymentForm(container, invoice, opts);
  }
  if (opts.onInvoice) opts.onInvoice(invoice);
}

// Encabezado tipo recibo hotelero (solo en la sección Facturación y Cobros)
function receiptHeader(scope, ctx) {
  if (scope !== 'billing' || !ctx) return '';
  return `
    <div class="receipt-hotel">
      <div class="receipt-brand">🏨 Medallotel</div>
      <div class="receipt-sub">Recibo de Factura · Hotel</div>
    </div>
    <div class="receipt-meta">
      <div><span>Huésped</span><strong>${esc(ctx.guest)}</strong></div>
      <div><span>Reserva</span><strong>${esc(ctx.code)}</strong></div>
      <div><span>Habitación</span><strong>${esc(ctx.room)}</strong></div>
      <div><span>Estancia</span><strong>${esc(ctx.dates)}</strong></div>
    </div>`;
}

function invoiceBody(invoice, scope, opts) {
  const paid = invoice.balance <= 0;
  const lodging = invoice.items.lodging;
  const itemRows = [
    `<tr><td>${esc(lodging.description)}</td><td>${lodging.nights} ${lodging.nights === 1 ? 'noche' : 'noches'}</td><td>${formatCOP(lodging.unit_price)}</td><td><strong>${formatCOP(lodging.subtotal)}</strong></td></tr>`,
    ...invoice.items.services.map(s =>
      `<tr><td>${esc(s.description)}</td><td>${s.quantity}</td><td>${formatCOP(s.unit_price)}</td><td><strong>${formatCOP(s.subtotal)}</strong></td></tr>`)
  ].join('');
  const items = scope === 'billing' ? `
    <div class="table-wrapper">
      <table class="data-table receipt-items">
        <thead><tr><th>Concepto</th><th>Cant.</th><th>Precio unit.</th><th>Subtotal</th></tr></thead>
        <tbody>${itemRows}</tbody>
      </table>
    </div>` : '';

  const totals = `
    <div class="invoice-totals">
      <div class="totals-row"><span>Total Alojamiento</span><span data-testid="total-lodging">${formatCOP(invoice.total_lodging)}</span></div>
      <div class="totals-row"><span>Total Consumos</span><span data-testid="total-services">${formatCOP(invoice.total_services)}</span></div>
      <div class="totals-row total-due"><span>Total a Pagar</span><span data-testid="grand-total">${formatCOP(invoice.grand_total)}</span></div>
      <div class="totals-row total-paid"><span>Total Pagado</span><span data-testid="paid-amount">${formatCOP(invoice.paid_amount)}</span></div>
      <div class="totals-row balance-row ${paid ? 'balance-zero' : ''}"><span>Saldo Pendiente</span><span data-testid="balance">${formatCOP(invoice.balance)}</span></div>
    </div>`;

  const methodOptions = PAYMENT_METHODS.map(m => `<option value="${m.value}">${m.label}</option>`).join('');
  const paymentForm = `
    ${paid ? '<div class="paid-banner" role="status">✅ Factura Pagada en su totalidad</div>' : ''}
    <form class="payment-form" id="${scope}-pay-form" novalidate>
      <fieldset id="${scope}-pay-fieldset" class="plain-fieldset" ${paid ? 'disabled' : ''}>
        <h5 class="payment-form-title">Registrar Pago</h5>
        <div class="payment-grid">
          <div class="form-group">
            <label for="${scope}-pay-method">Método de pago</label>
            <select id="${scope}-pay-method">
              <option value="">-- Selecciona --</option>
              ${methodOptions}
            </select>
            <span class="field-error" id="${scope}-err-method"></span>
          </div>
          <div class="form-group">
            <label for="${scope}-pay-amount">Monto a abonar (COP)</label>
            <div class="amount-wrap">
              <input type="number" id="${scope}-pay-amount" step="any" min="0" inputmode="decimal" placeholder="0">
              <button type="button" class="btn btn-secondary btn-sm" id="${scope}-pay-all">Saldo total</button>
            </div>
            <span class="field-error" id="${scope}-err-amount"></span>
          </div>
          <div class="form-group payment-ref">
            <label for="${scope}-pay-ref">Referencia / Número de comprobante (opcional)</label>
            <input type="text" id="${scope}-pay-ref" maxlength="100" placeholder="Ej: 004512" autocomplete="off">
          </div>
        </div>
        <span class="field-error" id="${scope}-err-payment"></span>
        <button type="submit" class="btn btn-confirm" id="${scope}-pay-submit">💳 Registrar Pago</button>
      </fieldset>
    </form>`;

  const paymentRows = invoice.payments.length === 0
    ? '<tr><td colspan="4" style="text-align:center; color: var(--text-muted); padding: 1rem;">Aún no se han registrado pagos.</td></tr>'
    : invoice.payments.map(p => {
        const m = PAYMENT_METHODS.find(x => x.value === p.payment_method);
        return `<tr>
          <td>${m ? m.label : esc(p.payment_method)}</td>
          <td><strong>${formatCOP(p.amount)}</strong></td>
          <td>${formatDateTime(p.paid_at)}</td>
          <td>${p.reference ? esc(p.reference) : '<span style="color:var(--text-muted)">-</span>'}</td>
        </tr>`;
      }).join('');
  const history = `
    <h5 class="payment-form-title">Historial de pagos</h5>
    <div class="table-wrapper">
      <table class="data-table payments-table" style="font-size: 0.825rem;">
        <thead><tr><th>Método</th><th>Monto</th><th>Fecha / Hora</th><th>Referencia</th></tr></thead>
        <tbody>${paymentRows}</tbody>
      </table>
    </div>`;

  return items + totals + paymentForm + history;
}

// Generar (con confirmación) o consultar la factura de la reserva
async function handleInvoiceButton(container, reservationId, invoice, opts) {
  const scope = opts.scope || 'modal';
  const errEl = container.querySelector(`#${scope}-err-invoice`);
  errEl.textContent = '';

  let result;
  if (invoice) {
    result = await api(`/api/invoices/${invoice.id}`); // consulta: refresca desde el servidor
  } else {
    const ok = window.confirm('Se generará la factura de esta reserva. Después ya no podrás agregar más consumos. ¿Continuar?');
    if (!ok) return;
    result = await api(`/api/reservations/${reservationId}/invoice`, { method: 'POST' });
  }

  if (!result.ok) {
    errEl.textContent = result.error;
    return;
  }
  renderBillingPanel(container, reservationId, result.data, opts);
  if (opts.onChange) opts.onChange(result.data);
}

// Validación en vivo y envío del formulario de pago
function wirePaymentForm(container, invoice, opts) {
  const scope = opts.scope || 'modal';
  const form = container.querySelector(`#${scope}-pay-form`);
  const method = container.querySelector(`#${scope}-pay-method`);
  const amount = container.querySelector(`#${scope}-pay-amount`);
  const ref = container.querySelector(`#${scope}-pay-ref`);
  const payAll = container.querySelector(`#${scope}-pay-all`);
  const submit = container.querySelector(`#${scope}-pay-submit`);
  const errMethod = container.querySelector(`#${scope}-err-method`);
  const errAmount = container.querySelector(`#${scope}-err-amount`);
  const errPayment = container.querySelector(`#${scope}-err-payment`);

  const cents = (n) => Math.round(Number(n) * 100);

  // Devuelve el mensaje de error del monto ('' si es válido o está vacío)
  const amountProblem = (requireValue) => {
    if (amount.value.trim() === '') return requireValue ? 'Ingresa el monto a abonar.' : '';
    const value = Number(amount.value);
    if (!isFinite(value) || value <= 0) return 'El monto debe ser mayor que 0.';
    if (cents(value) > cents(invoice.balance)) {
      return `El monto no puede superar el saldo pendiente (${formatCOP(invoice.balance)}).`;
    }
    return '';
  };

  const refreshLive = () => {
    errAmount.textContent = amountProblem(false);
    errPayment.textContent = '';
  };
  amount.addEventListener('input', refreshLive);
  method.addEventListener('change', () => { errMethod.textContent = ''; errPayment.textContent = ''; });

  payAll.addEventListener('click', () => {
    amount.value = invoice.balance;
    refreshLive();
    amount.focus();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errMethod.textContent = '';
    errPayment.textContent = '';

    const methodProblem = method.value ? '' : 'Selecciona un método de pago.';
    const problem = amountProblem(true);
    errMethod.textContent = methodProblem;
    errAmount.textContent = problem;
    if (methodProblem || problem) return;

    submit.disabled = true;
    submit.textContent = '⏳ Registrando pago...';

    const result = await api(`/api/invoices/${invoice.id}/payments`, {
      method: 'POST',
      body: {
        amount: Number(amount.value),
        payment_method: method.value,
        reference: ref.value.trim() || null
      }
    });

    if (!result.ok) {
      submit.disabled = false;
      submit.textContent = '💳 Registrar Pago';
      if (/m[ée]todo/i.test(result.error)) errMethod.textContent = result.error;
      else if (/monto/i.test(result.error)) errAmount.textContent = result.error;
      else errPayment.textContent = result.error;
      return;
    }

    // El backend devuelve la factura actualizada: se redibuja sin recargar la página
    renderBillingPanel(container, invoice.reservation_id, result.data, opts);
    if (opts.onChange) opts.onChange(result.data);
  });
}

// ---------- Sección "Facturación y Cobros" ----------

function setupBillingSection() {
  document.getElementById('btn-refresh-billing').addEventListener('click', loadBillingList);
}

async function loadBillingList() {
  const list = document.getElementById('billing-list');
  const empty = document.getElementById('billing-list-empty');
  list.innerHTML = '<p class="helper-text">Cargando reservas...</p>';
  empty.classList.add('hidden');

  const [reservations, rooms, invoices] = await Promise.all([
    api('/api/reservations'), api('/api/rooms'), api('/api/invoices')
  ]);
  const failed = [reservations, rooms, invoices].find(r => !r.ok);
  if (failed) {
    list.innerHTML = `<div class="alert-box alert-error">❌ ${esc(failed.error)}</div>`;
    return;
  }

  const roomsById = Object.fromEntries(rooms.data.map(r => [r.id, r]));
  const invoiceByRes = Object.fromEntries(invoices.data.map(i => [i.reservation_id, i]));

  // Pendientes de pago: reservas vigentes sin factura o con factura no pagada
  const pending = reservations.data
    .filter(r => ACTIVE_STATUSES.includes(r.status))
    .filter(r => !invoiceByRes[r.id] || invoiceByRes[r.id].status !== 'PAGADA');

  state.billingPending = pending;
  list.innerHTML = '';
  if (pending.length === 0) {
    empty.classList.remove('hidden');
    return;
  }

  pending.forEach(r => {
    const room = roomsById[r.room_id] || {};
    const inv = invoiceByRes[r.id];
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'billing-item' + (String(r.id) === String(state.billingSelectedId) ? ' selected' : '');
    item.dataset.id = r.id;
    item.innerHTML = `
      <div class="billing-item-top">
        <strong>${reservationCode(r.id)}</strong>
        ${invoiceBadge(inv ? inv.status : 'SIN_FACTURAR')}
      </div>
      <div class="billing-item-guest">${esc(r.guest_name)}</div>
      <div class="billing-item-meta">Hab. ${esc(room.number || r.room_id)} · ${esc(r.check_in)} → ${esc(r.check_out)}</div>
      ${inv ? `<div class="billing-item-balance">Saldo: <strong>${formatCOP(inv.balance)}</strong></div>` : ''}
    `;
    item.addEventListener('click', () => selectBillingReservation(r, room));
    list.appendChild(item);
  });
}

function selectBillingReservation(r, room) {
  state.billingSelectedId = r.id;
  document.querySelectorAll('.billing-item').forEach(el =>
    el.classList.toggle('selected', el.dataset.id === String(r.id)));

  const detail = document.getElementById('billing-detail');
  detail.innerHTML = '<div class="card"><div id="billing-panel-host"></div></div>';
  mountBillingPanel(document.getElementById('billing-panel-host'), r.id, {
    scope: 'billing',
    context: {
      guest: r.guest_name + (r.guest_document ? ` (${r.guest_document})` : ''),
      code: reservationCode(r.id),
      room: `Hab. ${room.number || r.room_id} (${room.room_type || '-'})`,
      dates: `${r.check_in} al ${r.check_out}`
    },
    // Mantiene la lista lateral al día tras generar facturas o registrar pagos
    onChange: () => loadBillingList()
  });
}

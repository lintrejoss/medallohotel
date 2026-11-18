/**
 * Controlador de Frontend para Medallotel - Etapa 1
 */

// Estado global de la vista
const state = {
  currentGuest: null,
  checkIn: null,
  checkOut: null,
  nights: 0,
  availableRooms: [],
  selectedRoom: null
};

// Formato de moneda COP
const formatCOP = (val) => {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0
  }).format(val);
};

// Limpieza de mensajes de error
function clearErrors() {
  document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
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
  setupGuestSearch();
  setupAvailabilityCheck();
  setupConfirmation();
  setupActiveReservations();
  setupModal();

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

      if (targetSection === 'active-reservations') {
        loadActiveReservations();
      }
    });
  });
}

// Búsqueda de Huéspedes
function setupGuestSearch() {
  const searchBtn = document.getElementById('btn-search-guest');
  const docInput = document.getElementById('doc-search-input');

  const executeSearch = async () => {
    clearErrors();
    const doc = docInput.value.trim();
    if (!doc) {
      setError('error-doc-search', 'Por favor ingresa un número de documento.');
      return;
    }

    try {
      const res = await fetch(`/api/guests/search?doc_number=${encodeURIComponent(doc)}`);
      const result = await res.json();

      if (!res.ok || !result.success) {
        state.currentGuest = null;
        document.getElementById('guest-result-card').classList.add('hidden');
        setError('error-doc-search', result.error || 'Huésped no encontrado.');
        updateSummary();
        return;
      }

      state.currentGuest = result.data;
      document.getElementById('guest-name').textContent = `${result.data.first_name} ${result.data.last_name}`;
      document.getElementById('guest-doc').textContent = `${result.data.doc_type} ${result.data.doc_number}`;
      document.getElementById('guest-phone').textContent = result.data.phone || 'N/A';
      document.getElementById('guest-email').textContent = result.data.email || 'N/A';
      document.getElementById('selected-guest-id').value = result.data.id;
      document.getElementById('guest-result-card').classList.remove('hidden');

      updateSummary();
    } catch (err) {
      setError('error-doc-search', 'Error de conexión con el servidor.');
    }
  };

  searchBtn.addEventListener('click', executeSearch);
  docInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      executeSearch();
    }
  });
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

    try {
      const res = await fetch(`/api/rooms/available?check_in=${checkIn}&check_out=${checkOut}`);
      const result = await res.json();

      if (!res.ok || !result.success) {
        if (result.field === 'check_in_date') setError('error-check-in', result.error);
        else if (result.field === 'check_out_date') setError('error-check-out', result.error);
        else setError('error-availability-general', result.error || 'Error al consultar disponibilidad.');
        document.getElementById('rooms-results-container').classList.add('hidden');
        state.selectedRoom = null;
        updateSummary();
        return;
      }

      state.checkIn = checkIn;
      state.checkOut = checkOut;
      const dIn = new Date(checkIn);
      const dOut = new Date(checkOut);
      state.nights = Math.round((dOut - dIn) / (1000 * 60 * 60 * 24));
      state.availableRooms = result.data;
      state.selectedRoom = null; // Reiniciar selección al cambiar fechas

      renderAvailableRooms();
      updateSummary();
    } catch (err) {
      setError('error-availability-general', 'No fue posible conectar con el servidor.');
    }
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
  title.textContent = `${state.availableRooms.length} habitaciones disponibles`;

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
      <div class="room-card-number">Habitación ${room.room_number}</div>
      <div class="room-card-type">${room.room_type}</div>
      <div class="room-card-capacity">👥 Capacidad: ${room.capacity} ${room.capacity === 1 ? 'persona' : 'personas'}</div>
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

  if (state.currentGuest) {
    summaryGuest.textContent = `${state.currentGuest.first_name} ${state.currentGuest.last_name} (${state.currentGuest.doc_number})`;
  } else {
    summaryGuest.textContent = 'No seleccionado';
  }

  if (state.selectedRoom) {
    summaryRoom.textContent = `Habitación ${state.selectedRoom.room_number}`;
    summaryRoomType.textContent = `${state.selectedRoom.room_type} (Hasta ${state.selectedRoom.capacity} pers.)`;
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
    const total = state.selectedRoom.price_per_night * state.nights;
    summaryTotal.textContent = formatCOP(total);
  } else {
    summaryTotal.textContent = '$0 COP';
  }

  // Activar botón de confirmación únicamente si todos los datos están completos
  const canConfirm = Boolean(state.currentGuest && state.selectedRoom && state.checkIn && state.checkOut && state.nights > 0);
  btnConfirm.disabled = !canConfirm;
}

// Confirmación de la Reserva
function setupConfirmation() {
  const btnConfirm = document.getElementById('btn-confirm-reservation');
  const errBox = document.getElementById('confirm-error-message');
  const succBox = document.getElementById('confirm-success-message');

  btnConfirm.addEventListener('click', async () => {
    clearErrors();
    btnConfirm.disabled = true;
    btnConfirm.textContent = '⏳ Registrando reserva...';

    const payload = {
      guest_id: state.currentGuest.id,
      room_id: state.selectedRoom.id,
      check_in_date: state.checkIn,
      check_out_date: state.checkOut
    };

    try {
      const res = await fetch('/api/reservations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await res.json();

      if (!res.ok || !result.success) {
        errBox.textContent = `❌ ${result.error || 'No se pudo crear la reserva.'}`;
        errBox.classList.remove('hidden');
        if (result.field === 'room_id' || result.field === 'room_selection') {
          setError('error-room-selection', result.error);
        }
        btnConfirm.disabled = false;
        btnConfirm.textContent = '✅ Confirmar y Registrar Reserva';
        return;
      }

      succBox.innerHTML = `
        <strong>🎉 ¡Reserva confirmada con éxito!</strong><br>
        Código: <strong>${result.data.code}</strong><br>
        Habitación: <strong>${result.data.room_number}</strong> (${result.data.room_type})<br>
        Huésped: ${result.data.first_name} ${result.data.last_name}
      `;
      succBox.classList.remove('hidden');

      // Limpiar selección de habitación para evitar duplicados accidentales
      state.selectedRoom = null;
      document.querySelectorAll('.room-card').forEach(c => c.classList.remove('selected'));
      updateSummary();

      btnConfirm.textContent = '✅ Confirmar y Registrar Reserva';
    } catch (err) {
      errBox.textContent = 'Error al comunicar con el servidor.';
      errBox.classList.remove('hidden');
      btnConfirm.disabled = false;
      btnConfirm.textContent = '✅ Confirmar y Registrar Reserva';
    }
  });
}

// Carga y Visualización de Reservas Activas
async function loadActiveReservations() {
  const tbody = document.getElementById('reservations-tbody');
  const emptyMsg = document.getElementById('no-reservations-msg');
  tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 2rem;">Cargando reservas activas...</td></tr>';
  emptyMsg.classList.add('hidden');

  try {
    const res = await fetch('/api/reservations/active');
    const result = await res.json();

    if (!res.ok || !result.success) {
      tbody.innerHTML = `<tr><td colspan="10" style="color: red; text-align: center;">Error al cargar reservas: ${result.error}</td></tr>`;
      return;
    }

    const reservations = result.data;
    if (reservations.length === 0) {
      tbody.innerHTML = '';
      emptyMsg.classList.remove('hidden');
      return;
    }

    tbody.innerHTML = '';
    reservations.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${r.code}</strong></td>
        <td>${r.first_name} ${r.last_name}</td>
        <td><small>${r.doc_type} ${r.doc_number}</small></td>
        <td><strong>Hab. ${r.room_number}</strong><br><small style="color:var(--text-muted)">${r.room_type}</small></td>
        <td>${r.check_in_date}</td>
        <td>${r.check_out_date}</td>
        <td>${r.total_nights} n</td>
        <td><strong>${formatCOP(r.total_lodging)}</strong></td>
        <td><span class="badge-status badge-activa">${r.status}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm btn-view-res" data-id="${r.id}">
            Ver Detalle
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.querySelectorAll('.btn-view-res').forEach(btn => {
      btn.addEventListener('click', () => {
        openReservationModal(btn.dataset.id);
      });
    });

  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="10" style="color: red; text-align: center;">Error de conexión.</td></tr>';
  }
}

function setupActiveReservations() {
  document.getElementById('btn-refresh-reservations').addEventListener('click', loadActiveReservations);
}

// Modal de Detalle de Reserva
function setupModal() {
  const modal = document.getElementById('detail-modal');
  const btnClose = document.getElementById('btn-close-modal');
  const btnCloseAction = document.getElementById('btn-modal-close-action');

  const closeModal = () => modal.classList.add('hidden');
  btnClose.addEventListener('click', closeModal);
  btnCloseAction.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });
}

async function openReservationModal(resId) {
  const modal = document.getElementById('detail-modal');
  const content = document.getElementById('modal-content');
  content.innerHTML = '<p style="text-align: center; padding: 1rem;">Cargando detalle...</p>';
  modal.classList.remove('hidden');

  try {
    const res = await fetch(`/api/reservations/${resId}`);
    const result = await res.json();

    if (!res.ok || !result.success) {
      content.innerHTML = `<p style="color: red;">Error: ${result.error}</p>`;
      return;
    }

    const d = result.data;
    content.innerHTML = `
      <div class="modal-detail-grid">
        <div class="detail-item">
          <span class="lbl">Código de Reserva</span>
          <span class="val highlight" style="color: var(--primary); font-size: 1.1rem;">${d.code}</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Estado Actual</span>
          <span class="val"><span class="badge-status badge-activa">${d.status}</span></span>
        </div>
        <div class="detail-item">
          <span class="lbl">Huésped Titular</span>
          <span class="val">${d.first_name} ${d.last_name}</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Documento de Identidad</span>
          <span class="val">${d.doc_type} ${d.doc_number}</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Teléfono / Contacto</span>
          <span class="val">${d.phone || 'No registrado'}</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Correo Electrónico</span>
          <span class="val">${d.email || 'No registrado'}</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Habitación Asignada</span>
          <span class="val">Habitación ${d.room_number} (${d.room_type})</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Capacidad Habitación</span>
          <span class="val">${d.capacity} personas</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Fecha de Entrada</span>
          <span class="val">${d.check_in_date}</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Fecha de Salida</span>
          <span class="val">${d.check_out_date}</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Noches de Estancia</span>
          <span class="val">${d.total_nights} noches</span>
        </div>
        <div class="detail-item">
          <span class="lbl">Tarifa por Noche</span>
          <span class="val">${formatCOP(d.nightly_rate)}</span>
        </div>
      </div>
      <div class="summary-divider" style="margin: 1.25rem 0;"></div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 600; font-size: 1.05rem;">Total Alojamiento:</span>
        <strong style="color: var(--primary); font-size: 1.3rem;">${formatCOP(d.total_lodging)}</strong>
      </div>
    `;
  } catch (err) {
    content.innerHTML = '<p style="color: red;">Error al obtener la información de la reserva.</p>';
  }
}

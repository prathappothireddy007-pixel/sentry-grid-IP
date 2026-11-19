/**
 * SentryGrid – Missing Persons Management Controller (missing_persons.js)
 * ======================================================================
 * Demonstrates: FormData file upload, Leaflet spatial mapping,
 * asynchronous filtering, privacy masking, and lifecycle workflow management.
 * CSA4310 – Internet Programming
 */

let mpMap = null;
let mpMarkers = [];
let searchTimeout = null;
let activeDossierId = null;

$(document).ready(function() {
    initMPMap();
    loadMissingPersons();
    loadMPStats();

    // Check if URL has ?id=X parameter
    const urlParams = new URLSearchParams(window.location.search);
    const targetId = urlParams.get('id');
    if (targetId) {
        setTimeout(() => viewCaseDossier(parseInt(targetId)), 600);
    }
});

// Initialize Leaflet Map
function initMPMap() {
    const mapEl = document.getElementById('mp-map');
    if (!mapEl) return;

    mpMap = L.map('mp-map').setView([13.0827, 80.2707], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(mpMap);
}

// Debounce Search
function debounceMPSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadMissingPersons();
    }, 400);
}

// Load Missing Person Records
function loadMissingPersons() {
    const q = $('#mp-search-input').val().trim();
    const status = $('#mp-status-filter').val();

    let query = [];
    if (q) query.push(`q=${encodeURIComponent(q)}`);
    if (status) query.push(`status=${encodeURIComponent(status)}`);

    $('#mp-cases-container').html(`
        <div class="text-center py-5 text-muted">
            <div class="spinner-sm mb-2"></div>
            <div>Retrieving missing person dossiers...</div>
        </div>
    `);

    $.ajax({
        url: `/api/missing-persons?${query.join('&')}`,
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            if (res.success) {
                renderMPCards(res.data);
                updateMPMapMarkers(res.data);
                $('#mp-count-label').text(`Showing ${res.data.length} of ${res.total} registered cases`);
            }
        },
        error: function(xhr) {
            $('#mp-cases-container').html(`
                <div class="alert alert-danger py-3">
                    Failed to load missing persons: ${(xhr.responseJSON && xhr.responseJSON.message) || 'Network error'}
                </div>
            `);
        }
    });
}

// Load KPI Stats
function loadMPStats() {
    $.ajax({
        url: '/api/missing-persons/stats',
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            if (res.success && res.data) {
                const s = res.data;
                $('#mp-stat-total').text(s.total || 0);
                $('#mp-stat-active').text(s.active_searches || 0);
                $('#mp-stat-located').text(s.located || 0);
                $('#mp-stat-review').text((s.by_status && s.by_status['Under Review']) || 0);
            }
        }
    });
}

// Render Case Cards
function renderMPCards(cases) {
    const container = document.getElementById('mp-cases-container');
    if (!container) return;

    if (!cases || cases.length === 0) {
        container.innerHTML = `
            <div class="card p-5 text-center text-muted">
                <i class="fa-solid fa-person-circle-check fs-1 text-success mb-3"></i>
                <h5>No Matching Missing Person Cases</h5>
                <p class="small text-muted m-0">No open incident reports match your current search and status filters.</p>
            </div>
        `;
        return;
    }

    let html = '';
    cases.forEach(c => {
        const statClass = getStatusBadgeClass(c.status);
        const photoHtml = c.photo_path
            ? `<img src="${escapeHtml(c.photo_path)}" class="rounded" style="width: 75px; height: 75px; object-fit: cover;">`
            : `<div class="rounded bg-secondary d-flex align-items-center justify-content-center text-muted" style="width: 75px; height: 75px;"><i class="fa-solid fa-user fs-4"></i></div>`;

        html += `
            <div class="card p-3 border-secondary" style="background: #16213e; transition: transform 0.2s ease;">
                <div class="d-flex flex-column flex-md-row justify-content-between align-items-start gap-3">
                    <div class="d-flex gap-3 align-items-center">
                        ${photoHtml}
                        <div>
                            <div class="d-flex align-items-center gap-2 mb-1">
                                <span class="badge ${statClass}">${escapeHtml(c.status)}</span>
                                <span class="badge badge-outline text-muted" style="font-size: 0.75rem;">${escapeHtml(c.case_number)}</span>
                            </div>
                            <h5 class="m-0 text-white">${escapeHtml(c.full_name)} <small class="text-muted fs-6">(${c.age ? c.age + ' yrs' : 'Age unknown'}, ${escapeHtml(c.gender || 'Unknown')})</small></h5>
                            <div class="small text-muted mt-1">
                                <i class="fa-solid fa-location-dot text-danger me-1"></i> ${escapeHtml(c.last_seen_location)}
                            </div>
                        </div>
                    </div>
                    <div class="d-flex flex-column align-items-md-end gap-1 w-100 w-md-auto">
                        <small class="text-muted"><i class="fa-regular fa-clock me-1"></i> ${escapeHtml(c.created_at)}</small>
                        <button class="btn btn-sm btn-outline text-warning mt-2" onclick="viewCaseDossier(${c.id})">
                            <i class="fa-solid fa-folder-open me-1"></i> View Case Dossier
                        </button>
                    </div>
                </div>
                <div class="border-top border-secondary pt-2 mt-2 text-muted small text-truncate">
                    ${escapeHtml(c.description || 'No physical description recorded.')}
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// Update Map Markers
function updateMPMapMarkers(cases) {
    if (!mpMap) return;
    mpMarkers.forEach(m => mpMap.removeLayer(m));
    mpMarkers = [];

    const bounds = [];
    let count = 0;

    cases.forEach(c => {
        if (c.latitude && c.longitude) {
            const marker = L.circleMarker([c.latitude, c.longitude], {
                radius: 8,
                fillColor: c.status === 'Located' ? '#27ae60' : '#e94560',
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.85
            }).addTo(mpMap);

            marker.bindPopup(`
                <div style="font-family: 'Segoe UI', sans-serif;">
                    <strong style="color: #e94560;">${escapeHtml(c.case_number)}</strong><br>
                    <strong>${escapeHtml(c.full_name)}</strong> (${c.age || '?'} yrs)<br>
                    <small>Status: <b>${escapeHtml(c.status)}</b></small><br>
                    <small>${escapeHtml(c.last_seen_location)}</small><br>
                    <button class="btn btn-sm btn-primary mt-2 py-0" style="font-size: 0.75rem;" onclick="viewCaseDossier(${c.id})">Open Case</button>
                </div>
            `);

            mpMarkers.push(marker);
            bounds.push([c.latitude, c.longitude]);
            count++;
        }
    });

    $('#mp-map-marker-count').text(`${count} pins`);
    if (bounds.length > 0) {
        mpMap.fitBounds(L.latLngBounds(bounds), { padding: [30, 30], maxZoom: 14 });
    }
}

// Helper: Badge Classes
function getStatusBadgeClass(status) {
    const map = {
        'Reported': 'badge-warning',
        'Under Review': 'badge-medium',
        'Search Active': 'badge-danger',
        'Located': 'badge-safe',
        'Closed': 'badge-outline',
        'Invalid/Duplicate': 'badge-outline text-muted'
    };
    return map[status] || 'badge-medium';
}

// Open Modal: File Case
function openCreateMissingPersonModal() {
    $('#modal-create-missing-person').addClass('active');
    // Pre-fill datetime
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    document.getElementById('mp-input-date').value = now.toISOString().slice(0, 16);
}

function closeCreateMissingPersonModal() {
    $('#modal-create-missing-person').removeClass('active');
}

// Capture GPS coordinates for form
function captureMPLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => {
                $('#mp-input-lat').val(pos.coords.latitude.toFixed(6));
                $('#mp-input-lon').val(pos.coords.longitude.toFixed(6));
                showToast('success', 'GPS coordinates captured from device.');
            },
            err => {
                showToast('warning', 'Location access unavailable. Please type location manually.');
            }
        );
    }
}

// Submit Create Case Form
function handleCreateMPSubmit(e) {
    e.preventDefault();
    const form = document.getElementById('form-create-missing-person');
    const formData = new FormData(form);
    const btn = $('#btn-submit-mp');

    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    $.ajax({
        url: '/api/missing-persons',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(res) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (res.success) {
                showToast('success', res.message, 'Case Broadcasted');
                form.reset();
                closeCreateMissingPersonModal();
                loadMissingPersons();
                loadMPStats();
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');
            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to file case.';
            showToast('error', err);
        }
    });
}

// View Case Dossier
function viewCaseDossier(caseId) {
    activeDossierId = caseId;
    showLoading('Loading case dossier...');

    $.ajax({
        url: `/api/missing-persons/${caseId}`,
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            hideLoading();
            if (res.success && res.data) {
                const c = res.data;
                $('#dossier-case-number').text(`Case Dossier: ${c.case_number}`);
                $('#dossier-name').text(c.full_name);
                $('#dossier-demographics').text(`Age: ${c.age || 'Unknown'} | Gender: ${c.gender || 'Unknown'} | Filed: ${c.created_at}`);
                $('#dossier-location').text(c.last_seen_location);
                $('#dossier-time').text(c.last_seen_date || 'Unknown');
                $('#dossier-description').text(c.description || 'No detailed characteristics provided.');
                $('#dossier-status-badge').text(c.status).removeClass().addClass(`badge ${getStatusBadgeClass(c.status)}`);

                $('#dossier-contact').text(c.contact_name || 'Authorized Relative');
                $('#dossier-phone').text(c.contact_phone || 'Protected Contact');

                const photoEl = document.getElementById('dossier-photo-container');
                if (c.photo_path) {
                    photoEl.innerHTML = `<img src="${escapeHtml(c.photo_path)}" class="img-fluid rounded" style="max-height: 220px;">`;
                } else {
                    photoEl.innerHTML = `<i class="fa-solid fa-user text-muted fs-1"></i>`;
                }

                if ($('#update-case-status-select').length) {
                    $('#update-case-status-select').val(c.status);
                }

                $('#modal-view-missing-person').addClass('active');
            }
        },
        error: function(xhr) {
            hideLoading();
            showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to fetch case details.');
        }
    });
}

function closeViewMissingPersonModal() {
    $('#modal-view-missing-person').removeClass('active');
}

// Update Case Status (Admin/Responder)
function submitCaseStatusUpdate() {
    if (!activeDossierId) return;
    const status = $('#update-case-status-select').val();
    const notes = $('#update-case-notes').val().trim();

    $.ajax({
        url: `/api/missing-persons/${activeDossierId}/status`,
        type: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({ status: status, notes: notes }),
        success: function(res) {
            if (res.success) {
                showToast('success', res.message, 'Status Updated');
                viewCaseDossier(activeDossierId);
                loadMissingPersons();
                loadMPStats();
            }
        },
        error: function(xhr) {
            showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'Status update denied.');
        }
    });
}

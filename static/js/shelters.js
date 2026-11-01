/**
 * SentryGrid – Module 3: Shelters & Reports (shelters.js)
 * ========================================================
 * Demonstrates: Geolocation API proximity distance calculation,
 * Leaflet map plotting, shelter capacity visualization,
 * situation reporting (SITREPs), and CSV analytical data exports.
 * CSA4310 – Internet Programming
 */

let shelterMap = null;
let shelterMarkers = [];
let userLocationMarker = null;
let currentUserLat = (APP_CONFIG && APP_CONFIG.currentUserLat) ? APP_CONFIG.currentUserLat : 13.0827;
let currentUserLon = (APP_CONFIG && APP_CONFIG.currentUserLon) ? APP_CONFIG.currentUserLon : 80.2707;

$(document).ready(function() {
    initShelterMap();
    loadShelters();
    loadDisasterReports();
});

// Initialize Leaflet Map for Shelters
function initShelterMap() {
    const mapElem = document.getElementById('map-shelters');
    if (!mapElem) return;

    shelterMap = L.map('map-shelters').setView([currentUserLat, currentUserLon], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(shelterMap);
}

// Locate User via Browser Geolocation API and sort shelters nearest-first
function locateUserAndSortShelters() {
    if (!navigator.geolocation) {
        showToast('error', 'Browser does not support Geolocation API.');
        return;
    }

    showLoading('Acquiring precise GPS location...');

    navigator.geolocation.getCurrentPosition(
        function(pos) {
            hideLoading();
            currentUserLat = pos.coords.latitude;
            currentUserLon = pos.coords.longitude;

            $('#shelter-gps-indicator').html(`<span class="text-success"><i class="fa-solid fa-location-crosshairs me-1"></i>Sorted by distance to your GPS (${currentUserLat.toFixed(4)}, ${currentUserLon.toFixed(4)})</span>`);

            if (userLocationMarker && shelterMap) {
                shelterMap.removeLayer(userLocationMarker);
            }

            if (shelterMap) {
                userLocationMarker = L.marker([currentUserLat, currentUserLon], {
                    title: 'Your Current Position'
                }).addTo(shelterMap);
                userLocationMarker.bindPopup('<b>Your Current Location</b>').openPopup();
            }

            showToast('success', 'GPS locked! Shelters re-sorted by nearest distance.', 'Proximity Updated');
            loadShelters();
        },
        function(err) {
            hideLoading();
            showToast('warning', `GPS query failed: ${err.message}. Using default locality coordinates.`);
            loadShelters();
        },
        { enableHighAccuracy: true, timeout: 8000 }
    );
}

// Load Shelters from Flask API (Nearest First via Haversine)
function loadShelters() {
    const url = `/api/shelters?lat=${currentUserLat}&lon=${currentUserLon}&active=true`;

    $.ajax({
        url: url,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderSheltersCards(response.data);
                updateShelterMapMarkers(response.data);
            }
        },
        error: function(xhr) {
            $('#shelters-cards-container').html(`
                <div class="col-12 text-center py-4 text-danger">
                    Failed to fetch shelter locations: ${(xhr.responseJSON && xhr.responseJSON.message) || 'Server error'}
                </div>
            `);
        }
    });
}

// Render Shelter Cards with Progress Bars & Facilities
function renderSheltersCards(shelters) {
    const container = document.getElementById('shelters-cards-container');
    if (!container) return;

    if (!shelters || shelters.length === 0) {
        container.innerHTML = `
            <div class="col-12 text-center py-4 text-muted">
                <i class="fa-solid fa-house-circle-xmark fs-2 text-warning mb-2 d-block"></i>
                No active disaster shelters found in database.
            </div>
        `;
        return;
    }

    let html = '';
    shelters.forEach(s => {
        const occPct = Math.round((s.current_occupancy / s.total_capacity) * 100);
        const availBeds = s.available_capacity;
        const distKm = s.distance_km !== null ? `${s.distance_km} km away` : 'Distance unavailable';

        // Google Maps & OSM navigation directions link (Requirement 8.B)
        const gmapsLink = `https://www.google.com/maps/dir/?api=1&destination=${s.latitude},${s.longitude}`;

        let facilitiesHtml = '';
        if (s.facilities && s.facilities.length > 0) {
            s.facilities.forEach(f => {
                facilitiesHtml += `<span class="badge badge-medium me-1 mb-1" style="font-size: 0.7rem;"><i class="fa-solid fa-check me-1 text-success"></i>${escapeHtml(f.facility_name)}</span>`;
            });
        } else {
            facilitiesHtml = '<span class="text-muted small">Standard emergency rations & bedding</span>';
        }

        html += `
            <div class="col-12 col-md-6 col-lg-4">
                <div class="card h-100 p-3" style="border-top: 3px solid #27ae60;">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h4 class="fs-6 m-0 text-light"><strong>${escapeHtml(s.name)}</strong></h4>
                        <span class="badge badge-safe"><i class="fa-solid fa-person-walking-arrow-right me-1"></i>${escapeHtml(distKm)}</span>
                    </div>

                    <p class="text-muted small mb-2"><i class="fa-solid fa-location-dot me-1 text-danger"></i>${escapeHtml(s.address)}</p>

                    <!-- Capacity Gauge -->
                    <div class="mb-3">
                        <div class="d-flex justify-content-between small text-secondary mb-1">
                            <span>Occupancy: <strong>${s.current_occupancy} / ${s.total_capacity}</strong></span>
                            <span class="${availBeds > 20 ? 'text-success' : 'text-danger'} font-weight-bold">${availBeds} Beds Free</span>
                        </div>
                        <div class="progress" style="height: 8px; background: #0f1629;">
                            <div class="progress-bar ${occPct > 85 ? 'bg-danger' : (occPct > 60 ? 'bg-warning' : 'bg-success')}" 
                                 role="progressbar" style="width: ${occPct}%;" aria-valuenow="${occPct}" aria-valuemin="0" aria-valuemax="100"></div>
                        </div>
                    </div>

                    <!-- Available Facilities Badges -->
                    <div class="mb-3">
                        <small class="text-muted d-block mb-1">Available Facilities:</small>
                        <div class="d-flex flex-wrap">${facilitiesHtml}</div>
                    </div>

                    <!-- Action Links -->
                    <div class="mt-auto pt-2 border-top border-secondary d-flex justify-content-between align-items-center">
                        <small class="text-muted"><i class="fa-solid fa-phone me-1"></i>${escapeHtml(s.contact_phone || 'Emergency Desk')}</small>
                        <a href="${gmapsLink}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline text-info">
                            <i class="fa-solid fa-diamond-turn-right me-1"></i> Get Directions
                        </a>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Plot Shelters on Leaflet Map
function updateShelterMapMarkers(shelters) {
    if (!shelterMap) return;

    shelterMarkers.forEach(m => shelterMap.removeLayer(m));
    shelterMarkers = [];

    const latLngs = [];

    shelters.forEach(s => {
        if (s.latitude && s.longitude) {
            const marker = L.circleMarker([s.latitude, s.longitude], {
                radius: 10,
                fillColor: '#27ae60',
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            }).addTo(shelterMap);

            const gmapsLink = `https://www.google.com/maps/dir/?api=1&destination=${s.latitude},${s.longitude}`;

            marker.bindPopup(`
                <div style="font-family: 'Segoe UI', sans-serif;">
                    <strong style="color: #27ae60; font-size: 1rem;"><i class="fa-solid fa-house-shield"></i> ${escapeHtml(s.name)}</strong><br>
                    <small>${escapeHtml(s.address)}</small><br>
                    <div class="mt-1">
                        <b>Available Capacity:</b> ${s.available_capacity} / ${s.total_capacity} beds<br>
                        <b>Contact:</b> ${escapeHtml(s.contact_phone || 'N/A')}
                    </div>
                    <div class="mt-2">
                        <a href="${gmapsLink}" target="_blank" class="btn btn-sm btn-primary py-0" style="font-size: 0.75rem;">Google Maps Route</a>
                    </div>
                </div>
            `);

            shelterMarkers.push(marker);
            latLngs.push([s.latitude, s.longitude]);
        }
    });

    $('#shelters-map-count').text(`${shelters.length} safe havens online`);

    if (latLngs.length > 0) {
        shelterMap.fitBounds(L.latLngBounds(latLngs), { padding: [40, 40], maxZoom: 13 });
    }
}

// Load Disaster Reports & SITREPs (Requirement 8.D)
function loadDisasterReports() {
    $.ajax({
        url: '/api/reports',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderDisasterReportsTable(response.data);
            }
        }
    });

    // Also load summary metrics for report cards
    $.ajax({
        url: '/api/reports/summary',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                const d = response.data;
                $('#report-total-requests').text(d.requests.total);
                $('#report-resolved-requests').text(d.requests.resolved);
                $('#report-pending-requests').text(d.requests.pending);
                $('#report-available-beds').text(d.shelters.available);
            }
        }
    });
}

function renderDisasterReportsTable(reports) {
    const tbody = document.getElementById('disaster-reports-tbody');
    if (!tbody) return;

    if (!reports || reports.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-4 text-muted">
                    No SITREP disaster reports compiled yet.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    reports.forEach(r => {
        html += `
            <tr>
                <td><strong>${escapeHtml(r.title)}</strong></td>
                <td><span class="badge badge-medium">${escapeHtml(r.report_type.toUpperCase())}</span></td>
                <td>${escapeHtml(r.disaster_type || 'General Hazard')}</td>
                <td>${escapeHtml(r.affected_location || 'Various Sectors')}</td>
                <td class="${r.missing_persons > 0 ? 'text-warning font-weight-bold' : ''}">${r.missing_persons}</td>
                <td class="${r.casualties > 0 ? 'text-danger font-weight-bold' : ''}">${r.casualties}</td>
                <td>${escapeHtml(r.generated_by_name || 'System')}</td>
                <td class="small text-muted">${escapeHtml(r.created_at)}</td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// Modal Handlers: Register Shelter (Admin Only)
function openCreateShelterModal() {
    $('#modal-create-shelter').addClass('active');
}

function closeCreateShelterModal() {
    $('#modal-create-shelter').removeClass('active');
}

function handleCreateShelterSubmit(e) {
    e.preventDefault();

    const name = $('#sh-name').val().trim();
    const address = $('#sh-address').val().trim();
    const lat = $('#sh-lat').val();
    const lon = $('#sh-lon').val();
    const capacity = $('#sh-capacity').val();
    const occupancy = $('#sh-occupancy').val() || 0;
    const phone = $('#sh-phone').val().trim();
    const email = $('#sh-email').val().trim();
    const facilitiesRaw = $('#sh-facilities').val().trim();

    const facilities = facilitiesRaw ? facilitiesRaw.split(',').map(f => f.trim()).filter(f => f.length > 0) : [];

    const btn = $('#btn-submit-shelter');
    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    $.ajax({
        url: '/api/shelters',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            name: name,
            address: address,
            latitude: parseFloat(lat),
            longitude: parseFloat(lon),
            total_capacity: parseInt(capacity),
            current_occupancy: parseInt(occupancy),
            contact_phone: phone,
            contact_email: email,
            facilities: facilities
        }),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', 'Relief shelter registered successfully!', 'Shelter Active');
                closeCreateShelterModal();
                $('#form-create-shelter')[0].reset();
                loadShelters();
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to create shelter.';
            showToast('error', err);
        }
    });
}

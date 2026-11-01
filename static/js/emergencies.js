/**
 * SentryGrid – Module 2: Emergency Reporting & Rescue Coordination (emergencies.js)
 * =================================================================================
 * Demonstrates: Geolocation API, FormData file uploads, Leaflet incident maps,
 * Reported → Verified → Dispatched → Rescued → Closed state workflow,
 * response team assignment, and 5-second asynchronous message polling.
 * CSA4310 – Internet Programming
 */

let incidentMap = null;
let incidentMarkers = [];
let activeIncidentId = null;
let chatPollingInterval = null;
let lastChatTimestamp = null;
let searchReqTimeout = null;

$(document).ready(function() {
    initIncidentMap();
    loadEmergencies();

    // Check if URL has ?id=X parameter to automatically open detail modal
    const urlParams = new URLSearchParams(window.location.search);
    const targetId = urlParams.get('id');
    if (targetId) {
        setTimeout(() => {
            viewRequestDetail(parseInt(targetId));
        }, 800);
    }

    // Configurable polling for emergency incidents
    const pollTime = (APP_CONFIG && APP_CONFIG.pollIntervalRequests) ? APP_CONFIG.pollIntervalRequests : 15000;
    setInterval(function() {
        loadEmergencies(false);
    }, pollTime);
});

// Initialize Leaflet Map
function initIncidentMap() {
    const mapElem = document.getElementById('map');
    if (!mapElem) return;

    // Center map initially around default coordinates (Chennai) or user coordinates
    const initialLat = (APP_CONFIG && APP_CONFIG.currentUserLat) ? APP_CONFIG.currentUserLat : 13.0827;
    const initialLon = (APP_CONFIG && APP_CONFIG.currentUserLon) ? APP_CONFIG.currentUserLon : 80.2707;

    incidentMap = L.map('map').setView([initialLat, initialLon], 11);

    // OpenStreetMap Tile Layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
    }).addTo(incidentMap);
}

// Debounce search
function debounceRequestSearch() {
    clearTimeout(searchReqTimeout);
    searchReqTimeout = setTimeout(() => {
        loadEmergencies();
    }, 400);
}

// Load Emergencies from API
function loadEmergencies(showLoader = true) {
    const status = $('#filter-req-status').val();
    const type = $('#filter-req-type').val();
    const priority = $('#filter-req-priority').val();
    const search = $('#filter-req-search').val().trim();

    let query = [];
    if (status) query.push(`status=${encodeURIComponent(status)}`);
    if (type) query.push(`type=${encodeURIComponent(type)}`);
    if (priority) query.push(`priority=${encodeURIComponent(priority)}`);
    if (search) query.push(`search=${encodeURIComponent(search)}`);

    if (showLoader) {
        $('#emergencies-table-body').html(`
            <tr>
                <td colspan="9" class="text-center py-4 text-muted">
                    <div class="spinner-sm mb-2"></div>
                    <div>Loading incident data...</div>
                </td>
            </tr>
        `);
    }

    $.ajax({
        url: `/api/requests?${query.join('&')}`,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderEmergenciesTable(response.data);
                updateMapMarkers(response.data);

                // Update counter and badge
                const total = response.total || 0;
                $('#total-requests-counter').text(`${total} total incidents`);
                const badge = $('#sidebar-emergency-badge');
                if (total > 0) {
                    badge.text(total).removeClass('d-none');
                } else {
                    badge.addClass('d-none');
                }
            }
        },
        error: function(xhr) {
            $('#emergencies-table-body').html(`
                <tr>
                    <td colspan="9" class="text-center py-4 text-danger">
                        Failed to fetch incidents: ${(xhr.responseJSON && xhr.responseJSON.message) || 'Network error'}
                    </td>
                </tr>
            `);
        }
    });
}

// Render Table Rows
function renderEmergenciesTable(items) {
    const tbody = document.getElementById('emergencies-table-body');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-5 text-muted">
                    <i class="fa-solid fa-circle-check fs-2 text-success mb-2 d-block"></i>
                    No emergency requests match your current filters.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    items.forEach(r => {
        const prioClass = (r.priority || 'medium').toLowerCase();
        const statClass = (r.status || 'reported').toLowerCase();
        const typeLabel = r.emergency_type.replace('_', ' ').toUpperCase();

        html += `
            <tr>
                <td><strong>#${r.id}</strong></td>
                <td>
                    <span class="badge badge-medium">${escapeHtml(typeLabel)}</span>
                    ${r.is_sos ? '<span class="badge badge-critical ms-1"><i class="fa-solid fa-tower-broadcast"></i> SOS</span>' : ''}
                </td>
                <td>
                    <div><strong>${escapeHtml(r.citizen_name)}</strong></div>
                    <div class="text-muted small"><i class="fa-solid fa-phone me-1"></i>${escapeHtml(r.contact_number)}</div>
                </td>
                <td>${escapeHtml(r.location || 'Coordinates only')}</td>
                <td>
                    ${r.assigned_teams ? `
                        <span class="badge badge-dispatched"><i class="fa-solid fa-truck-medical me-1"></i>${escapeHtml(r.assigned_teams)}</span>
                    ` : '<span class="text-muted small">Unassigned</span>'}
                </td>
                <td><span class="badge badge-${prioClass}">${escapeHtml(r.priority)}</span></td>
                <td><span class="badge badge-${statClass}">${escapeHtml(r.status)}</span></td>
                <td class="small text-muted">${escapeHtml(r.created_at)}</td>
                <td>
                    <button class="btn btn-sm btn-outline" onclick="viewRequestDetail(${r.id})">
                        <i class="fa-solid fa-eye me-1"></i> View & Act
                    </button>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// Update Markers on Leaflet Map
function updateMapMarkers(items) {
    if (!incidentMap) return;

    // Clear old markers
    incidentMarkers.forEach(m => incidentMap.removeLayer(m));
    incidentMarkers = [];

    let count = 0;
    const latLngs = [];

    items.forEach(r => {
        if (r.latitude && r.longitude) {
            count++;
            const marker = L.circleMarker([r.latitude, r.longitude], {
                radius: r.is_sos ? 12 : 8,
                fillColor: r.is_sos ? '#e94560' : (r.status === 'Rescued' ? '#27ae60' : '#f39c12'),
                color: '#fff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(incidentMap);

            marker.bindPopup(`
                <div style="font-family: 'Segoe UI', sans-serif;">
                    <strong style="color: #e94560;">#${r.id} ${escapeHtml(r.emergency_type.toUpperCase())}</strong><br>
                    <strong>${escapeHtml(r.citizen_name)}</strong> (${escapeHtml(r.contact_number)})<br>
                    <small>Status: <b>${escapeHtml(r.status)}</b></small><br>
                    <small>${escapeHtml(r.location || 'Lat/Lon GPS')}</small><br>
                    <button onclick="viewRequestDetail(${r.id})" class="btn btn-sm btn-primary mt-2 py-0" style="font-size: 0.75rem;">View Console</button>
                </div>
            `);

            incidentMarkers.push(marker);
            latLngs.push([r.latitude, r.longitude]);
        }
    });

    $('#map-incident-count').text(`${count} GPS markers active`);

    if (latLngs.length > 0) {
        incidentMap.fitBounds(L.latLngBounds(latLngs), { padding: [30, 30], maxZoom: 14 });
    }
}

// Immediate One-Touch SOS Dispatch (Requirement 7.B)
function triggerImmediateSOS() {
    if (!confirm('CONFIRM INSTANT SOS:\nThis will broadcast an emergency dispatch beacon with your current coordinates. Proceed?')) {
        return;
    }

    const feedback = $('#sos-gps-feedback');
    feedback.html('<span class="text-danger"><i class="fa-solid fa-spinner fa-spin me-1"></i>Capturing GPS satellite fix...</span>');

    function sendSOS(lat, lon) {
        $.ajax({
            url: '/api/requests',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                citizen_name: APP_CONFIG.currentUserName || 'Citizen SOS Beacon',
                contact_number: 'Emergency SOS Broadcast',
                emergency_type: 'other',
                priority: 'Critical',
                is_sos: true,
                latitude: lat,
                longitude: lon,
                location: `GPS: ${lat || 'Unknown'}, ${lon || 'Unknown'}`,
                description: 'SOS DISTRESS BEACON: Citizen reported life-critical disaster emergency requiring rescue dispatch.'
            }),
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    feedback.html('<span class="text-success"><i class="fa-solid fa-check me-1"></i>SOS beacon active & dispatched!</span>');
                    showToast('success', response.message, 'SOS TRANSMITTED');
                    loadEmergencies();
                }
            },
            error: function(xhr) {
                feedback.html('<span class="text-danger">SOS transmission error</span>');
                showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'SOS failed.');
            }
        });
    }

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(pos) {
                sendSOS(pos.coords.latitude, pos.coords.longitude);
            },
            function() {
                // If location access denied, submit without GPS as required
                sendSOS(null, null);
            },
            { enableHighAccuracy: true, timeout: 6000 }
        );
    } else {
        sendSOS(null, null);
    }
}

// Modal Handlers: Detailed Emergency Report
function openNewRequestModal() {
    $('#modal-new-emergency').addClass('active');
}

function closeNewRequestModal() {
    $('#modal-new-emergency').removeClass('active');
}

// GPS detection inside the emergency modal form
function captureEmergencyFormGPS() {
    const statusElem = $('#em-gps-status');
    statusElem.html('<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i>Triangulating browser GPS...</span>');

    if (!navigator.geolocation) {
        statusElem.html('<span class="text-danger">Geolocation API unsupported in this browser</span>');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        function(pos) {
            const lat = pos.coords.latitude.toFixed(6);
            const lon = pos.coords.longitude.toFixed(6);
            $('#em-lat').val(lat);
            $('#em-lon').val(lon);
            statusElem.html(`<span class="text-success"><i class="fa-solid fa-circle-check me-1"></i>Coordinates locked: ${lat}, ${lon}</span>`);
            showToast('success', 'GPS coordinates populated in form.');
        },
        function(err) {
            statusElem.html(`<span class="text-warning">GPS permission denied (${err.message}). Enter location text manually.</span>`);
        },
        { enableHighAccuracy: true, timeout: 8000 }
    );
}

// Form Submission with FormData (Supports Photo Upload)
function handleEmergencySubmit(e) {
    e.preventDefault();

    const form = document.getElementById('form-emergency-report');
    const formData = new FormData();

    formData.append('citizen_name', $('#em-citizen-name').val().trim());
    formData.append('contact_number', $('#em-contact-number').val().trim());
    formData.append('emergency_type', $('#em-type').val());
    formData.append('priority', $('#em-priority').val());
    formData.append('location', $('#em-location').val().trim());
    formData.append('latitude', $('#em-lat').val());
    formData.append('longitude', $('#em-lon').val());
    formData.append('description', $('#em-description').val().trim());
    formData.append('is_sos', false);

    const imageFile = document.getElementById('em-image').files[0];
    if (imageFile) {
        formData.append('image', imageFile);
    }

    const btn = $('#btn-submit-emergency');
    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    // Demonstrates FormData and AJAX file submission
    $.ajax({
        url: '/api/requests',
        type: 'POST',
        data: formData,
        processData: false, // Required for FormData
        contentType: false, // Required for FormData
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', response.message, 'Emergency Logged');
                closeNewRequestModal();
                form.reset();
                loadEmergencies();
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Submission failed.';
            showToast('error', err);
        }
    });
}

// View Request Detail & Workflow Console
function viewRequestDetail(requestId) {
    activeIncidentId = requestId;
    lastChatTimestamp = null;

    showLoading('Loading incident console...');

    $.ajax({
        url: `/api/requests/${requestId}`,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            hideLoading();
            if (response.success) {
                const req = response.data;
                renderDetailModal(req);
                $('#modal-request-detail').addClass('active');

                // Start polling messages for this incident
                loadChatMessages(true);
                clearInterval(chatPollingInterval);
                chatPollingInterval = setInterval(() => {
                    loadChatMessages(false);
                }, (APP_CONFIG && APP_CONFIG.pollIntervalMessages) ? APP_CONFIG.pollIntervalMessages : 5000);
            }
        },
        error: function(xhr) {
            hideLoading();
            showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to load details.');
        }
    });
}

function renderDetailModal(req) {
    $('#detail-modal-id').text(`#${req.id}`);
    $('#detail-type-badge').text(req.emergency_type.replace('_', ' ').toUpperCase());
    $('#detail-priority-badge').text(req.priority).removeClass().addClass(`badge badge-${(req.priority || 'medium').toLowerCase()}`);
    $('#detail-status-badge').text(req.status).removeClass().addClass(`badge badge-${(req.status || 'reported').toLowerCase()}`);
    $('#detail-time-text').text(`Filed: ${req.created_at}`);
    $('#detail-citizen-header').text(req.citizen_name);
    $('#detail-phone-text').text(req.contact_number);
    $('#detail-location-text').text(req.location || `GPS (${req.latitude}, ${req.longitude})`);
    $('#detail-desc-text').text(req.description);

    // Image preview if uploaded
    if (req.image_path) {
        $('#detail-image-preview').attr('src', '/' + req.image_path.replace(/\\/g, '/'));
        $('#detail-image-container').removeClass('d-none');
    } else {
        $('#detail-image-container').addClass('d-none');
    }

    // Highlight Status Pipeline Step
    const steps = ['Reported', 'Verified', 'Dispatched', 'Rescued', 'Closed'];
    const currentIdx = steps.indexOf(req.status);

    steps.forEach((s, idx) => {
        const elem = $(`#step-${s.toLowerCase()}`);
        if (idx <= currentIdx) {
            elem.find('.badge').css('opacity', '1').css('border', '2px solid #27ae60');
        } else {
            elem.find('.badge').css('opacity', '0.4').css('border', 'none');
        }
    });

    // Control status action buttons availability
    $('#btn-advance-verify').prop('disabled', req.status !== 'Reported');
    $('#btn-advance-dispatch').prop('disabled', req.status !== 'Verified');
    $('#btn-advance-rescue').prop('disabled', req.status !== 'Dispatched');
    $('#btn-advance-close').prop('disabled', req.status !== 'Rescued');
}

function closeRequestDetailModal() {
    $('#modal-request-detail').removeClass('active');
    activeIncidentId = null;
    clearInterval(chatPollingInterval);
}

// Advance Incident Workflow Status
function advanceStatus(newStatus) {
    if (!activeIncidentId) return;

    if (!confirm(`Confirm workflow transition to '${newStatus}'?`)) return;

    showLoading(`Updating status to ${newStatus}...`);

    $.ajax({
        url: `/api/requests/${activeIncidentId}/status`,
        type: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({
            status: newStatus,
            notes: `Status changed to ${newStatus} by ${APP_CONFIG.currentUserName} (${APP_CONFIG.currentUserRole})`
        }),
        dataType: 'json',
        success: function(response) {
            hideLoading();
            if (response.success) {
                showToast('success', response.message, 'Workflow Advanced');
                viewRequestDetail(activeIncidentId);
                loadEmergencies(false);
            }
        },
        error: function(xhr) {
            hideLoading();
            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Status transition denied.';
            showToast('error', err);
        }
    });
}

// Team Assignment Modal
function openAssignTeamModal() {
    $('#modal-assign-team').addClass('active');

    // Load available teams via AJAX
    $.ajax({
        url: '/api/teams?status=available',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                const select = $('#assign-team-select');
                select.empty();

                if (!response.data || response.data.length === 0) {
                    select.append('<option value="">No teams currently available</option>');
                    return;
                }

                select.append('<option value="">-- Choose Unit --</option>');
                response.data.forEach(t => {
                    select.append(`<option value="${t.id}">${escapeHtml(t.team_name)} (${escapeHtml(t.team_category.toUpperCase())})</option>`);
                });
            }
        }
    });
}

function closeAssignTeamModal() {
    $('#modal-assign-team').removeClass('active');
}

function handleAssignTeamSubmit(e) {
    e.preventDefault();
    const teamId = $('#assign-team-select').val();
    const notes = $('#assign-notes').val().trim();

    if (!teamId) {
        showToast('error', 'Please select a response team.');
        return;
    }

    const btn = $('#btn-submit-assign');
    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    $.ajax({
        url: `/api/requests/${activeIncidentId}/assign`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            team_id: teamId,
            notes: notes
        }),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', response.message, 'Unit Deployed');
                closeAssignTeamModal();
                viewRequestDetail(activeIncidentId);
                loadEmergencies(false);
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Assignment failed.';
            showToast('error', err);
        }
    });
}

// Two-Way Incident Communication Messaging (AJAX Polling System)
function loadChatMessages(initialLoad = false) {
    if (!activeIncidentId) return;

    let url = `/api/requests/${activeIncidentId}/messages`;
    if (!initialLoad && lastChatTimestamp) {
        url += `?after=${encodeURIComponent(lastChatTimestamp)}`;
    }

    $.ajax({
        url: url,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success && response.data) {
                renderChatMessages(response.data, initialLoad);
            }
        }
    });
}

function renderChatMessages(messages, isInitial) {
    const box = document.getElementById('chat-messages-box');
    if (!box) return;

    if (isInitial && (!messages || messages.length === 0)) {
        box.innerHTML = `
            <div class="empty-state py-3">
                <i class="fa-regular fa-comment-dots fs-3 mb-2"></i>
                <p>No messages yet. Send instructions or queries below.</p>
            </div>
        `;
        return;
    }

    if (isInitial) {
        box.innerHTML = '';
    }

    messages.forEach(m => {
        // If initial empty state is present, clear it
        if (box.querySelector('.empty-state')) {
            box.innerHTML = '';
        }

        const isMe = (m.sender_id === APP_CONFIG.currentUserId);
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${isMe ? 'sent' : 'received'}`;
        msgDiv.innerHTML = `
            <div class="chat-sender">${escapeHtml(m.sender_name)} (${escapeHtml(m.sender_role)})</div>
            <div class="chat-bubble">${escapeHtml(m.message)}</div>
            <div class="chat-time">${escapeHtml(m.created_at)}</div>
        `;
        box.appendChild(msgDiv);
        lastChatTimestamp = m.created_at;
    });

    if (messages.length > 0) {
        box.scrollTop = box.scrollHeight;
    }
}

function handleSendChatMessage(e) {
    e.preventDefault();
    const input = $('#chat-input-text');
    const msg = input.val().trim();

    if (!msg || !activeIncidentId) return;

    $.ajax({
        url: `/api/requests/${activeIncidentId}/messages`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ message: msg }),
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                input.val('');
                loadChatMessages(false);
            }
        },
        error: function(xhr) {
            showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'Message failed to send.');
        }
    });
}

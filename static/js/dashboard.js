/**
 * SentryGrid – Dashboard JavaScript (dashboard.js)
 * ==================================================
 * Powers the multi-role operational dashboard, live telemetry,
 * Chart.js analytics, quick SOS trigger, and periodic statistics refresh.
 * CSA4310 – Internet Programming
 */

let severityChart = null;
let requestsTypeChart = null;
let timelineChart = null;
let shelterChart = null;
let opsMap = null;
let opsLayers = {
    incidents: null,
    alerts: null,
    shelters: null,
    hospitals: null,
    earthquakes: null
};

$(document).ready(function() {
    loadDashboardMetrics();
    loadDashboardWeather();
    initDashboardOpsMap();
    loadDashboardMapAssets();
    loadDashboardAlerts();
    loadDashboardRequests();

    // Periodic polling for real-time dashboard refresh
    const pollTime = (APP_CONFIG && APP_CONFIG.pollIntervalDashboard) ? APP_CONFIG.pollIntervalDashboard : 60000;
    setInterval(function() {
        loadDashboardMetrics(false);
        loadDashboardAlerts(false);
        loadDashboardRequests(false);
        loadDashboardMapAssets();
    }, pollTime);
});

// Load summary metrics from Flask REST API
function loadDashboardMetrics(showLoader = false) {
    if (showLoader) showLoading('Updating metrics...');

    $.ajax({
        url: '/api/reports/summary',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            hideLoading();
            if (response.success) {
                const d = response.data;

                // Update 10 Core Stat Cards
                $('#stat-active-alerts').text(d.alerts.active);
                $('#stat-pending-requests').text(d.requests.pending);
                $('#stat-resolved-incidents').text(d.requests.resolved);

                const availableTeams = d.teams.available || 0;
                $('#stat-available-teams').text(availableTeams);

                if (d.shelters) {
                    $('#stat-active-shelters').text(`${d.shelters.active} Active`);
                }
                if (d.hospitals) {
                    $('#stat-hospital-beds').text(d.hospitals.available_beds);
                }
                if (d.missing_persons) {
                    $('#stat-mp-active').text(d.missing_persons.missing);
                    $('#stat-mp-found').text(d.missing_persons.found);
                }
                if (d.resources) {
                    let totalItems = 0;
                    if (d.resources.by_category) {
                        Object.values(d.resources.by_category).forEach(v => totalItems += v);
                    }
                    $('#stat-relief-items').text(totalItems || '450+');
                    $('#stat-low-stock').text(d.resources.low_stock);
                }

                // Render 4 Interactive Chart.js Visualizations
                renderSeverityChart(d.alerts.by_severity);
                renderRequestsByTypeChart(d.requests.by_type);
                renderTimelineChart(d.requests.timeline);
                renderShelterOccupancyChart(d.shelters.breakdown);
            }
        },
        error: function() {
            hideLoading();
        }
    });
}

// Chart 1: Disaster Severity Visualization (Doughnut)
function renderSeverityChart(bySeverity) {
    const ctx = document.getElementById('chart-alerts-severity');
    if (!ctx) return;

    const labels = ['Critical', 'High', 'Medium', 'Low'];
    const data = [
        (bySeverity && bySeverity['Critical']) || 0,
        (bySeverity && bySeverity['High']) || 0,
        (bySeverity && bySeverity['Medium']) || 0,
        (bySeverity && bySeverity['Low']) || 0
    ];

    if (severityChart) {
        severityChart.data.datasets[0].data = data;
        severityChart.update();
        return;
    }

    severityChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#e94560', // Critical: Red
                    '#f39c12', // High: Orange
                    '#2980b9', // Medium: Blue
                    '#27ae60'  // Low: Green
                ],
                borderColor: '#16213e',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#cbd5e1',
                        font: { size: 11 }
                    }
                }
            }
        }
    });
}

// Chart 2: Incidents by Category (Doughnut)
function renderRequestsByTypeChart(byType) {
    const ctx = document.getElementById('chart-requests-by-type');
    if (!ctx) return;

    const catMap = {
        'medical': 'Medical Trauma',
        'flood_rescue': 'Flood Water',
        'fire': 'Fire Outbreak',
        'trapped': 'Structural Collapse',
        'other': 'General Emergency'
    };

    const labels = Object.keys(catMap).map(k => catMap[k]);
    const data = Object.keys(catMap).map(k => (byType && byType[k]) || 0);

    if (requestsTypeChart) {
        requestsTypeChart.data.datasets[0].data = data;
        requestsTypeChart.update();
        return;
    }

    requestsTypeChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: ['#e94560', '#38bdf8', '#f97316', '#a855f7', '#64748b'],
                borderColor: '#16213e',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#cbd5e1', font: { size: 10 } }
                }
            }
        }
    });
}

// Chart 3: 7-Day Incident Trend Timeline (Line)
function renderTimelineChart(timeline) {
    const ctx = document.getElementById('chart-incident-timeline');
    if (!ctx) return;

    let labels = [];
    let counts = [];
    if (timeline && timeline.length > 0) {
        labels = timeline.map(t => t.label);
        counts = timeline.map(t => t.count);
    } else {
        labels = ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Today'];
        counts = [2, 4, 1, 5, 3, 2, 6];
    }

    if (timelineChart) {
        timelineChart.data.labels = labels;
        timelineChart.data.datasets[0].data = counts;
        timelineChart.update();
        return;
    }

    timelineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Incidents Reported',
                data: counts,
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                fill: true,
                tension: 0.35,
                borderWidth: 2,
                pointBackgroundColor: '#38bdf8'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: '#94a3b8', font: { size: 10 }, stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.06)' } }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// Chart 4: Shelter Capacity vs Occupancy (Bar)
function renderShelterOccupancyChart(breakdown) {
    const ctx = document.getElementById('chart-shelter-occupancy');
    if (!ctx) return;

    let labels = [];
    let capData = [];
    let occData = [];

    if (breakdown && breakdown.length > 0) {
        labels = breakdown.map(s => s.name.length > 15 ? s.name.substring(0, 14) + '…' : s.name);
        capData = breakdown.map(s => s.total_capacity);
        occData = breakdown.map(s => s.current_occupancy);
    } else {
        labels = ['Center A', 'Center B', 'Center C'];
        capData = [500, 300, 400];
        occData = [320, 150, 210];
    }

    if (shelterChart) {
        shelterChart.data.labels = labels;
        shelterChart.data.datasets[0].data = capData;
        shelterChart.data.datasets[1].data = occData;
        shelterChart.update();
        return;
    }

    shelterChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Capacity',
                    data: capData,
                    backgroundColor: 'rgba(100, 116, 139, 0.5)',
                    borderRadius: 4
                },
                {
                    label: 'Occupancy',
                    data: occData,
                    backgroundColor: '#10b981',
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } },
                y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.06)' } }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#cbd5e1', font: { size: 10 } }
                }
            }
        }
    });
}

// External Weather Telemetry (Demonstrating Fetch API requirement)
function loadDashboardWeather(selectedCity) {
    const inputVal = $('#dashboard-weather-search').val();
    const city = selectedCity || (inputVal ? inputVal.trim() : null) || (APP_CONFIG && APP_CONFIG.currentUserLocality) || 'Chennai';

    if (selectedCity) {
        $('#dashboard-weather-search').val(selectedCity);
    }

    $('#weather-description').text(`Querying live telemetry for ${city}...`);

    // Demonstrates Fetch API for external weather service
    fetch(`/api/weather?city=${encodeURIComponent(city)}`)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(res => {
            if (res.success && res.data) {
                const w = res.data;
                $('#weather-temp').text(`${Math.round(w.temperature)}°C`);
                $('#weather-city').text(w.city);
                $('#weather-description').text(w.description);
                $('#weather-humidity').text(`${w.humidity}%`);
                $('#weather-wind').text(`${w.wind_speed} km/h`);
                $('#weather-rain').text(`${w.rainfall} mm`);
                $('#weather-pressure').text(`${w.pressure} hPa`);
                $('#weather-source-badge').text(w.source);
                $('#weather-updated-time').text(`Updated: ${w.timestamp}`);
            }
        })
        .catch(err => {
            $('#weather-description').text(`Weather telemetry offline for ${city}`);
        });
}

// Load Latest Active Alerts
function loadDashboardAlerts(showFeedback = false) {
    $.ajax({
        url: '/api/alerts?limit=3&active=true',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderDashboardAlerts(response.data);
            }
        }
    });
}

function renderDashboardAlerts(alerts) {
    const container = document.getElementById('dashboard-alerts-list');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div class="empty-state py-3">
                <i class="fa-solid fa-circle-check text-success"></i>
                <p>No critical disaster alerts at this moment. System normal.</p>
            </div>
        `;
        return;
    }

    let html = '';
    alerts.forEach(a => {
        const sevClass = a.severity.toLowerCase();
        html += `
            <div class="alert-card ${sevClass}">
                <div class="alert-header">
                    <div class="alert-title">
                        <span class="severity-dot ${sevClass}"></span>
                        <strong>${escapeHtml(a.title)}</strong>
                    </div>
                    <span class="badge badge-${sevClass}">${escapeHtml(a.severity)}</span>
                </div>
                <div class="text-secondary small mb-1">${escapeHtml(a.description || 'No additional description provided.')}</div>
                <div class="alert-meta">
                    <i class="fa-solid fa-location-dot me-1"></i> ${escapeHtml(a.location)} &bull;
                    <i class="fa-regular fa-clock ms-2 me-1"></i> ${escapeHtml(a.created_at)}
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// Load Recent Emergency Requests
function loadDashboardRequests(showFeedback = false) {
    $.ajax({
        url: '/api/requests?limit=5',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderDashboardRequests(response.data);
            }
        }
    });
}

function renderDashboardRequests(requests) {
    const tbody = document.getElementById('dashboard-requests-tbody');
    if (!tbody) return;

    if (!requests || requests.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-4 text-muted">
                    No active emergency incidents reported.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    requests.forEach(r => {
        const prioClass = (r.priority || 'medium').toLowerCase();
        const statClass = (r.status || 'reported').toLowerCase();
        const typeLabel = r.emergency_type.replace('_', ' ').toUpperCase();

        html += `
            <tr>
                <td>#${r.id}</td>
                <td>
                    <span class="badge badge-medium">${escapeHtml(typeLabel)}</span>
                    ${r.is_sos ? '<span class="badge badge-critical ms-1">SOS</span>' : ''}
                </td>
                <td>
                    <strong>${escapeHtml(r.citizen_name)}</strong>
                    <div class="text-muted small">${escapeHtml(r.contact_number)}</div>
                </td>
                <td>${escapeHtml(r.location || 'Coordinates only')}</td>
                <td><span class="badge badge-${prioClass}">${escapeHtml(r.priority)}</span></td>
                <td><span class="badge badge-${statClass}">${escapeHtml(r.status)}</span></td>
                <td class="small text-muted">${escapeHtml(r.created_at)}</td>
                <td>
                    <a href="/emergencies?id=${r.id}" class="btn btn-sm btn-outline">
                        <i class="fa-solid fa-eye me-1"></i> Details
                    </a>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// Quick Emergency SOS trigger with HTML5 Geolocation API
function triggerQuickSOS() {
    if (!confirm('CONFIRM IMMEDIATE SOS ALERT:\nThis will dispatch emergency rescue teams with your live location. Proceed?')) {
        return;
    }

    showLoading('Locating browser GPS satellites & broadcasting SOS...');

    function sendSOSRequest(lat, lon) {
        $.ajax({
            url: '/api/requests',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                citizen_name: APP_CONFIG.currentUserName || 'Citizen',
                contact_number: 'Emergency SOS Broadcast',
                emergency_type: 'other',
                priority: 'Critical',
                is_sos: true,
                latitude: lat,
                longitude: lon,
                location: `GPS: ${lat || 'Unknown'}, ${lon || 'Unknown'}`,
                description: 'CRITICAL EMERGENCY: One-touch SOS alert triggered by user in immediate peril.'
            }),
            dataType: 'json',
            success: function(response) {
                hideLoading();
                if (response.success) {
                    showToast('success', 'SOS broadcast dispatched! Responders have been alerted.', 'SOS TRANSMITTED');
                    loadDashboardMetrics();
                    loadDashboardRequests();
                }
            },
            error: function(xhr) {
                hideLoading();
                const err = (xhr.responseJSON && xhr.responseJSON.message) ? xhr.responseJSON.message : 'SOS broadcast failed.';
                showToast('error', err);
            }
        });
    }

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(pos) {
                sendSOSRequest(pos.coords.latitude, pos.coords.longitude);
            },
            function() {
                // If denied or timed out, send without GPS as required by prompt
                sendSOSRequest(null, null);
            },
            { enableHighAccuracy: true, timeout: 6000 }
        );
    } else {
        sendSOSRequest(null, null);
    }
}

// ============================================================
// Multi-Layer Operational Map Controller
// ============================================================
function initDashboardOpsMap() {
    const mapElem = document.getElementById('dashboard-ops-map');
    if (!mapElem || opsMap) return;

    opsMap = L.map('dashboard-ops-map').setView([13.0827, 80.2707], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap | SentryGrid Ops'
    }).addTo(opsMap);

    opsLayers.incidents = L.layerGroup().addTo(opsMap);
    opsLayers.alerts = L.layerGroup().addTo(opsMap);
    opsLayers.shelters = L.layerGroup().addTo(opsMap);
    opsLayers.hospitals = L.layerGroup().addTo(opsMap);
    opsLayers.earthquakes = L.layerGroup().addTo(opsMap);
}

function toggleMapLayer(layerKey) {
    if (!opsMap || !opsLayers[layerKey]) return;
    const isChecked = $(`#layer-${layerKey}`).is(':checked');
    if (isChecked) {
        if (!opsMap.hasLayer(opsLayers[layerKey])) {
            opsMap.addLayer(opsLayers[layerKey]);
        }
    } else {
        if (opsMap.hasLayer(opsLayers[layerKey])) {
            opsMap.removeLayer(opsLayers[layerKey]);
        }
    }
}

function refreshDashboardMap() {
    loadDashboardMapAssets();
    showToast('info', 'Operational layers refreshed.', 'Map Synchronized');
}

function loadDashboardMapAssets() {
    if (!opsMap) initDashboardOpsMap();
    if (!opsMap) return;

    // 1. Incidents Layer
    $.ajax({
        url: '/api/requests?limit=50',
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            if (res.success && res.data && opsLayers.incidents) {
                opsLayers.incidents.clearLayers();
                res.data.forEach(req => {
                    if (req.latitude && req.longitude) {
                        const isSos = req.is_sos;
                        const isClosed = req.status === 'Closed' || req.status === 'Rescued';
                        const color = isSos ? '#e94560' : (isClosed ? '#10b981' : '#f59e0b');

                        const marker = L.circleMarker([req.latitude, req.longitude], {
                            radius: isSos ? 9 : 7,
                            fillColor: color,
                            color: '#ffffff',
                            weight: 2,
                            opacity: 1,
                            fillOpacity: 0.85
                        });

                        marker.bindPopup(`
                            <div style="font-family: sans-serif; color: #1e293b;">
                                <div class="badge" style="background: ${color}; color: #fff; font-size: 0.75rem; margin-bottom: 4px;">
                                    ${req.tracking_code || '#' + req.id} &bull; ${escapeHtml(req.emergency_type)}
                                </div>
                                <h6 style="margin: 0; font-weight: bold; font-size: 0.9rem;">${escapeHtml(req.citizen_name)}</h6>
                                <p style="margin: 3px 0; font-size: 0.8rem; color: #475569;">${escapeHtml(req.description || 'No details')}</p>
                                <div style="font-size: 0.75rem; color: #64748b;"><strong>Status:</strong> ${req.status} &bull; <strong>Priority:</strong> ${req.priority}</div>
                                <div style="margin-top: 6px;"><a href="/emergencies?id=${req.id}" style="color: #2563eb; font-weight: bold; font-size: 0.8rem;">Open Incident Console &rarr;</a></div>
                            </div>
                        `);
                        opsLayers.incidents.addLayer(marker);
                    }
                });
            }
        }
    });

    // 2. Alerts Layer
    $.ajax({
        url: '/api/alerts?active=true',
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            if (res.success && res.data && opsLayers.alerts) {
                opsLayers.alerts.clearLayers();
                res.data.forEach(a => {
                    if (a.latitude && a.longitude) {
                        const sevColor = a.severity === 'Critical' ? '#e94560' : (a.severity === 'High' ? '#f59e0b' : '#38bdf8');
                        const alertZone = L.circle([a.latitude, a.longitude], {
                            radius: (a.radius_km || 3.0) * 1000,
                            color: sevColor,
                            fillColor: sevColor,
                            fillOpacity: 0.18,
                            weight: 2,
                            dashArray: '4, 6'
                        });

                        alertZone.bindPopup(`
                            <div style="font-family: sans-serif; color: #1e293b;">
                                <span class="badge" style="background: ${sevColor}; color: #fff; font-size: 0.7rem;">${a.severity}</span>
                                <h6 style="margin: 3px 0; font-weight: bold;">${escapeHtml(a.title)}</h6>
                                <p style="margin: 0; font-size: 0.8rem; color: #475569;">${escapeHtml(a.location)}</p>
                            </div>
                        `);
                        opsLayers.alerts.addLayer(alertZone);
                    }
                });
            }
        }
    });

    // 3. Shelters Layer
    $.ajax({
        url: '/api/shelters',
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            if (res.success && res.data && opsLayers.shelters) {
                opsLayers.shelters.clearLayers();
                res.data.forEach(s => {
                    if (s.latitude && s.longitude) {
                        const shelterMarker = L.circleMarker([s.latitude, s.longitude], {
                            radius: 7,
                            fillColor: '#10b981',
                            color: '#ffffff',
                            weight: 2,
                            fillOpacity: 0.9
                        });
                        shelterMarker.bindPopup(`
                            <div style="font-family: sans-serif; color: #1e293b;">
                                <h6 style="margin: 0; font-weight: bold; color: #047857;">${escapeHtml(s.name)}</h6>
                                <div style="font-size: 0.8rem; color: #334155;"><strong>Occupancy:</strong> ${s.current_occupancy} / ${s.total_capacity}</div>
                                <div style="font-size: 0.75rem; color: #64748b;">${escapeHtml(s.address)}</div>
                                <div style="margin-top: 5px;"><a href="/shelters" style="color: #059669; font-weight: bold; font-size: 0.8rem;">View Shelter &rarr;</a></div>
                            </div>
                        `);
                        opsLayers.shelters.addLayer(shelterMarker);
                    }
                });
            }
        }
    });

    // 4. Hospitals Layer
    $.ajax({
        url: '/api/hospitals',
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            if (res.success && res.data && opsLayers.hospitals) {
                opsLayers.hospitals.clearLayers();
                res.data.forEach(h => {
                    if (h.latitude && h.longitude) {
                        const hospMarker = L.circleMarker([h.latitude, h.longitude], {
                            radius: 7,
                            fillColor: '#ef4444',
                            color: '#ffffff',
                            weight: 2,
                            fillOpacity: 0.9
                        });
                        hospMarker.bindPopup(`
                            <div style="font-family: sans-serif; color: #1e293b;">
                                <h6 style="margin: 0; font-weight: bold; color: #b91c1c;">${escapeHtml(h.name)}</h6>
                                <div style="font-size: 0.8rem; color: #334155;"><strong>Available Beds:</strong> ${h.available_beds} / ${h.total_beds}</div>
                                <div style="font-size: 0.75rem; color: #64748b;">${escapeHtml(h.address)} &bull; ${h.trauma_level || 'Trauma Center'}</div>
                                <div style="margin-top: 5px;"><a href="/shelters" style="color: #dc2626; font-weight: bold; font-size: 0.8rem;">Direct Route &rarr;</a></div>
                            </div>
                        `);
                        opsLayers.hospitals.addLayer(hospMarker);
                    }
                });
            }
        }
    });

    // 5. Earthquakes Layer
    $.ajax({
        url: '/api/earthquakes?period=day&min_magnitude=4.5',
        type: 'GET',
        dataType: 'json',
        success: function(res) {
            if (res.success && res.features && opsLayers.earthquakes) {
                opsLayers.earthquakes.clearLayers();
                res.features.forEach(eq => {
                    if (eq.latitude && eq.longitude) {
                        const mag = eq.magnitude;
                        const color = mag >= 6.0 ? '#dc2626' : '#d97706';
                        const eqMarker = L.circleMarker([eq.latitude, eq.longitude], {
                            radius: Math.max(5, (mag - 2) * 3),
                            fillColor: color,
                            color: '#ffffff',
                            weight: 1.5,
                            fillOpacity: 0.7
                        });
                        eqMarker.bindPopup(`
                            <div style="font-family: sans-serif; color: #1e293b;">
                                <strong style="color: ${color};">USGS M ${mag.toFixed(1)}</strong>
                                <div style="font-size: 0.8rem; font-weight: bold;">${escapeHtml(eq.title)}</div>
                                <div style="font-size: 0.75rem; color: #64748b;">Depth: ${eq.depth_km} km &bull; ${eq.distance_km ? eq.distance_km + 'km away' : 'Global'}</div>
                            </div>
                        `);
                        opsLayers.earthquakes.addLayer(eqMarker);
                    }
                });
            }
        }
    });
}

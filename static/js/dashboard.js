/**
 * SentryGrid – Dashboard JavaScript (dashboard.js)
 * ==================================================
 * Powers the multi-role operational dashboard, live telemetry,
 * Chart.js analytics, quick SOS trigger, and periodic statistics refresh.
 * CSA4310 – Internet Programming
 */

let severityChart = null;

$(document).ready(function() {
    loadDashboardMetrics();
    loadDashboardWeather();
    loadDashboardAlerts();
    loadDashboardRequests();

    // Periodic polling for real-time dashboard refresh
    const pollTime = (APP_CONFIG && APP_CONFIG.pollIntervalDashboard) ? APP_CONFIG.pollIntervalDashboard : 60000;
    setInterval(function() {
        loadDashboardMetrics(false);
        loadDashboardAlerts(false);
        loadDashboardRequests(false);
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

                // Update Stat Cards
                $('#stat-active-alerts').text(d.alerts.active);
                $('#stat-pending-requests').text(d.requests.pending);
                $('#stat-resolved-incidents').text(d.requests.resolved);

                const availableTeams = d.teams.available || 0;
                $('#stat-available-teams').text(availableTeams);

                // Render Chart.js
                renderSeverityChart(d.alerts.by_severity);
            }
        },
        error: function() {
            hideLoading();
        }
    });
}

// Chart.js Disaster Severity Visualization
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
                        font: { size: 12 }
                    }
                }
            }
        }
    });
}

// External Weather Telemetry (Demonstrating Fetch API requirement)
function loadDashboardWeather() {
    const city = (APP_CONFIG && APP_CONFIG.currentUserLocality) ? APP_CONFIG.currentUserLocality : 'Chennai';

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
            $('#weather-description').text('Weather telemetry offline');
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

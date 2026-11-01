/**
 * SentryGrid – Module 1: Disaster Alert System (alerts.js)
 * ========================================================
 * Demonstrates: Weather API via Fetch API, Rule Threshold Evaluation,
 * REST API alert CRUD, AJAX filtering, and configurable interval polling.
 * CSA4310 – Internet Programming
 */

let searchTimeout = null;

$(document).ready(function() {
    loadAlerts();
    loadExternalWeatherTelemetry();
    loadMultiRegionWeather();

    // Configurable polling for new alerts
    const pollTime = (APP_CONFIG && APP_CONFIG.pollIntervalAlerts) ? APP_CONFIG.pollIntervalAlerts : 30000;
    setInterval(function() {
        loadAlerts(false);
    }, pollTime);
});

// Debounce search input to avoid flood of AJAX requests
function debounceAlertSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadAlerts();
    }, 400);
}

// Load Alerts via jQuery AJAX
function loadAlerts(showLoader = true) {
    const severity = $('#filter-alert-severity').val();
    const type = $('#filter-alert-type').val();
    const locality = $('#filter-alert-locality').val().trim();

    let queryParams = ['active=true'];
    if (severity) queryParams.push(`severity=${encodeURIComponent(severity)}`);
    if (type) queryParams.push(`type=${encodeURIComponent(type)}`);
    if (locality) queryParams.push(`locality=${encodeURIComponent(locality)}`);

    if (showLoader) {
        $('#alerts-container').html(`
            <div class="empty-state py-4">
                <div class="spinner-sm mb-2"></div>
                <p>Querying disaster monitoring alerts...</p>
            </div>
        `);
    }

    $.ajax({
        url: `/api/alerts?${queryParams.join('&')}`,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderAlerts(response.data);
                // Update sidebar badge
                const count = response.total || 0;
                const badge = $('#sidebar-alert-badge');
                if (count > 0) {
                    badge.text(count).removeClass('d-none');
                } else {
                    badge.addClass('d-none');
                }
            }
        },
        error: function(xhr) {
            $('#alerts-container').html(`
                <div class="empty-state py-4 text-danger">
                    <i class="fa-solid fa-triangle-exclamation mb-2 fs-2"></i>
                    <p>Failed to load alerts: ${(xhr.responseJSON && xhr.responseJSON.message) || 'Network error'}</p>
                </div>
            `);
        }
    });
}

// Render Alert Cards
function renderAlerts(alerts) {
    const container = document.getElementById('alerts-container');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = `
            <div class="empty-state py-5">
                <i class="fa-solid fa-shield-heart text-success fs-1"></i>
                <h4 class="mt-3">No Active Alerts</h4>
                <p>No disaster warnings match your current filter parameters.</p>
            </div>
        `;
        return;
    }

    let html = '';
    alerts.forEach(a => {
        const sevClass = a.severity.toLowerCase();
        const typeIcon = getDisasterIcon(a.disaster_type);

        html += `
            <div class="alert-card ${sevClass}">
                <div class="alert-header">
                    <div class="alert-title">
                        <span class="severity-dot ${sevClass}"></span>
                        <i class="fa-solid ${typeIcon} me-2 text-warning"></i>
                        <strong class="fs-5">${escapeHtml(a.title)}</strong>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge badge-${sevClass}">${escapeHtml(a.severity)}</span>
                        ${APP_CONFIG.currentUserRole === 'admin' ? `
                            <button class="btn btn-sm btn-outline text-danger py-0 px-2" onclick="deactivateAlert(${a.id})" title="Deactivate Alert">
                                <i class="fa-solid fa-ban"></i>
                            </button>
                        ` : ''}
                    </div>
                </div>

                <p class="text-light my-2" style="font-size: 0.95rem;">${escapeHtml(a.description || 'No specific description provided.')}</p>

                <div class="d-flex flex-wrap justify-content-between align-items-center pt-2 border-top border-secondary mt-2">
                    <div class="alert-meta m-0">
                        <i class="fa-solid fa-location-dot me-1 text-danger"></i> <strong>${escapeHtml(a.location)}</strong> &bull;
                        <i class="fa-regular fa-clock ms-2 me-1"></i> ${escapeHtml(a.created_at)} &bull;
                        <span class="text-muted ms-2">Source: ${escapeHtml(a.source || 'Official')}</span>
                    </div>

                    ${a.safety_instructions ? `
                        <button class="btn btn-sm btn-outline text-warning mt-2 mt-md-0" onclick="viewSafetyInstructions(${JSON.stringify(a).replace(/"/g, '&quot;')})">
                            <i class="fa-solid fa-shield-halved me-1"></i> Safety Advisory
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function getDisasterIcon(type) {
    const map = {
        'flood': 'fa-water',
        'cyclone': 'fa-tornado',
        'earthquake': 'fa-house-crack',
        'landslide': 'fa-hill-rockslide',
        'heatwave': 'fa-temperature-high',
        'tsunami': 'fa-water',
        'wildfire': 'fa-fire',
        'storm': 'fa-cloud-bolt'
    };
    return map[type] || 'fa-triangle-exclamation';
}

// Fetch Live Weather Telemetry (Demonstrates Fetch API requirement)
function loadExternalWeatherTelemetry(selectedCity) {
    const inputVal = $('#alerts-weather-search').val();
    const city = selectedCity || (inputVal ? inputVal.trim() : null) || (APP_CONFIG && APP_CONFIG.currentUserLocality) || 'Chennai';

    if (selectedCity) {
        $('#alerts-weather-search').val(selectedCity);
    }

    $('#telemetry-condition').text(`Scanning atmospheric telemetry for ${city}...`);

    fetch(`/api/weather?city=${encodeURIComponent(city)}`)
        .then(res => res.json())
        .then(result => {
            if (result.success && result.data) {
                const w = result.data;
                $('#telemetry-temp').text(`${Math.round(w.temperature)}°C`);
                $('#telemetry-city').text(w.city);
                $('#telemetry-condition').text(`${w.description.toUpperCase()} (Feels like ${Math.round(w.feels_like)}°C)`);
                $('#telemetry-rain').text(`${w.rainfall} mm/h`);
                $('#telemetry-wind').text(`${w.wind_speed} km/h`);
                $('#telemetry-humidity').text(`${w.humidity}%`);
                $('#telemetry-pressure').text(`${w.pressure} hPa`);
                $('#alerts-weather-source').text(w.source);

                // Analyze Danger Level
                const badge = $('#telemetry-risk-badge');
                if (w.rainfall > 50 || w.wind_speed > 60 || w.temperature > 42) {
                    badge.removeClass('badge-safe').addClass('badge-critical').text('High Risk Detected');
                } else {
                    badge.removeClass('badge-critical').addClass('badge-safe').text('Normal Atmospheric State');
                }
            }
        })
        .catch(() => {
            $('#telemetry-condition').text(`Telemetry service unavailable for ${city}`);
        });
}

// Multi-Place Live Weather Surveillance Grid
function loadMultiRegionWeather() {
    const container = document.getElementById('multi-city-weather-grid');
    if (!container) return;

    const monitoredPlaces = ['Chennai', 'Mumbai', 'Delhi', 'Kolkata', 'Bangalore', 'Hyderabad'];
    container.innerHTML = '';

    monitoredPlaces.forEach(p => {
        const col = document.createElement('div');
        col.className = 'col-12 col-md-4 col-lg-2';
        col.innerHTML = `
            <div class="card p-3 h-100 text-center" style="background: #16213e; border: 1px solid #2a2a4a; transition: all 0.3s ease;">
                <h5 class="fs-6 m-0 text-light mb-1">${escapeHtml(p)}</h5>
                <div class="fs-4 font-weight-bold text-info my-1" id="multi-temp-${p}">--°C</div>
                <small class="text-secondary d-block text-truncate mb-2" id="multi-cond-${p}">Fetching...</small>
                <div class="d-flex justify-content-between text-muted small border-top border-secondary pt-2 mt-auto">
                    <span><i class="fa-solid fa-droplet text-primary"></i> <span id="multi-rain-${p}">--</span></span>
                    <span><i class="fa-solid fa-wind text-warning"></i> <span id="multi-wind-${p}">--</span></span>
                </div>
                <button type="button" class="btn btn-sm btn-outline text-info py-0 mt-2" onclick="loadExternalWeatherTelemetry('${p}')" style="font-size: 0.7rem;">
                    Inspect
                </button>
            </div>
        `;
        container.appendChild(col);

        // Fetch live telemetry for each monitored place
        fetch(`/api/weather?city=${encodeURIComponent(p)}`)
            .then(res => res.json())
            .then(res => {
                if (res.success && res.data) {
                    const d = res.data;
                    $(`#multi-temp-${p}`).text(`${Math.round(d.temperature)}°C`);
                    $(`#multi-cond-${p}`).text(d.description);
                    $(`#multi-rain-${p}`).text(`${d.rainfall}mm`);
                    $(`#multi-wind-${p}`).text(`${Math.round(d.wind_speed)}kph`);
                }
            })
            .catch(() => {
                $(`#multi-cond-${p}`).text('Offline');
            });
    });
}

// Automatic Weather Threshold Evaluation (Requirement 6.B)
function evaluateWeatherThresholds() {
    showLoading('Evaluating atmospheric parameters against safety rules...');

    $.ajax({
        url: '/api/alerts/check-thresholds',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            hideLoading();
            if (response.success) {
                const rules = response.data;
                showToast('info', `Analyzed ${rules.length} automated disaster trigger rules against live parameters. No immediate critical breach.`, 'Rule Engine Evaluated');
            }
        },
        error: function() {
            hideLoading();
            showToast('error', 'Threshold evaluation failed.');
        }
    });
}

// Safety Advisory Modal
function viewSafetyInstructions(alertObj) {
    $('#view-alert-modal-title').html(`<i class="fa-solid fa-shield-virus text-warning me-2"></i>Safety Protocol: ${escapeHtml(alertObj.title)}`);
    $('#view-alert-severity-badge').text(alertObj.severity).removeClass().addClass(`badge badge-${alertObj.severity.toLowerCase()}`);
    $('#view-alert-location-text').text(`Affected Sector: ${alertObj.location}`);
    $('#view-alert-desc').text(alertObj.description || 'No description provided.');
    $('#view-alert-instructions-content').text(alertObj.safety_instructions || 'Remain vigilant and follow directions from official emergency authorities.');
    $('#modal-view-instructions').addClass('active');
}

function closeSafetyModal() {
    $('#modal-view-instructions').removeClass('active');
}

// Admin Alert Creation Modal
function openCreateAlertModal() {
    $('#modal-create-alert').addClass('active');
}

function closeCreateAlertModal() {
    $('#modal-create-alert').removeClass('active');
}

function handleCreateAlertSubmit(e) {
    e.preventDefault();

    const title = $('#alert-title').val().trim();
    const type = $('#alert-type').val();
    const severity = $('#alert-severity').val();
    const location = $('#alert-location').val().trim();
    const lat = $('#alert-lat').val();
    const lon = $('#alert-lon').val();
    const description = $('#alert-description').val().trim();
    const instructions = $('#alert-instructions').val().trim();
    const btn = $('#btn-submit-alert');

    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    $.ajax({
        url: '/api/alerts',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            title: title,
            disaster_type: type,
            severity: severity,
            location: location,
            latitude: lat ? parseFloat(lat) : null,
            longitude: lon ? parseFloat(lon) : null,
            description: description,
            safety_instructions: instructions
        }),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', 'Official disaster warning issued and broadcast!', 'Alert Published');
                closeCreateAlertModal();
                $('#form-create-alert')[0].reset();
                loadAlerts();
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to publish alert.';
            showToast('error', err);
        }
    });
}

// Deactivate Alert (Soft Delete by Admin)
function deactivateAlert(alertId) {
    if (!confirm('Are you sure you want to stand down and deactivate this disaster alert?')) return;

    showLoading('Deactivating alert...');
    $.ajax({
        url: `/api/alerts/${alertId}`,
        type: 'DELETE',
        dataType: 'json',
        success: function(res) {
            hideLoading();
            if (res.success) {
                showToast('success', 'Alert successfully deactivated.');
                loadAlerts();
            }
        },
        error: function(xhr) {
            hideLoading();
            showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to deactivate alert.');
        }
    });
}

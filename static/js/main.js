/**
 * SentryGrid – Core JavaScript (main.js)
 * ========================================
 * Provides global utilities, jQuery AJAX setup, toast notifications,
 * polling timers, sidebar controls, and in-app notification center.
 * CSA4310 – Internet Programming
 */

// ============================================================
// Global Notification / Toast System
// ============================================================
function showToast(type, message, title = '') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'fa-circle-info';
    let defaultTitle = 'Notification';
    if (type === 'success') {
        icon = 'fa-circle-check text-success';
        defaultTitle = title || 'Success';
    } else if (type === 'error') {
        icon = 'fa-triangle-exclamation text-danger';
        defaultTitle = title || 'Error';
    } else if (type === 'warning') {
        icon = 'fa-bell text-warning';
        defaultTitle = title || 'Warning';
    }

    toast.innerHTML = `
        <i class="fa-solid ${icon} fs-5"></i>
        <div class="toast-content" style="flex: 1;">
            <strong class="d-block text-light" style="font-size: 0.85rem;">${escapeHtml(defaultTitle)}</strong>
            <span style="font-size: 0.8rem; color: #cbd5e1;">${escapeHtml(message)}</span>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

// ============================================================
// Loading Spinner Overlay Controller
// ============================================================
function showLoading(message = 'Processing request...') {
    const overlay = document.getElementById('loading-overlay');
    const msgElem = document.getElementById('loading-message');
    if (overlay) {
        if (msgElem) msgElem.textContent = message;
        overlay.classList.add('active');
    }
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// ============================================================
// HTML Escaping (XSS Prevention)
// ============================================================
function escapeHtml(string) {
    if (string === null || string === undefined) return '';
    return String(string)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ============================================================
// Sidebar & Navigation Toggle (Responsive Mobile Support)
// ============================================================
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('active');
    }
}

// Close sidebar on click outside (mobile)
$(document).on('click', function(e) {
    if ($(window).width() <= 768) {
        const sidebar = $('#sidebar');
        const hamburger = $('#hamburger-btn');
        if (!sidebar.is(e.target) && sidebar.has(e.target).length === 0 &&
            !hamburger.is(e.target) && hamburger.has(e.target).length === 0) {
            sidebar.removeClass('active');
        }
    }
});

// ============================================================
// In-App Notification Center Drawer
// ============================================================
function toggleNotificationPanel() {
    const panel = document.getElementById('notif-panel');
    if (panel) {
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) {
            loadNotifications();
        }
    }
}

function loadNotifications(showFeedback = false) {
    $.ajax({
        url: '/api/notifications?limit=15',
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderNotifications(response.data);
                updateNotificationBadge(response.unread_count);
                if (showFeedback) {
                    showToast('info', 'Notifications refreshed.');
                }
            }
        },
        error: function() {
            // Quiet fail for periodic background poll
        }
    });
}

function renderNotifications(items) {
    const container = document.getElementById('notif-list-container');
    if (!container) return;

    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="empty-state py-4">
                <i class="fa-solid fa-bell-slash"></i>
                <p>No recent notifications</p>
            </div>
        `;
        return;
    }

    let html = '';
    items.forEach(item => {
        const unreadClass = !item.is_read ? 'unread' : '';
        html += `
            <div class="notif-item ${unreadClass}" onclick="markNotificationRead(${item.id}, '${escapeHtml(item.link || '')}')">
                <div class="notif-title">${escapeHtml(item.title)}</div>
                <div class="notif-message">${escapeHtml(item.message)}</div>
                <div class="notif-time"><i class="fa-regular fa-clock me-1"></i>${escapeHtml(item.created_at)}</div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function updateNotificationBadge(unreadCount) {
    const badge = document.getElementById('notif-count-badge');
    if (!badge) return;
    if (unreadCount > 0) {
        badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
        badge.classList.remove('d-none');
    } else {
        badge.classList.add('d-none');
    }
}

function markNotificationRead(notifId, targetLink) {
    $.ajax({
        url: `/api/notifications/${notifId}/read`,
        type: 'PUT',
        dataType: 'json',
        success: function() {
            if (targetLink && targetLink.trim() !== '') {
                window.location.href = targetLink;
            } else {
                loadNotifications();
            }
        }
    });
}

// ============================================================
// Interactive Emergency SOS Modal (with Place Selection & GPS)
// ============================================================
function openSOSModal() {
    const modal = document.getElementById('modal-sos-dispatch');
    if (!modal) return;

    modal.classList.add('active');

    // Default to user locality if available
    const customInput = document.getElementById('sos-custom-place');
    if (customInput && !customInput.value && APP_CONFIG && APP_CONFIG.currentUserLocality) {
        customInput.value = `${APP_CONFIG.currentUserLocality} Sector`;
    }

    // Try auto-locking GPS in background
    captureSOSModalGPS(false);
}

function closeSOSModal() {
    const modal = document.getElementById('modal-sos-dispatch');
    if (modal) modal.classList.remove('active');
}

function onSOSLocationModeChange() {
    const mode = $('input[name="sos-loc-mode"]:checked').val();
    const placeContainer = $('#sos-place-container');
    const gpsContainer = $('#sos-gps-container');
    const customInput = $('#sos-custom-place');

    if (mode === 'gps') {
        placeContainer.addClass('d-none');
        gpsContainer.removeClass('d-none');
        customInput.prop('required', false);
        captureSOSModalGPS(true);
    } else {
        placeContainer.removeClass('d-none');
        gpsContainer.addClass('d-none');
        customInput.prop('required', true);
    }
}

function onSOSPlaceDropdownChange() {
    const select = document.getElementById('sos-select-place');
    const customInput = document.getElementById('sos-custom-place');
    const selectedOpt = select.options[select.selectedIndex];

    if (select.value && select.value !== 'CUSTOM') {
        customInput.value = selectedOpt.text.replace(' • ', ', ');
        const lat = selectedOpt.getAttribute('data-lat');
        const lon = selectedOpt.getAttribute('data-lon');
        if (lat && lon) {
            $('#sos-lat-input').val(lat);
            $('#sos-lon-input').val(lon);
        }
    } else if (select.value === 'CUSTOM') {
        customInput.value = '';
        customInput.focus();
    }
}

function captureSOSModalGPS(showFeedback = true) {
    const feedback = $('#sos-gps-modal-feedback');
    if (showFeedback) {
        feedback.html('<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i>Acquiring satellite GPS fix...</span>');
    }

    if (!navigator.geolocation) {
        if (showFeedback) feedback.html('<span class="text-danger">Geolocation API unsupported in browser</span>');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        function(pos) {
            const lat = pos.coords.latitude.toFixed(6);
            const lon = pos.coords.longitude.toFixed(6);
            $('#sos-lat-input').val(lat);
            $('#sos-lon-input').val(lon);
            feedback.html(`<span class="text-success"><i class="fa-solid fa-check-circle me-1"></i>GPS locked: ${lat}, ${lon}</span>`);
            if (showFeedback) {
                showToast('success', `GPS coordinates (${lat}, ${lon}) locked for SOS.`);
            }
        },
        function(err) {
            feedback.html(`<span class="text-warning">GPS unavailable (${err.message}). Please select place above.</span>`);
        },
        { enableHighAccuracy: true, timeout: 6000 }
    );
}

function handleSOSSubmit(e) {
    e.preventDefault();

    const mode = $('input[name="sos-loc-mode"]:checked').val();
    const emergencyType = $('#sos-emergency-type').val();
    const note = $('#sos-situation-note').val().trim();
    let placeLocation = '';
    let lat = null;
    let lon = null;

    if (mode === 'place') {
        placeLocation = $('#sos-custom-place').val().trim();
        if (!placeLocation) {
            showToast('error', 'Please enter or select the incident place location.');
            return;
        }
        lat = $('#sos-lat-input').val() ? parseFloat($('#sos-lat-input').val()) : null;
        lon = $('#sos-lon-input').val() ? parseFloat($('#sos-lon-input').val()) : null;
    } else {
        lat = $('#sos-lat-input').val() ? parseFloat($('#sos-lat-input').val()) : null;
        lon = $('#sos-lon-input').val() ? parseFloat($('#sos-lon-input').val()) : null;
        placeLocation = (lat && lon) ? `GPS Incident Fix: (${lat}, ${lon})` : (APP_CONFIG.currentUserLocality || 'GPS Target Location');
    }

    const btn = $('#btn-submit-sos-modal');
    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    const payload = {
        citizen_name: APP_CONFIG.currentUserName || 'Citizen SOS Beacon',
        contact_number: 'Emergency SOS Broadcast',
        emergency_type: emergencyType,
        priority: 'Critical',
        is_sos: true,
        location: placeLocation,
        latitude: lat,
        longitude: lon,
        description: `URGENT SOS BEACON: Incident at [${placeLocation}]. ${note || 'Immediate rescue extrication requested.'}`
    };

    $.ajax({
        url: '/api/requests',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                closeSOSModal();
                showToast('success', `🚨 SOS DISPATCH TRANSMITTED for ${placeLocation}! Rescue units alerted.`, 'SOS ACTIVE');

                // Trigger page refresh if on dashboard or emergencies page
                if (typeof loadEmergencies === 'function') {
                    loadEmergencies(false);
                }
                if (typeof loadDashboardRequests === 'function') {
                    loadDashboardRequests(false);
                    loadDashboardMetrics(false);
                }
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'SOS transmission failed.';
            showToast('error', err);
        }
    });
}

// ============================================================
// User Logout Handler
// ============================================================
function handleLogout() {
    if (!confirm('Are you sure you want to log out of SentryGrid?')) return;
    showLoading('Logging out...');
    $.ajax({
        url: '/api/logout',
        type: 'POST',
        dataType: 'json',
        success: function() {
            window.location.href = '/login';
        },
        error: function() {
            window.location.href = '/login';
        }
    });
}

// ============================================================
// Global Polling Scheduler
// ============================================================
$(document).ready(function() {
    // Only initialize background pollers if user is authenticated
    if (typeof APP_CONFIG !== 'undefined' && APP_CONFIG.currentUserId > 0) {
        // Initial notification load
        loadNotifications();

        // 1. Poll notifications every 30 seconds
        setInterval(function() {
            loadNotifications();
        }, 30000);
    }
});

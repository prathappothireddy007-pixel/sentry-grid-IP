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

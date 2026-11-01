/**
 * SentryGrid – Response Teams Management (teams.js)
 * ====================================================
 * Handles response unit registration, categorization,
 * live operational readiness status updates, and deployment metrics.
 * CSA4310 – Internet Programming
 */

$(document).ready(function() {
    loadTeams();
});

// Load Response Units via AJAX
function loadTeams() {
    const status = $('#filter-team-status').val();
    const category = $('#filter-team-category').val();

    let query = [];
    if (status) query.push(`status=${encodeURIComponent(status)}`);
    if (category) query.push(`category=${encodeURIComponent(category)}`);

    $.ajax({
        url: `/api/teams?${query.join('&')}`,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderTeamsTable(response.data);
                updateTeamStats(response.data);
            }
        },
        error: function(xhr) {
            $('#teams-table-body').html(`
                <tr>
                    <td colspan="8" class="text-center py-4 text-danger">
                        Failed to fetch teams: ${(xhr.responseJSON && xhr.responseJSON.message) || 'Server error'}
                    </td>
                </tr>
            `);
        }
    });
}

function updateTeamStats(teams) {
    if (!teams) return;
    let total = teams.length;
    let available = 0;
    let deployed = 0;
    let offduty = 0;

    teams.forEach(t => {
        if (t.status === 'available') available++;
        else if (t.status === 'deployed') deployed++;
        else offduty++;
    });

    $('#team-stat-total').text(total);
    $('#team-stat-available').text(available);
    $('#team-stat-deployed').text(deployed);
    $('#team-stat-offduty').text(offduty);
    $('#teams-count-label').text(`${total} units`);
}

function renderTeamsTable(teams) {
    const tbody = document.getElementById('teams-table-body');
    if (!tbody) return;

    if (!teams || teams.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-4 text-muted">
                    No response units match your current filter.
                </td>
            </tr>
        `;
        return;
    }

    const isAdmin = (APP_CONFIG && APP_CONFIG.currentUserRole === 'admin');

    let html = '';
    teams.forEach(t => {
        const statClass = t.status.toLowerCase().replace('-', '_');
        const catLabel = t.team_category.replace('_', ' ').toUpperCase();

        html += `
            <tr>
                <td><strong>${escapeHtml(t.team_name)}</strong></td>
                <td><span class="badge badge-medium">${escapeHtml(catLabel)}</span></td>
                <td>${escapeHtml(t.team_leader || 'Unit Commander')}</td>
                <td><i class="fa-solid fa-users me-1 text-muted"></i>${t.member_count} personnel</td>
                <td>${escapeHtml(t.base_location || 'Field Station')}</td>
                <td>${escapeHtml(t.phone || 'Dispatch Radio')}</td>
                <td><span class="badge badge-${statClass}">${escapeHtml(t.status)}</span></td>
                ${isAdmin ? `
                    <td>
                        <div class="dropdown d-inline-block">
                            <button class="btn btn-sm btn-outline" onclick="cycleTeamStatus(${t.id}, '${t.status}')">
                                <i class="fa-solid fa-repeat me-1"></i> Toggle Status
                            </button>
                        </div>
                    </td>
                ` : ''}
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// Toggle Team Operational Status
function cycleTeamStatus(teamId, currentStatus) {
    const nextMap = {
        'available': 'deployed',
        'deployed': 'off_duty',
        'off_duty': 'available'
    };
    const nextStatus = nextMap[currentStatus] || 'available';

    showLoading(`Updating team status to ${nextStatus}...`);

    $.ajax({
        url: `/api/teams/${teamId}`,
        type: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({ status: nextStatus }),
        dataType: 'json',
        success: function(response) {
            hideLoading();
            if (response.success) {
                showToast('success', `Team status updated to ${nextStatus}.`);
                loadTeams();
            }
        },
        error: function(xhr) {
            hideLoading();
            showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'Update failed.');
        }
    });
}

// Modal Handlers: Register New Team
function openCreateTeamModal() {
    $('#modal-create-team').addClass('active');
}

function closeCreateTeamModal() {
    $('#modal-create-team').removeClass('active');
}

function handleCreateTeamSubmit(e) {
    e.preventDefault();

    const name = $('#tm-name').val().trim();
    const category = $('#tm-category').val();
    const members = $('#tm-members').val();
    const leader = $('#tm-leader').val().trim();
    const phone = $('#tm-phone').val().trim();
    const location = $('#tm-location').val().trim();
    const lat = $('#tm-lat').val();
    const lon = $('#tm-lon').val();

    const btn = $('#btn-submit-team');
    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    $.ajax({
        url: '/api/teams',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            team_name: name,
            team_category: category,
            member_count: parseInt(members || 0),
            team_leader: leader,
            phone: phone,
            base_location: location,
            latitude: lat ? parseFloat(lat) : null,
            longitude: lon ? parseFloat(lon) : null
        }),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', 'Emergency rescue team registered successfully!', 'Unit Operational');
                closeCreateTeamModal();
                $('#form-create-team')[0].reset();
                loadTeams();
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to register team.';
            showToast('error', err);
        }
    });
}

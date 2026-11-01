/**
 * SentryGrid – Resource Management JavaScript (resources.js)
 * ==========================================================
 * Handles emergency stockpile tracking, inventory replenishment,
 * critical deficit alerts, and RESTful resource operations.
 * CSA4310 – Internet Programming
 */

let activeRestockResourceId = null;

$(document).ready(function() {
    loadResources();
});

// Load Resources from Flask REST API
function loadResources() {
    const category = $('#filter-res-category').val();
    const lowStock = $('#filter-res-stock').val();

    let query = [];
    if (category) query.push(`category=${encodeURIComponent(category)}`);
    if (lowStock === 'true') query.push('low_stock=true');

    $.ajax({
        url: `/api/resources?${query.join('&')}`,
        type: 'GET',
        dataType: 'json',
        success: function(response) {
            if (response.success) {
                renderResourcesTable(response.data);
                updateResourceMetrics(response.data);
            }
        },
        error: function(xhr) {
            $('#resources-table-body').html(`
                <tr>
                    <td colspan="8" class="text-center py-4 text-danger">
                        Failed to load resource inventory: ${(xhr.responseJSON && xhr.responseJSON.message) || 'Server error'}
                    </td>
                </tr>
            `);
        }
    });
}

function updateResourceMetrics(items) {
    if (!items) return;
    let total = items.length;
    let lowCount = 0;
    let medicalCount = 0;
    let foodWaterCount = 0;

    items.forEach(r => {
        if (r.is_low_stock) lowCount++;
        if (r.category === 'medical') medicalCount += r.quantity;
        if (r.category === 'food_water') foodWaterCount += r.quantity;
    });

    $('#res-stat-total').text(total);
    $('#res-stat-low').text(lowCount);
    $('#res-stat-medical').text(medicalCount);
    $('#res-stat-food').text(foodWaterCount);
    $('#res-count-label').text(`${total} items`);
}

function renderResourcesTable(items) {
    const tbody = document.getElementById('resources-table-body');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-4 text-muted">
                    No resource inventory items found.
                </td>
            </tr>
        `;
        return;
    }

    let html = '';
    items.forEach(r => {
        const isLow = r.is_low_stock;
        const catLabel = r.category.replace('_', ' ').toUpperCase();

        html += `
            <tr class="${isLow ? 'table-danger-subtle' : ''}">
                <td><strong>${escapeHtml(r.name)}</strong></td>
                <td><span class="badge badge-purple">${escapeHtml(catLabel)}</span></td>
                <td>
                    <span class="fs-6 font-weight-bold ${isLow ? 'text-danger' : 'text-light'}">
                        ${r.quantity}
                    </span>
                    <small class="text-muted">${escapeHtml(r.unit)}</small>
                </td>
                <td><small class="text-muted">Min: ${r.min_threshold} ${escapeHtml(r.unit)}</small></td>
                <td>${escapeHtml(r.location || 'Central Depot')}</td>
                <td>
                    ${isLow ? `
                        <span class="badge badge-critical"><i class="fa-solid fa-triangle-exclamation me-1"></i>LOW DEFICIT</span>
                    ` : `
                        <span class="badge badge-safe"><i class="fa-solid fa-circle-check me-1"></i>OPTIMAL</span>
                    `}
                </td>
                <td class="small text-muted">${escapeHtml(r.last_restocked || 'Initial batch')}</td>
                <td>
                    <button class="btn btn-sm btn-outline text-success py-0 px-2" onclick="openRestockModal(${r.id}, '${escapeHtml(r.name)}')">
                        <i class="fa-solid fa-dolly me-1"></i> Restock
                    </button>
                    <button class="btn btn-sm btn-outline text-danger py-0 px-2 ms-1" onclick="deleteResource(${r.id})" title="Delete Item">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// Modal Handlers: Add Resource
function openCreateResourceModal() {
    $('#modal-create-resource').addClass('active');
}

function closeCreateResourceModal() {
    $('#modal-create-resource').removeClass('active');
}

function handleCreateResourceSubmit(e) {
    e.preventDefault();

    const name = $('#rc-name').val().trim();
    const category = $('#rc-category').val();
    const unit = $('#rc-unit').val().trim();
    const quantity = $('#rc-quantity').val();
    const threshold = $('#rc-threshold').val();
    const location = $('#rc-location').val().trim();

    const btn = $('#btn-submit-resource');
    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    $.ajax({
        url: '/api/resources',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            name: name,
            category: category,
            unit: unit,
            quantity: parseInt(quantity),
            min_threshold: parseInt(threshold),
            location: location
        }),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', 'Resource item added to logistics ledger.', 'Stock Added');
                closeCreateResourceModal();
                $('#form-create-resource')[0].reset();
                loadResources();
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Failed to add resource.';
            showToast('error', err);
        }
    });
}

// Modal Handlers: Restock Resource
function openRestockModal(resourceId, resourceName) {
    activeRestockResourceId = resourceId;
    $('#restock-resource-id').val(resourceId);
    $('#restock-resource-name').text(resourceName);
    $('#restock-quantity').val('');
    $('#modal-restock-resource').addClass('active');
}

function closeRestockModal() {
    $('#modal-restock-resource').removeClass('active');
    activeRestockResourceId = null;
}

function handleRestockSubmit(e) {
    e.preventDefault();

    const qty = $('#restock-quantity').val();
    if (!qty || parseInt(qty) <= 0) {
        showToast('error', 'Enter a valid positive restock quantity.');
        return;
    }

    const btn = $('#btn-submit-restock');
    btn.prop('disabled', true);
    btn.find('.btn-text').addClass('d-none');
    btn.find('.spinner-sm').removeClass('d-none');

    $.ajax({
        url: `/api/resources/${activeRestockResourceId}/restock`,
        type: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({ quantity: parseInt(qty) }),
        dataType: 'json',
        success: function(response) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            if (response.success) {
                showToast('success', response.message, 'Restocked');
                closeRestockModal();
                loadResources();
            }
        },
        error: function(xhr) {
            btn.prop('disabled', false);
            btn.find('.btn-text').removeClass('d-none');
            btn.find('.spinner-sm').addClass('d-none');

            const err = (xhr.responseJSON && xhr.responseJSON.message) || 'Restock failed.';
            showToast('error', err);
        }
    });
}

// Delete Resource Item
function deleteResource(resourceId) {
    if (!confirm('Are you sure you want to permanently delete this resource from the ledger?')) return;

    showLoading('Deleting item...');
    $.ajax({
        url: `/api/resources/${resourceId}`,
        type: 'DELETE',
        dataType: 'json',
        success: function(response) {
            hideLoading();
            if (response.success) {
                showToast('success', 'Resource item removed.');
                loadResources();
            }
        },
        error: function(xhr) {
            hideLoading();
            showToast('error', (xhr.responseJSON && xhr.responseJSON.message) || 'Delete failed.');
        }
    });
}

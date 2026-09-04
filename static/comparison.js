/*
    COMPARISON PAGE LOGIC (Patched)
    ==============================
    - XSS-safe HTML escaping
    - Field-aware delta coloring (progress gains = green, slips = red)
    - Safe DataTables lifecycle & teardown
    - Relationship & logic variance rendering
    - Preserves file handles on failed comparison
*/

let baselineFile = null;
let currentFile = null;
let changeChart = null;

const MAX_UPLOAD_MB = 100;
const MAX_COMPARE_ROWS = 2000;

// ═══════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════

function esc(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function deltaClassFor(field, change) {
    const f = (field || '').toLowerCase();
    let n = change.delta_days;

    if (n == null && typeof change.delta === 'string') {
        const m = String(change.delta).match(/^([+-]?\d+(?:\.\d+)?)/);
        n = m ? parseFloat(m[1]) : 0;
    }

    if (!n || isNaN(n)) return '';

    // "More days is worse" -> Positive delta is Red (Slipped)
    const moreIsBad = ['finish date', 'start date', 'duration'].indexOf(f) >= 0;
    // "More is better" -> Positive delta is Green (Improved)
    const moreIsGood = ['progress', 'total float', 'free float'].indexOf(f) >= 0;

    if (moreIsBad) {
        return n > 0 ? 'delta-positive' : 'delta-negative';
    }
    if (moreIsGood) {
        return n > 0 ? 'delta-negative' : 'delta-positive';
    }
    return '';
}

function destroyTable(selector) {
    try {
        if (window.jQuery && $.fn.DataTable && $.fn.DataTable.isDataTable(selector)) {
            $(selector).DataTable().clear().destroy();
        }
    } catch (e) {
        console.warn('DataTable destroy error on ' + selector, e);
    }
    const tbody = document.querySelector(selector + ' tbody');
    if (tbody) tbody.innerHTML = '';
}

async function safeFetchJSON(url, options) {
    const res = await fetch(url, options || {});
    let data = {};
    try {
        data = await res.json();
    } catch (e) {
        if (!res.ok) throw new Error('Request failed (' + res.status + ')');
        throw new Error('Invalid JSON response from server');
    }
    if (!res.ok || data.error) {
        throw new Error(data.error || ('Request failed (' + res.status + ')'));
    }
    return data;
}

// ═══════════════════════════════════════════
// BOOT & HANDLERS
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
    setupFileHandlers('baseline');
    setupFileHandlers('current');

    const compareBtn = document.getElementById('compareBtn');
    if (compareBtn) {
        compareBtn.addEventListener('click', runComparison);
    }

    checkExistingComparison();
});

function setupFileHandlers(type) {
    const dropZone = document.getElementById(type + 'Drop');
    const input = document.getElementById(type + 'Input');

    if (!dropZone || !input) return;

    dropZone.addEventListener('click', function () {
        input.click();
    });

    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', function () {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileSelected(type, e.dataTransfer.files[0]);
        }
    });

    input.addEventListener('change', function (e) {
        if (e.target.files && e.target.files.length > 0) {
            handleFileSelected(type, e.target.files[0]);
        }
    });
}

function handleFileSelected(type, file) {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.xer')) {
        alert('❌ Please select a .xer file');
        return;
    }

    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
        alert('❌ File exceeds ' + MAX_UPLOAD_MB + ' MB limit');
        return;
    }

    if (type === 'baseline') {
        baselineFile = file;
    } else {
        currentFile = file;
    }

    const nameLabel = document.getElementById(type + 'FileName');
    const dropBox = document.getElementById(type + 'Drop');

    if (nameLabel) nameLabel.textContent = '✅ ' + file.name;
    if (dropBox) dropBox.classList.add('has-file');

    const compareBtn = document.getElementById('compareBtn');
    if (compareBtn && baselineFile && currentFile) {
        compareBtn.disabled = false;
    }
}

// ═══════════════════════════════════════════
// COMPARISON EXECUTION
// ═══════════════════════════════════════════

async function runComparison() {
    if (!baselineFile || !currentFile) return;

    const uploadSec = document.getElementById('uploadSection');
    const loadingSec = document.getElementById('loadingSection');

    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'block';

    const formData = new FormData();
    formData.append('baseline', baselineFile);
    formData.append('current', currentFile);

    try {
        const response = await safeFetchJSON('/api/compare', {
            method: 'POST',
            body: formData
        });

        showResults(response);
    } catch (err) {
        console.error('Comparison error:', err);
        alert('❌ ' + (err.message || 'Comparison failed'));

        if (loadingSec) loadingSec.style.display = 'none';
        if (uploadSec) uploadSec.style.display = 'block';
    }
}

async function checkExistingComparison() {
    try {
        const res = await fetch('/api/comparison-data');
        const data = await res.json().catch(function () { return {}; });
        if (res.ok && data.has_data) {
            showResults(data);
        }
    } catch (e) {
        console.warn('No existing comparison found', e);
    }
}

function showResults(response) {
    const loadingSec = document.getElementById('loadingSection');
    const resultsSec = document.getElementById('resultsSection');
    const uploadSec = document.getElementById('uploadSection');

    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'none';
    if (resultsSec) resultsSec.style.display = 'block';

    const baseName = document.getElementById('baselineName');
    const currName = document.getElementById('currentName');

    if (baseName) baseName.textContent = response.baseline_file || '--';
    if (currName) currName.textContent = response.current_file || '--';

    const results = response.results || {};

    renderSummary(results.summary || {});
    renderChart(results.summary || {});
    renderCriticalChanges(results.critical_changes || {});
    renderRelationshipChanges(results.relationship_changes || {});
    renderChangedActivities(results.changed || []);
    renderAddedActivities(results.added || []);
    renderDeletedActivities(results.deleted || []);
}

// ═══════════════════════════════════════════
// RENDERERS
// ═══════════════════════════════════════════

function renderSummary(summary) {
    const container = document.getElementById('summaryCards');
    if (!container) return;

    const cards = [
        { icon: '➕', label: 'Added', value: summary.added_count ?? 0, color: 'blue' },
        { icon: '➖', label: 'Deleted', value: summary.deleted_count ?? 0, color: 'red' },
        { icon: '🔄', label: 'Changed', value: summary.changed_count ?? 0, color: 'orange' },
        { icon: '✓', label: 'Unchanged', value: summary.unchanged_count ?? 0, color: 'green' },
        { icon: '📉', label: 'Slipped', value: summary.slipped_count ?? 0, color: 'red' },
        { icon: '📈', label: 'Improved', value: summary.improved_count ?? 0, color: 'green' },
    ];

    container.innerHTML = cards.map(function (c) {
        return (
            '<div class="summary-card ' + esc(c.color) + '">' +
            '<div class="card-icon">' + esc(c.icon) + '</div>' +
            '<div class="card-value">' + esc(c.value) + '</div>' +
            '<div class="card-label">' + esc(c.label) + '</div>' +
            '</div>'
        );
    }).join('');
}

function renderChart(summary) {
    const canvas = document.getElementById('changeChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (changeChart) {
        changeChart.destroy();
        changeChart = null;
    }

    changeChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Added', 'Deleted', 'Changed', 'Unchanged'],
            datasets: [{
                data: [
                    summary.added_count || 0,
                    summary.deleted_count || 0,
                    summary.changed_count || 0,
                    summary.unchanged_count || 0
                ],
                backgroundColor: ['#3b82f6', '#dc2626', '#f59e0b', '#10b981'],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

function renderCriticalChanges(criticalData) {
    const newly = (criticalData && criticalData.newly_critical) || [];
    const noLonger = (criticalData && criticalData.no_longer_critical) || [];

    const newlyDiv = document.getElementById('newlyCriticalList');
    if (newlyDiv) {
        if (!newly.length) {
            newlyDiv.innerHTML = '<p style="color:#64748b;">None</p>';
        } else {
            newlyDiv.innerHTML = newly.slice(0, 50).map(function (a) {
                return (
                    '<div class="issue-item high" style="margin-bottom:0.5rem;">' +
                    '<div><strong>' + esc(a.code) + '</strong> - ' + esc(a.name) +
                    '<div style="font-size:0.85rem; color:#64748b;">Float: ' + esc(a.float) + 'd</div>' +
                    '</div></div>'
                );
            }).join('') + (newly.length > 50 ? '<p style="font-size:0.8rem;color:#64748b;">… and ' + (newly.length - 50) + ' more</p>' : '');
        }
    }

    const noLongerDiv = document.getElementById('noLongerCriticalList');
    if (noLongerDiv) {
        if (!noLonger.length) {
            noLongerDiv.innerHTML = '<p style="color:#64748b;">None</p>';
        } else {
            noLongerDiv.innerHTML = noLonger.slice(0, 50).map(function (a) {
                return (
                    '<div class="issue-item medium" style="margin-bottom:0.5rem;">' +
                    '<div><strong>' + esc(a.code) + '</strong> - ' + esc(a.name) +
                    '<div style="font-size:0.85rem; color:#64748b;">Float: ' + esc(a.float) + 'd</div>' +
                    '</div></div>'
                );
            }).join('') + (noLonger.length > 50 ? '<p style="font-size:0.8rem;color:#64748b;">… and ' + (noLonger.length - 50) + ' more</p>' : '');
        }
    }
}

function renderRelationshipChanges(relData) {
    const section = document.getElementById('relationshipSection');
    if (!section) return;

    if (!relData || (!relData.added_count && !relData.deleted_count && !relData.modified_count)) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';

    const cardsContainer = document.getElementById('relSummaryCards');
    if (cardsContainer) {
        cardsContainer.innerHTML = `
            <div class="summary-card blue">
                <div class="card-icon">➕</div>
                <div class="card-value">${esc(relData.added_count || 0)}</div>
                <div class="card-label">Added Logic Ties</div>
            </div>
            <div class="summary-card red">
                <div class="card-icon">➖</div>
                <div class="card-value">${esc(relData.deleted_count || 0)}</div>
                <div class="card-label">Deleted Logic Ties</div>
            </div>
            <div class="summary-card orange">
                <div class="card-icon">🔄</div>
                <div class="card-value">${esc(relData.modified_count || 0)}</div>
                <div class="card-label">Modified Logic/Lags</div>
            </div>
        `;
    }

    destroyTable('#relChangedTable');
    const tbody = document.querySelector('#relChangedTable tbody');
    if (!tbody) return;

    const details = relData.modified_details || [];
    details.slice(0, MAX_COMPARE_ROWS).forEach(function (r) {
        const tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + esc(r.tie || (r.pred_code + ' → ' + r.succ_code)) + '</strong></td>' +
            '<td>' + esc(r.baseline_type || r.old_type || '') + '</td>' +
            '<td>' + esc(r.current_type || r.new_type || '') + '</td>' +
            '<td>' + esc(r.baseline_lag ?? r.old_lag ?? 0) + 'd</td>' +
            '<td>' + esc(r.current_lag ?? r.new_lag ?? 0) + 'd</td>';
        tbody.appendChild(tr);
    });

    if (window.jQuery && $.fn.DataTable && details.length > 0) {
        $('#relChangedTable').DataTable({ pageLength: 25, deferRender: true });
    }
}

function renderChangedActivities(changed) {
    destroyTable('#changedTable');

    const tbody = document.querySelector('#changedTable tbody');
    if (!tbody) return;

    const list = Array.isArray(changed) ? changed : [];

    list.slice(0, MAX_COMPARE_ROWS).forEach(function (item) {
        const changes = item.changes || [];
        changes.forEach(function (change) {
            const tr = document.createElement('tr');
            const deltaClass = deltaClassFor(change.field, change);
            const sev = esc((change.severity || 'low').toLowerCase());

            tr.innerHTML =
                '<td><strong>' + esc(item.code) + '</strong></td>' +
                '<td>' + esc(item.name) + '</td>' +
                '<td>' + esc(item.wbs) + '</td>' +
                '<td><strong>' + esc(change.field) + '</strong></td>' +
                '<td>' + esc(change.baseline) + '</td>' +
                '<td>' + esc(change.current) + '</td>' +
                '<td class="' + deltaClass + '">' + esc(change.delta) + '</td>' +
                '<td><span class="change-badge ' + sev + '">' + esc(sev.toUpperCase()) + '</span></td>';
            tbody.appendChild(tr);
        });
    });

    if (window.jQuery && $.fn.DataTable) {
        $('#changedTable').DataTable({ pageLength: 25, order: [[0, 'asc']], deferRender: true });
    }
}

function renderAddedActivities(added) {
    destroyTable('#addedTable');

    const tbody = document.querySelector('#addedTable tbody');
    if (!tbody) return;

    const list = Array.isArray(added) ? added : [];

    list.slice(0, MAX_COMPARE_ROWS).forEach(function (a) {
        const tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + esc(a.code) + '</strong></td>' +
            '<td>' + esc(a.name) + '</td>' +
            '<td>' + esc(a.wbs) + '</td>' +
            '<td>' + esc(a.duration) + 'd</td>' +
            '<td>' + esc(a.start) + '</td>' +
            '<td>' + esc(a.finish) + '</td>';
        tbody.appendChild(tr);
    });

    if (window.jQuery && $.fn.DataTable) {
        $('#addedTable').DataTable({ pageLength: 25, deferRender: true });
    }
}

function renderDeletedActivities(deleted) {
    destroyTable('#deletedTable');

    const tbody = document.querySelector('#deletedTable tbody');
    if (!tbody) return;

    const list = Array.isArray(deleted) ? deleted : [];

    list.slice(0, MAX_COMPARE_ROWS).forEach(function (a) {
        const tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + esc(a.code) + '</strong></td>' +
            '<td>' + esc(a.name) + '</td>' +
            '<td>' + esc(a.wbs) + '</td>' +
            '<td>' + esc(a.duration) + 'd</td>' +
            '<td>' + esc(a.start) + '</td>' +
            '<td>' + esc(a.finish) + '</td>';
        tbody.appendChild(tr);
    });

    if (window.jQuery && $.fn.DataTable) {
        $('#deletedTable').DataTable({ pageLength: 25, deferRender: true });
    }
}

function resetComparison() {
    baselineFile = null;
    currentFile = null;

    const bInput = document.getElementById('baselineInput');
    const cInput = document.getElementById('currentInput');
    if (bInput) bInput.value = '';
    if (cInput) cInput.value = '';

    const bName = document.getElementById('baselineFileName');
    const cName = document.getElementById('currentFileName');
    const bDrop = document.getElementById('baselineDrop');
    const cDrop = document.getElementById('currentDrop');
    const compareBtn = document.getElementById('compareBtn');

    if (bName) bName.textContent = '';
    if (cName) cName.textContent = '';
    if (bDrop) bDrop.classList.remove('has-file');
    if (cDrop) cDrop.classList.remove('has-file');
    if (compareBtn) compareBtn.disabled = true;

    if (changeChart) {
        changeChart.destroy();
        changeChart = null;
    }

    destroyTable('#changedTable');
    destroyTable('#addedTable');
    destroyTable('#deletedTable');
    destroyTable('#relChangedTable');

    const resultsSec = document.getElementById('resultsSection');
    const loadingSec = document.getElementById('loadingSection');
    const uploadSec = document.getElementById('uploadSection');

    if (resultsSec) resultsSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'none';
    if (uploadSec) uploadSec.style.display = 'block';
}
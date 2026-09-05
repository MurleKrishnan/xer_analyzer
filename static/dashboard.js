/*
    DASHBOARD JAVASCRIPT (Patched)
    ==============================
    - XSS-safe rendering
    - Robust fetch / upload errors
    - DataTables lifecycle + large-table guard
    - Preserve dashboard on failed re-upload
*/

// ─── CHART / TABLE REFERENCES ───
let statusChart = null;
let floatChart = null;
let wbsChart = null;
let activitiesDataTable = null;
let criticalDataTable = null;

const MAX_UPLOAD_MB = 100;
const MAX_TABLE_ROWS = 5000;

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

function statusClass(status) {
    return esc(status)
        .toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9-_]/g, '');
}

async function safeFetchJSON(url, options = {}) {
    const res = await fetch(url, options);
    let data = {};
    try {
        data = await res.json();
    } catch (e) {
        if (!res.ok) {
            throw new Error(`Request failed (${res.status})`);
        }
        throw new Error('Invalid JSON response from server');
    }
    if (!res.ok || data.error) {
        throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
}

async function downloadFile(url, defaultName) {
    try {
        const res = await fetch(url);
        if (!res.ok) {
            let msg = `Download failed (${res.status})`;
            try {
                const j = await res.json();
                if (j.error) msg = j.error;
            } catch (e) { /* ignore */ }
            throw new Error(msg);
        }
        const blob = await res.blob();
        const cd = res.headers.get('content-disposition') || '';
        const m = cd.match(/filename\*?=(?:UTF-8''|")?([^\";]+)/i);
        const name = m ? decodeURIComponent(m[1].replace(/"/g, '')) : defaultName;
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(a.href);
    } catch (err) {
        alert('❌ ' + err.message);
    }
}

function destroyDataTable(ref, selector) {
    try {
        if (ref) {
            ref.destroy();
        } else if (window.jQuery && $.fn.DataTable && $.fn.DataTable.isDataTable(selector)) {
            $(selector).DataTable().destroy();
        }
    } catch (e) {
        console.warn('DataTable destroy:', e);
    }
    const tbody = document.querySelector(selector + ' tbody');
    if (tbody) tbody.innerHTML = '';
    return null;
}

// ═══════════════════════════════════════════
// STARTUP
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 Dashboard initialized');
    setupEventListeners();
    checkForExistingData();
});

// ═══════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════

function setupEventListeners() {
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    const loadSampleBtn = document.getElementById('loadSampleBtn');
    const exportBtn = document.getElementById('exportBtn');

    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', function () {
            fileInput.click();
        });
        fileInput.addEventListener('change', function (e) {
            if (e.target.files && e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
                fileInput.value = '';
            }
        });
    }

    if (loadSampleBtn) {
        loadSampleBtn.addEventListener('click', loadSample);
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            downloadFile(
                '/api/export-excel',
                `schedule_report_${Date.now()}.xlsx`
            );
        });
    }

    const dropZone = document.getElementById('dropZone');
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', function () {
            fileInput.click();
        });
        dropZone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', function () {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });
    }

    document.querySelectorAll('.tab-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const tabName = this.getAttribute('data-tab');
            if (tabName) switchTab(tabName);
        });
    });
}

// ═══════════════════════════════════════════
// FILE OPERATIONS
// ═══════════════════════════════════════════

async function uploadFile(file) {
    if (!file) return;

    if (!file.name.toLowerCase().match(/\.(xer|xml)$/i)) {
        alert('❌ Please upload a .xer or .xml or .xml file');
        return;
    }

    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
        alert('❌ File exceeds ' + MAX_UPLOAD_MB + ' MB limit');
        return;
    }

    console.log('📤 Uploading:', file.name);
    showLoading('Uploading and analyzing...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const data = await safeFetchJSON('/api/upload', {
            method: 'POST',
            body: formData
        });
        console.log('✅ Analysis complete');
        showDashboard(data);
    } catch (error) {
        console.error('Upload error:', error);
        alert('❌ ' + (error.message || 'Failed to upload file'));
        hideLoading(true);
    }
}

async function loadSample() {
    console.log('📄 Loading sample file...');
    showLoading('Loading sample Schedule file...');
    try {
        const data = await safeFetchJSON('/api/load-sample');
        showDashboard(data);
    } catch (error) {
        console.error(error);
        alert('❌ ' + (error.message || 'Failed to load sample'));
        hideLoading(true);
    }
}

async function checkForExistingData() {
    try {
        const res = await fetch('/api/dashboard');
        const data = await res.json().catch(function () { return {}; });
        if (res.ok && data.has_data) {
            showDashboard(data);
        }
    } catch (e) {
        console.warn('No existing dashboard data', e);
    }
}

// ═══════════════════════════════════════════
// UI STATE
// ═══════════════════════════════════════════

function showLoading(text) {
    const welcome = document.getElementById('welcomeScreen');
    const dash = document.getElementById('dashboard');
    const loading = document.getElementById('loadingScreen');
    const loadingText = document.getElementById('loadingText');

    if (welcome) welcome.style.display = 'none';
    if (dash) dash.style.display = 'none';
    if (loading) loading.style.display = 'flex';
    if (loadingText) loadingText.textContent = text || 'Loading...';
}

function hideLoading(keepDashboard) {
    const welcome = document.getElementById('welcomeScreen');
    const dash = document.getElementById('dashboard');
    const loading = document.getElementById('loadingScreen');

    if (loading) loading.style.display = 'none';

    const loaded = dash && dash.dataset.loaded === '1';
    if (keepDashboard && loaded) {
        if (dash) dash.style.display = 'block';
        if (welcome) welcome.style.display = 'none';
    } else {
        if (welcome) welcome.style.display = 'flex';
        if (dash) dash.style.display = 'none';
    }
}

function showDashboard(response) {
    const welcome = document.getElementById('welcomeScreen');
    const loading = document.getElementById('loadingScreen');
    const dash = document.getElementById('dashboard');
    const exportBtn = document.getElementById('exportBtn');

    if (welcome) welcome.style.display = 'none';
    if (loading) loading.style.display = 'none';
    if (dash) {
        dash.style.display = 'block';
        dash.dataset.loaded = '1';
    }
    if (exportBtn) exportBtn.style.display = 'inline-flex';

    const fileName = document.getElementById('fileName');
    const analyzedAt = document.getElementById('analyzedAt');
    const projectName = document.getElementById('projectName');

    if (fileName) fileName.textContent = response.file_name || '--';
    if (analyzedAt) analyzedAt.textContent = response.analyzed_at || '--';

    const data = response.data || {};

    if (projectName && data.project_info) {
        projectName.textContent = data.project_info.name || '--';
    }

    try { renderSummaryCards(data.summary_cards || []); } catch (e) { console.error(e); }
    try { renderStatusChart(data.status_distribution); } catch (e) { console.error(e); }
    try { renderFloatChart(data.float_distribution); } catch (e) { console.error(e); }
    try { renderWbsChart(data.wbs_breakdown); } catch (e) { console.error(e); }
    try { renderDcmaCards(data.dcma_summary || []); } catch (e) { console.error(e); }
    try { renderIssues(data.top_issues || []); } catch (e) { console.error(e); }
    try { renderActivitiesTable(data.activities_table || []); } catch (e) { console.error(e); }
    try { renderCriticalTable(data.critical_activities || []); } catch (e) { console.error(e); }
}

// ═══════════════════════════════════════════
// RENDER
// ═══════════════════════════════════════════

function renderSummaryCards(cards) {
    const container = document.getElementById('summaryCards');
    if (!container) return;
    container.innerHTML = '';

    (cards || []).forEach(function (card) {
        const div = document.createElement('div');
        const color = esc(card.color || 'blue');
        div.className = 'summary-card ' + color;
        div.innerHTML =
            '<div class="card-icon">' + esc(card.icon) + '</div>' +
            '<div class="card-value">' + esc(card.value) + '</div>' +
            '<div class="card-label">' + esc(card.label) + '</div>';
        container.appendChild(div);
    });
}

function renderStatusChart(data) {
    if (!data || !data.labels || !data.values) return;
    const canvas = document.getElementById('statusChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (statusChart) {
        statusChart.destroy();
        statusChart = null;
    }

    statusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: data.colors || ['#94a3b8', '#f59e0b', '#10b981'],
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

function renderFloatChart(data) {
    if (!data || !data.labels || !data.values) return;
    const canvas = document.getElementById('floatChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (floatChart) {
        floatChart.destroy();
        floatChart = null;
    }

    floatChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Activities',
                data: data.values,
                backgroundColor: data.colors || '#3b82f6',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function renderWbsChart(data) {
    if (!data || !data.labels || !data.values) return;
    const canvas = document.getElementById('wbsChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (wbsChart) {
        wbsChart.destroy();
        wbsChart = null;
    }

    wbsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Activities',
                data: data.values,
                backgroundColor: '#3b82f6',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderDcmaCards(dcmaData) {
    const container = document.getElementById('dcmaGrid');
    if (!container) return;
    container.innerHTML = '';

    (dcmaData || []).forEach(function (check) {
        const passed = !!check.pass;
        const div = document.createElement('div');
        div.className = 'dcma-card ' + (passed ? 'pass' : 'fail');

        let details;
        if (check.count != null && check.total != null) {
            details = esc(check.count) + ' of ' + esc(check.total) +
                ' | Threshold: ' + esc(check.threshold);
        } else {
            details = 'Threshold: ' + esc(check.threshold || '');
        }

        div.innerHTML =
            '<div class="dcma-card-header">' +
            '<div class="dcma-card-name">' + esc(check.name) + '</div>' +
            '<span class="dcma-badge ' + (passed ? 'pass' : 'fail') + '">' +
            (passed ? '✓ PASS' : '✗ FAIL') +
            '</span></div>' +
            '<div class="dcma-value">' + esc(check.value) + '</div>' +
            '<div class="dcma-details">' + details + '</div>';
        container.appendChild(div);
    });
}

function renderIssues(issues) {
    const section = document.getElementById('issuesSection');
    const container = document.getElementById('issuesList');
    if (!section || !container) return;

    if (!issues || issues.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    container.innerHTML = '';

    issues.forEach(function (issue) {
        const sev = esc((issue.severity || 'medium').toLowerCase());
        const div = document.createElement('div');
        div.className = 'issue-item ' + sev;
        div.innerHTML =
            '<div><strong>' + esc(issue.check) + '</strong>' +
            '<div style="font-size:0.85rem;color:#64748b;">' +
            esc(issue.count) + ' activities affected (' + esc(issue.percentage) + '%)' +
            '</div></div>' +
            '<span class="dcma-badge fail">' + esc((issue.severity || '').toUpperCase()) + '</span>';
        container.appendChild(div);
    });
}

function renderActivitiesTable(activities) {
    activitiesDataTable = destroyDataTable(activitiesDataTable, '#activitiesTable');

    const list = Array.isArray(activities) ? activities : [];
    let rows = list;
    let note = '';
    if (list.length > MAX_TABLE_ROWS) {
        rows = list.slice(0, MAX_TABLE_ROWS);
        note = 'Showing first ' + MAX_TABLE_ROWS + ' of ' + list.length +
            ' activities. Export Excel for the full list.';
    }

    const tbody = document.querySelector('#activitiesTable tbody');
    if (!tbody) return;

    // Prefer DataTables data API when jQuery available
    if (window.jQuery && $.fn.DataTable) {
        activitiesDataTable = $('#activitiesTable').DataTable({
            data: rows,
            pageLength: 25,
            order: [[6, 'asc']],
            deferRender: true,
            columns: [
                {
                    data: 'code',
                    render: function (d) {
                        return '<strong>' + esc(d) + '</strong>';
                    }
                },
                { data: 'name', render: function (d) { return esc(d); } },
                { data: 'wbs', render: function (d) { return esc(d); } },
                { data: 'type', render: function (d) { return esc(d); } },
                {
                    data: 'status',
                    render: function (d) {
                        const c = statusClass(d);
                        return '<span class="status-badge ' + c + '">' + esc(d) + '</span>';
                    }
                },
                {
                    data: 'duration',
                    render: function (d) { return esc(d) + 'd'; }
                },
                {
                    data: 'float',
                    render: function (d, t, row) {
                        return (row.critical ? '🔴 ' : '') + esc(d) + 'd';
                    }
                },
                { data: 'start', render: function (d) { return esc(d); } },
                { data: 'finish', render: function (d) { return esc(d); } }
            ],
            createdRow: function (row, data) {
                if (data.critical) row.classList.add('critical-row');
            }
        });
    } else {
        tbody.innerHTML = '';
        rows.forEach(function (act) {
            const tr = document.createElement('tr');
            if (act.critical) tr.className = 'critical-row';
            const sc = statusClass(act.status);
            tr.innerHTML =
                '<td><strong data-activity-code="' + esc(act.code) + '">' + esc(act.code) + '</strong></td>' +
                '<td>' + esc(act.name) + '</td>' +
                '<td>' + esc(act.wbs) + '</td>' +
                '<td>' + esc(act.type) + '</td>' +
                '<td><span class="status-badge ' + sc + '">' + esc(act.status) + '</span></td>' +
                '<td>' + esc(act.duration) + 'd</td>' +
                '<td>' + (act.critical ? '🔴 ' : '') + esc(act.float) + 'd</td>' +
                '<td>' + esc(act.start) + '</td>' +
                '<td>' + esc(act.finish) + '</td>';
            tbody.appendChild(tr);
        });
    }

    if (note) {
        console.info(note);
    }
}

function renderCriticalTable(criticals) {
    criticalDataTable = destroyDataTable(criticalDataTable, '#criticalTable');

    const rows = Array.isArray(criticals) ? criticals : [];

    if (window.jQuery && $.fn.DataTable) {
        criticalDataTable = $('#criticalTable').DataTable({
            data: rows,
            pageLength: 25,
            deferRender: true,
            columns: [
                {
                    data: 'code',
                    render: function (d) {
                        return '<strong>' + esc(d) + '</strong>';
                    }
                },
                { data: 'name', render: function (d) { return esc(d); } },
                { data: 'wbs', render: function (d) { return esc(d); } },
                {
                    data: 'duration',
                    render: function (d) { return esc(d) + 'd'; }
                },
                {
                    data: 'float',
                    render: function (d) { return '🔴 ' + esc(d) + 'd'; }
                },
                {
                    data: 'status',
                    render: function (d) {
                        const c = statusClass(d);
                        return '<span class="status-badge ' + c + '">' + esc(d) + '</span>';
                    }
                },
                { data: 'start', render: function (d) { return esc(d); } },
                { data: 'finish', render: function (d) { return esc(d); } }
            ],
            createdRow: function (row) {
                row.classList.add('critical-row');
            }
        });
    } else {
        const tbody = document.querySelector('#criticalTable tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        rows.forEach(function (act) {
            const tr = document.createElement('tr');
            tr.className = 'critical-row';
            const sc = statusClass(act.status);
            tr.innerHTML =
                '<td><strong data-activity-code="' + esc(act.code) + '">' + esc(act.code) + '</strong></td>' +
                '<td>' + esc(act.name) + '</td>' +
                '<td>' + esc(act.wbs) + '</td>' +
                '<td>' + esc(act.duration) + 'd</td>' +
                '<td>🔴 ' + esc(act.float) + 'd</td>' +
                '<td><span class="status-badge ' + sc + '">' + esc(act.status) + '</span></td>' +
                '<td>' + esc(act.start) + '</td>' +
                '<td>' + esc(act.finish) + '</td>';
            tbody.appendChild(tr);
        });
    }
}

// ═══════════════════════════════════════════
// TABS
// ═══════════════════════════════════════════

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(function (btn) {
        btn.classList.remove('active');
    });
    const activeBtn = document.querySelector('[data-tab="' + tabName + '"]');
    if (activeBtn) activeBtn.classList.add('active');

    document.querySelectorAll('.tab-content').forEach(function (content) {
        content.classList.remove('active');
    });
    const panel = document.getElementById('tab-' + tabName);
    if (panel) panel.classList.add('active');
}
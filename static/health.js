/*
    ADVANCED HEALTH DASHBOARD (Patched + AI Narrative Support)
    ==========================================================
*/

let healthData = null;
let currentStandard = 'all';
let searchTimer = null;

const MAX_ITEMS_UI = 200;
const MAX_TOP_ACTIONS_UI = 15;

const SEVERITY_LEVELS = {
    critical: ['critical'],
    high: ['critical', 'high'],
    medium: ['critical', 'high', 'medium'],
    all: ['critical', 'high', 'medium', 'low', 'info']
};

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

function severityAllowed(sev, filter) {
    const f = (filter || 'all').toLowerCase();
    const list = SEVERITY_LEVELS[f] || SEVERITY_LEVELS.all;
    return list.indexOf((sev || 'low').toLowerCase()) >= 0;
}

function getSelectedSeverity() {
    const el = document.getElementById('excelSeverityFilter');
    return el && el.value ? el.value.toLowerCase() : 'all';
}

function getFilterValue(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    return el.value != null ? el.value : fallback;
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

async function downloadFile(url, defaultName, btn) {
    const label = btn ? btn.textContent : '';
    try {
        if (btn) {
            btn.disabled = true;
            btn.textContent = '⏳ Working…';
        }
        const res = await fetch(url);
        if (!res.ok) {
            let msg = 'Download failed (' + res.status + ')';
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
        alert('❌ ' + (err.message || 'Download failed'));
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = label;
        }
    }
}

function showHealthError(msg) {
    const loading = document.getElementById('loadingMessage');
    const content = document.getElementById('healthContent');
    if (content) content.style.display = 'none';
    if (loading) {
        loading.style.display = 'block';
        loading.innerHTML =
            '<p style="color:#dc2626;">❌ ' + esc(msg) + '</p>' +
            '<p style="color:#64748b;margin-top:0.5rem;">Upload an XER on the Dashboard first.</p>' +
            '<a href="/" class="btn btn-primary" style="margin-top:1rem;display:inline-flex;">← Dashboard</a>';
    }
}

function itemRowHtml(item) {
    const code = esc(item && item.code);
    const name = item && item.name ? ' - ' + esc(item.name) : '';
    const wbs = item && item.wbs
        ? ' <span style="color:#64748b;">(' + esc(item.wbs) + ')</span>'
        : '';
    return (
        '<div style="font-size:0.82rem;padding:0.15rem 0;border-bottom:1px solid #f1f5f9;">' +
        '<strong data-activity-code="' + code + '">' + code + '</strong>' + name + wbs +
        '</div>'
    );
}

function renderItemsBlock(items, summaryLabel) {
    const list = Array.isArray(items) ? items : [];
    if (!list.length) {
        return (
            '<div style="margin-top:0.4rem;font-size:0.82rem;color:#64748b;">' +
            'No activity list available for this metric.</div>'
        );
    }
    const shown = list.slice(0, MAX_ITEMS_UI);
    const more = list.length - shown.length;
    let html =
        '<details style="margin-top:0.5rem;">' +
        '<summary style="cursor:pointer;color:#1d4ed8;font-size:0.85rem;">' +
        esc(summaryLabel || 'Show affected items') + ' (' + list.length + ')</summary>' +
        '<div style="margin-top:0.4rem;background:#fff;border:1px solid #e2e8f0;' +
        'border-radius:6px;padding:0.6rem;max-height:280px;overflow:auto;">';

    shown.forEach(function (item) { html += itemRowHtml(item); });
    if (more > 0) {
        html +=
            '<div style="font-size:0.82rem;color:#64748b;padding-top:0.35rem;">' +
            '… and ' + more + ' more (see Excel export for full list)</div>';
    }
    html += '</div></details>';
    return html;
}

function statusIcon(status) {
    const map = { pass: '✅', fail: '❌', info: 'ℹ️', na: '⚪' };
    return map[status] || 'ℹ️';
}

// ═══════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
    try {
        const params = new URLSearchParams(window.location.search || '');
        const std = params.get('standard');
        if (std) currentStandard = std;
    } catch (e) { /* ignore */ }

    wireFilterListeners();
    loadHealthData(currentStandard);
});

function wireFilterListeners() {
    const search = document.getElementById('filterSearch');
    if (search) {
        search.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(function () { applyFilter(); }, 250);
        });
    }

    ['filterStatus', 'filterSeverity'].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', applyFilter);
    });

    const sevExport = document.getElementById('excelSeverityFilter');
    if (sevExport) {
        sevExport.addEventListener('change', function () { renderTopActions(); });
    }

    document.querySelectorAll('.std-select-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const std = btn.getAttribute('data-std');
            if (std) selectStandard(std);
        });
    });
}

// ═══════════════════════════════════════════
// DATA LOAD
// ═══════════════════════════════════════════

function selectStandard(standard) {
    currentStandard = standard || 'all';
    document.querySelectorAll('.std-select-btn').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-std') === currentStandard);
    });
    loadHealthData(currentStandard);
}

async function loadHealthData(standard) {
    const loading = document.getElementById('loadingMessage');
    const content = document.getElementById('healthContent');
    if (loading) {
        loading.style.display = 'block';
        loading.innerHTML = '<p>Loading health analytics…</p>';
    }
    if (content) content.style.display = 'none';

    const std = standard || 'all';

    try {
        const response = await safeFetchJSON('/api/health-data?standard=' + encodeURIComponent(std));
        healthData = response.data || {};
        currentStandard = std;
        renderDashboard();
    } catch (err) {
        console.error(err);
        showHealthError(err.message || 'Failed to load health data');
    }
}

// ═══════════════════════════════════════════
// DASHBOARD RENDER
// ═══════════════════════════════════════════

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value == null ? '' : String(value);
}

function renderDashboard() {
    const loading = document.getElementById('loadingMessage');
    const content = document.getElementById('healthContent');
    if (loading) loading.style.display = 'none';
    if (content) content.style.display = 'block';

    if (!healthData) { showHealthError('No health data returned'); return; }

    setText('overallScore', healthData.overall_score);
    setText('totalChecks', healthData.total_checks);
    setText('passedChecks', healthData.passed_checks);
    setText('failedChecks', healthData.failed_checks);
    setText('criticalFailures', healthData.critical_failures);

    const stdName = currentStandard === 'all' ? 'All Standards' : currentStandard;
    setText('reportTitle', currentStandard === 'all' ? 'Comprehensive Assessment' : stdName + ' Assessment');
    setText('reportSubtitle',
        currentStandard === 'all'
            ? 'Analysis based on all applicable standards'
            : 'Detailed analysis of ' + stdName + ' compliance'
    );

    renderStandardsScores();
    renderTopActions();
    renderDetailedResults();
}

function renderStandardsScores() {
    const container = document.getElementById('scoreGrid');
    if (!container) return;
    container.innerHTML = '';

    const scores = healthData.standard_scores || {};
    const keys = Object.keys(scores);
    if (!keys.length) {
        container.innerHTML = '<p style="color:#64748b;">No standards evaluated.</p>';
        return;
    }

    keys.forEach(function (std) {
        const data = scores[std] || {};
        const div = document.createElement('div');
        div.className = 'std-score-card ' + esc(data.color || '');
        div.style.cursor = 'pointer';

        const failedLine = data.failed > 0
            ? '<span style="color:#dc2626;">' + esc(data.failed) + ' failed</span>'
            : 'All passed ✅';

        div.innerHTML =
            '<div style="font-size:0.85rem;color:#64748b;font-weight:600;">' + esc(std) + '</div>' +
            '<div class="std-score-value">' + esc(data.score) + '</div>' +
            '<div class="std-score-grade grade-' + esc(data.grade) + '">Grade ' + esc(data.grade) + '</div>' +
            '<div class="std-score-details">' +
            esc(data.passed) + '/' + esc(data.total_checks) + ' passed<br>' + failedLine +
            '</div>';

        div.addEventListener('click', function () { selectStandard(std); });
        container.appendChild(div);
    });
}

function renderTopActions() {
    const container = document.getElementById('topActionsList');
    const section = document.getElementById('topActionsSection');
    if (!container || !section) return;

    const raw = (healthData && healthData.top_actions) || [];
    const sev = getSelectedSeverity();
    const list = raw
        .filter(function (a) { return severityAllowed(a.severity, sev); })
        .slice(0, MAX_TOP_ACTIONS_UI);

    if (!list.length) {
        if (!raw.length) { section.style.display = 'none'; return; }
        section.style.display = 'block';
        container.innerHTML =
            '<p style="color:#64748b;padding:0.5rem 0;">No top actions match severity filter: ' +
            esc(sev.toUpperCase()) + '.</p>';
        return;
    }

    section.style.display = 'block';
    container.innerHTML = '';

    list.forEach(function (action, idx) {
        const severity = (action.severity || 'low').toLowerCase();
        const severityColor = {
            critical: '#7f1d1d', high: '#dc2626', medium: '#f59e0b', low: '#64748b', info: '#64748b'
        }[severity] || '#64748b';

        const failedItems = action.failed_items || [];
        const itemsHtml = renderItemsBlock(failedItems, 'Show affected activities');

        let metricText;
        if (action.count !== undefined && action.count !== null) {
            metricText = esc(action.count) + ' activities affected (' + esc(action.percentage || 0) + '%)';
        } else if (action.value !== undefined && action.value !== null) {
            metricText = 'Value: ' + esc(action.value);
        } else {
            metricText = 'Review required';
        }

        const div = document.createElement('div');
        div.className = 'action-item';
        div.innerHTML =
            '<div class="action-priority" style="background:' + severityColor + ';">' + (idx + 1) + '</div>' +
            '<div style="flex:1;">' +
            '<div style="font-weight:600;">' +
            esc(action.id || '') + ': ' + esc(action.name || '') + ' ' +
            '<span class="badge badge-' + esc(severity) + '">' + esc(severity.toUpperCase()) + '</span> ' +
            '<span class="badge badge-std">' + esc(action.standard || '') + '</span>' +
            '</div>' +
            '<div style="font-size:0.85rem;color:#64748b;margin-top:0.25rem;">' +
            (action.category ? 'Category: ' + esc(action.category) + ' | ' : '') + metricText +
            '</div>' +
            (action.recommendation
                ? '<div class="recommendation-box">💡 ' + esc(action.recommendation) + '</div>'
                : '') +
            itemsHtml + '</div>';

        container.appendChild(div);
    });
}

function renderDetailedResults() {
    const container = document.getElementById('detailedResults');
    if (!container) return;
    container.innerHTML = '';

    if (!healthData || !healthData.standards) {
        container.innerHTML = '<p style="text-align:center;padding:2rem;color:#64748b;">No detailed results.</p>';
        return;
    }

    const filterStatus = getFilterValue('filterStatus', 'all');
    const filterSeverity = getFilterValue('filterSeverity', 'all').toLowerCase();
    const filterSearch = String(getFilterValue('filterSearch', '')).toLowerCase();

    const frag = document.createDocumentFragment();
    let sections = 0;

    Object.keys(healthData.standards).forEach(function (stdName) {
        const stdData = healthData.standards[stdName] || {};
        const categories = stdData.categories || [];

        categories.forEach(function (category) {
            const checks = category.checks || [];
            const filteredChecks = checks.filter(function (check) {
                if (filterStatus !== 'all' && check.status !== filterStatus) return false;
                if (filterSeverity !== 'all' && !severityAllowed(check.severity, filterSeverity)) return false;
                if (filterSearch) {
                    const name = String(check.name || '').toLowerCase();
                    const id = String(check.id || '').toLowerCase();
                    if (name.indexOf(filterSearch) < 0 && id.indexOf(filterSearch) < 0) return false;
                }
                return true;
            });

            if (!filteredChecks.length) return;

            sections += 1;
            const section = document.createElement('div');
            section.className = 'category-section';

            const passed = filteredChecks.filter(function (c) { return c.passed; }).length;
            const failed = filteredChecks.filter(function (c) { return c.status === 'fail'; }).length;

            section.innerHTML =
                '<div class="category-header">' +
                '<div><h3>' + esc(category.name) + '</h3>' +
                '<div style="font-size:0.85rem;color:#64748b;">' + esc(stdName) + '</div></div>' +
                '<div class="category-stats">' +
                passed + '/' + filteredChecks.length + ' passed' +
                (failed > 0 ? ' | <span style="color:#dc2626;">' + failed + ' failed</span>' : '') +
                '</div></div>' +
                '<div class="checks-list"></div>';

            const checksList = section.querySelector('.checks-list');
            filteredChecks.forEach(function (check) { checksList.appendChild(createCheckItem(check)); });
            frag.appendChild(section);
        });
    });

    if (!sections) {
        container.innerHTML = '<p style="text-align:center;padding:2rem;color:#64748b;">No checks match your filter criteria.</p>';
        return;
    }
    container.appendChild(frag);
}

function createCheckItem(check) {
    const div = document.createElement('div');
    const status = check.status || (check.passed ? 'pass' : 'fail');
    div.className = 'check-item ' + esc(status);

    const icon = statusIcon(status);
    const severity = (check.severity || 'low').toLowerCase();

    let details = '';
    if (check.value !== undefined && check.value !== null && check.value !== '') {
        details = '<strong>Value:</strong> ' + esc(check.value) + esc(check.unit || '');
    } else if (check.count !== undefined && check.count !== null) {
        details = '<strong>Count:</strong> ' + esc(check.count) + ' / ' + esc(check.total) + ' (' + esc(check.percentage) + '%)';
    }

    const itemsHtml = (check.failed_items && check.failed_items.length)
        ? renderItemsBlock(check.failed_items, 'Show affected items')
        : '';

    div.innerHTML =
        '<div class="check-icon">' + icon + '</div>' +
        '<div class="check-content">' +
        '<div class="check-title">' +
        '<span>' + esc(check.id) + ': ' + esc(check.name) + '</span> ' +
        '<span class="badge badge-' + esc(severity) + '">' + esc(severity) + '</span> ' +
        '<span class="badge badge-std">' + esc(check.standard) + '</span>' +
        '</div>' +
        '<div style="font-size:0.85rem;color:#64748b;margin-bottom:0.5rem;">' + esc(check.description) + '</div>' +
        '<div style="font-size:0.85rem;">' + details +
        (check.threshold ? ' | <strong>Threshold:</strong> ' + esc(check.threshold) : '') +
        '</div>' +
        (check.recommendation ? '<div class="recommendation-box">💡 ' + esc(check.recommendation) + '</div>' : '') +
        itemsHtml + '</div>';

    return div;
}

function applyFilter() { renderDetailedResults(); }

// ═══════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════

function downloadPDF(ev) {
    const severity = getSelectedSeverity();
    const btn = ev && ev.currentTarget ? ev.currentTarget : null;
    const url = '/api/executive-pdf?standard=' + encodeURIComponent(currentStandard) + '&severity=' + encodeURIComponent(severity);
    downloadFile(url, 'executive_report.pdf', btn);
}

function downloadActionsPDF(ev) {
    const severity = getSelectedSeverity();
    const btn = ev && ev.currentTarget ? ev.currentTarget : null;
    const url = '/api/actions-pdf?standard=' + encodeURIComponent(currentStandard) + '&severity=' + encodeURIComponent(severity);
    downloadFile(url, 'action_list.pdf', btn);
}

function downloadActionsExcel(ev) {
    const severity = getSelectedSeverity();
    const btn = ev && ev.currentTarget ? ev.currentTarget : null;
    const url = '/api/actions-excel?standard=' + encodeURIComponent(currentStandard) + '&severity=' + encodeURIComponent(severity);
    downloadFile(url, 'health_top_actions.xlsx', btn);
}

// ═══════════════════════════════════════════
// AI EXECUTIVE NARRATIVE
// ═══════════════════════════════════════════

async function fetchAINarrative(forceRefresh) {
    const body = document.getElementById('aiNarrativeBody');
    const methodEl = document.getElementById('aiNarrativeMethod');
    if (!body) return;

    body.innerHTML = '<p style="color:var(--color-muted);">⏳ Synthesizing executive briefing from health, EVM, and variance data...</p>';
    if (methodEl) methodEl.textContent = '';

    try {
        const res = await fetch('/api/ai-narrative');
        const data = await res.json().catch(function () { return {}; });

        if (!res.ok || data.error) {
            throw new Error(data.error || 'Failed to generate narrative');
        }

        const narrativeText = (data.data && data.data.narrative) || '';
        const method = (data.data && data.data.method) || 'Engine';

        if (methodEl) {
            methodEl.innerHTML = '<span>✨ Generated via: <strong>' + esc(method) + '</strong></span>';
        }

        // Convert basic markdown to HTML (with escape safety)
        let formattedHtml = esc(narrativeText)
            .replace(/^### (.*)$/gm, '<h3>$1</h3>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n- /g, '<br>• ')
            .replace(/^- /gm, '• ');

        body.innerHTML = formattedHtml;
    } catch (err) {
        body.innerHTML = '<p style="color:var(--color-danger);">❌ ' + esc(err.message) + '</p>';
    }
}

// Back-compat exports
window.downloadPDF = downloadPDF;
window.downloadActionsPDF = downloadActionsPDF;
window.downloadActionsExcel = downloadActionsExcel;
window.selectStandard = selectStandard;
window.applyFilter = applyFilter;
window.loadHealthData = loadHealthData;
window.fetchAINarrative = fetchAINarrative;

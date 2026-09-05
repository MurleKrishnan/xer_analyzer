/*
    MULTI-PERIOD TREND ANALYSIS PAGE LOGIC
    ========================================
*/

let selectedFiles = [];
let trendData = null;
let finishTrendChart = null;
let healthTrendChart = null;
let criticalTrendChart = null;
let evmTrendChart = null;
let activityTrendChart = null;

const MAX_UPLOAD_MB = 1000;
const MAX_FILES = 12;

// ═══════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════

function esc(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtNum(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return '—';
    return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtDelta(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return '—';
    if (n === 0) return '0d';
    return (n > 0 ? '+' : '') + n + 'd';
}

async function safeFetchJSON(url, options) {
    const res = await fetch(url, options || {});
    let data = {};
    try { data = await res.json(); }
    catch (e) {
        if (!res.ok) throw new Error('Request failed (' + res.status + ')');
        throw new Error('Invalid JSON response from server');
    }
    if (!res.ok || data.error) {
        throw new Error(data.error || ('Request failed (' + res.status + ')'));
    }
    return data;
}

// ═══════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
    setupFileHandler();
    setupButtons();
    checkExistingTrend();
});

function setupFileHandler() {
    const dropZone = document.getElementById('trendDropZone');
    const input = document.getElementById('trendFileInput');
    if (!dropZone || !input) return;

    dropZone.addEventListener('click', function () { input.click(); });
    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', function () { dropZone.classList.remove('dragover'); });
    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFilesSelected(Array.from(e.dataTransfer.files));
        }
    });
    input.addEventListener('change', function (e) {
        if (e.target.files && e.target.files.length > 0) {
            handleFilesSelected(Array.from(e.target.files));
        }
    });
}

function setupButtons() {
    const analyzeBtn = document.getElementById('analyzeTrendBtn');
    if (analyzeBtn) analyzeBtn.addEventListener('click', runTrendAnalysis);
    
    const resetBtn = document.getElementById('resetTrendBtn');
    if (resetBtn) resetBtn.addEventListener('click', resetSelection);
}

function handleFilesSelected(files) {
    const validFiles = files.filter(function (f) {
        if (!f.name.toLowerCase().match(/\.(xer|xml)$/i)) {
            alert('❌ Skipping ' + f.name + ' - not a .xer or .xml file');
            return false;
        }
        if (f.size > MAX_UPLOAD_MB * 1024 * 1024) {
            alert('❌ ' + f.name + ' exceeds ' + MAX_UPLOAD_MB + ' MB limit');
            return false;
        }
        return true;
    });
    
    // Merge with existing selection, avoid duplicates by name
    const existingNames = new Set(selectedFiles.map(function (f) { return f.name; }));
    validFiles.forEach(function (f) {
        if (!existingNames.has(f.name)) {
            selectedFiles.push(f);
        }
    });
    
    if (selectedFiles.length > MAX_FILES) {
        alert('⚠️ Maximum ' + MAX_FILES + ' files supported. Trimming to first ' + MAX_FILES + '.');
        selectedFiles = selectedFiles.slice(0, MAX_FILES);
    }
    
    updateSelectedFilesUI();
}

function updateSelectedFilesUI() {
    const list = document.getElementById('selectedFilesList');
    const dropZone = document.getElementById('trendDropZone');
    const analyzeBtn = document.getElementById('analyzeTrendBtn');
    
    if (!selectedFiles.length) {
        list.style.display = 'none';
        dropZone.classList.remove('has-files');
        analyzeBtn.disabled = true;
        return;
    }
    
    list.style.display = 'grid';
    dropZone.classList.add('has-files');
    analyzeBtn.disabled = selectedFiles.length < 2;
    
    list.innerHTML = selectedFiles.map(function (f, idx) {
        return (
            '<div class="selected-file-chip">' +
            '<span class="num">' + (idx + 1) + '</span>' +
            '<span class="name" title="' + esc(f.name) + '">' + esc(f.name) + '</span>' +
            '<button onclick="removeFile(' + idx + ')" ' +
            'style="background:none;border:none;color:#dc2626;cursor:pointer;font-size:1.1rem;padding:0 0.25rem;" ' +
            'title="Remove">✕</button>' +
            '</div>'
        );
    }).join('');
}

function removeFile(idx) {
    selectedFiles.splice(idx, 1);
    updateSelectedFilesUI();
}

function resetSelection() {
    selectedFiles = [];
    const input = document.getElementById('trendFileInput');
    if (input) input.value = '';
    updateSelectedFilesUI();
}

async function runTrendAnalysis() {
    if (selectedFiles.length < 2) {
        alert('❌ Please select at least 2 Schedule files.');
        return;
    }
    
    const uploadSec = document.getElementById('uploadSection');
    const loadingSec = document.getElementById('loadingSection');
    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'block';
    
    const formData = new FormData();
    selectedFiles.forEach(function (f) {
        formData.append('files', f);
    });
    
    try {
        const response = await safeFetchJSON('/api/trend-upload', {
            method: 'POST',
            body: formData,
        });
        trendData = response.data;
        renderTrendResults();
    } catch (err) {
        console.error('Trend analysis error:', err);
        alert('❌ ' + (err.message || 'Trend analysis failed'));
        if (loadingSec) loadingSec.style.display = 'none';
        if (uploadSec) uploadSec.style.display = 'block';
    }
}

async function checkExistingTrend() {
    try {
        const res = await fetch('/api/trend-data');
        const data = await res.json().catch(function () { return {}; });
        if (res.ok && data.has_data) {
            trendData = data.data;
            renderTrendResults();
        }
    } catch (e) { console.warn('No existing trend', e); }
}

function renderTrendResults() {
    const uploadSec = document.getElementById('uploadSection');
    const loadingSec = document.getElementById('loadingSection');
    const resultsSec = document.getElementById('resultsSection');
    
    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'none';
    if (resultsSec) resultsSec.style.display = 'block';
    
    if (!trendData) return;
    
    const periodCount = document.getElementById('periodCount');
    const analyzedAt = document.getElementById('analyzedAt');
    if (periodCount) periodCount.textContent = trendData.period_count || 0;
    if (analyzedAt) analyzedAt.textContent = trendData.analyzed_at || '';
    
    renderSummaryCards();
    renderFinishTrendChart();
    renderHealthTrendChart();
    renderCriticalTrendChart();
    renderEvmTrendChart();
    renderActivityTrendChart();
    renderChronicCritical();
}

function renderSummaryCards() {
    const container = document.getElementById('trendSummary');
    if (!container) return;
    
    const slippage = trendData.slippage_trend || {};
    const slipDays = slippage.slippage_days || [];
    const totalSlip = slipDays.length ? slipDays[slipDays.length - 1] : 0;
    
    const health = trendData.health_trend || {};
    const scores = (health.scores || []).filter(function (s) { return s != null; });
    const healthChange = scores.length >= 2 ? (scores[scores.length - 1] - scores[0]).toFixed(1) : 'N/A';
    
    const critical = trendData.critical_trend || {};
    const critCounts = critical.critical_count || [];
    const critChange = critCounts.length >= 2 ? (critCounts[critCounts.length - 1] - critCounts[0]) : 0;
    
    const evm = trendData.evm_trend || {};
    const spis = (evm.spi || []).filter(function (v) { return v != null && v !== 0; });
    const spiChange = spis.length >= 2 ? (spis[spis.length - 1] - spis[0]).toFixed(3) : 'N/A';
    
    const chronic = trendData.chronic_critical || [];
    
    const cards = [
        {
            value: fmtDelta(totalSlip),
            label: 'Total Slippage vs Period 1',
            cls: totalSlip > 0 ? 'slipped' : (totalSlip < 0 ? 'improved' : ''),
        },
        {
            value: healthChange !== 'N/A' ? (healthChange > 0 ? '+' : '') + healthChange : 'N/A',
            label: 'Health Score Change',
            cls: healthChange !== 'N/A' && parseFloat(healthChange) < 0 ? 'slipped' : (parseFloat(healthChange) > 0 ? 'improved' : ''),
        },
        {
            value: (critChange > 0 ? '+' : '') + critChange,
            label: 'Critical Activity Change',
            cls: critChange > 0 ? 'slipped' : (critChange < 0 ? 'improved' : ''),
        },
        {
            value: spiChange !== 'N/A' ? (spiChange > 0 ? '+' : '') + spiChange : 'N/A',
            label: 'SPI Change',
            cls: spiChange !== 'N/A' && parseFloat(spiChange) < 0 ? 'slipped' : (parseFloat(spiChange) > 0 ? 'improved' : ''),
        },
        {
            value: chronic.length,
            label: 'Chronic Critical Activities',
            cls: chronic.length > 10 ? 'slipped' : (chronic.length > 0 ? 'warning' : 'improved'),
        },
    ];
    
    container.innerHTML = cards.map(function (c) {
        return (
            '<div class="trend-summary-card ' + esc(c.cls) + '">' +
            '<div class="value">' + esc(c.value) + '</div>' +
            '<div class="label">' + esc(c.label) + '</div>' +
            '</div>'
        );
    }).join('');
}

function renderFinishTrendChart() {
    const canvas = document.getElementById('finishTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (finishTrendChart) { finishTrendChart.destroy(); finishTrendChart = null; }
    
    const slippage = trendData.slippage_trend || {};
    const labels = slippage.labels || [];
    const slipDays = slippage.slippage_days || [];
    const finishes = slippage.project_finishes || [];
    
    if (!labels.length) return;
    
    finishTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Slippage from Period 1 (days)',
                data: slipDays,
                borderColor: '#dc2626',
                backgroundColor: 'rgba(220, 38, 38, 0.15)',
                borderWidth: 3,
                fill: true,
                tension: 0.2,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBackgroundColor: '#dc2626',
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const idx = ctx.dataIndex;
                            const days = ctx.parsed.y;
                            const finish = finishes[idx] || '—';
                            return [
                                'Slippage: ' + fmtDelta(days),
                                'Project Finish: ' + finish
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: { callback: function (v) { return fmtDelta(v); } },
                    grid: { color: function (ctx) { return ctx.tick.value === 0 ? '#000' : '#e2e8f0'; } }
                }
            }
        }
    });
}

function renderHealthTrendChart() {
    const canvas = document.getElementById('healthTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (healthTrendChart) { healthTrendChart.destroy(); healthTrendChart = null; }
    
    const health = trendData.health_trend || {};
    
    healthTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: health.labels || [],
            datasets: [
                {
                    label: 'Health Score',
                    data: health.scores || [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.15)',
                    borderWidth: 3, fill: true, tension: 0.2,
                    pointRadius: 5, pointHoverRadius: 7,
                },
                {
                    label: 'Pass Rate (%)',
                    data: health.pass_rates || [],
                    borderColor: '#10b981',
                    borderDash: [5, 5], borderWidth: 2, fill: false, tension: 0.2,
                    pointRadius: 4,
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + '%'; } } } }
        }
    });
}

function renderCriticalTrendChart() {
    const canvas = document.getElementById('criticalTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (criticalTrendChart) { criticalTrendChart.destroy(); criticalTrendChart = null; }
    
    const critical = trendData.critical_trend || {};
    
    criticalTrendChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: critical.labels || [],
            datasets: [
                {
                    label: 'Critical (TF ≤ 0)',
                    data: critical.critical_count || [],
                    backgroundColor: '#dc2626',
                },
                {
                    label: 'Longest Path',
                    data: critical.longest_path_count || [],
                    backgroundColor: '#7c3aed',
                },
                {
                    label: 'Negative Float',
                    data: critical.negative_float_count || [],
                    backgroundColor: '#f59e0b',
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function renderEvmTrendChart() {
    const canvas = document.getElementById('evmTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (evmTrendChart) { evmTrendChart.destroy(); evmTrendChart = null; }
    
    const evm = trendData.evm_trend || {};
    
    evmTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: evm.labels || [],
            datasets: [
                {
                    label: 'SPI',
                    data: evm.spi || [],
                    borderColor: '#3b82f6',
                    borderWidth: 3, fill: false, tension: 0.2,
                    pointRadius: 5,
                },
                {
                    label: 'CPI',
                    data: evm.cpi || [],
                    borderColor: '#10b981',
                    borderWidth: 3, fill: false, tension: 0.2,
                    pointRadius: 5,
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                annotation: {
                    annotations: {
                        line1: { type: 'line', yMin: 1, yMax: 1, borderColor: '#000', borderWidth: 1, borderDash: [3, 3] }
                    }
                }
            },
            scales: {
                y: {
                    min: 0.7, max: 1.3,
                    ticks: { callback: function (v) { return v.toFixed(2); } }
                }
            }
        }
    });
}

function renderActivityTrendChart() {
    const canvas = document.getElementById('activityTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (activityTrendChart) { activityTrendChart.destroy(); activityTrendChart = null; }
    
    const activity = trendData.activity_trend || {};
    
    activityTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: activity.labels || [],
            datasets: [
                { label: 'Total Activities', data: activity.total || [], borderColor: '#3b82f6', borderWidth: 2, fill: false, tension: 0.2 },
                { label: 'Incomplete', data: activity.incomplete || [], borderColor: '#f59e0b', borderWidth: 2, fill: false, tension: 0.2 },
                { label: 'Completed', data: activity.completed || [], borderColor: '#10b981', borderWidth: 2, fill: false, tension: 0.2 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function renderChronicCritical() {
    const container = document.getElementById('chronicCriticalContent');
    if (!container) return;
    
    const chronic = trendData.chronic_critical || [];
    
    if (!chronic.length) {
        container.innerHTML = '<p style="text-align:center;padding:2rem;color:#64748b;">✅ No chronic critical activities detected!</p>';
        return;
    }
    
    let html = '<table class="chronic-table"><thead><tr>' +
        '<th>Activity Code</th><th>Name</th><th>WBS</th>' +
        '<th>Critical in Periods</th><th style="text-align:right;">Frequency</th>' +
        '</tr></thead><tbody>';
    
    chronic.slice(0, 50).forEach(function (c) {
        const isSevere = c.chronic_percentage >= 75;
        const badgeClass = isSevere ? 'chronic-badge severe' : 'chronic-badge';
        
        html += '<tr>' +
            '<td><strong data-activity-code="' + esc(c.code) + '">' + esc(c.code) + '</strong></td>' +
            '<td>' + esc(c.name) + '</td>' +
            '<td style="font-size:0.8rem;color:#64748b;">' + esc(c.wbs) + '</td>' +
            '<td style="font-size:0.75rem;">' + esc(c.critical_in_periods.join(', ')) + '</td>' +
            '<td style="text-align:right;">' +
            '<span class="' + badgeClass + '">' +
            c.critical_count + ' / ' + trendData.period_count + ' (' + c.chronic_percentage + '%)' +
            '</span></td>' +
            '</tr>';
    });
    
    if (chronic.length > 50) {
        html += '<tr><td colspan="5" style="text-align:center;padding:1rem;color:#64748b;">' +
            '… and ' + (chronic.length - 50) + ' more chronic activities</td></tr>';
    }
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

async function resetTrends() {
    try {
        await fetch('/api/trend-reset', { method: 'POST' });
    } catch (e) {}
    
    trendData = null;
    selectedFiles = [];
    
    if (finishTrendChart) { finishTrendChart.destroy(); finishTrendChart = null; }
    if (healthTrendChart) { healthTrendChart.destroy(); healthTrendChart = null; }
    if (criticalTrendChart) { criticalTrendChart.destroy(); criticalTrendChart = null; }
    if (evmTrendChart) { evmTrendChart.destroy(); evmTrendChart = null; }
    if (activityTrendChart) { activityTrendChart.destroy(); activityTrendChart = null; }
    
    const uploadSec = document.getElementById('uploadSection');
    const resultsSec = document.getElementById('resultsSection');
    if (uploadSec) uploadSec.style.display = 'block';
    if (resultsSec) resultsSec.style.display = 'none';
    
    updateSelectedFilesUI();
}

window.removeFile = removeFile;
window.resetTrends = resetTrends;

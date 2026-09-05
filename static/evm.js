/*
    EVM PAGE LOGIC + RESOURCE ANALYTICS (Phase 1, Step 3)
    ======================================================
*/

let scurveChart = null;
let monthlyUnitsChart = null;
let monthlyCostChart = null;
let cumulativeUnitsChart = null;

document.addEventListener('DOMContentLoaded', function () {
    loadEVM();
});

function esc(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function statusClass(statusObj) {
    const st = (statusObj && statusObj.status) ? String(statusObj.status) : 'neutral';
    if (st === 'good' || st === 'warning' || st === 'bad') return st;
    return 'neutral';
}

function fmtMoney(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return '—';
    try {
        return new Intl.NumberFormat('en-US', {
            style: 'currency', currency: 'USD', maximumFractionDigits: 0
        }).format(n);
    } catch (e) {
        return '$' + Math.round(n).toLocaleString('en-US');
    }
}

function fmtNum(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return '—';
    return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtIndex(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return 'N/A';
    return n.toFixed(3);
}

function fmtPct(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return '—';
    return n.toFixed(1) + '%';
}

function normalizeSeries(arr) {
    return (arr || []).map(function (v) {
        if (v === null || v === undefined) return null;
        const n = Number(v);
        return Number.isFinite(n) ? n : null;
    });
}

function showEvmError(msg) {
    const loading = document.getElementById('loadingMessage');
    const content = document.getElementById('evmContent');
    if (content) content.style.display = 'none';
    if (loading) {
        loading.style.display = 'block';
        loading.innerHTML =
            '<div style="text-align:center;padding:2rem;">' +
            '<p style="color:#dc2626;">❌ ' + esc(msg) + '</p>' +
            '<p style="color:#64748b;margin-top:0.5rem;">Upload an XER on the Dashboard first.</p>' +
            '<a href="/" class="btn btn-primary" style="margin-top:1rem;display:inline-flex;">← Dashboard</a>' +
            '</div>';
    }
}

async function loadEVM() {
    const loading = document.getElementById('loadingMessage');
    if (loading) {
        loading.style.display = 'block';
        loading.innerHTML = '<p style="text-align:center;padding:2rem;">Loading EVM data...</p>';
    }

    try {
        const res = await fetch('/api/evm-data');
        let response = {};
        try {
            response = await res.json();
        } catch (e) {
            throw new Error(res.ok ? 'Invalid JSON from server' : ('Request failed (' + res.status + ')'));
        }
        if (!res.ok || response.error) {
            throw new Error(response.error || ('Failed to load EVM (' + res.status + ')'));
        }
        const metrics = response.data && response.data.metrics;
        const scurve = (response.data && response.data.scurve) || {};
        if (!metrics) throw new Error('Invalid EVM payload (missing metrics)');

        if (loading) loading.style.display = 'none';
        const content = document.getElementById('evmContent');
        if (content) content.style.display = 'block';

        const fileName = document.getElementById('fileName');
        const dataDate = document.getElementById('dataDate');
        if (fileName) fileName.textContent = response.file_name || '—';
        if (dataDate) dataDate.textContent = metrics.data_date || '—';

        renderPerformanceMetrics(metrics);
        renderFinancialMetrics(metrics);
        renderScurve(scurve, metrics);
        
        // Load resource analytics after EVM
        loadResourceData(false);
    } catch (err) {
        console.error(err);
        showEvmError(err.message || 'Failed to load EVM data');
    }
}

function renderPerformanceMetrics(m) {
    const container = document.getElementById('performanceMetrics');
    if (!container) return;
    const sSt = statusClass(m.schedule_status);
    const cSt = statusClass(m.cost_status);
    const sText = (m.schedule_status && m.schedule_status.text) ? m.schedule_status.text : '';
    const cText = (m.cost_status && m.cost_status.text) ? m.cost_status.text : '';

    container.innerHTML =
        '<div class="metric-card ' + sSt + '">' +
        '<div class="metric-label">SPI (Schedule)</div>' +
        '<div class="metric-value">' + esc(fmtIndex(m.spi)) + '</div>' +
        '<div class="metric-subtitle status-' + sSt + '">' + esc(sText) + '</div></div>' +

        '<div class="metric-card ' + cSt + '">' +
        '<div class="metric-label">CPI (Cost)</div>' +
        '<div class="metric-value">' +
        (m.is_cost_loaded === false ? 'N/A*' : esc(fmtIndex(m.cpi))) +
        '</div>' +
        '<div class="metric-subtitle status-' + cSt + '">' + esc(cText) + '</div></div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">% Complete</div>' +
        '<div class="metric-value">' + esc(fmtPct(m.pct_complete)) + '</div>' +
        '<div class="metric-subtitle">Earned / BAC</div></div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">% Spent</div>' +
        '<div class="metric-value">' + esc(fmtPct(m.pct_spent)) + '</div>' +
        '<div class="metric-subtitle">AC / BAC</div></div>';
}

function renderFinancialMetrics(m) {
    const container = document.getElementById('financialMetrics');
    if (!container) return;
    const svClass = Number(m.sv) >= 0 ? 'good' : 'bad';
    const cvClass = Number(m.cv) >= 0 ? 'good' : 'bad';
    const vacClass = Number(m.vac) >= 0 ? 'good' : 'bad';
    const cvCardClass = m.is_cost_loaded === false ? 'neutral' : cvClass;
    const vacCardClass = m.is_cost_loaded === false ? 'neutral' : vacClass;

    container.innerHTML =
        '<div class="metric-card neutral"><div class="metric-label">BAC</div><div class="metric-value">' + esc(fmtMoney(m.bac)) + '</div><div class="metric-subtitle">Budget at Completion</div></div>' +
        '<div class="metric-card neutral"><div class="metric-label">PV</div><div class="metric-value">' + esc(fmtMoney(m.pv)) + '</div><div class="metric-subtitle">Planned Value</div></div>' +
        '<div class="metric-card neutral"><div class="metric-label">EV</div><div class="metric-value">' + esc(fmtMoney(m.ev)) + '</div><div class="metric-subtitle">Earned Value</div></div>' +
        '<div class="metric-card neutral"><div class="metric-label">AC</div><div class="metric-value">' + esc(fmtMoney(m.ac)) + '</div><div class="metric-subtitle">Actual Cost</div></div>' +
        '<div class="metric-card ' + svClass + '"><div class="metric-label">SV</div><div class="metric-value">' + esc(fmtMoney(m.sv)) + '</div><div class="metric-subtitle">EV − PV</div></div>' +
        '<div class="metric-card ' + cvCardClass + '"><div class="metric-label">CV</div><div class="metric-value">' + esc(fmtMoney(m.cv)) + '</div><div class="metric-subtitle">EV − AC</div></div>' +
        '<div class="metric-card neutral"><div class="metric-label">EAC</div><div class="metric-value">' + esc(fmtMoney(m.eac)) + '</div><div class="metric-subtitle">Est. at Completion</div></div>' +
        '<div class="metric-card neutral"><div class="metric-label">ETC</div><div class="metric-value">' + esc(fmtMoney(m.etc)) + '</div><div class="metric-subtitle">Est. to Complete</div></div>' +
        '<div class="metric-card ' + vacCardClass + '"><div class="metric-label">VAC</div><div class="metric-value">' + esc(fmtMoney(m.vac)) + '</div><div class="metric-subtitle">BAC − EAC</div></div>';
}

function renderScurve(scurveData, metrics) {
    const canvas = document.getElementById('scurveChart');
    const errNode = document.getElementById('scurveError');

    if (errNode) { errNode.style.display = 'none'; errNode.textContent = ''; }

    if (!scurveData || scurveData.error) {
        if (errNode) {
            errNode.style.display = 'block';
            errNode.textContent = (scurveData && scurveData.error) ? String(scurveData.error) : 'No S-curve data available';
        }
        if (scurveChart) { scurveChart.destroy(); scurveChart = null; }
        return;
    }
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (scurveChart) { scurveChart.destroy(); scurveChart = null; }

    const labels = scurveData.labels || [];
    const pv = normalizeSeries(scurveData.planned_value);
    const ev = normalizeSeries(scurveData.earned_value);
    const ac = normalizeSeries(scurveData.actual_cost);

    scurveChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'Planned Value (PV)', data: pv, borderColor: '#3b82f6', borderWidth: 2, fill: false, tension: 0.1, spanGaps: false, pointRadius: 0, pointHoverRadius: 4 },
                { label: 'Earned Value (EV)', data: ev, borderColor: '#10b981', borderWidth: 3, fill: false, tension: 0.1, spanGaps: false, pointRadius: 0, pointHoverRadius: 4 },
                { label: 'Actual Cost (AC)', data: ac, borderColor: '#dc2626', borderWidth: 2, borderDash: [5, 5], fill: false, tension: 0.1, spanGaps: false, pointRadius: 0, pointHoverRadius: 4 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const val = ctx.parsed && ctx.parsed.y;
                            if (val === null || val === undefined || !Number.isFinite(val)) return null;
                            return ctx.dataset.label + ': ' + fmtMoney(val);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: function (v) { return '$' + Number(v).toLocaleString('en-US'); } }
                },
                x: { ticks: { maxTicksLimit: 20, maxRotation: 45 } }
            }
        }
    });
}

// ═══════════════════════════════════════════
// 👷 RESOURCE ANALYTICS RENDERER
// ═══════════════════════════════════════════

async function loadResourceData(forceRefresh) {
    const section = document.getElementById('resourceSection');
    const errorBox = document.getElementById('resourceErrorBox');
    if (!section) return;

    section.style.display = 'block';

    try {
        const res = await fetch('/api/resource-data');
        const data = await res.json().catch(function () { return {}; });

        if (!res.ok || data.error) {
            throw new Error(data.error || 'Failed to load resource data');
        }

        const rData = data.data || {};

        if (rData.error) {
            if (errorBox) {
                errorBox.style.display = 'block';
                errorBox.textContent = '⚠️ ' + rData.error;
            }
            return;
        }

        if (errorBox) errorBox.style.display = 'none';

        renderResourceStats(rData);
        renderMonthlyUnitsChart(rData.monthly_units || {});
        renderMonthlyCostChart(rData.monthly_cost || {});
        renderCumulativeUnitsChart(rData.monthly_units || {});
        renderTopResources(rData.top_resources || {});
    } catch (err) {
        console.error('Resource load error:', err);
        if (errorBox) {
            errorBox.style.display = 'block';
            errorBox.textContent = '❌ ' + (err.message || 'Failed to load resource data');
        }
    }
}

function renderResourceStats(rData) {
    const container = document.getElementById('resourceStats');
    if (!container) return;

    const units = rData.monthly_units || {};
    const cost = rData.monthly_cost || {};
    const top = rData.top_resources || {};

    const stats = [
        { label: 'Total Man-Hours', value: fmtNum(units.total_units || 0) },
        { label: 'Peak Month (Hrs)', value: (units.peak_month || '—') + ' (' + fmtNum(units.peak_units || 0) + ')' },
        { label: 'Total Planned Cost', value: fmtMoney(cost.total_planned || 0) },
        { label: 'Total Actual Cost', value: fmtMoney(cost.total_actual || 0) },
        { label: 'Unique Resources', value: fmtNum(top.total_count || 0) },
    ];

    container.innerHTML = stats.map(function (s) {
        return '<div class="resource-stat"><div class="val">' + esc(s.value) + '</div><div class="lbl">' + esc(s.label) + '</div></div>';
    }).join('');
}

function renderMonthlyUnitsChart(unitsData) {
    const canvas = document.getElementById('monthlyUnitsChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (monthlyUnitsChart) { monthlyUnitsChart.destroy(); monthlyUnitsChart = null; }

    if (!unitsData.labels || !unitsData.labels.length) {
        ctx.fillStyle = '#64748b';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No resource unit data available', canvas.width / 2, canvas.height / 2);
        return;
    }

    monthlyUnitsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: unitsData.labels,
            datasets: unitsData.datasets || []
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return ctx.dataset.label + ': ' + fmtNum(ctx.parsed.y) + ' hrs';
                        }
                    }
                }
            },
            scales: {
                x: { stacked: true, ticks: { maxTicksLimit: 24, maxRotation: 45 } },
                y: { 
                    stacked: true, 
                    beginAtZero: true,
                    ticks: { callback: function (v) { return fmtNum(v) + ' hrs'; } }
                }
            }
        }
    });
}

function renderMonthlyCostChart(costData) {
    const canvas = document.getElementById('monthlyCostChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (monthlyCostChart) { monthlyCostChart.destroy(); monthlyCostChart = null; }

    if (!costData.labels || !costData.labels.length) {
        ctx.fillStyle = '#64748b';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No cost data available', canvas.width / 2, canvas.height / 2);
        return;
    }

    const datasets = [
        {
            label: 'Planned Cost (Monthly)',
            data: costData.planned || [],
            backgroundColor: 'rgba(59, 130, 246, 0.6)',
            borderColor: '#3b82f6',
            type: 'bar',
            order: 2
        }
    ];

    if (costData.actual && costData.actual.length) {
        datasets.push({
            label: 'Actual Cost (Monthly)',
            data: costData.actual,
            backgroundColor: 'rgba(220, 38, 38, 0.6)',
            borderColor: '#dc2626',
            type: 'bar',
            order: 2
        });
    }

    // Cumulative overlay lines
    if (costData.cumulative_planned && costData.cumulative_planned.length) {
        datasets.push({
            label: 'Cumulative Planned',
            data: costData.cumulative_planned,
            borderColor: '#1e40af',
            backgroundColor: 'transparent',
            type: 'line',
            yAxisID: 'y1',
            borderWidth: 2,
            fill: false,
            tension: 0.1,
            pointRadius: 0,
            order: 1
        });
    }
    if (costData.cumulative_actual && costData.cumulative_actual.length) {
        datasets.push({
            label: 'Cumulative Actual',
            data: costData.cumulative_actual,
            borderColor: '#7f1d1d',
            backgroundColor: 'transparent',
            type: 'line',
            yAxisID: 'y1',
            borderWidth: 2,
            borderDash: [3, 3],
            fill: false,
            tension: 0.1,
            pointRadius: 0,
            order: 1
        });
    }

    monthlyCostChart = new Chart(ctx, {
        data: {
            labels: costData.labels,
            datasets: datasets
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return ctx.dataset.label + ': ' + fmtMoney(ctx.parsed.y);
                        }
                    }
                }
            },
            scales: {
                x: { ticks: { maxTicksLimit: 24, maxRotation: 45 } },
                y: {
                    type: 'linear', position: 'left', beginAtZero: true,
                    title: { display: true, text: 'Monthly Cost' },
                    ticks: { callback: function (v) { return '$' + Number(v).toLocaleString('en-US'); } }
                },
                y1: {
                    type: 'linear', position: 'right', beginAtZero: true,
                    title: { display: true, text: 'Cumulative Cost' },
                    grid: { drawOnChartArea: false },
                    ticks: { callback: function (v) { return '$' + Number(v).toLocaleString('en-US'); } }
                }
            }
        }
    });
}

function renderCumulativeUnitsChart(unitsData) {
    const canvas = document.getElementById('cumulativeUnitsChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (cumulativeUnitsChart) { cumulativeUnitsChart.destroy(); cumulativeUnitsChart = null; }

    if (!unitsData.labels || !unitsData.labels.length) {
        ctx.fillStyle = '#64748b';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No cumulative data available', canvas.width / 2, canvas.height / 2);
        return;
    }

    cumulativeUnitsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: unitsData.labels,
            datasets: [{
                label: 'Cumulative Man-Hours',
                data: unitsData.cumulative_curve || [],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                borderWidth: 3,
                fill: true,
                tension: 0.2,
                pointRadius: 0,
                pointHoverRadius: 4
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return 'Cumulative: ' + fmtNum(ctx.parsed.y) + ' hrs';
                        }
                    }
                }
            },
            scales: {
                x: { ticks: { maxTicksLimit: 20, maxRotation: 45 } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: function (v) { return fmtNum(v) + ' hrs'; } }
                }
            }
        }
    });
}

function renderTopResources(topData) {
    const container = document.getElementById('topResourcesUnits');
    if (!container) return;

    const list = topData.by_units || [];
    if (!list.length) {
        container.innerHTML = '<p style="text-align:center;padding:1rem;color:#64748b;">No resources with man-hours found.</p>';
        return;
    }

    container.innerHTML = list.map(function (r, idx) {
        return '<div class="top-resource-item">' +
            '<div>' +
            '<span style="color:#94a3b8;font-weight:600;">' + (idx + 1) + '.</span> ' +
            '<span class="name">' + esc(r.name) + '</span>' +
            '<span class="type">' + esc(r.type) + '</span>' +
            '</div>' +
            '<div class="val">' + fmtNum(r.units) + ' hrs</div>' +
            '</div>';
    }).join('');
}

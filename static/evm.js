/*
    EVM PAGE LOGIC (Patched)
    ========================
    - Safe API handling
    - XSS-safe error/status text
    - Null-safe money/index formatters
    - Cost-loaded disclaimer
    - S-curve nulls + data-date line
    - Canvas preserved on scurve error
*/

let scurveChart = null;

document.addEventListener('DOMContentLoaded', function () {
    loadEVM();
});

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
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0
        }).format(n);
    } catch (e) {
        return '$' + Math.round(n).toLocaleString('en-US');
    }
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

function showDisclaimer(text) {
    // Remove prior disclaimer
    const old = document.getElementById('evmDisclaimer');
    if (old) old.remove();

    const bar = document.createElement('div');
    bar.id = 'evmDisclaimer';
    bar.className = 'file-info-bar';
    bar.style.borderLeft = '4px solid #f59e0b';
    bar.style.marginBottom = '1rem';
    bar.innerHTML = '<span>⚠️ ' + esc(text) + '</span>';

    const content = document.getElementById('evmContent');
    const anchor = content ? content.querySelector('.file-info-bar') : null;
    if (anchor && anchor.parentNode) {
        anchor.parentNode.insertBefore(bar, anchor.nextSibling);
    } else if (content) {
        content.insertBefore(bar, content.firstChild);
    }
}

function ensureScurveErrorNode() {
    let err = document.getElementById('scurveError');
    if (err) return err;

    const canvas = document.getElementById('scurveChart');
    if (!canvas || !canvas.parentNode) return null;

    err = document.createElement('div');
    err.id = 'scurveError';
    err.style.display = 'none';
    err.style.color = '#dc2626';
    err.style.padding = '0.75rem 0';
    err.style.fontSize = '0.9rem';
    canvas.parentNode.insertBefore(err, canvas);
    return err;
}

// ═══════════════════════════════════════════
// LOAD
// ═══════════════════════════════════════════

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

        if (!metrics) {
            throw new Error('Invalid EVM payload (missing metrics)');
        }

        if (loading) loading.style.display = 'none';
        const content = document.getElementById('evmContent');
        if (content) content.style.display = 'block';

        const fileName = document.getElementById('fileName');
        const dataDate = document.getElementById('dataDate');
        if (fileName) fileName.textContent = response.file_name || '—';
        if (dataDate) dataDate.textContent = metrics.data_date || '—';

        if (metrics.is_cost_loaded === false) {
            showDisclaimer(
                'Schedule is not cost-loaded (or has no resource costs). ' +
                'BAC/PV/EV may use duration-based estimates; CPI/EAC/AC are indicative only — not audit-grade EVM.'
            );
        }

        renderPerformanceMetrics(metrics);
        renderFinancialMetrics(metrics);
        renderScurve(scurve, metrics);
    } catch (err) {
        console.error(err);
        showEvmError(err.message || 'Failed to load EVM data');
    }
}

// ═══════════════════════════════════════════
// PERFORMANCE CARDS
// ═══════════════════════════════════════════

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
        '<div class="metric-subtitle status-' + sSt + '">' + esc(sText) + '</div>' +
        '</div>' +

        '<div class="metric-card ' + cSt + '">' +
        '<div class="metric-label">CPI (Cost)</div>' +
        '<div class="metric-value">' +
        (m.is_cost_loaded === false ? 'N/A*' : esc(fmtIndex(m.cpi))) +
        '</div>' +
        '<div class="metric-subtitle status-' + cSt + '">' + esc(cText) + '</div>' +
        '</div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">% Complete</div>' +
        '<div class="metric-value">' + esc(fmtPct(m.pct_complete)) + '</div>' +
        '<div class="metric-subtitle">Earned / BAC</div>' +
        '</div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">% Spent</div>' +
        '<div class="metric-value">' + esc(fmtPct(m.pct_spent)) + '</div>' +
        '<div class="metric-subtitle">AC / BAC</div>' +
        '</div>';
}

// ═══════════════════════════════════════════
// FINANCIAL CARDS
// ═══════════════════════════════════════════

function renderFinancialMetrics(m) {
    const container = document.getElementById('financialMetrics');
    if (!container) return;

    const svClass = Number(m.sv) >= 0 ? 'good' : 'bad';
    const cvClass = Number(m.cv) >= 0 ? 'good' : 'bad';
    const vacClass = Number(m.vac) >= 0 ? 'good' : 'bad';

    // When not cost-loaded, CV/VAC/CPI narrative is weak — still show numbers with neutral where needed
    const cvCardClass = m.is_cost_loaded === false ? 'neutral' : cvClass;
    const vacCardClass = m.is_cost_loaded === false ? 'neutral' : vacClass;

    container.innerHTML =
        '<div class="metric-card neutral">' +
        '<div class="metric-label">BAC (Budget at Completion)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.bac)) + '</div>' +
        '<div class="metric-subtitle">Total planned budget</div>' +
        '</div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">PV (Planned Value)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.pv)) + '</div>' +
        '<div class="metric-subtitle">Should be done by data date</div>' +
        '</div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">EV (Earned Value)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.ev)) + '</div>' +
        '<div class="metric-subtitle">Budget × % complete</div>' +
        '</div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">AC (Actual Cost)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.ac)) + '</div>' +
        '<div class="metric-subtitle">' +
        (m.is_cost_loaded === false ? 'Proxy / limited actuals' : 'From resource actuals') +
        '</div></div>' +

        '<div class="metric-card ' + svClass + '">' +
        '<div class="metric-label">SV (Schedule Variance)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.sv)) + '</div>' +
        '<div class="metric-subtitle">EV − PV</div>' +
        '</div>' +

        '<div class="metric-card ' + cvCardClass + '">' +
        '<div class="metric-label">CV (Cost Variance)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.cv)) + '</div>' +
        '<div class="metric-subtitle">EV − AC</div>' +
        '</div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">EAC (Est. at Completion)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.eac)) + '</div>' +
        '<div class="metric-subtitle">BAC / CPI (when CPI &gt; 0)</div>' +
        '</div>' +

        '<div class="metric-card neutral">' +
        '<div class="metric-label">ETC (Est. to Complete)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.etc)) + '</div>' +
        '<div class="metric-subtitle">EAC − AC</div>' +
        '</div>' +

        '<div class="metric-card ' + vacCardClass + '">' +
        '<div class="metric-label">VAC (Variance at Completion)</div>' +
        '<div class="metric-value">' + esc(fmtMoney(m.vac)) + '</div>' +
        '<div class="metric-subtitle">BAC − EAC (positive = under budget)</div>' +
        '</div>';
}

// ═══════════════════════════════════════════
// S-CURVE
// ═══════════════════════════════════════════

function renderScurve(scurveData, metrics) {
    const errNode = ensureScurveErrorNode();
    const canvas = document.getElementById('scurveChart');

    if (errNode) {
        errNode.style.display = 'none';
        errNode.textContent = '';
    }

    if (!scurveData || scurveData.error) {
        if (errNode) {
            errNode.style.display = 'block';
            errNode.textContent = (scurveData && scurveData.error)
                ? String(scurveData.error)
                : 'No S-curve data available';
        }
        if (scurveChart) {
            scurveChart.destroy();
            scurveChart = null;
        }
        return;
    }

    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (scurveChart) {
        scurveChart.destroy();
        scurveChart = null;
    }

    const labels = scurveData.labels || [];
    const pv = normalizeSeries(scurveData.planned_value);
    const ev = normalizeSeries(scurveData.earned_value);
    const ac = normalizeSeries(scurveData.actual_cost);
    const dataDate = scurveData.data_date || (metrics && metrics.data_date) || null;
    const bac = Number(scurveData.bac != null ? scurveData.bac : (metrics && metrics.bac));

    const dataDatePlugin = {
        id: 'dataDateLine',
        afterDraw: function (chart) {
            if (!dataDate || !labels.length) return;

            // Exact or nearest label
            let idx = labels.indexOf(dataDate);
            if (idx < 0) {
                const target = Date.parse(dataDate);
                if (!Number.isFinite(target)) return;
                let best = -1;
                let bestDist = Infinity;
                for (let i = 0; i < labels.length; i++) {
                    const t = Date.parse(labels[i]);
                    if (!Number.isFinite(t)) continue;
                    const d = Math.abs(t - target);
                    if (d < bestDist) {
                        bestDist = d;
                        best = i;
                    }
                }
                idx = best;
            }
            if (idx < 0) return;

            const meta = chart.getDatasetMeta(0);
            if (!meta || !meta.data || !meta.data[idx]) return;
            const x = meta.data[idx].x;
            const { ctx: c, chartArea } = chart;
            if (x == null || !chartArea) return;

            c.save();
            c.strokeStyle = '#64748b';
            c.lineWidth = 1.5;
            c.setLineDash([4, 4]);
            c.beginPath();
            c.moveTo(x, chartArea.top);
            c.lineTo(x, chartArea.bottom);
            c.stroke();
            c.setLineDash([]);
            c.fillStyle = '#64748b';
            c.font = '11px sans-serif';
            c.fillText('Data Date', x + 4, chartArea.top + 12);

            // Optional BAC horizontal guide
            if (Number.isFinite(bac) && bac > 0 && chart.scales && chart.scales.y) {
                const y = chart.scales.y.getPixelForValue(bac);
                if (y >= chartArea.top && y <= chartArea.bottom) {
                    c.strokeStyle = '#94a3b8';
                    c.setLineDash([2, 4]);
                    c.beginPath();
                    c.moveTo(chartArea.left, y);
                    c.lineTo(chartArea.right, y);
                    c.stroke();
                    c.fillText('BAC', chartArea.left + 4, y - 4);
                }
            }
            c.restore();
        }
    };

    scurveChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Planned Value (PV)',
                    data: pv,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.08)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1,
                    spanGaps: false,
                    pointRadius: 0,
                    pointHoverRadius: 4
                },
                {
                    label: 'Earned Value (EV)',
                    data: ev,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    borderWidth: 3,
                    fill: false,
                    tension: 0.1,
                    spanGaps: false,
                    pointRadius: 0,
                    pointHoverRadius: 4
                },
                {
                    label: 'Actual Cost (AC)',
                    data: ac,
                    borderColor: '#dc2626',
                    backgroundColor: 'rgba(220, 38, 38, 0.05)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.1,
                    spanGaps: false,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const val = ctx.parsed && ctx.parsed.y;
                            if (val === null || val === undefined || !Number.isFinite(val)) {
                                return null;
                            }
                            return ctx.dataset.label + ': ' +
                                Number(val).toLocaleString('en-US', {
                                    style: 'currency',
                                    currency: 'USD',
                                    maximumFractionDigits: 0
                                });
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function (value) {
                            return '$' + Number(value).toLocaleString('en-US');
                        }
                    }
                },
                x: {
                    ticks: {
                        maxTicksLimit: 20,
                        maxRotation: 45,
                        minRotation: 0
                    }
                }
            }
        },
        plugins: [dataDatePlugin]
    });
}
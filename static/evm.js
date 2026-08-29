/*
    EVM PAGE LOGIC
    ==============
*/

let scurveChart = null;

document.addEventListener('DOMContentLoaded', function() {
    loadEVM();
});

function loadEVM() {
    fetch('/api/evm-data')
        .then(res => res.json())
        .then(response => {
            if (response.error) {
                document.getElementById('loadingMessage').innerHTML = 
                    `<p style="color:red;">❌ ${response.error}</p>
                     <a href="/" class="btn btn-primary">Go to Dashboard</a>`;
                return;
            }
            
            document.getElementById('loadingMessage').style.display = 'none';
            document.getElementById('evmContent').style.display = 'block';
            
            document.getElementById('fileName').textContent = response.file_name;
            document.getElementById('dataDate').textContent = 
                response.data.metrics.data_date || '--';
            
            renderPerformanceMetrics(response.data.metrics);
            renderFinancialMetrics(response.data.metrics);
            renderScurve(response.data.scurve);
        })
        .catch(err => {
            console.error(err);
            document.getElementById('loadingMessage').innerHTML = 
                '<p style="color:red;">❌ Failed to load</p>';
        });
}

function renderPerformanceMetrics(m) {
    const container = document.getElementById('performanceMetrics');
    
    container.innerHTML = `
        <div class="metric-card ${m.schedule_status.status}">
            <div class="metric-label">SPI (Schedule)</div>
            <div class="metric-value">${m.spi.toFixed(3)}</div>
            <div class="metric-subtitle status-${m.schedule_status.status}">
                ${m.schedule_status.text}
            </div>
        </div>
        
        <div class="metric-card ${m.cost_status.status}">
            <div class="metric-label">CPI (Cost)</div>
            <div class="metric-value">${m.cpi.toFixed(3)}</div>
            <div class="metric-subtitle status-${m.cost_status.status}">
                ${m.cost_status.text}
            </div>
        </div>
        
        <div class="metric-card neutral">
            <div class="metric-label">% Complete</div>
            <div class="metric-value">${m.pct_complete}%</div>
            <div class="metric-subtitle">Physical progress</div>
        </div>
        
        <div class="metric-card neutral">
            <div class="metric-label">% Spent</div>
            <div class="metric-value">${m.pct_spent}%</div>
            <div class="metric-subtitle">Of total budget</div>
        </div>
    `;
}

function renderFinancialMetrics(m) {
    const container = document.getElementById('financialMetrics');
    
    const fmt = (val) => '$' + val.toLocaleString('en-US', {maximumFractionDigits: 0});
    
    container.innerHTML = `
        <div class="metric-card neutral">
            <div class="metric-label">BAC (Budget at Completion)</div>
            <div class="metric-value">${fmt(m.bac)}</div>
            <div class="metric-subtitle">Total planned budget</div>
        </div>
        
        <div class="metric-card neutral">
            <div class="metric-label">PV (Planned Value)</div>
            <div class="metric-value">${fmt(m.pv)}</div>
            <div class="metric-subtitle">Should be done by now</div>
        </div>
        
        <div class="metric-card neutral">
            <div class="metric-label">EV (Earned Value)</div>
            <div class="metric-value">${fmt(m.ev)}</div>
            <div class="metric-subtitle">Actually completed</div>
        </div>
        
        <div class="metric-card neutral">
            <div class="metric-label">AC (Actual Cost)</div>
            <div class="metric-value">${fmt(m.ac)}</div>
            <div class="metric-subtitle">Actually spent</div>
        </div>
        
        <div class="metric-card ${m.sv >= 0 ? 'good' : 'bad'}">
            <div class="metric-label">SV (Schedule Variance)</div>
            <div class="metric-value">${fmt(m.sv)}</div>
            <div class="metric-subtitle">EV - PV</div>
        </div>
        
        <div class="metric-card ${m.cv >= 0 ? 'good' : 'bad'}">
            <div class="metric-label">CV (Cost Variance)</div>
            <div class="metric-value">${fmt(m.cv)}</div>
            <div class="metric-subtitle">EV - AC</div>
        </div>
        
        <div class="metric-card neutral">
            <div class="metric-label">EAC (Est. at Completion)</div>
            <div class="metric-value">${fmt(m.eac)}</div>
            <div class="metric-subtitle">Forecasted final cost</div>
        </div>
        
        <div class="metric-card ${m.vac >= 0 ? 'good' : 'bad'}">
            <div class="metric-label">VAC (Variance at Completion)</div>
            <div class="metric-value">${fmt(m.vac)}</div>
            <div class="metric-subtitle">BAC - EAC</div>
        </div>
    `;
}

function renderScurve(scurveData) {
    if (scurveData.error) {
        document.querySelector('#scurveChart').parentElement.innerHTML = 
            `<p style="color:red;">${scurveData.error}</p>`;
        return;
    }
    
    const ctx = document.getElementById('scurveChart').getContext('2d');
    
    if (scurveChart) scurveChart.destroy();
    
    scurveChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: scurveData.labels,
            datasets: [
                {
                    label: 'Planned Value (PV)',
                    data: scurveData.planned_value,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1
                },
                {
                    label: 'Earned Value (EV)',
                    data: scurveData.earned_value,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 3,
                    fill: false,
                    tension: 0.1
                },
                {
                    label: 'Actual Cost (AC)',
                    data: scurveData.actual_cost,
                    borderColor: '#dc2626',
                    backgroundColor: 'rgba(220, 38, 38, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.1
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
                        label: function(ctx) {
                            const val = ctx.parsed.y;
                            if (val === null) return null;
                            return `${ctx.dataset.label}: $${val.toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => '$' + value.toLocaleString()
                    }
                },
                x: {
                    ticks: {
                        maxTicksLimit: 20
                    }
                }
            }
        }
    });
}
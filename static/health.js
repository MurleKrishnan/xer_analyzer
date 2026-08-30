/*
    ADVANCED HEALTH DASHBOARD - MULTI-STANDARD
    ==========================================
    Features:
    - Full affected activity lists (scrollable)
    - Multi-standard filtering
    - Top priority actions with expandable activity lists
    - Excel export with severity filter (All / Critical / High / Medium)
*/

let healthData = null;
let currentStandard = 'all';

document.addEventListener('DOMContentLoaded', function() {
    loadHealthData('all');
});

function selectStandard(standard) {
    currentStandard = standard;
    
    document.querySelectorAll('.std-select-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.std === standard);
    });
    
    loadHealthData(standard);
}

function loadHealthData(standard) {
    document.getElementById('loadingMessage').style.display = 'block';
    document.getElementById('healthContent').style.display = 'none';
    
    fetch(`/api/health-data?standard=${standard}`)
        .then(res => res.json())
        .then(response => {
            if (response.error) {
                document.getElementById('loadingMessage').innerHTML = `
                    <p style="color:red;">❌ ${response.error}</p>
                    <a href="/" class="btn btn-primary">Go to Dashboard</a>
                `;
                return;
            }
            
            healthData = response.data;
            renderDashboard();
        })
        .catch(err => {
            console.error(err);
            document.getElementById('loadingMessage').innerHTML = 
                '<p style="color:red;">Failed to load health data</p>';
        });
}

function renderDashboard() {
    document.getElementById('loadingMessage').style.display = 'none';
    document.getElementById('healthContent').style.display = 'block';
    
    document.getElementById('overallScore').textContent = healthData.overall_score;
    document.getElementById('totalChecks').textContent = healthData.total_checks;
    document.getElementById('passedChecks').textContent = healthData.passed_checks;
    document.getElementById('failedChecks').textContent = healthData.failed_checks;
    document.getElementById('criticalFailures').textContent = healthData.critical_failures;
    
    const stdName = currentStandard === 'all' ? 'All Standards' : currentStandard;
    document.getElementById('reportTitle').textContent = 
        currentStandard === 'all' ? 'Comprehensive Assessment' : `${stdName} Assessment`;
    document.getElementById('reportSubtitle').textContent = 
        currentStandard === 'all' 
            ? 'Analysis based on all applicable standards'
            : `Detailed analysis of ${stdName} compliance`;
    
    renderStandardsScores();
    renderTopActions();
    renderDetailedResults();
}

function renderStandardsScores() {
    const container = document.getElementById('scoreGrid');
    container.innerHTML = '';
    
    Object.entries(healthData.standard_scores).forEach(([std, data]) => {
        const div = document.createElement('div');
        div.className = `std-score-card ${data.color}`;
        div.innerHTML = `
            <div style="font-size:0.85rem; color:#64748b; font-weight:600;">${std}</div>
            <div class="std-score-value">${data.score}</div>
            <div class="std-score-grade grade-${data.grade}">Grade ${data.grade}</div>
            <div class="std-score-details">
                ${data.passed}/${data.total_checks} passed<br>
                ${data.failed > 0 ? `<span style="color:#dc2626;">${data.failed} failed</span>` : 'All passed ✅'}
            </div>
        `;
        div.style.cursor = 'pointer';
        div.onclick = () => selectStandard(std);
        container.appendChild(div);
    });
}

function renderTopActions() {
    const container = document.getElementById('topActionsList');
    const section = document.getElementById('topActionsSection');

    if (!healthData.top_actions || healthData.top_actions.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    container.innerHTML = '';

    healthData.top_actions.slice(0, 15).forEach((action, idx) => {
        const severityColor = {
            'critical': '#7f1d1d',
            'high': '#dc2626',
            'medium': '#f59e0b',
            'low': '#64748b'
        }[action.severity] || '#64748b';

        const failedItems = action.failed_items || [];
        let itemsHtml = '';

        if (failedItems.length > 0) {
            itemsHtml = `
                <details style="margin-top:0.5rem;">
                    <summary style="cursor:pointer; color:#1d4ed8; font-size:0.85rem;">
                        Show affected activities (${failedItems.length})
                    </summary>
                    <div style="margin-top:0.4rem; background:#fff; border:1px solid #e2e8f0;
                                border-radius:6px; padding:0.6rem; max-height:280px; overflow:auto;">
                        ${failedItems.map(item => `
                            <div style="font-size:0.82rem; padding:0.15rem 0; border-bottom:1px solid #f1f5f9;">
                                <strong>${item.code || ''}</strong>
                                ${item.name ? ` - ${item.name}` : ''}
                                ${item.wbs ? ` <span style="color:#64748b;">(${item.wbs})</span>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </details>
            `;
        } else {
            itemsHtml = `
                <div style="margin-top:0.4rem; font-size:0.82rem; color:#64748b;">
                    No activity list available for this metric.
                </div>
            `;
        }

        const metricText = (action.count !== undefined && action.count !== null)
            ? `${action.count} activities affected (${action.percentage || 0}%)`
            : (action.value !== undefined && action.value !== null
                ? `Value: ${action.value}`
                : 'Review required');

        const div = document.createElement('div');
        div.className = 'action-item';
        div.innerHTML = `
            <div class="action-priority" style="background:${severityColor};">${idx + 1}</div>
            <div style="flex:1;">
                <div style="font-weight:600;">
                    ${action.id || ''}: ${action.name || ''}
                    <span class="badge badge-${action.severity || 'low'}">${(action.severity || 'low').toUpperCase()}</span>
                    <span class="badge badge-std">${action.standard || ''}</span>
                </div>
                <div style="font-size:0.85rem; color:#64748b; margin-top:0.25rem;">
                    ${action.category ? `Category: ${action.category} | ` : ''}${metricText}
                </div>
                ${action.recommendation ? `<div class="recommendation-box">💡 ${action.recommendation}</div>` : ''}
                ${itemsHtml}
            </div>
        `;
        container.appendChild(div);
    });
}

function renderDetailedResults() {
    const container = document.getElementById('detailedResults');
    container.innerHTML = '';
    
    const filterStatus = document.getElementById('filterStatus').value;
    const filterSeverity = document.getElementById('filterSeverity').value;
    const filterSearch = document.getElementById('filterSearch').value.toLowerCase();
    
    const severityLevels = {
        'critical': ['critical'],
        'high': ['critical', 'high'],
        'medium': ['critical', 'high', 'medium'],
        'all': ['critical', 'high', 'medium', 'low', 'info']
    };
    
    Object.entries(healthData.standards).forEach(([stdName, stdData]) => {
        stdData.categories.forEach(category => {
            const filteredChecks = category.checks.filter(check => {
                if (filterStatus !== 'all' && check.status !== filterStatus) return false;
                if (filterSeverity !== 'all' && !severityLevels[filterSeverity].includes(check.severity)) return false;
                if (filterSearch && !check.name.toLowerCase().includes(filterSearch) 
                    && !check.id.toLowerCase().includes(filterSearch)) return false;
                return true;
            });
            
            if (filteredChecks.length === 0) return;
            
            const section = document.createElement('div');
            section.className = 'category-section';
            
            const passed = filteredChecks.filter(c => c.passed).length;
            const failed = filteredChecks.filter(c => c.status === 'fail').length;
            
            section.innerHTML = `
                <div class="category-header">
                    <div>
                        <h3>${category.name}</h3>
                        <div style="font-size:0.85rem; color:#64748b;">${stdName}</div>
                    </div>
                    <div class="category-stats">
                        ${passed}/${filteredChecks.length} passed
                        ${failed > 0 ? `| <span style="color:#dc2626;">${failed} failed</span>` : ''}
                    </div>
                </div>
                <div class="checks-list"></div>
            `;
            
            const checksList = section.querySelector('.checks-list');
            filteredChecks.forEach(check => {
                checksList.appendChild(createCheckItem(check));
            });
            
            container.appendChild(section);
        });
    });
    
    if (container.children.length === 0) {
        container.innerHTML = '<p style="text-align:center; padding:2rem; color:#64748b;">No checks match your filter criteria.</p>';
    }
}

function createCheckItem(check) {
    const div = document.createElement('div');
    div.className = `check-item ${check.status}`;
    
    const icon = check.status === 'pass' ? '✅' : 
                 check.status === 'fail' ? '❌' : 'ℹ️';
    
    let details = '';
    if (check.value !== undefined) {
        details = `<strong>Value:</strong> ${check.value}${check.unit || ''}`;
    } else if (check.count !== undefined) {
        details = `<strong>Count:</strong> ${check.count} / ${check.total} (${check.percentage}%)`;
    }
    
    div.innerHTML = `
        <div class="check-icon">${icon}</div>
        <div class="check-content">
            <div class="check-title">
                <span>${check.id}: ${check.name}</span>
                <span class="badge badge-${check.severity}">${check.severity}</span>
                <span class="badge badge-std">${check.standard}</span>
            </div>
            <div style="font-size:0.85rem; color:#64748b; margin-bottom:0.5rem;">${check.description}</div>
            <div style="font-size:0.85rem;">
                ${details}
                ${check.threshold ? `| <strong>Threshold:</strong> ${check.threshold}` : ''}
            </div>
            ${check.recommendation ? `<div class="recommendation-box">💡 ${check.recommendation}</div>` : ''}
            ${check.failed_items && check.failed_items.length > 0 ? renderFailedItems(check.failed_items) : ''}
        </div>
    `;
    
    return div;
}

function renderFailedItems(items) {
    return `
        <details style="margin-top:0.5rem;">
            <summary style="cursor:pointer; font-size:0.85rem; color:#3b82f6;">
                Show affected items (${items.length})
            </summary>
            <div style="margin-top:0.5rem; padding:0.5rem; background:white;
                        border:1px solid #e2e8f0; border-radius:4px; font-size:0.85rem;
                        max-height:280px; overflow-y:auto;">
                ${items.map(i => `
                    <div style="padding:0.15rem 0; border-bottom:1px solid #f1f5f9;">
                        <strong>${i.code}</strong>${i.name ? ' - ' + i.name : ''}
                        ${i.wbs ? ` <span style="color:#64748b;">(${i.wbs})</span>` : ''}
                    </div>
                `).join('')}
            </div>
        </details>
    `;
}

function applyFilter() {
    renderDetailedResults();
}

// ═══════════════════════════════════════════
// EXPORT / DOWNLOAD ACTIONS
// ═══════════════════════════════════════════

function downloadPDF() {
    window.location.href = `/api/executive-pdf?standard=${currentStandard}`;
}

function downloadActionsPDF() {
    window.location.href = `/api/actions-pdf?standard=${currentStandard}`;
}

function downloadActionsExcel() {
    // Read severity filter from dropdown
    const sevEl = document.getElementById('excelSeverityFilter');
    const severity = sevEl ? sevEl.value : 'all';

    // Build query with standard + severity
    window.location.href =
        `/api/actions-excel?standard=${currentStandard}&severity=${severity}`;
}
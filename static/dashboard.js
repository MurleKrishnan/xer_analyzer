/*
    DASHBOARD JAVASCRIPT
    ====================
    This file makes the web page interactive.
    
    Handles:
    - File uploads (drag & drop and button)
    - Fetching data from the Python server
    - Drawing charts
    - Filling tables
    - Tab switching
*/

// ─── STORE CHART REFERENCES (so we can update them) ───
let statusChart = null;
let floatChart = null;
let wbsChart = null;
let activitiesDataTable = null;
let criticalDataTable = null;

// ═══════════════════════════════════════════
// STARTUP - runs when page loads
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Dashboard initialized');
    
    setupEventListeners();
    checkForExistingData();
});

// ═══════════════════════════════════════════
// EVENT LISTENERS - respond to user actions
// ═══════════════════════════════════════════

function setupEventListeners() {
    // Upload button
    document.getElementById('uploadBtn').addEventListener('click', function() {
        document.getElementById('fileInput').click();
    });
    
    // File input change
    document.getElementById('fileInput').addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });
    
    // Load sample button
    document.getElementById('loadSampleBtn').addEventListener('click', loadSample);
    
    // Export button
    document.getElementById('exportBtn').addEventListener('click', function() {
        window.location.href = '/api/export-excel';
    });
    
    // Drag & drop zone
    const dropZone = document.getElementById('dropZone');
    if (dropZone) {
        dropZone.addEventListener('click', function() {
            document.getElementById('fileInput').click();
        });
        
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        
        dropZone.addEventListener('dragleave', function() {
            dropZone.classList.remove('drag-over');
        });
        
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            
            if (e.dataTransfer.files.length > 0) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });
    }
    
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

// ═══════════════════════════════════════════
// FILE OPERATIONS
// ═══════════════════════════════════════════

function uploadFile(file) {
    console.log('📤 Uploading:', file.name);
    
    // Validate file
    if (!file.name.toLowerCase().endsWith('.xer')) {
        alert('❌ Please upload a .xer file');
        return;
    }
    
    showLoading('Uploading and analyzing...');
    
    const formData = new FormData();
    formData.append('file', file);
    
    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('❌ Error: ' + data.error);
            hideLoading();
            return;
        }
        
        console.log('✅ Analysis complete');
        showDashboard(data);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('❌ Failed to upload file: ' + error.message);
        hideLoading();
    });
}

function loadSample() {
    console.log('📄 Loading sample file...');
    showLoading('Loading sample XER file...');
    
    fetch('/api/load-sample')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('❌ ' + data.error);
                hideLoading();
                return;
            }
            showDashboard(data);
        })
        .catch(error => {
            alert('❌ Failed to load sample');
            hideLoading();
        });
}

function checkForExistingData() {
    fetch('/api/dashboard')
        .then(response => response.json())
        .then(data => {
            if (data.has_data) {
                showDashboard(data);
            }
        });
}

// ═══════════════════════════════════════════
// UI STATE MANAGEMENT
// ═══════════════════════════════════════════

function showLoading(text) {
    document.getElementById('welcomeScreen').style.display = 'none';
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('loadingScreen').style.display = 'flex';
    document.getElementById('loadingText').textContent = text || 'Loading...';
}

function hideLoading() {
    document.getElementById('loadingScreen').style.display = 'none';
    document.getElementById('welcomeScreen').style.display = 'flex';
}

function showDashboard(response) {
    document.getElementById('welcomeScreen').style.display = 'none';
    document.getElementById('loadingScreen').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
    document.getElementById('exportBtn').style.display = 'inline-flex';
    
    // Update file info
    document.getElementById('fileName').textContent = response.file_name || '--';
    document.getElementById('analyzedAt').textContent = response.analyzed_at || '--';
    
    const data = response.data;
    
    // Update project info
    if (data.project_info) {
        document.getElementById('projectName').textContent = 
            data.project_info.name || '--';
    }
    
    // Render each section
    renderSummaryCards(data.summary_cards);
    renderStatusChart(data.status_distribution);
    renderFloatChart(data.float_distribution);
    renderWbsChart(data.wbs_breakdown);
    renderDcmaCards(data.dcma_summary);
    renderIssues(data.top_issues);
    renderActivitiesTable(data.activities_table);
    renderCriticalTable(data.critical_activities);
}

// ═══════════════════════════════════════════
// RENDER FUNCTIONS - draw stuff on screen
// ═══════════════════════════════════════════

function renderSummaryCards(cards) {
    const container = document.getElementById('summaryCards');
    container.innerHTML = '';
    
    cards.forEach(card => {
        const div = document.createElement('div');
        div.className = `summary-card ${card.color}`;
        div.innerHTML = `
            <div class="card-icon">${card.icon}</div>
            <div class="card-value">${card.value}</div>
            <div class="card-label">${card.label}</div>
        `;
        container.appendChild(div);
    });
}

function renderStatusChart(data) {
    const ctx = document.getElementById('statusChart').getContext('2d');
    
    if (statusChart) statusChart.destroy();
    
    statusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: data.colors,
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
    const ctx = document.getElementById('floatChart').getContext('2d');
    
    if (floatChart) floatChart.destroy();
    
    floatChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Activities',
                data: data.values,
                backgroundColor: data.colors,
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
    const ctx = document.getElementById('wbsChart').getContext('2d');
    
    if (wbsChart) wbsChart.destroy();
    
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
    container.innerHTML = '';
    
    dcmaData.forEach(check => {
        const div = document.createElement('div');
        div.className = `dcma-card ${check.pass ? 'pass' : 'fail'}`;
        div.innerHTML = `
            <div class="dcma-card-header">
                <div class="dcma-card-name">${check.name}</div>
                <span class="dcma-badge ${check.pass ? 'pass' : 'fail'}">
                    ${check.pass ? '✓ PASS' : '✗ FAIL'}
                </span>
            </div>
            <div class="dcma-value">${check.value}</div>
            <div class="dcma-details">
                ${check.count} of ${check.total} | Threshold: ${check.threshold}
            </div>
        `;
        container.appendChild(div);
    });
}

function renderIssues(issues) {
    if (!issues || issues.length === 0) {
        document.getElementById('issuesSection').style.display = 'none';
        return;
    }
    
    document.getElementById('issuesSection').style.display = 'block';
    const container = document.getElementById('issuesList');
    container.innerHTML = '';
    
    issues.forEach(issue => {
        const div = document.createElement('div');
        div.className = `issue-item ${issue.severity}`;
        div.innerHTML = `
            <div>
                <strong>${issue.check}</strong>
                <div style="font-size: 0.85rem; color: #64748b;">
                    ${issue.count} activities affected (${issue.percentage}%)
                </div>
            </div>
            <span class="dcma-badge fail">${issue.severity.toUpperCase()}</span>
        `;
        container.appendChild(div);
    });
}

function renderActivitiesTable(activities) {
    if (activitiesDataTable) {
        activitiesDataTable.destroy();
    }
    
    const tbody = document.querySelector('#activitiesTable tbody');
    tbody.innerHTML = '';
    
    activities.forEach(act => {
        const statusClass = act.status.toLowerCase().replace(' ', '-');
        const row = document.createElement('tr');
        if (act.critical) row.className = 'critical-row';
        
        row.innerHTML = `
            <td><strong>${act.code}</strong></td>
            <td>${act.name}</td>
            <td>${act.wbs}</td>
            <td>${act.type}</td>
            <td><span class="status-badge ${statusClass}">${act.status}</span></td>
            <td>${act.duration}d</td>
            <td>${act.critical ? '🔴 ' : ''}${act.float}d</td>
            <td>${act.start}</td>
            <td>${act.finish}</td>
        `;
        tbody.appendChild(row);
    });
    
    activitiesDataTable = $('#activitiesTable').DataTable({
        pageLength: 25,
        order: [[6, 'asc']],  // Sort by float
        destroy: true
    });
}

function renderCriticalTable(criticals) {
    if (criticalDataTable) {
        criticalDataTable.destroy();
    }
    
    const tbody = document.querySelector('#criticalTable tbody');
    tbody.innerHTML = '';
    
    criticals.forEach(act => {
        const statusClass = act.status.toLowerCase().replace(' ', '-');
        const row = document.createElement('tr');
        row.className = 'critical-row';
        
        row.innerHTML = `
            <td><strong>${act.code}</strong></td>
            <td>${act.name}</td>
            <td>${act.wbs}</td>
            <td>${act.duration}d</td>
            <td>🔴 ${act.float}d</td>
            <td><span class="status-badge ${statusClass}">${act.status}</span></td>
            <td>${act.start}</td>
            <td>${act.finish}</td>
        `;
        tbody.appendChild(row);
    });
    
    criticalDataTable = $('#criticalTable').DataTable({
        pageLength: 25,
        destroy: true
    });
}

// ═══════════════════════════════════════════
// TAB SWITCHING
// ═══════════════════════════════════════════

function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
}
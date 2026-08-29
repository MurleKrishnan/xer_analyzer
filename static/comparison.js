/*
    COMPARISON PAGE LOGIC
    =====================
*/

let baselineFile = null;
let currentFile = null;
let changeChart = null;

document.addEventListener('DOMContentLoaded', function() {
    setupFileHandlers('baseline');
    setupFileHandlers('current');
    
    document.getElementById('compareBtn').addEventListener('click', runComparison);
    
    // Check for existing comparison
    checkExistingComparison();
});

function setupFileHandlers(type) {
    const dropZone = document.getElementById(`${type}Drop`);
    const input = document.getElementById(`${type}Input`);
    const fileName = document.getElementById(`${type}FileName`);
    
    dropZone.addEventListener('click', () => input.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            handleFileSelected(type, e.dataTransfer.files[0]);
        }
    });
    
    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelected(type, e.target.files[0]);
        }
    });
}

function handleFileSelected(type, file) {
    if (!file.name.toLowerCase().endsWith('.xer')) {
        alert('❌ Please select a .xer file');
        return;
    }
    
    if (type === 'baseline') {
        baselineFile = file;
    } else {
        currentFile = file;
    }
    
    document.getElementById(`${type}FileName`).textContent = `✅ ${file.name}`;
    document.getElementById(`${type}Drop`).classList.add('has-file');
    
    // Enable compare button if both files selected
    if (baselineFile && currentFile) {
        document.getElementById('compareBtn').disabled = false;
    }
}

function runComparison() {
    if (!baselineFile || !currentFile) return;
    
    document.getElementById('uploadSection').style.display = 'none';
    document.getElementById('loadingSection').style.display = 'block';
    
    const formData = new FormData();
    formData.append('baseline', baselineFile);
    formData.append('current', currentFile);
    
    fetch('/api/compare', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(response => {
        if (response.error) {
            alert('❌ ' + response.error);
            resetComparison();
            return;
        }
        
        showResults(response);
    })
    .catch(err => {
        alert('❌ Comparison failed');
        console.error(err);
        resetComparison();
    });
}

function showResults(response) {
    document.getElementById('loadingSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';
    
    document.getElementById('baselineName').textContent = response.baseline_file;
    document.getElementById('currentName').textContent = response.current_file;
    
    const results = response.results;
    
    renderSummary(results.summary);
    renderChart(results.summary);
    renderCriticalChanges(results.critical_changes);
    renderChangedActivities(results.changed);
    renderAddedActivities(results.added);
    renderDeletedActivities(results.deleted);
}

function renderSummary(summary) {
    const container = document.getElementById('summaryCards');
    
    const cards = [
        { icon: '➕', label: 'Added', value: summary.added_count, color: 'blue' },
        { icon: '➖', label: 'Deleted', value: summary.deleted_count, color: 'red' },
        { icon: '🔄', label: 'Changed', value: summary.changed_count, color: 'orange' },
        { icon: '✓', label: 'Unchanged', value: summary.unchanged_count, color: 'green' },
        { icon: '📉', label: 'Slipped', value: summary.slipped_count, color: 'red' },
        { icon: '📈', label: 'Improved', value: summary.improved_count, color: 'green' },
    ];
    
    container.innerHTML = cards.map(c => `
        <div class="summary-card ${c.color}">
            <div class="card-icon">${c.icon}</div>
            <div class="card-value">${c.value}</div>
            <div class="card-label">${c.label}</div>
        </div>
    `).join('');
}

function renderChart(summary) {
    const ctx = document.getElementById('changeChart').getContext('2d');
    
    if (changeChart) changeChart.destroy();
    
    changeChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Added', 'Deleted', 'Changed', 'Unchanged'],
            datasets: [{
                data: [
                    summary.added_count,
                    summary.deleted_count,
                    summary.changed_count,
                    summary.unchanged_count
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
    // Newly critical
    const newlyDiv = document.getElementById('newlyCriticalList');
    if (criticalData.newly_critical.length === 0) {
        newlyDiv.innerHTML = '<p style="color:#64748b;">None</p>';
    } else {
        newlyDiv.innerHTML = criticalData.newly_critical.map(a => `
            <div class="issue-item" style="margin-bottom:0.5rem;">
                <div>
                    <strong>${a.code}</strong> - ${a.name}
                    <div style="font-size:0.85rem; color:#64748b;">Float: ${a.float}d</div>
                </div>
            </div>
        `).join('');
    }
    
    // No longer critical
    const noLongerDiv = document.getElementById('noLongerCriticalList');
    if (criticalData.no_longer_critical.length === 0) {
        noLongerDiv.innerHTML = '<p style="color:#64748b;">None</p>';
    } else {
        noLongerDiv.innerHTML = criticalData.no_longer_critical.map(a => `
            <div class="issue-item medium" style="margin-bottom:0.5rem;">
                <div>
                    <strong>${a.code}</strong> - ${a.name}
                    <div style="font-size:0.85rem; color:#64748b;">Float: ${a.float}d</div>
                </div>
            </div>
        `).join('');
    }
}

function renderChangedActivities(changed) {
    const tbody = document.querySelector('#changedTable tbody');
    tbody.innerHTML = '';
    
    changed.forEach(item => {
        item.changes.forEach((change, idx) => {
            const row = document.createElement('tr');
            
            const deltaClass = change.delta.startsWith('+') ? 'delta-positive' : 
                              change.delta.startsWith('-') ? 'delta-negative' : '';
            
            row.innerHTML = `
                <td>${idx === 0 ? `<strong>${item.code}</strong>` : ''}</td>
                <td>${idx === 0 ? item.name : ''}</td>
                <td>${idx === 0 ? item.wbs : ''}</td>
                <td><strong>${change.field}</strong></td>
                <td>${change.baseline}</td>
                <td>${change.current}</td>
                <td class="${deltaClass}">${change.delta}</td>
                <td><span class="change-badge ${change.severity}">${change.severity.toUpperCase()}</span></td>
            `;
            tbody.appendChild(row);
        });
    });
    
    $('#changedTable').DataTable({ pageLength: 25, destroy: true });
}

function renderAddedActivities(added) {
    const tbody = document.querySelector('#addedTable tbody');
    tbody.innerHTML = added.map(a => `
        <tr>
            <td><strong>${a.code}</strong></td>
            <td>${a.name}</td>
            <td>${a.wbs}</td>
            <td>${a.duration}d</td>
            <td>${a.start}</td>
            <td>${a.finish}</td>
        </tr>
    `).join('');
    
    $('#addedTable').DataTable({ pageLength: 25, destroy: true });
}

function renderDeletedActivities(deleted) {
    const tbody = document.querySelector('#deletedTable tbody');
    tbody.innerHTML = deleted.map(a => `
        <tr>
            <td><strong>${a.code}</strong></td>
            <td>${a.name}</td>
            <td>${a.wbs}</td>
            <td>${a.duration}d</td>
            <td>${a.start}</td>
            <td>${a.finish}</td>
        </tr>
    `).join('');
    
    $('#deletedTable').DataTable({ pageLength: 25, destroy: true });
}

function resetComparison() {
    baselineFile = null;
    currentFile = null;
    
    document.getElementById('baselineFileName').textContent = '';
    document.getElementById('currentFileName').textContent = '';
    document.getElementById('baselineDrop').classList.remove('has-file');
    document.getElementById('currentDrop').classList.remove('has-file');
    document.getElementById('compareBtn').disabled = true;
    
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('loadingSection').style.display = 'none';
    document.getElementById('uploadSection').style.display = 'block';
}

function checkExistingComparison() {
    fetch('/api/comparison-data')
        .then(res => res.json())
        .then(response => {
            if (response.has_data) {
                showResults(response);
            }
        });
}
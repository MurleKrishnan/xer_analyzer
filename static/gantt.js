/*
    P6-STYLE PROFESSIONAL GANTT CHART
    ===================================
    Uses DHTMLX Gantt (free open-source version)
    with full P6-compatible column set.
*/

// ═══════════════════════════════════════════
// AVAILABLE COLUMNS (P6-STANDARD)
// ═══════════════════════════════════════════

const AVAILABLE_COLUMNS = {
    // Identity & WBS
    'activity_id':      { label: 'Activity ID', width: 90, category: 'Identity' },
    'text':             { label: 'Activity Name', width: 250, category: 'Identity', tree: true },
    'wbs':              { label: 'WBS', width: 150, category: 'Identity' },
    'wbs_code':         { label: 'WBS Code', width: 100, category: 'Identity' },
    'activity_type':    { label: 'Activity Type', width: 120, category: 'Identity' },
    'status':           { label: 'Status', width: 90, category: 'Identity' },
    
    // Durations
    'original_duration':      { label: 'OD', width: 60, category: 'Duration', align: 'right' },
    'remaining_duration':     { label: 'RD', width: 60, category: 'Duration', align: 'right' },
    'actual_duration':        { label: 'AD', width: 60, category: 'Duration', align: 'right' },
    'at_completion_duration': { label: 'ADC', width: 60, category: 'Duration', align: 'right' },
    
    // Dates - Early
    'early_start':    { label: 'Early Start', width: 90, category: 'Dates' },
    'early_finish':   { label: 'Early Finish', width: 90, category: 'Dates' },
    
    // Dates - Late
    'late_start':     { label: 'Late Start', width: 90, category: 'Dates' },
    'late_finish':    { label: 'Late Finish', width: 90, category: 'Dates' },
    
    // Dates - Actual
    'actual_start':   { label: 'Actual Start', width: 90, category: 'Dates' },
    'actual_finish':  { label: 'Actual Finish', width: 90, category: 'Dates' },
    
    // Dates - Baseline
    'baseline_start':  { label: 'BL Start', width: 90, category: 'Baseline' },
    'baseline_finish': { label: 'BL Finish', width: 90, category: 'Baseline' },
    
    // Float
    'total_float':   { label: 'Total Float', width: 70, category: 'Float', align: 'right' },
    'free_float':    { label: 'Free Float', width: 70, category: 'Float', align: 'right' },
    
    // Progress
    'physical_percent':    { label: 'Physical %', width: 80, category: 'Progress', align: 'right' },
    'schedule_percent':    { label: 'Schedule %', width: 80, category: 'Progress', align: 'right' },
    'performance_percent': { label: 'Performance %', width: 90, category: 'Progress', align: 'right' },
    
    // Resources
    'budgeted_units':  { label: 'Budgeted Units', width: 100, category: 'Resources', align: 'right' },
    'actual_units':    { label: 'Actual Units', width: 100, category: 'Resources', align: 'right' },
    'remaining_units': { label: 'Remaining Units', width: 100, category: 'Resources', align: 'right' },
    
    // Cost
    'budgeted_cost':          { label: 'Budgeted Cost', width: 110, category: 'Cost', align: 'right' },
    'actual_cost':            { label: 'Actual Cost', width: 110, category: 'Cost', align: 'right' },
    'remaining_cost':         { label: 'Remaining Cost', width: 110, category: 'Cost', align: 'right' },
    'at_completion_cost':     { label: 'Cost at Completion', width: 120, category: 'Cost', align: 'right' },
    'variance_at_completion': { label: 'VAC', width: 90, category: 'Cost', align: 'right' },
    
    // Earned Value
    'earned_value': { label: 'Earned Value', width: 110, category: 'EVM', align: 'right' },
    'spi':          { label: 'SPI', width: 60, category: 'EVM', align: 'right' },
    'cpi':          { label: 'CPI', width: 60, category: 'EVM', align: 'right' },
    
    // Constraints
    'constraint_type': { label: 'Constraint', width: 130, category: 'Constraints' },
    'constraint_date': { label: 'Const. Date', width: 90, category: 'Constraints' },
    
    // Logic
    'predecessors':      { label: 'Predecessors', width: 200, category: 'Logic' },
    'successors':        { label: 'Successors', width: 200, category: 'Logic' },
    'predecessor_count': { label: 'Pred #', width: 60, category: 'Logic', align: 'right' },
    'successor_count':   { label: 'Succ #', width: 60, category: 'Logic', align: 'right' },
    
    // Calendar
    'calendar': { label: 'Calendar', width: 100, category: 'Other' },
};

// Default visible columns (P6 default view)
const DEFAULT_COLUMNS = [
    'activity_id', 'text', 'original_duration', 
    'early_start', 'early_finish', 'total_float'
];

// User's currently selected columns
let selectedColumns = [...DEFAULT_COLUMNS];

// State
let allTasks = [];
let allLinks = [];
let showBaseline = false;
let showCriticalOnly = false;

// ═══════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function() {
    initGantt();
    loadData(500);
    buildColumnSelector();
});

function initGantt() {
    // Configure DHTMLX Gantt
    gantt.config.date_format = "%Y-%m-%d";
    gantt.config.row_height = 30;
    gantt.config.min_column_width = 40;
    gantt.config.scale_height = 60;
    gantt.config.grid_resize = true;
    gantt.config.readonly = true; // Read-only mode
    gantt.config.smart_rendering = true;
    gantt.config.static_background = true;
    gantt.config.show_links = true;
    gantt.config.auto_scheduling = false;
    
    // Bar text
    gantt.templates.task_text = function(start, end, task) {
        return `${task.activity_id}`;
    };
    
    // Row class
    gantt.templates.grid_row_class = function(start, end, task) {
        if (task.is_critical) return 'critical-row';
        return '';
    };
    
    // Task class
    gantt.templates.task_class = function(start, end, task) {
        return task.custom_class || '';
    };
    
    // Tooltip
    gantt.plugins({ tooltip: true });
    gantt.templates.tooltip_text = function(start, end, task) {
        return `
            <div style="padding: 6px; min-width: 250px;">
                <b>${task.activity_id}</b> - ${task.text}<br>
                <hr style="margin: 4px 0;">
                <b>WBS:</b> ${task.wbs}<br>
                <b>Start:</b> ${task.start_date}<br>
                <b>Finish:</b> ${task.end_date}<br>
                <b>Duration:</b> ${task.original_duration}d<br>
                <b>Float:</b> ${task.total_float}d ${task.is_critical ? '🔴' : ''}<br>
                <b>Progress:</b> ${task.physical_percent}%<br>
                <b>Status:</b> ${task.status}
            </div>
        `;
    };
    
    // Apply columns and init
    applyColumnConfig();
    gantt.init("ganttChart");
}

function applyColumnConfig() {
    const columns = selectedColumns.map(colKey => {
        const col = AVAILABLE_COLUMNS[colKey];
        return {
            name: colKey,
            label: col.label,
            width: col.width,
            align: col.align || 'left',
            resize: true,
            tree: col.tree || false,
            template: function(task) {
                let val = task[colKey];
                
                // Format numbers
                if (typeof val === 'number') {
                    if (colKey.includes('cost') || colKey === 'earned_value') {
                        return '$' + val.toLocaleString(undefined, {maximumFractionDigits: 0});
                    }
                    if (colKey.includes('percent') || colKey === 'progress') {
                        if (colKey === 'progress') return (val * 100).toFixed(0) + '%';
                        return val.toFixed(1) + '%';
                    }
                    if (colKey === 'spi' || colKey === 'cpi') {
                        return val.toFixed(3);
                    }
                    return val.toFixed(1);
                }
                
                // Critical indicator
                if (colKey === 'total_float' && task.is_critical) {
                    return `🔴 ${val}`;
                }
                
                return val || '';
            }
        };
    });
    
    gantt.config.columns = columns;
}

// ═══════════════════════════════════════════
// DATA LOADING
// ═══════════════════════════════════════════

function loadData(maxActivities) {
    document.getElementById('loadingOverlay').style.display = 'flex';
    
    fetch(`/api/gantt-data?max=${maxActivities}`)
        .then(res => res.json())
        .then(response => {
            if (response.error) {
                document.getElementById('loadingOverlay').innerHTML = `
                    <div style="text-align:center;">
                        <p style="color:red;">❌ ${response.error}</p>
                        <a href="/" class="btn btn-primary">Go to Dashboard</a>
                    </div>
                `;
                return;
            }
            
            allTasks = response.data.tasks;
            allLinks = response.data.links;
            
            // Update stats
            document.getElementById('statsDisplay').innerHTML = `
                📌 ${response.data.total} activities | 
                🔴 ${response.data.critical_count} critical | 
                📅 Data Date: ${response.data.data_date || 'N/A'}
            `;
            
            renderGantt();
            document.getElementById('loadingOverlay').style.display = 'none';
        })
        .catch(err => {
            console.error(err);
            document.getElementById('loadingOverlay').innerHTML = 
                '<p style="color:red;">Failed to load data</p>';
        });
}

function renderGantt() {
    let tasksToShow = allTasks;
    
    if (showCriticalOnly) {
        tasksToShow = allTasks.filter(t => t.is_critical);
    }
    
    gantt.clearAll();
    gantt.parse({
        data: tasksToShow,
        links: allLinks
    });
}

function reloadData(maxActivities) {
    loadData(maxActivities);
}

// ═══════════════════════════════════════════
// TOOLBAR ACTIONS
// ═══════════════════════════════════════════

function setZoom(scale) {
    document.querySelectorAll('.toolbar-group .tb-btn').forEach(btn => {
        if (['Hour','Day','Week','Month','Quarter','Year'].includes(btn.textContent.trim())) {
            btn.classList.remove('active');
        }
    });
    event.target.classList.add('active');
    
    switch(scale) {
        case 'hour':
            gantt.config.scales = [
                { unit: 'day', step: 1, format: '%d %M' },
                { unit: 'hour', step: 1, format: '%H:%i' }
            ];
            gantt.config.scale_height = 50;
            gantt.config.min_column_width = 30;
            break;
        case 'day':
            gantt.config.scales = [
                { unit: 'month', step: 1, format: '%F %Y' },
                { unit: 'day', step: 1, format: '%d' }
            ];
            gantt.config.min_column_width = 30;
            break;
        case 'week':
            gantt.config.scales = [
                { unit: 'month', step: 1, format: '%F %Y' },
                { unit: 'week', step: 1, format: 'Week %W' }
            ];
            gantt.config.min_column_width = 60;
            break;
        case 'month':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' },
                { unit: 'month', step: 1, format: '%M' }
            ];
            gantt.config.min_column_width = 70;
            break;
        case 'quarter':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' },
                { unit: 'quarter', step: 1, format: function(date) {
                    const q = Math.floor(date.getMonth() / 3) + 1;
                    return 'Q' + q;
                }}
            ];
            gantt.config.min_column_width = 80;
            break;
        case 'year':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' }
            ];
            gantt.config.min_column_width = 100;
            break;
    }
    
    gantt.render();
}

function expandAll() {
    gantt.eachTask(function(task) {
        gantt.open(task.id);
    });
}

function collapseAll() {
    gantt.eachTask(function(task) {
        gantt.close(task.id);
    });
}

function toggleBaseline() {
    showBaseline = !showBaseline;
    const btn = document.getElementById('baselineBtn');
    btn.parentElement.classList.toggle('active', showBaseline);
    
    if (showBaseline) {
        // Show baseline bars
        gantt.templates.rightside_text = function(start, end, task) {
            if (task.baseline_start && task.baseline_finish) {
                return `<span style="color: #94a3b8; font-size: 0.75rem;">
                    BL: ${task.baseline_start} → ${task.baseline_finish}
                </span>`;
            }
            return '';
        };
    } else {
        gantt.templates.rightside_text = function() { return ''; };
    }
    
    gantt.render();
}

function toggleCritical() {
    showCriticalOnly = !showCriticalOnly;
    document.getElementById('criticalBtn').parentElement.classList.toggle('active', showCriticalOnly);
    renderGantt();
}

// ═══════════════════════════════════════════
// COLUMN SELECTOR
// ═══════════════════════════════════════════

function buildColumnSelector() {
    const container = document.getElementById('columnList');
    container.innerHTML = '';
    
    // Group by category
    const categories = {};
    Object.entries(AVAILABLE_COLUMNS).forEach(([key, col]) => {
        if (!categories[col.category]) categories[col.category] = [];
        categories[col.category].push({ key, ...col });
    });
    
    // Build UI
    Object.entries(categories).forEach(([cat, cols]) => {
        const header = document.createElement('div');
        header.style.cssText = 'grid-column: span 2; font-weight: 600; padding: 0.5rem 0 0.25rem; color: #3b82f6; border-bottom: 1px solid #e2e8f0;';
        header.textContent = cat;
        container.appendChild(header);
        
        cols.forEach(col => {
            const item = document.createElement('label');
            item.className = 'column-item';
            item.innerHTML = `
                <input type="checkbox" 
                       value="${col.key}" 
                       ${selectedColumns.includes(col.key) ? 'checked' : ''}>
                <span>${col.label}</span>
            `;
            container.appendChild(item);
        });
    });
}

function showColumnSelector() {
    buildColumnSelector();
    document.getElementById('columnModal').classList.add('show');
}

function closeColumnSelector() {
    document.getElementById('columnModal').classList.remove('show');
}

function selectAllColumns(select) {
    document.querySelectorAll('#columnList input[type="checkbox"]').forEach(cb => {
        cb.checked = select;
    });
}

function resetColumns() {
    document.querySelectorAll('#columnList input[type="checkbox"]').forEach(cb => {
        cb.checked = DEFAULT_COLUMNS.includes(cb.value);
    });
}

function applyColumns() {
    const checked = Array.from(
        document.querySelectorAll('#columnList input[type="checkbox"]:checked')
    ).map(cb => cb.value);
    
    if (checked.length === 0) {
        alert('Please select at least one column');
        return;
    }
    
    selectedColumns = checked;
    
    // Ensure 'text' column always exists for tree
    if (!selectedColumns.includes('text')) {
        selectedColumns.unshift('text');
    }
    
    applyColumnConfig();
    gantt.render();
    closeColumnSelector();
}
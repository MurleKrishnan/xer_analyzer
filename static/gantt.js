/*
    P6 ENTERPRISE GANTT - Full WBS Hierarchy + Safe Parent Validation
*/

const AVAILABLE_COLUMNS = {
    'activity_id': { label: 'Activity ID', width: 90, category: 'Identity' },
    'text': { label: 'Activity Name', width: 320, category: 'Identity', tree: true },
    'wbs': { label: 'WBS', width: 150, category: 'Identity' },
    'wbs_path': { label: 'WBS Path', width: 220, category: 'Identity' },
    'activity_type': { label: 'Activity Type', width: 120, category: 'Identity' },
    'status': { label: 'Status', width: 90, category: 'Identity' },
    'primary_resource': { label: 'Primary Resource', width: 130, category: 'Identity' },
    'original_duration': { label: 'OD', width: 55, category: 'Duration', align: 'right' },
    'remaining_duration': { label: 'RD', width: 55, category: 'Duration', align: 'right' },
    'actual_duration': { label: 'AD', width: 55, category: 'Duration', align: 'right' },
    'early_start': { label: 'Start', width: 90, category: 'Dates' },
    'early_finish': { label: 'Finish', width: 90, category: 'Dates' },
    'late_start': { label: 'Late Start', width: 90, category: 'Dates' },
    'late_finish': { label: 'Late Finish', width: 90, category: 'Dates' },
    'actual_start': { label: 'Actual Start', width: 90, category: 'Dates' },
    'actual_finish': { label: 'Actual Finish', width: 90, category: 'Dates' },
    'baseline_start': { label: 'BL Start', width: 90, category: 'Baseline' },
    'baseline_finish': { label: 'BL Finish', width: 90, category: 'Baseline' },
    'total_float': { label: 'Total Float', width: 75, category: 'Float', align: 'right' },
    'free_float': { label: 'Free Float', width: 75, category: 'Float', align: 'right' },
    'physical_percent': { label: 'Physical %', width: 80, category: 'Progress', align: 'right' },
    'schedule_percent': { label: 'Schedule %', width: 80, category: 'Progress', align: 'right' },
    'performance_percent': { label: 'Performance %', width: 90, category: 'Progress', align: 'right' },
    'budgeted_cost': { label: 'Budgeted Cost', width: 110, category: 'Cost', align: 'right' },
    'actual_cost': { label: 'Actual Cost', width: 110, category: 'Cost', align: 'right' },
    'remaining_cost': { label: 'Remaining Cost', width: 110, category: 'Cost', align: 'right' },
    'earned_value': { label: 'Earned Value', width: 110, category: 'EVM', align: 'right' },
    'spi': { label: 'SPI', width: 55, category: 'EVM', align: 'right' },
    'cpi': { label: 'CPI', width: 55, category: 'EVM', align: 'right' },
    'constraint_type': { label: 'Constraint', width: 130, category: 'Constraints' },
    'predecessors': { label: 'Predecessors', width: 200, category: 'Logic' },
    'successors': { label: 'Successors', width: 200, category: 'Logic' },
    'calendar': { label: 'Calendar', width: 100, category: 'Other' },
};

const DEFAULT_COLUMNS = ['activity_id', 'text', 'original_duration', 'early_start', 'early_finish', 'total_float'];

const GROUPING_FIELDS = {
    'wbs_level_1': 'WBS Level 1', 'wbs_level_2': 'WBS Level 2', 'wbs_level_3': 'WBS Level 3',
    'wbs_level_4': 'WBS Level 4', 'wbs_level_5': 'WBS Level 5', 'wbs_level_6': 'WBS Level 6',
    'wbs_level_7': 'WBS Level 7', 'wbs_level_8': 'WBS Level 8', 'wbs_level_9': 'WBS Level 9',
    'wbs_level_10': 'WBS Level 10', 'wbs_level_11': 'WBS Level 11', 'wbs_level_12': 'WBS Level 12',
    'wbs_path': 'WBS Full Path',
    'status': 'Status', 'activity_type': 'Activity Type', 'critical_text': 'Critical / Non-Critical',
    'primary_resource': 'Primary Resource', 'calendar': 'Calendar',
    'float_band': 'Total Float Band', 'duration_band': 'Duration Band', 'progress_band': 'Progress Band',
    'start_month': 'Start Month', 'start_quarter': 'Start Quarter', 'start_year': 'Start Year',
    'finish_month': 'Finish Month', 'finish_quarter': 'Finish Quarter', 'finish_year': 'Finish Year',
};

const DEFAULT_LEVEL_COLORS = [
    { bgColor: '#1E40AF', textColor: '#FFFFFF', fontSize: 12 },
    { bgColor: '#059669', textColor: '#FFFFFF', fontSize: 11 },
    { bgColor: '#EAB308', textColor: '#000000', fontSize: 10 },
    { bgColor: '#DC2626', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#7C3AED', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#0891B2', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#EA580C', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#DB2777', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#65A30D', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#7C2D12', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#475569', textColor: '#FFFFFF', fontSize: 10 },
    { bgColor: '#831843', textColor: '#FFFFFF', fontSize: 10 },
];

let selectedColumns = [...DEFAULT_COLUMNS];
let allTasks = [];
let allLinks = [];
let groupableValues = {};
let showCriticalOnly = false;
let showWbsOnly = false;

let groupConfig = {
    displayOptions: {
        showGroupTotals: true, showGrandTotals: false, showSummariesOnly: false,
        shrinkBands: true, hideEmpty: false, sortBandsAlpha: true,
    },
    groupLevels: [],
    sort: { field: 'activity_id', order: 'asc' }
};

let filterConditions = [];
let filterLogic = 'AND';
let displayTasks = [];
let currentZoom = 'week';
let selectedGroupRowIndex = -1;

document.addEventListener('DOMContentLoaded', function() {
    initGantt();
    initializeDefaultGroupConfig();
    applyColorsToDom();
    loadData(2000);
});

function initializeDefaultGroupConfig() {
    if (groupConfig.groupLevels.length === 0) {
        for (let i = 0; i < 12; i++) {
            groupConfig.groupLevels.push({
                field: '', indent: true, toLevel: 'all', interval: 'none', pageBreak: false,
                ...DEFAULT_LEVEL_COLORS[i]
            });
        }
    }
}

function initGantt() {
    gantt.config.date_format = "%Y-%m-%d";
    gantt.config.row_height = 26;
    gantt.config.min_column_width = 40;
    gantt.config.scale_height = 60;
    gantt.config.grid_resize = true;
    gantt.config.readonly = true;
    gantt.config.smart_rendering = true;
    gantt.config.show_links = true;
    gantt.config.open_tree_initially = false;
    gantt.config.grid_width = 700;
    gantt.config.scrollable = true;
    
    gantt.templates.task_text = function(start, end, task) {
        if (task.is_grand_total) return `<strong>GRAND TOTAL</strong>`;
        if (task.is_wbs_summary) return `<strong>${task.text}</strong> (${task.child_count || 0})`;
        if (task.is_group) return `<strong>${task.text}</strong> (${task.group_count || 0})`;
        return task.activity_id || '';
    };
    
    gantt.templates.grid_row_class = function(start, end, task) {
        if (task.is_grand_total) return 'gantt-grand-total';
        if (task.is_wbs_summary) return 'gantt-wbs-summary';
        if (task.is_group) return `gantt-group-l${task.group_level || 1}`;
        if (task.is_critical) return 'critical-row';
        return '';
    };
    
    gantt.templates.task_class = function(start, end, task) {
        if (task.is_grand_total) return 'gantt-grand-total';
        if (task.is_wbs_summary) return `gantt-wbs-l${Math.min(task.wbs_depth || 1, 12)}`;
        if (task.is_group) return `gantt-summary-l${task.group_level || 1}`;
        return task.custom_class || '';
    };
    
    gantt.plugins({ tooltip: true });
    gantt.templates.tooltip_text = function(start, end, task) {
        if (task.is_wbs_summary) return `<div style="padding:6px;"><b>WBS: ${task.text}</b><br>Activities: ${task.child_count}<br>Duration: ${task.original_duration}d</div>`;
        if (task.is_group) return `<div style="padding:6px;"><b>${task.text}</b><br>Activities: ${task.group_count}</div>`;
        return `<div style="padding:6px;"><b>${task.activity_id}</b> - ${task.text}<br><b>Start:</b> ${task.start_date}<br><b>Finish:</b> ${task.end_date}<br><b>Duration:</b> ${task.original_duration}d<br><b>Float:</b> ${task.total_float}d${task.is_critical ? ' 🔴' : ''}</div>`;
    };
    
    applyColumnConfig();
    gantt.init("ganttChart");
    setZoom('week');
}

function applyColumnConfig() {
    const columns = selectedColumns.map(colKey => {
        const col = AVAILABLE_COLUMNS[colKey];
        return {
            name: colKey, label: col.label, width: col.width, align: col.align || 'left',
            resize: true, tree: col.tree || false,
            template: function(task) {
                if (task.is_grand_total) {
                    if (col.tree) return '<strong>GRAND TOTAL</strong>';
                    if (colKey === 'original_duration') return task.original_duration ? task.original_duration.toFixed(0) + 'd' : '';
                    return '';
                }
                if (task.is_wbs_summary) {
                    if (col.tree) return `<strong>${task.text}</strong> <span style="opacity:0.8;">(${task.child_count})</span>`;
                    if (colKey === 'activity_id') return `<strong>${task.wbs_code || ''}</strong>`;
                    if (colKey === 'original_duration') return task.original_duration ? task.original_duration.toFixed(0) + 'd' : '';
                    if (colKey === 'early_start' || colKey === 'baseline_start') return task.early_start || '';
                    if (colKey === 'early_finish' || colKey === 'baseline_finish') return task.early_finish || '';
                    if (colKey === 'total_float') return task.total_float !== undefined ? task.total_float.toFixed(0) + 'd' : '';
                    if (colKey === 'physical_percent') return task.physical_percent !== undefined ? task.physical_percent.toFixed(1) + '%' : '';
                    return '';
                }
                if (task.is_group) {
                    if (col.tree) return `<strong>${task.text}</strong> <span style="opacity:0.8;">(${task.group_count})</span>`;
                    if (['original_duration', 'remaining_duration', 'actual_duration'].includes(colKey)) return task[colKey] ? task[colKey].toFixed(0) + 'd' : '';
                    if (['early_start', 'baseline_start', 'actual_start'].includes(colKey)) return task['group_start'] || '';
                    if (['early_finish', 'baseline_finish', 'actual_finish'].includes(colKey)) return task['group_end'] || '';
                    if (colKey === 'total_float') return task[colKey] !== undefined ? task[colKey].toFixed(0) + 'd' : '';
                    return '';
                }
                let val = task[colKey];
                if (val === undefined || val === null) return '';
                if (typeof val === 'number') {
                    if (colKey.includes('cost') || colKey === 'earned_value') return '$' + val.toLocaleString(undefined, {maximumFractionDigits: 0});
                    if (colKey.includes('percent')) return val.toFixed(1) + '%';
                    if (colKey === 'spi' || colKey === 'cpi') return val.toFixed(3);
                    return val.toFixed(1);
                }
                if (colKey === 'total_float' && task.is_critical) return `🔴 ${val}`;
                return val || '';
            }
        };
    });
    gantt.config.columns = columns;
}

function loadData(maxActivities) {
    document.getElementById('loadingOverlay').style.display = 'flex';
    fetch(`/api/gantt-data?max=${maxActivities}`)
        .then(res => res.json())
        .then(response => {
            if (response.error) {
                document.getElementById('loadingOverlay').innerHTML = `<div style="text-align:center;"><p style="color:red;">❌ ${response.error}</p><a href="/" class="btn btn-primary">Go to Dashboard</a></div>`;
                return;
            }
            allTasks = response.data.tasks || [];
            allLinks = response.data.links || [];
            groupableValues = response.data.groupable_values || {};
            document.getElementById('statsDisplay').innerHTML = `📌 ${response.data.total || 0} activities | 🌳 ${response.data.wbs_summary_count || 0} WBS | 🔴 ${response.data.critical_count || 0} critical | rows: ${allTasks.length}`;
            console.log('Loaded tasks:', allTasks.length, 'Sample:', allTasks.slice(0, 3));
            renderGantt();
            document.getElementById('loadingOverlay').style.display = 'none';
        })
        .catch(err => {
            console.error(err);
            document.getElementById('loadingOverlay').innerHTML = '<p style="color:red;">Failed to load data</p>';
        });
}

function reloadData(maxActivities) { loadData(maxActivities); }

function getGroupValue(task, field) {
    if (!field) return '';
    if (field.startsWith('activity_codes.')) {
        const codeType = field.substring('activity_codes.'.length);
        return (task.activity_codes && task.activity_codes[codeType]) || '(No Code)';
    }
    return task[field] || '(Unassigned)';
}

function taskMatchesFilters(task) {
    if (filterConditions.length === 0) return true;
    const results = filterConditions.map(cond => {
        const val = task[cond.field];
        const op = cond.operator;
        const cmp = cond.value;
        if (op === 'equals') return String(val).toLowerCase() === String(cmp).toLowerCase();
        if (op === 'contains') return String(val).toLowerCase().includes(String(cmp).toLowerCase());
        if (op === 'greater_than') return parseFloat(val) > parseFloat(cmp);
        if (op === 'less_than') return parseFloat(val) < parseFloat(cmp);
        return true;
    });
    return filterLogic === 'AND' ? results.every(r => r) : results.some(r => r);
}

function renderGantt() {
    let tasksToShow = Array.isArray(allTasks) ? [...allTasks] : [];
    
    if (!tasksToShow.length) {
        console.warn('No tasks received');
        gantt.clearAll();
        return;
    }
    
    if (showWbsOnly) tasksToShow = tasksToShow.filter(t => t.is_wbs_summary);
    if (showCriticalOnly) tasksToShow = tasksToShow.filter(t => t.is_wbs_summary || t.is_critical);
    tasksToShow = tasksToShow.filter(t => t.is_wbs_summary || taskMatchesFilters(t));
    
    const sort = groupConfig.sort || { field: 'activity_id', order: 'asc' };
    tasksToShow.sort((a, b) => {
        if (a.is_wbs_summary || b.is_wbs_summary) return 0;
        let va = a[sort.field]; let vb = b[sort.field];
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return sort.order === 'asc' ? -1 : 1;
        if (va > vb) return sort.order === 'asc' ? 1 : -1;
        return 0;
    });
    
    displayTasks = [];
    const activeGrouping = (groupConfig.groupLevels || []).filter(g => g.field);
    
    if (activeGrouping.length === 0) {
        tasksToShow.forEach(t => displayTasks.push({ ...t }));
    } else {
        const flatActivities = tasksToShow.filter(t => !t.is_wbs_summary);
        buildGroupedTasks(flatActivities, activeGrouping, 0, 0);
    }
    
    // Sanitize parents
    const validIds = new Set(displayTasks.map(t => String(t.id)));
    displayTasks.forEach(t => {
        const p = t.parent;
        if (p === null || p === undefined || p === '' || p === 0 || p === '0') {
            t.parent = 0;
        } else if (!validIds.has(String(p))) {
            t.parent = 0;
        }
        if (!t.start_date) t.start_date = '2000-01-01';
        if (!t.end_date) t.end_date = t.start_date;
    });
    
    if (groupConfig.displayOptions?.showGrandTotals && displayTasks.length > 0) {
        const actualTasks = displayTasks.filter(t => !t.is_group && !t.is_wbs_summary);
        const totalDur = actualTasks.reduce((s, t) => s + (t.original_duration || 0), 0);
        const startDates = actualTasks.map(t => t.start_date).filter(Boolean).sort();
        const endDates = actualTasks.map(t => t.end_date).filter(Boolean).sort();
        displayTasks.push({
            id: '__grand_total__', text: 'GRAND TOTAL',
            start_date: startDates[0] || '2000-01-01', end_date: endDates[endDates.length - 1] || '2000-01-01',
            parent: 0, is_group: true, is_grand_total: true, group_level: 0,
            group_count: actualTasks.length, original_duration: totalDur,
            type: 'project', open: true, progress: 0
        });
    }
    
    try {
        gantt.clearAll();
        gantt.parse({ data: displayTasks, links: allLinks || [] });
    } catch (err) {
        console.error('Gantt parse failed, falling back to flat', err);
        const flat = displayTasks.filter(t => !t.is_group).map(t => ({ ...t, parent: 0, type: t.is_milestone ? 'milestone' : 'task' }));
        gantt.clearAll();
        gantt.parse({ data: flat, links: [] });
        displayTasks = flat;
    }
    
    gantt.eachTask(function(task) {
        if (task.is_wbs_summary || (task.is_group && (task.group_level || 0) <= 2)) {
            try { gantt.open(task.id); } catch(e) {}
        }
    });
    
    let shown = 0;
    gantt.eachTask(function() { shown++; });
    if (shown === 0) {
        console.warn('Gantt empty after parse. Forcing flat.');
        const flat = allTasks.filter(t => !t.is_wbs_summary).map(t => ({
            ...t, parent: 0, type: t.is_milestone ? 'milestone' : 'task',
            start_date: t.start_date || '2000-01-01',
            end_date: t.end_date || t.start_date || '2000-01-01'
        }));
        gantt.clearAll();
        gantt.parse({ data: flat, links: [] });
        displayTasks = flat;
    }
    
    updateGroupInfoBar();
}

function buildGroupedTasks(tasks, groupingConfigs, level, parentId) {
    if (level >= groupingConfigs.length) {
        tasks.forEach(t => displayTasks.push({ ...t, parent: parentId }));
        return;
    }
    const field = groupingConfigs[level].field;
    const groups = {};
    tasks.forEach(t => {
        const gv = getGroupValue(t, field);
        if (!groups[gv]) groups[gv] = [];
        groups[gv].push(t);
    });
    const keys = groupConfig.displayOptions?.sortBandsAlpha ? Object.keys(groups).sort() : Object.keys(groups);
    keys.forEach(gv => {
        const gt = groups[gv];
        const gid = `group_${level}_${gv}_${parentId}`.replace(/[^a-zA-Z0-9_]/g, '_');
        const starts = gt.map(t => t.start_date).filter(Boolean).sort();
        const ends = gt.map(t => t.end_date).filter(Boolean).sort();
        displayTasks.push({
            id: gid, text: gv,
            start_date: starts[0] || '2000-01-01', end_date: ends[ends.length - 1] || '2000-01-01',
            group_start: starts[0] || '', group_end: ends[ends.length - 1] || '',
            parent: parentId, is_group: true, group_level: level + 1, group_count: gt.length,
            original_duration: gt.reduce((s, t) => s + (t.original_duration || 0), 0),
            total_float: gt.length ? Math.min(...gt.map(t => t.total_float || 0)) : 0,
            type: 'project', open: level < 2, progress: 0,
        });
        buildGroupedTasks(gt, groupingConfigs, level + 1, gid);
    });
}

function updateGroupInfoBar() {
    const bar = document.getElementById('groupInfoBar');
    if (!bar) return;
    const activeGrouping = (groupConfig.groupLevels || []).filter(g => g.field);
    if (activeGrouping.length === 0 && filterConditions.length === 0) {
        bar.style.display = 'none';
        return;
    }
    bar.style.display = 'flex';
    if (activeGrouping.length > 0) {
        document.getElementById('groupBadges').innerHTML = activeGrouping.map((g, idx) => `<span class="group-badge">L${idx+1}: ${GROUPING_FIELDS[g.field] || g.field}</span>`).join(' ');
    } else {
        document.getElementById('groupBadges').innerHTML = '<span style="color:#94a3b8;">WBS hierarchy</span>';
    }
    document.getElementById('sortInfo').textContent = `${groupConfig.sort.field} (${groupConfig.sort.order === 'asc' ? '↑' : '↓'})`;
}

function applyColorsToDom() {
    groupConfig.groupLevels.forEach((level, idx) => {
        if (idx < 12) document.documentElement.style.setProperty(`--group-color-${idx + 1}`, level.bgColor);
    });
}

function setZoom(scale) {
    currentZoom = scale;
    const sel = document.getElementById('timescaleSelect');
    if (sel) sel.value = scale;
    switch(scale) {
        case 'day': gantt.config.scales = [{ unit: 'month', step: 1, format: '%F %Y' }, { unit: 'day', step: 1, format: '%d' }]; gantt.config.min_column_width = 30; break;
        case 'week': gantt.config.scales = [{ unit: 'month', step: 1, format: '%F %Y' }, { unit: 'week', step: 1, format: 'Wk %W' }]; gantt.config.min_column_width = 55; break;
        case 'month': gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }, { unit: 'month', step: 1, format: '%M' }]; gantt.config.min_column_width = 65; break;
        case 'quarter': gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }, { unit: 'quarter', step: 1, format: function(d) { return 'Q' + (Math.floor(d.getMonth() / 3) + 1); }}]; gantt.config.min_column_width = 75; break;
        case 'year': gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }]; gantt.config.min_column_width = 90; break;
        case 'year_quarter': gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }, { unit: 'quarter', step: 1, format: function(d) { return 'Q' + (Math.floor(d.getMonth() / 3) + 1); }}]; gantt.config.min_column_width = 80; break;
        case 'year_month': gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }, { unit: 'month', step: 1, format: '%M' }]; gantt.config.min_column_width = 55; break;
        case 'year_quarter_month': gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }, { unit: 'quarter', step: 1, format: function(d) { return 'Q' + (Math.floor(d.getMonth() / 3) + 1); }}, { unit: 'month', step: 1, format: '%M' }]; gantt.config.min_column_width = 55; gantt.config.scale_height = 80; break;
        case 'quarter_month': gantt.config.scales = [{ unit: 'quarter', step: 1, format: function(d) { return 'Q' + (Math.floor(d.getMonth() / 3) + 1) + ' ' + d.getFullYear(); }}, { unit: 'month', step: 1, format: '%M' }]; gantt.config.min_column_width = 55; break;
    }
    if (scale !== 'year_quarter_month') gantt.config.scale_height = 60;
    gantt.render();
}

function scrollToToday() { gantt.showDate(new Date()); }
function fitAll() { const t = gantt.getTaskByTime(); if (t.length) gantt.showDate(t[0].start_date); }
function expandAll() { gantt.eachTask(t => gantt.open(t.id)); }
function collapseAll() { gantt.eachTask(t => gantt.close(t.id)); }

function toggleCritical() {
    showCriticalOnly = !showCriticalOnly;
    const btn = document.getElementById('criticalBtn');
    if (btn) btn.parentElement.classList.toggle('active', showCriticalOnly);
    renderGantt();
}

function toggleWbsSummary() {
    showWbsOnly = !showWbsOnly;
    const btn = document.getElementById('wbsSummaryBtn');
    if (btn) btn.parentElement.classList.toggle('active', showWbsOnly);
    renderGantt();
}

function closeModal(id) { document.getElementById(id).classList.remove('show'); }

function showColumnSelector() {
    const container = document.getElementById('columnList');
    container.innerHTML = '';
    const categories = {};
    Object.entries(AVAILABLE_COLUMNS).forEach(([key, col]) => {
        if (!categories[col.category]) categories[col.category] = [];
        categories[col.category].push({ key, ...col });
    });
    Object.entries(categories).forEach(([cat, cols]) => {
        const h = document.createElement('div');
        h.style.cssText = 'grid-column: span 2; font-weight: 600; padding: 0.5rem 0 0.25rem; color: #3b82f6; border-bottom: 1px solid #e2e8f0;';
        h.textContent = cat;
        container.appendChild(h);
        cols.forEach(col => {
            const item = document.createElement('label');
            item.style.cssText = 'display:flex; align-items:center; gap:0.5rem; padding:0.4rem; cursor:pointer;';
            item.innerHTML = `<input type="checkbox" value="${col.key}" ${selectedColumns.includes(col.key) ? 'checked' : ''}><span>${col.label}</span>`;
            container.appendChild(item);
        });
    });
    document.getElementById('columnModal').classList.add('show');
}

function selectAllColumns(select) { document.querySelectorAll('#columnList input[type="checkbox"]').forEach(cb => cb.checked = select); }
function resetColumns() { document.querySelectorAll('#columnList input[type="checkbox"]').forEach(cb => cb.checked = DEFAULT_COLUMNS.includes(cb.value)); }

function applyColumns() {
    const checked = Array.from(document.querySelectorAll('#columnList input[type="checkbox"]:checked')).map(cb => cb.value);
    if (checked.length === 0) { alert('Please select at least one column'); return; }
    selectedColumns = checked;
    if (!selectedColumns.includes('text')) selectedColumns.unshift('text');
    applyColumnConfig();
    renderGantt();
    closeModal('columnModal');
}

function showGroupModal() { document.getElementById('groupModal').classList.add('show'); renderGroupByTable(); }

function renderGroupByTable() {
    const tbody = document.getElementById('groupByTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    while (groupConfig.groupLevels.length < 12) {
        groupConfig.groupLevels.push({ field: '', indent: true, toLevel: 'all', interval: 'none', pageBreak: false, ...DEFAULT_LEVEL_COLORS[groupConfig.groupLevels.length] });
    }
    let opts = '<option value="">-- None --</option>';
    Object.entries(GROUPING_FIELDS).forEach(([k, l]) => opts += `<option value="${k}">${l}</option>`);
    groupConfig.groupLevels.forEach((level, idx) => {
        const tr = document.createElement('tr');
        const sel = opts.replace(`value="${level.field}"`, `value="${level.field}" selected`);
        tr.innerHTML = `
            <td style="text-align:center;">${idx + 1}</td>
            <td><select onchange="groupConfig.groupLevels[${idx}].field = this.value">${sel}</select></td>
            <td style="text-align:center;"><input type="checkbox" ${level.indent ? 'checked' : ''}></td>
            <td><select><option>All</option></select></td>
            <td><select><option>-</option></select></td>
            <td style="text-align:center;"><input type="checkbox"></td>
            <td style="background:${level.bgColor}; color:${level.textColor}; text-align:center;">${level.fontSize} Arial</td>
        `;
        tbody.appendChild(tr);
    });
}

function applyGroupConfig(keepOpen) {
    renderGantt();
    if (!keepOpen) closeModal('groupModal');
}

function applyPreset(preset) {
    groupConfig.groupLevels = [];
    for (let i = 0; i < 12; i++) {
        groupConfig.groupLevels.push({ field: '', indent: true, toLevel: 'all', interval: 'none', pageBreak: false, ...DEFAULT_LEVEL_COLORS[i] });
    }
    switch(preset) {
        case 'wbs': for (let i = 0; i < 12; i++) groupConfig.groupLevels[i].field = `wbs_level_${i+1}`; break;
        case 'status': groupConfig.groupLevels[0].field = 'status'; break;
        case 'critical': groupConfig.groupLevels[0].field = 'critical_text'; break;
        case 'type': groupConfig.groupLevels[0].field = 'activity_type'; break;
    }
    renderGroupByTable();
}
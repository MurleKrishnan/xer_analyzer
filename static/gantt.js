/*
    P6 ENTERPRISE GANTT (Patched)
    =============================
    Full WBS hierarchy + safe parents + XSS-safe templates
    + filtered links + native WBS preset + data_date fallbacks
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

let selectedColumns = DEFAULT_COLUMNS.slice();
let allTasks = [];
let allLinks = [];
let groupableValues = {};
let showCriticalOnly = false;
let showLongestPathOnly = false;
let showWbsOnly = false;
let ganttDataDate = null;

let groupConfig = {
    displayOptions: {
        showGroupTotals: true,
        showGrandTotals: false,
        showSummariesOnly: false,
        shrinkBands: true,
        hideEmpty: false,
        sortBandsAlpha: true,
    },
    groupLevels: [],
    sort: { field: 'activity_id', order: 'asc' }
};

let filterConditions = [];
let filterLogic = 'AND';
let displayTasks = [];
let currentZoom = 'week';

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

function fallbackDate() {
    if (ganttDataDate && /^\d{4}-\d{2}-\d{2}/.test(String(ganttDataDate))) {
        return String(ganttDataDate).slice(0, 10);
    }
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return d.getFullYear() + '-' + m + '-' + day;
}

function ensureDates(t) {
    const fb = fallbackDate();
    if (!t.start_date) t.start_date = fb;
    if (!t.end_date) t.end_date = t.start_date || fb;
    if (t.end_date < t.start_date) t.end_date = t.start_date;
    return t;
}

function visibleLinks(tasks) {
    const ids = new Set((tasks || []).map(function (t) { return String(t.id); }));
    return (allLinks || []).filter(function (l) {
        return ids.has(String(l.source)) && ids.has(String(l.target));
    });
}

function activeGroupingLevels() {
    return (groupConfig.groupLevels || []).filter(function (g) { return g.field; });
}

function isNativeWbsMode() {
    return activeGroupingLevels().length === 0 && !showWbsOnly;
}

// ═══════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
    initGantt();
    initializeDefaultGroupConfig();
    applyColorsToDom();
    loadData(2000);
});

function initializeDefaultGroupConfig() {
    if (!groupConfig.groupLevels.length) {
        for (let i = 0; i < 12; i++) {
            groupConfig.groupLevels.push(Object.assign({
                field: '',
                indent: true,
                toLevel: 'all',
                interval: 'none',
                pageBreak: false
            }, DEFAULT_LEVEL_COLORS[i]));
        }
    }
}

function initGantt() {
    gantt.config.date_format = '%Y-%m-%d';
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

    gantt.templates.task_text = function (start, end, task) {
        if (task.is_grand_total) return '<strong>GRAND TOTAL</strong>';
        if (task.is_wbs_summary) {
            return '<strong>' + esc(task.text) + '</strong> (' + esc(task.child_count || 0) + ')';
        }
        if (task.is_group) {
            return '<strong>' + esc(task.text) + '</strong> (' + esc(task.group_count || 0) + ')';
        }
        return esc(task.activity_id || '');
    };

    gantt.templates.grid_row_class = function (start, end, task) {
        if (task.is_grand_total) return 'gantt-grand-total';
        if (task.is_wbs_summary) return 'gantt-wbs-summary';
        if (task.is_group) return 'gantt-group-l' + (task.group_level || 1);
        if (task.is_longest_path) return 'longest-path-row';
        if (task.is_critical) return 'critical-row';
        return '';
    };

    gantt.templates.task_class = function (start, end, task) {
        if (task.is_grand_total) return 'gantt-grand-total';
        if (task.is_wbs_summary) return 'gantt-wbs-l' + Math.min(task.wbs_depth || 1, 12);
        if (task.is_group) return 'gantt-summary-l' + (task.group_level || 1);
        if (task.is_longest_path) return 'gantt-longest-path';
        return task.custom_class || '';
    };

    gantt.plugins({ tooltip: true });
    gantt.templates.tooltip_text = function (start, end, task) {
        if (task.is_wbs_summary) {
            return '<div style="padding:6px;"><b>WBS: ' + esc(task.text) + '</b><br>Activities: ' +
                esc(task.child_count) + '<br>Duration: ' + esc(task.original_duration) + 'd</div>';
        }
        if (task.is_group) {
            return '<div style="padding:6px;"><b>' + esc(task.text) + '</b><br>Activities: ' +
                esc(task.group_count) + '</div>';
        }
        return '<div style="padding:6px;"><b>' + esc(task.activity_id) + '</b> - ' + esc(task.text) +
            '<br><b>Start:</b> ' + esc(task.start_date) +
            '<br><b>Finish:</b> ' + esc(task.end_date) +
            '<br><b>Duration:</b> ' + esc(task.original_duration) + 'd' +
            '<br><b>Float:</b> ' + esc(task.total_float) + 'd' +
            (task.is_critical ? ' 🔴' : '') + '</div>';
    };

    applyColumnConfig();
    gantt.init('ganttChart');
    setZoom('week');
}

function applyColumnConfig() {
    const columns = selectedColumns.map(function (colKey) {
        const col = AVAILABLE_COLUMNS[colKey];
        if (!col) return null;
        return {
            name: colKey,
            label: col.label,
            width: col.width,
            align: col.align || 'left',
            resize: true,
            tree: !!col.tree,
            template: function (task) {
                if (task.is_grand_total) {
                    if (col.tree) return '<strong>GRAND TOTAL</strong>';
                    if (colKey === 'original_duration' && task.original_duration != null) {
                        return Number(task.original_duration).toFixed(0) + 'd';
                    }
                    return '';
                }
                if (task.is_wbs_summary) {
                    if (col.tree) {
                        return '<strong>' + esc(task.text) + '</strong> <span style="opacity:0.8;">(' +
                            esc(task.child_count) + ')</span>';
                    }
                    if (colKey === 'activity_id') return '<strong>' + esc(task.wbs_code || '') + '</strong>';
                    if (colKey === 'original_duration' && task.original_duration != null) {
                        return Number(task.original_duration).toFixed(0) + 'd';
                    }
                    if (colKey === 'early_start' || colKey === 'baseline_start') return esc(task.early_start || '');
                    if (colKey === 'early_finish' || colKey === 'baseline_finish') return esc(task.early_finish || '');
                    if (colKey === 'total_float' && task.total_float !== undefined) {
                        return Number(task.total_float).toFixed(0) + 'd';
                    }
                    if (colKey === 'physical_percent' && task.physical_percent !== undefined) {
                        return Number(task.physical_percent).toFixed(1) + '%';
                    }
                    return '';
                }
                if (task.is_group) {
                    if (col.tree) {
                        return '<strong>' + esc(task.text) + '</strong> <span style="opacity:0.8;">(' +
                            esc(task.group_count) + ')</span>';
                    }
                    if (['original_duration', 'remaining_duration', 'actual_duration'].indexOf(colKey) >= 0) {
                        return task[colKey] != null ? Number(task[colKey]).toFixed(0) + 'd' : '';
                    }
                    if (['early_start', 'baseline_start', 'actual_start'].indexOf(colKey) >= 0) {
                        return esc(task.group_start || '');
                    }
                    if (['early_finish', 'baseline_finish', 'actual_finish'].indexOf(colKey) >= 0) {
                        return esc(task.group_end || '');
                    }
                    if (colKey === 'total_float' && task.total_float !== undefined) {
                        return Number(task.total_float).toFixed(0) + 'd';
                    }
                    return '';
                }

                let val = task[colKey];
                if (val === undefined || val === null) return '';
                if (typeof val === 'number') {
                    if (colKey.indexOf('cost') >= 0 || colKey === 'earned_value') {
                        return '$' + val.toLocaleString(undefined, { maximumFractionDigits: 0 });
                    }
                    if (colKey.indexOf('percent') >= 0) return val.toFixed(1) + '%';
                    if (colKey === 'spi' || colKey === 'cpi') return val.toFixed(3);
                    if (colKey === 'total_float' || colKey === 'free_float' ||
                        colKey.indexOf('duration') >= 0) {
                        return val.toFixed(1) + 'd';
                    }
                    return val.toFixed(1);
                }
                if (colKey === 'total_float' && task.is_critical) {
                    return '🔴 ' + esc(val);
                }
                return esc(val);
            }
        };
    }).filter(Boolean);

    gantt.config.columns = columns;
}

// ═══════════════════════════════════════════
// DATA LOAD
// ═══════════════════════════════════════════

function loadData(maxActivities) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'flex';
        overlay.innerHTML =
            '<div style="text-align:center;"><div class="spinner"></div>' +
            '<p style="margin-top:1rem;">Loading Gantt data...</p></div>';
    }

    const max = maxActivities || 2000;
    fetch('/api/gantt-data?max=' + encodeURIComponent(max))
        .then(function (res) {
            return res.json().then(function (body) {
                return { res: res, body: body };
            }).catch(function () {
                return { res: res, body: {} };
            });
        })
        .then(function (pack) {
            const res = pack.res;
            const response = pack.body || {};
            if (!res.ok || response.error) {
                throw new Error(response.error || ('Failed to load Gantt (' + res.status + ')'));
            }

            const data = response.data || {};
            allTasks = data.tasks || [];
            allLinks = data.links || [];
            groupableValues = data.groupable_values || {};
            ganttDataDate = data.data_date || null;

            mergeActivityCodeGroupFields();

            const stats = document.getElementById('statsDisplay');
            if (stats) {
                stats.textContent =
                    '📌 ' + (data.total || 0) + ' activities | 🌳 ' +
                    (data.wbs_summary_count || 0) + ' WBS | 🔴 ' +
                    (data.critical_count || 0) + ' critical | 🎯 ' +
                    (data.longest_path_count || 0) + ' longest path | rows: ' + allTasks.length;
            }

            renderGantt();
            if (overlay) overlay.style.display = 'none';
        })
        .catch(function (err) {
            console.error(err);
            if (overlay) {
                overlay.innerHTML =
                    '<div style="text-align:center;padding:1rem;">' +
                    '<p style="color:#dc2626;">❌ ' + esc(err.message || 'Failed to load') + '</p>' +
                    '<a href="/" class="btn btn-primary" style="margin-top:1rem;display:inline-flex;">Go to Dashboard</a>' +
                    '</div>';
            }
        });
}

function reloadData(maxActivities) {
    loadData(maxActivities);
}

function mergeActivityCodeGroupFields() {
    const codes = (groupableValues && groupableValues.activity_codes) || {};
    Object.keys(codes).forEach(function (typeName) {
        const key = 'activity_codes.' + typeName;
        if (!GROUPING_FIELDS[key]) {
            GROUPING_FIELDS[key] = 'Code: ' + typeName;
        }
    });
}

// ═══════════════════════════════════════════
// FILTER / GROUP HELPERS
// ═══════════════════════════════════════════

function getGroupValue(task, field) {
    if (!field) return '';
    if (field.indexOf('activity_codes.') === 0) {
        const codeType = field.substring('activity_codes.'.length);
        return (task.activity_codes && task.activity_codes[codeType]) || '(No Code)';
    }
    return task[field] || '(Unassigned)';
}

function taskMatchesFilters(task) {
    if (!filterConditions.length) return true;
    const results = filterConditions.map(function (cond) {
        const val = task[cond.field];
        const op = cond.operator;
        const cmp = cond.value;
        if (op === 'equals') return String(val).toLowerCase() === String(cmp).toLowerCase();
        if (op === 'contains') return String(val).toLowerCase().indexOf(String(cmp).toLowerCase()) >= 0;
        if (op === 'greater_than') return parseFloat(val) > parseFloat(cmp);
        if (op === 'less_than') return parseFloat(val) < parseFloat(cmp);
        return true;
    });
    return filterLogic === 'AND' ? results.every(Boolean) : results.some(Boolean);
}

function sortLeafTasks(tasks) {
    const sort = groupConfig.sort || { field: 'activity_id', order: 'asc' };
    const field = sort.field || 'activity_id';
    const dir = sort.order === 'desc' ? -1 : 1;
    return tasks.slice().sort(function (a, b) {
        let va = a[field];
        let vb = b[field];
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return -1 * dir;
        if (va > vb) return 1 * dir;
        return 0;
    });
}

// ═══════════════════════════════════════════
// RENDER
// ═══════════════════════════════════════════

function renderGantt() {
    let tasksToShow = Array.isArray(allTasks) ? allTasks.slice() : [];

    if (!tasksToShow.length) {
        gantt.clearAll();
        return;
    }

    if (showWbsOnly) {
        tasksToShow = tasksToShow.filter(function (t) { return t.is_wbs_summary; });
    }
    if (showCriticalOnly) {
        tasksToShow = tasksToShow.filter(function (t) {
            return t.is_wbs_summary || t.is_critical;
        });
    }
    if (showLongestPathOnly) {
        tasksToShow = tasksToShow.filter(function (t) {
            return t.is_wbs_summary || t.is_longest_path;
        });
    }
    tasksToShow = tasksToShow.filter(function (t) {
        return t.is_wbs_summary || taskMatchesFilters(t);
    });

    const grouping = activeGroupingLevels();
    displayTasks = [];

    if (grouping.length === 0) {
        // Native hierarchy from server — do NOT shuffle WBS order
        let leaves = tasksToShow.filter(function (t) { return !t.is_wbs_summary; });
        const wbsNodes = tasksToShow.filter(function (t) { return t.is_wbs_summary; });

        // Optional leaf sort only when not relying on pure WBS display stability
        if (!showWbsOnly) {
            leaves = sortLeafTasks(leaves);
        }

        wbsNodes.forEach(function (t) { displayTasks.push(Object.assign({}, t)); });
        leaves.forEach(function (t) { displayTasks.push(Object.assign({}, t)); });
    } else {
        // Group mode: drop server WBS summaries, build synthetic bands
        let flat = tasksToShow.filter(function (t) { return !t.is_wbs_summary; });
        flat = sortLeafTasks(flat);
        buildGroupedTasks(flat, grouping, 0, 0);
    }

    // Sanitize parents + dates
    const validIds = new Set(displayTasks.map(function (t) { return String(t.id); }));
    displayTasks.forEach(function (t) {
        const p = t.parent;
        if (p === null || p === undefined || p === '' || p === 0 || p === '0') {
            t.parent = 0;
        } else if (!validIds.has(String(p))) {
            t.parent = 0;
        }
        ensureDates(t);
    });

    if (groupConfig.displayOptions && groupConfig.displayOptions.showGrandTotals && displayTasks.length) {
        const actual = displayTasks.filter(function (t) {
            return !t.is_group && !t.is_wbs_summary;
        });
        const totalDur = actual.reduce(function (s, t) {
            return s + (Number(t.original_duration) || 0);
        }, 0);
        const starts = actual.map(function (t) { return t.start_date; }).filter(Boolean).sort();
        const ends = actual.map(function (t) { return t.end_date; }).filter(Boolean).sort();
        displayTasks.push({
            id: '__grand_total__',
            text: 'GRAND TOTAL',
            start_date: starts[0] || fallbackDate(),
            end_date: ends[ends.length - 1] || fallbackDate(),
            parent: 0,
            is_group: true,
            is_grand_total: true,
            group_level: 0,
            group_count: actual.length,
            original_duration: totalDur,
            type: 'project',
            open: true,
            progress: 0
        });
    }

    parseSafe(displayTasks);

    // Open only shallow WBS / groups
    gantt.eachTask(function (task) {
        try {
            if (task.is_wbs_summary && (task.wbs_depth || 1) <= 2) {
                gantt.open(task.id);
            } else if (task.is_group && (task.group_level || 0) <= 2) {
                gantt.open(task.id);
            }
        } catch (e) { /* ignore */ }
    });

    let shown = 0;
    gantt.eachTask(function () { shown++; });
    if (shown === 0) {
        console.warn('Gantt empty after parse. Forcing flat.');
        const flat = allTasks
            .filter(function (t) { return !t.is_wbs_summary; })
            .map(function (t) {
                const x = Object.assign({}, t, {
                    parent: 0,
                    type: t.is_milestone ? 'milestone' : 'task'
                });
                return ensureDates(x);
            });
        parseSafe(flat);
        displayTasks = flat;
    }

    updateGroupInfoBar();
}

function parseSafe(tasks) {
    gantt.clearAll();
    try {
        gantt.parse({ data: tasks, links: visibleLinks(tasks) });
    } catch (err) {
        console.error('Gantt parse failed, falling back to flat', err);
        const flat = (tasks || [])
            .filter(function (t) { return !t.is_group; })
            .map(function (t) {
                const x = Object.assign({}, t, {
                    parent: 0,
                    type: t.is_milestone ? 'milestone' : (t.type || 'task')
                });
                return ensureDates(x);
            });
        gantt.clearAll();
        gantt.parse({ data: flat, links: visibleLinks(flat) });
        displayTasks = flat;
    }
}

function buildGroupedTasks(tasks, groupingConfigs, level, parentId) {
    if (level >= groupingConfigs.length) {
        tasks.forEach(function (t) {
            displayTasks.push(Object.assign({}, t, { parent: parentId }));
        });
        return;
    }

    const field = groupingConfigs[level].field;
    const groups = {};
    tasks.forEach(function (t) {
        const gv = getGroupValue(t, field);
        if (!groups[gv]) groups[gv] = [];
        groups[gv].push(t);
    });

    let keys = Object.keys(groups);
    if (groupConfig.displayOptions && groupConfig.displayOptions.sortBandsAlpha) {
        keys = keys.sort();
    }

    keys.forEach(function (gv) {
        const gt = groups[gv];
        const gid = ('group_' + level + '_' + gv + '_' + parentId).replace(/[^a-zA-Z0-9_]/g, '_');
        const starts = gt.map(function (t) { return t.start_date; }).filter(Boolean).sort();
        const ends = gt.map(function (t) { return t.end_date; }).filter(Boolean).sort();
        const floats = gt.map(function (t) { return Number(t.total_float) || 0; });

        displayTasks.push({
            id: gid,
            text: gv,
            start_date: starts[0] || fallbackDate(),
            end_date: ends[ends.length - 1] || fallbackDate(),
            group_start: starts[0] || '',
            group_end: ends[ends.length - 1] || '',
            parent: parentId,
            is_group: true,
            group_level: level + 1,
            group_count: gt.length,
            original_duration: gt.reduce(function (s, t) {
                return s + (Number(t.original_duration) || 0);
            }, 0),
            total_float: floats.length ? Math.min.apply(null, floats) : 0,
            type: 'project',
            open: level < 2,
            progress: 0
        });
        buildGroupedTasks(gt, groupingConfigs, level + 1, gid);
    });
}

function updateGroupInfoBar() {
    const bar = document.getElementById('groupInfoBar');
    if (!bar) return;
    const active = activeGroupingLevels();
    if (!active.length && !filterConditions.length) {
        bar.style.display = 'none';
        return;
    }
    bar.style.display = 'flex';
    const badges = document.getElementById('groupBadges');
    if (badges) {
        if (active.length) {
            badges.innerHTML = active.map(function (g, idx) {
                return '<span class="group-badge">L' + (idx + 1) + ': ' +
                    esc(GROUPING_FIELDS[g.field] || g.field) + '</span>';
            }).join(' ');
        } else {
            badges.innerHTML = '<span style="color:#94a3b8;">WBS hierarchy (native)</span>';
        }
    }
    const sortInfo = document.getElementById('sortInfo');
    if (sortInfo) {
        sortInfo.textContent =
            (groupConfig.sort.field || 'activity_id') +
            ' (' + (groupConfig.sort.order === 'asc' ? '↑' : '↓') + ')';
    }
}

function applyColorsToDom() {
    (groupConfig.groupLevels || []).forEach(function (level, idx) {
        if (idx < 12 && level.bgColor) {
            document.documentElement.style.setProperty('--group-color-' + (idx + 1), level.bgColor);
        }
    });
}

// ═══════════════════════════════════════════
// ZOOM / TOOLBAR
// ═══════════════════════════════════════════

function setZoom(scale) {
    currentZoom = scale;
    const sel = document.getElementById('timescaleSelect');
    if (sel) sel.value = scale;

    switch (scale) {
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
                { unit: 'week', step: 1, format: 'Wk %W' }
            ];
            gantt.config.min_column_width = 55;
            break;
        case 'month':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' },
                { unit: 'month', step: 1, format: '%M' }
            ];
            gantt.config.min_column_width = 65;
            break;
        case 'quarter':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' },
                {
                    unit: 'quarter', step: 1, format: function (d) {
                        return 'Q' + (Math.floor(d.getMonth() / 3) + 1);
                    }
                }
            ];
            gantt.config.min_column_width = 75;
            break;
        case 'year':
            gantt.config.scales = [{ unit: 'year', step: 1, format: '%Y' }];
            gantt.config.min_column_width = 90;
            break;
        case 'year_quarter':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' },
                {
                    unit: 'quarter', step: 1, format: function (d) {
                        return 'Q' + (Math.floor(d.getMonth() / 3) + 1);
                    }
                }
            ];
            gantt.config.min_column_width = 80;
            break;
        case 'year_month':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' },
                { unit: 'month', step: 1, format: '%M' }
            ];
            gantt.config.min_column_width = 55;
            break;
        case 'year_quarter_month':
            gantt.config.scales = [
                { unit: 'year', step: 1, format: '%Y' },
                {
                    unit: 'quarter', step: 1, format: function (d) {
                        return 'Q' + (Math.floor(d.getMonth() / 3) + 1);
                    }
                },
                { unit: 'month', step: 1, format: '%M' }
            ];
            gantt.config.min_column_width = 55;
            gantt.config.scale_height = 80;
            break;
        case 'quarter_month':
            gantt.config.scales = [
                {
                    unit: 'quarter', step: 1, format: function (d) {
                        return 'Q' + (Math.floor(d.getMonth() / 3) + 1) + ' ' + d.getFullYear();
                    }
                },
                { unit: 'month', step: 1, format: '%M' }
            ];
            gantt.config.min_column_width = 55;
            break;
        default:
            break;
    }
    if (scale !== 'year_quarter_month') gantt.config.scale_height = 60;
    gantt.render();
}

function scrollToToday() {
    gantt.showDate(new Date());
}

function fitAll() {
    const t = gantt.getTaskByTime();
    if (t && t.length) gantt.showDate(t[0].start_date);
}

function expandAll() {
    gantt.eachTask(function (t) { gantt.open(t.id); });
}

function collapseAll() {
    gantt.eachTask(function (t) { gantt.close(t.id); });
}

function toggleCritical() {
    showCriticalOnly = !showCriticalOnly;
    const el = document.getElementById('criticalBtn');
    const btn = el ? el.closest('.tb-btn') : null;
    if (btn) btn.classList.toggle('active', showCriticalOnly);
    if (el) el.textContent = showCriticalOnly ? '🔴 Critical Only ✓' : '🔴 Critical Only';
    renderGantt();
}



function toggleLongestPath() {
    showLongestPathOnly = !showLongestPathOnly;
    const el = document.getElementById('longestPathBtn');
    const btn = el ? el.closest('.tb-btn') : null;
    if (btn) btn.classList.toggle('active', showLongestPathOnly);
    if (el) el.textContent = showLongestPathOnly ? '🎯 Longest Path Only ✓' : '🎯 Longest Path Only';
    renderGantt();
}

function toggleWbsSummary() {
    showWbsOnly = !showWbsOnly;
    const el = document.getElementById('wbsSummaryBtn');
    const btn = el ? el.closest('.tb-btn') : null;
    if (btn) btn.classList.toggle('active', showWbsOnly);
    if (el) el.textContent = showWbsOnly ? '🌳 WBS Only ✓' : '🌳 WBS Only';
    renderGantt();
}

function closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove('show');
}

// ═══════════════════════════════════════════
// COLUMNS MODAL
// ═══════════════════════════════════════════

function showColumnSelector() {
    const container = document.getElementById('columnList');
    if (!container) return;
    container.innerHTML = '';

    const categories = {};
    Object.keys(AVAILABLE_COLUMNS).forEach(function (key) {
        const col = AVAILABLE_COLUMNS[key];
        if (!categories[col.category]) categories[col.category] = [];
        categories[col.category].push(Object.assign({ key: key }, col));
    });

    Object.keys(categories).forEach(function (cat) {
        const h = document.createElement('div');
        h.style.cssText = 'grid-column:span 2;font-weight:600;padding:0.5rem 0 0.25rem;color:#3b82f6;border-bottom:1px solid #e2e8f0;';
        h.textContent = cat;
        container.appendChild(h);

        categories[cat].forEach(function (col) {
            const item = document.createElement('label');
            item.style.cssText = 'display:flex;align-items:center;gap:0.5rem;padding:0.4rem;cursor:pointer;';
            const checked = selectedColumns.indexOf(col.key) >= 0 ? ' checked' : '';
            item.innerHTML =
                '<input type="checkbox" value="' + esc(col.key) + '"' + checked + '>' +
                '<span>' + esc(col.label) + '</span>';
            container.appendChild(item);
        });
    });

    const modal = document.getElementById('columnModal');
    if (modal) modal.classList.add('show');
}

function selectAllColumns(select) {
    document.querySelectorAll('#columnList input[type="checkbox"]').forEach(function (cb) {
        cb.checked = !!select;
    });
}

function resetColumns() {
    document.querySelectorAll('#columnList input[type="checkbox"]').forEach(function (cb) {
        cb.checked = DEFAULT_COLUMNS.indexOf(cb.value) >= 0;
    });
}

function applyColumns() {
    const checked = Array.prototype.map.call(
        document.querySelectorAll('#columnList input[type="checkbox"]:checked'),
        function (cb) { return cb.value; }
    );
    if (!checked.length) {
        alert('Please select at least one column');
        return;
    }
    selectedColumns = checked;
    if (selectedColumns.indexOf('text') < 0) selectedColumns.unshift('text');
    applyColumnConfig();
    renderGantt();
    closeModal('columnModal');
}

// ═══════════════════════════════════════════
// GROUP MODAL
// ═══════════════════════════════════════════

function showGroupModal() {
    const modal = document.getElementById('groupModal');
    if (modal) modal.classList.add('show');
    renderGroupByTable();
}

function renderGroupByTable() {
    const tbody = document.getElementById('groupByTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    while (groupConfig.groupLevels.length < 12) {
        const i = groupConfig.groupLevels.length;
        groupConfig.groupLevels.push(Object.assign({
            field: '', indent: true, toLevel: 'all', interval: 'none', pageBreak: false
        }, DEFAULT_LEVEL_COLORS[i] || DEFAULT_LEVEL_COLORS[0]));
    }

    let opts = '<option value="">-- None --</option>';
    Object.keys(GROUPING_FIELDS).forEach(function (k) {
        opts += '<option value="' + esc(k) + '">' + esc(GROUPING_FIELDS[k]) + '</option>';
    });

    groupConfig.groupLevels.forEach(function (level, idx) {
        const tr = document.createElement('tr');
        let sel = opts;
        if (level.field) {
            sel = opts.replace(
                'value="' + level.field + '"',
                'value="' + level.field + '" selected'
            );
        }
        tr.innerHTML =
            '<td style="text-align:center;">' + (idx + 1) + '</td>' +
            '<td><select data-idx="' + idx + '" class="grp-field">' + sel + '</select></td>' +
            '<td style="text-align:center;"><input type="checkbox" class="grp-indent" data-idx="' + idx + '"' +
            (level.indent ? ' checked' : '') + '></td>' +
            '<td><select disabled><option>All</option></select></td>' +
            '<td><select disabled><option>-</option></select></td>' +
            '<td style="text-align:center;"><input type="checkbox" disabled></td>' +
            '<td style="background:' + esc(level.bgColor) + ';color:' + esc(level.textColor) +
            ';text-align:center;">' + esc(level.fontSize) + ' Arial</td>';
        tbody.appendChild(tr);
    });

    tbody.querySelectorAll('select.grp-field').forEach(function (sel) {
        sel.addEventListener('change', function () {
            const i = parseInt(this.getAttribute('data-idx'), 10);
            groupConfig.groupLevels[i].field = this.value;
        });
    });
    tbody.querySelectorAll('input.grp-indent').forEach(function (cb) {
        cb.addEventListener('change', function () {
            const i = parseInt(this.getAttribute('data-idx'), 10);
            groupConfig.groupLevels[i].indent = this.checked;
        });
    });
}

function applyGroupConfig(keepOpen) {
    applyColorsToDom();
    renderGantt();
    if (!keepOpen) closeModal('groupModal');
}

function applyPreset(preset) {
    groupConfig.groupLevels = [];
    for (let i = 0; i < 12; i++) {
        groupConfig.groupLevels.push(Object.assign({
            field: '', indent: true, toLevel: 'all', interval: 'none', pageBreak: false
        }, DEFAULT_LEVEL_COLORS[i]));
    }

    switch (preset) {
        case 'wbs':
            // Native PROJWBS tree from API — clear synthetic grouping
            groupConfig.groupLevels.forEach(function (l) { l.field = ''; });
            showWbsOnly = false;
            break;
        case 'wbs_bands':
            for (let i = 0; i < 12; i++) {
                groupConfig.groupLevels[i].field = 'wbs_level_' + (i + 1);
            }
            break;
        case 'status':
            groupConfig.groupLevels[0].field = 'status';
            break;
        case 'critical':
            groupConfig.groupLevels[0].field = 'critical_text';
            break;
        case 'type':
            groupConfig.groupLevels[0].field = 'activity_type';
            break;
        default:
            break;
    }
    renderGroupByTable();
}

// Optional: click outside modal to close
document.addEventListener('click', function (e) {
    if (e.target && e.target.classList && e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('show');
    }
});

window.toggleLongestPath = toggleLongestPath;

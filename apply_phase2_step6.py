import os
import shutil
from datetime import datetime

print("🚀 Applying Phase 2 - Step 6: Activity Inspector Drawer...")

# 1. Create Backup Folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = f"_backup_phase2_step6_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
print(f"📦 Created backup folder: {backup_dir}")

files_to_backup = [
    "app.py",
    "templates/index.html",
    "templates/gantt.html",
    "templates/evm.html",
    "templates/comparison.html",
    "templates/health.html",
    "templates/trends.html",
    "static/dashboard.js",
    "static/comparison.js",
    "static/health.js",
    "static/trends.js",
]

for file_path in files_to_backup:
    if os.path.exists(file_path):
        dest = os.path.join(backup_dir, os.path.basename(file_path.replace("/", os.sep)))
        shutil.copy2(file_path, dest)
        print(f"   Backed up {file_path}")


# ==============================================================================
# FILE 1: activity_detail_engine.py (NEW)
# ==============================================================================

DETAIL_ENGINE_CODE = '''"""
ACTIVITY DETAIL ENGINE
=======================
Extracts comprehensive detail on a single activity for the Inspector Drawer.
Returns identity, dates, duration, float, predecessors, successors, resources,
constraints, and any health violations that impact this activity.
"""

import logging

logger = logging.getLogger(__name__)


class ActivityDetailEngine:
    """Retrieves a complete detail bundle for a single activity."""

    def __init__(self, engine):
        self.engine = engine

    def get_detail(self, activity_code):
        """Return a complete detail dict for the given activity_code."""
        act = self.engine.activity_by_code.get(activity_code)
        if not act:
            # Try lookup by task_id as a fallback
            act = self.engine.activity_by_id.get(str(activity_code))
            if not act:
                return {'error': f'Activity {activity_code} not found.'}

        task_id = str(act.get('task_id', ''))
        code = act.get('task_code', activity_code)

        return {
            'identity': self._get_identity(act),
            'dates': self._get_dates(act),
            'duration': self._get_duration(act),
            'float': self._get_float(act, task_id),
            'predecessors': self._get_predecessors(task_id),
            'successors': self._get_successors(task_id),
            'resources': self._get_resources(task_id),
            'constraints': self._get_constraints(act),
            'health_violations': self._get_health_violations(act, task_id),
            'raw_task_id': task_id,
        }

    def _get_identity(self, act):
        return {
            'code': act.get('task_code', ''),
            'name': act.get('task_name', ''),
            'type': act.get('type_text', ''),
            'type_code': act.get('task_type', ''),
            'status': act.get('status_text', ''),
            'wbs_name': act.get('wbs_name', ''),
            'wbs_code': act.get('wbs_code', ''),
            'calendar': self._get_calendar_name(act.get('clndr_id', '')),
            'phys_complete_pct': self._to_float(act.get('phys_complete_pct', '0')),
        }

    def _get_dates(self, act):
        def fmt(field):
            v = act.get(field, '')
            if not v:
                return ''
            return str(v)
        
        return {
            'early_start': fmt('early_start_date'),
            'early_finish': fmt('early_end_date'),
            'late_start': fmt('late_start_date'),
            'late_finish': fmt('late_end_date'),
            'actual_start': fmt('act_start_date'),
            'actual_finish': fmt('act_end_date'),
            'target_start': fmt('target_start_date'),
            'target_finish': fmt('target_end_date'),
        }

    def _get_duration(self, act):
        orig = self._to_float(act.get('original_duration_days', 0))
        remain = self._to_float(act.get('remaining_duration_days', 0))
        actual = max(0, orig - remain) if act.get('status_code') != 'TK_NotStart' else 0
        return {
            'original_days': round(orig, 1),
            'remaining_days': round(remain, 1),
            'actual_days': round(actual, 1),
            'at_completion_days': round(actual + remain, 1),
        }

    def _get_float(self, act, task_id):
        tf = self._to_float(act.get('total_float_days', 0))
        ff = self._to_float(act.get('free_float_days', 0))
        is_critical = bool(act.get('is_critical', False))
        is_longest_path = task_id in getattr(self.engine, 'longest_path_ids', set())
        return {
            'total_float_days': round(tf, 1),
            'free_float_days': round(ff, 1),
            'is_critical': is_critical,
            'is_longest_path': is_longest_path,
            'is_negative_float': tf < 0,
        }

    def _get_predecessors(self, task_id):
        result = []
        preds = self.engine.predecessors.get(task_id, [])
        for p in preds:
            pred_id = p.get('task_id', '')
            pred_act = self.engine.activity_by_id.get(str(pred_id), {})
            result.append({
                'code': pred_act.get('task_code', ''),
                'name': pred_act.get('task_name', ''),
                'type': self._rel_type_text(p.get('type', '')),
                'lag_days': round(self._to_float(p.get('lag_days', 0)), 1),
                'is_critical': bool(pred_act.get('is_critical', False)),
            })
        return result

    def _get_successors(self, task_id):
        result = []
        succs = self.engine.successors.get(task_id, [])
        for s in succs:
            succ_id = s.get('task_id', '')
            succ_act = self.engine.activity_by_id.get(str(succ_id), {})
            result.append({
                'code': succ_act.get('task_code', ''),
                'name': succ_act.get('task_name', ''),
                'type': self._rel_type_text(s.get('type', '')),
                'lag_days': round(self._to_float(s.get('lag_days', 0)), 1),
                'is_critical': bool(succ_act.get('is_critical', False)),
            })
        return result

    def _get_resources(self, task_id):
        result = []
        resources_by_task = getattr(self.engine, 'resources_by_task', None)
        
        if resources_by_task:
            res_list = resources_by_task.get(task_id, [])
        else:
            res_list = [r for r in self.engine.resources if str(r.get('task_id', '')) == task_id]
        
        rsrc_names = {}
        for r in self.engine.raw_tables.get('RSRC', {}).get('rows', []):
            rid = str(r.get('rsrc_id', ''))
            rsrc_names[rid] = r.get('rsrc_name', '') or r.get('rsrc_short_name', 'Unnamed')
        
        for r in res_list:
            rid = str(r.get('rsrc_id', ''))
            result.append({
                'name': rsrc_names.get(rid, f'Resource {rid}'),
                'planned_units': round(self._to_float(r.get('target_qty', 0)), 1),
                'actual_units': round(
                    self._to_float(r.get('act_reg_qty', 0)) + self._to_float(r.get('act_ot_qty', 0)), 1
                ),
                'planned_cost': round(self._to_float(r.get('target_cost', 0)), 2),
                'actual_cost': round(
                    self._to_float(r.get('act_reg_cost', 0)) + self._to_float(r.get('act_ot_cost', 0)), 2
                ),
            })
        return result

    def _get_constraints(self, act):
        cstr_map = {
            'CS_MSO': 'Must Start On',
            'CS_MSOA': 'Start On or After',
            'CS_MSOB': 'Start On or Before',
            'CS_MEO': 'Must Finish On',
            'CS_MEOA': 'Finish On or After',
            'CS_MEOB': 'Finish On or Before',
            'CS_MANDSTART': 'Mandatory Start',
            'CS_MANDFIN': 'Mandatory Finish',
            'CS_ALAP': 'As Late As Possible',
        }
        primary = act.get('cstr_type', '')
        secondary = act.get('cstr_type2', '')
        return {
            'primary_type': cstr_map.get(primary, primary) if primary else '',
            'primary_date': act.get('cstr_date', ''),
            'secondary_type': cstr_map.get(secondary, secondary) if secondary else '',
            'secondary_date': act.get('cstr_date2', ''),
        }

    def _get_health_violations(self, act, task_id):
        """Check if this activity is called out in any health violations."""
        violations = []
        tf = self._to_float(act.get('total_float_days', 0))
        od = self._to_float(act.get('original_duration_days', 0))
        status = act.get('status_code', '')
        task_type = act.get('task_type', '')
        
        # Missing predecessor (DCMA-01)
        if task_id not in self.engine.predecessors and task_type not in ('TT_Mile', 'TT_FinMile') and status != 'TK_Complete':
            violations.append({
                'id': 'DCMA-01', 'name': 'Missing Predecessor',
                'severity': 'high', 'standard': 'DCMA',
            })
        # Missing successor (DCMA-02)
        if task_id not in self.engine.successors and task_type not in ('TT_Mile', 'TT_FinMile') and status != 'TK_Complete':
            violations.append({
                'id': 'DCMA-02', 'name': 'Missing Successor',
                'severity': 'high', 'standard': 'DCMA',
            })
        # High float (DCMA-07)
        if tf > 44 and status != 'TK_Complete':
            violations.append({
                'id': 'DCMA-07', 'name': 'High Float (>44 days)',
                'severity': 'medium', 'standard': 'DCMA', 'value': f'{tf:.1f}d',
            })
        # Negative float (DCMA-08)
        if tf < 0 and status != 'TK_Complete':
            violations.append({
                'id': 'DCMA-08', 'name': 'Negative Float',
                'severity': 'critical', 'standard': 'DCMA', 'value': f'{tf:.1f}d',
            })
        # High duration (DCMA-09)
        if od > 44 and task_type not in ('TT_Mile', 'TT_FinMile') and status != 'TK_Complete':
            violations.append({
                'id': 'DCMA-09', 'name': 'High Duration (>44 days)',
                'severity': 'medium', 'standard': 'DCMA', 'value': f'{od:.1f}d',
            })
        # Invalid dates (DCMA-10)
        if status == 'TK_NotStart' and act.get('act_start_date', ''):
            violations.append({
                'id': 'DCMA-10', 'name': 'Invalid Actual Start on Not-Started Task',
                'severity': 'critical', 'standard': 'DCMA',
            })
        # Hard constraint (DCMA-06)
        hard_cstrs = ('CS_MSO', 'CS_MEO', 'CS_MANDSTART', 'CS_MANDFIN')
        if act.get('cstr_type') in hard_cstrs or act.get('cstr_type2') in hard_cstrs:
            violations.append({
                'id': 'DCMA-06', 'name': 'Hard Constraint',
                'severity': 'high', 'standard': 'DCMA',
            })
        # ALAP constraint (DCMA-06e)
        if act.get('cstr_type') == 'CS_ALAP' or act.get('cstr_type2') == 'CS_ALAP':
            violations.append({
                'id': 'DCMA-06e', 'name': 'As-Late-As-Possible Constraint',
                'severity': 'high', 'standard': 'DCMA',
            })
        
        return violations

    def _rel_type_text(self, t):
        return {
            'PR_FS': 'FS', 'PR_SS': 'SS', 'PR_FF': 'FF', 'PR_SF': 'SF'
        }.get(t, t)

    def _get_calendar_name(self, clndr_id):
        cal = self.engine.calendars.get(clndr_id, {})
        return cal.get('clndr_name', 'Default') if cal else ''

    def _to_float(self, value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
'''

with open("activity_detail_engine.py", "w", encoding="utf-8") as f:
    f.write(DETAIL_ENGINE_CODE)
print("  ✅ Created activity_detail_engine.py")


# ==============================================================================
# FILE 2: Patch app.py - Add /api/activity-detail/<code> route
# ==============================================================================

try:
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()
    
    # Add ActivityDetailEngine import
    if "from activity_detail_engine import ActivityDetailEngine" not in app_code:
        app_code = app_code.replace(
            "try:\n    from trend_engine import TrendAnalysisEngine",
            "try:\n    from activity_detail_engine import ActivityDetailEngine\n    logger.info(\"✅ ActivityDetailEngine imported\")\nexcept Exception as e:\n    ActivityDetailEngine = None\n    logger.warning(\"❌ ActivityDetailEngine import failed: %s\", e)\n\ntry:\n    from trend_engine import TrendAnalysisEngine"
        )
    
    # Add /api/activity-detail route before if __name__
    if "/api/activity-detail" not in app_code:
        detail_route = '''

# ═══════════════════════════════════════════
# ACTIVITY INSPECTOR DRAWER (Phase 2, Step 6)
# ═══════════════════════════════════════════

@app.route('/api/activity-detail/<path:activity_code>')
def get_activity_detail(activity_code):
    sess_data = get_session_data()
    analysis = sess_data['analysis']
    if analysis['engine'] is None:
        return jsonify({'error': 'No schedule loaded. Upload an XER file first.'}), 400
    if ActivityDetailEngine is None:
        return jsonify({'error': 'activity_detail_engine.py is missing!'}), 500
    try:
        detail_engine = ActivityDetailEngine(analysis['engine'])
        result = detail_engine.get_detail(activity_code)
        if 'error' in result:
            return jsonify(result), 404
        return jsonify({'success': True, 'activity_code': activity_code, 'data': result})
    except Exception as e:
        logger.exception("Activity detail error")
        return jsonify({'error': str(e)}), 500

'''
        app_code = app_code.replace(
            "if __name__ == '__main__':",
            detail_route + "\nif __name__ == '__main__':"
        )
    
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
    print("  ✅ Patched app.py (added /api/activity-detail route)")
except Exception as e:
    print(f"  ⚠️ Could not auto-patch app.py: {e}")


# ==============================================================================
# FILE 3: static/activity_inspector.js (NEW)
# ==============================================================================

INSPECTOR_JS_CODE = '''/*
    ACTIVITY INSPECTOR DRAWER
    ==========================
    Global slide-out drawer that opens when any activity code is clicked.
    Auto-attached to any element with `data-activity-code="XXX"` attribute
    OR `.activity-inspect-link` class.
*/

(function () {
    'use strict';

    let drawer = null;
    let drawerBody = null;
    let drawerTitle = null;
    let overlay = null;
    let currentCode = null;

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

    function fmtNum(v) {
        const n = Number(v);
        if (!Number.isFinite(n)) return '—';
        return n.toLocaleString('en-US', { maximumFractionDigits: 1 });
    }

    function fmtMoney(v) {
        const n = Number(v);
        if (!Number.isFinite(n) || n === 0) return '—';
        return '$' + Math.round(n).toLocaleString('en-US');
    }

    function fmtDate(v) {
        if (!v) return '—';
        return esc(v);
    }

    // ═══════════════════════════════════════════
    // BUILD DRAWER DOM
    // ═══════════════════════════════════════════

    function buildDrawer() {
        if (drawer) return;

        // Overlay
        overlay = document.createElement('div');
        overlay.className = 'ai-drawer-overlay';
        overlay.addEventListener('click', closeDrawer);
        document.body.appendChild(overlay);

        // Drawer
        drawer = document.createElement('div');
        drawer.className = 'ai-drawer';
        drawer.setAttribute('role', 'dialog');
        drawer.setAttribute('aria-labelledby', 'ai-drawer-title');

        drawer.innerHTML =
            '<div class="ai-drawer-header">' +
            '<div>' +
            '<div id="ai-drawer-title" class="ai-drawer-title">Activity Inspector</div>' +
            '<div id="ai-drawer-subtitle" class="ai-drawer-subtitle">Loading…</div>' +
            '</div>' +
            '<div class="ai-drawer-actions">' +
            '<button class="ai-drawer-btn" onclick="window.__aiCopyCode()" title="Copy Activity Code">📋</button>' +
            '<button class="ai-drawer-btn ai-drawer-close" onclick="window.__aiCloseDrawer()" title="Close (ESC)">✕</button>' +
            '</div>' +
            '</div>' +
            '<div id="ai-drawer-body" class="ai-drawer-body">' +
            '<div class="ai-loading">⏳ Loading activity details…</div>' +
            '</div>';

        document.body.appendChild(drawer);

        drawerBody = document.getElementById('ai-drawer-body');
        drawerTitle = document.getElementById('ai-drawer-title');
    }

    // ═══════════════════════════════════════════
    // OPEN / CLOSE
    // ═══════════════════════════════════════════

    async function openDrawer(activityCode) {
        buildDrawer();
        currentCode = activityCode;
        drawer.classList.add('ai-drawer-open');
        overlay.classList.add('ai-drawer-open');
        document.body.style.overflow = 'hidden';

        drawerTitle.textContent = 'Activity Inspector';
        document.getElementById('ai-drawer-subtitle').textContent = 'Loading ' + activityCode + '…';
        drawerBody.innerHTML = '<div class="ai-loading">⏳ Loading activity details…</div>';

        try {
            const res = await fetch('/api/activity-detail/' + encodeURIComponent(activityCode));
            const payload = await res.json().catch(function () { return {}; });

            if (!res.ok || payload.error) {
                throw new Error(payload.error || 'Failed to load activity');
            }

            renderDrawerContent(payload.data);
        } catch (err) {
            drawerBody.innerHTML =
                '<div class="ai-error">' +
                '<div style="font-size:2rem;">❌</div>' +
                '<p><strong>Failed to load activity ' + esc(activityCode) + '</strong></p>' +
                '<p style="color:#64748b;">' + esc(err.message || 'Unknown error') + '</p>' +
                '</div>';
        }
    }

    function closeDrawer() {
        if (!drawer) return;
        drawer.classList.remove('ai-drawer-open');
        overlay.classList.remove('ai-drawer-open');
        document.body.style.overflow = '';
        currentCode = null;
    }

    window.__aiCloseDrawer = closeDrawer;
    window.__aiOpenActivity = openDrawer;

    window.__aiCopyCode = function () {
        if (!currentCode) return;
        if (navigator.clipboard) {
            navigator.clipboard.writeText(currentCode).then(function () {
                showToast('📋 Copied: ' + currentCode);
            });
        }
    };

    function showToast(msg) {
        const toast = document.createElement('div');
        toast.className = 'ai-toast';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(function () { toast.classList.add('show'); }, 10);
        setTimeout(function () {
            toast.classList.remove('show');
            setTimeout(function () { toast.remove(); }, 300);
        }, 2000);
    }

    // ═══════════════════════════════════════════
    // RENDER CONTENT
    // ═══════════════════════════════════════════

    function renderDrawerContent(data) {
        if (!data) {
            drawerBody.innerHTML = '<div class="ai-error">No data returned</div>';
            return;
        }

        const id = data.identity || {};
        const dates = data.dates || {};
        const dur = data.duration || {};
        const flt = data.float || {};
        const preds = data.predecessors || [];
        const succs = data.successors || [];
        const resources = data.resources || [];
        const cstr = data.constraints || {};
        const violations = data.health_violations || [];

        drawerTitle.innerHTML = '<span class="ai-code-chip">' + esc(id.code) + '</span> ' + esc(id.name);
        document.getElementById('ai-drawer-subtitle').innerHTML =
            esc(id.type) + ' &middot; ' + esc(id.status) +
            (id.wbs_name ? ' &middot; WBS: ' + esc(id.wbs_name) : '');

        let html = '';

        // Status badges
        html += '<div class="ai-badges">';
        if (flt.is_longest_path) html += '<span class="ai-badge lp">🎯 Longest Path</span>';
        if (flt.is_critical) html += '<span class="ai-badge critical">🔴 Critical</span>';
        if (flt.is_negative_float) html += '<span class="ai-badge danger">⚠️ Negative Float</span>';
        if (id.status === 'Completed') html += '<span class="ai-badge success">✅ Completed</span>';
        else if (id.status === 'In Progress') html += '<span class="ai-badge warning">🔄 In Progress</span>';
        else html += '<span class="ai-badge muted">📋 ' + esc(id.status) + '</span>';
        html += '</div>';

        // Health violations
        if (violations.length) {
            html += '<div class="ai-section">' +
                '<div class="ai-section-title">⚠️ Health Violations (' + violations.length + ')</div>' +
                '<div class="ai-violations">';
            violations.forEach(function (v) {
                const sevClass = 'sev-' + esc((v.severity || 'low').toLowerCase());
                html += '<div class="ai-violation ' + sevClass + '">' +
                    '<span class="ai-violation-badge">' + esc(v.id) + '</span>' +
                    '<span class="ai-violation-name">' + esc(v.name) + '</span>' +
                    (v.value ? '<span class="ai-violation-value">' + esc(v.value) + '</span>' : '') +
                    '</div>';
            });
            html += '</div></div>';
        }

        // Duration & Float grid
        html += '<div class="ai-section"><div class="ai-section-title">⏱ Duration & Float</div>' +
            '<div class="ai-kv-grid">' +
            kvRow('Original Duration', fmtNum(dur.original_days) + 'd') +
            kvRow('Remaining Duration', fmtNum(dur.remaining_days) + 'd') +
            kvRow('Actual Duration', fmtNum(dur.actual_days) + 'd') +
            kvRow('% Complete', fmtNum(id.phys_complete_pct) + '%') +
            kvRow('Total Float', fmtNum(flt.total_float_days) + 'd', flt.is_negative_float ? 'danger' : (flt.is_critical ? 'warning' : '')) +
            kvRow('Free Float', fmtNum(flt.free_float_days) + 'd') +
            '</div></div>';

        // Dates grid
        html += '<div class="ai-section"><div class="ai-section-title">📅 Dates</div>' +
            '<div class="ai-kv-grid">' +
            kvRow('Early Start', fmtDate(dates.early_start)) +
            kvRow('Early Finish', fmtDate(dates.early_finish)) +
            kvRow('Late Start', fmtDate(dates.late_start)) +
            kvRow('Late Finish', fmtDate(dates.late_finish)) +
            kvRow('Actual Start', fmtDate(dates.actual_start)) +
            kvRow('Actual Finish', fmtDate(dates.actual_finish)) +
            kvRow('Target Start', fmtDate(dates.target_start)) +
            kvRow('Target Finish', fmtDate(dates.target_finish)) +
            '</div></div>';

        // Constraints
        if (cstr.primary_type || cstr.secondary_type) {
            html += '<div class="ai-section"><div class="ai-section-title">📌 Constraints</div>' +
                '<div class="ai-kv-grid">';
            if (cstr.primary_type) {
                html += kvRow('Primary', esc(cstr.primary_type) + (cstr.primary_date ? ' (' + esc(cstr.primary_date) + ')' : ''));
            }
            if (cstr.secondary_type) {
                html += kvRow('Secondary', esc(cstr.secondary_type) + (cstr.secondary_date ? ' (' + esc(cstr.secondary_date) + ')' : ''));
            }
            html += '</div></div>';
        }

        // Predecessors
        html += '<div class="ai-section">' +
            '<div class="ai-section-title">🔗 Predecessors (' + preds.length + ')</div>';
        if (!preds.length) {
            html += '<div class="ai-empty">No predecessors</div>';
        } else {
            html += '<div class="ai-rel-list">';
            preds.forEach(function (p) {
                html += '<div class="ai-rel-item' + (p.is_critical ? ' critical' : '') + '" data-activity-code="' + esc(p.code) + '">' +
                    '<span class="ai-rel-code">' + esc(p.code) + '</span>' +
                    '<span class="ai-rel-name">' + esc(p.name) + '</span>' +
                    '<span class="ai-rel-tag">' + esc(p.type) + (p.lag_days !== 0 ? ' ' + (p.lag_days > 0 ? '+' : '') + p.lag_days + 'd' : '') + '</span>' +
                    '</div>';
            });
            html += '</div>';
        }
        html += '</div>';

        // Successors
        html += '<div class="ai-section">' +
            '<div class="ai-section-title">➡️ Successors (' + succs.length + ')</div>';
        if (!succs.length) {
            html += '<div class="ai-empty">No successors</div>';
        } else {
            html += '<div class="ai-rel-list">';
            succs.forEach(function (s) {
                html += '<div class="ai-rel-item' + (s.is_critical ? ' critical' : '') + '" data-activity-code="' + esc(s.code) + '">' +
                    '<span class="ai-rel-code">' + esc(s.code) + '</span>' +
                    '<span class="ai-rel-name">' + esc(s.name) + '</span>' +
                    '<span class="ai-rel-tag">' + esc(s.type) + (s.lag_days !== 0 ? ' ' + (s.lag_days > 0 ? '+' : '') + s.lag_days + 'd' : '') + '</span>' +
                    '</div>';
            });
            html += '</div>';
        }
        html += '</div>';

        // Resources
        if (resources.length) {
            html += '<div class="ai-section">' +
                '<div class="ai-section-title">👷 Resources (' + resources.length + ')</div>' +
                '<div class="ai-resource-list">';
            resources.forEach(function (r) {
                html += '<div class="ai-resource-item">' +
                    '<div class="ai-resource-name">' + esc(r.name) + '</div>' +
                    '<div class="ai-resource-metrics">' +
                    '<span>📊 ' + fmtNum(r.planned_units) + ' hrs planned</span>' +
                    (r.actual_units > 0 ? '<span>✅ ' + fmtNum(r.actual_units) + ' hrs actual</span>' : '') +
                    (r.planned_cost > 0 ? '<span>💰 ' + fmtMoney(r.planned_cost) + ' planned</span>' : '') +
                    (r.actual_cost > 0 ? '<span>💵 ' + fmtMoney(r.actual_cost) + ' actual</span>' : '') +
                    '</div>' +
                    '</div>';
            });
            html += '</div></div>';
        }

        // Calendar / Meta
        html += '<div class="ai-section"><div class="ai-section-title">🧭 Metadata</div>' +
            '<div class="ai-kv-grid">' +
            kvRow('Calendar', esc(id.calendar)) +
            kvRow('WBS Code', esc(id.wbs_code)) +
            kvRow('WBS Name', esc(id.wbs_name)) +
            kvRow('Activity Type', esc(id.type)) +
            '</div></div>';

        drawerBody.innerHTML = html;
    }

    function kvRow(label, value, cls) {
        return '<div class="ai-kv-row' + (cls ? ' ' + cls : '') + '">' +
            '<div class="ai-kv-label">' + label + '</div>' +
            '<div class="ai-kv-value">' + value + '</div>' +
            '</div>';
    }

    // ═══════════════════════════════════════════
    // EVENT DELEGATION (Global click handler)
    // ═══════════════════════════════════════════

    document.addEventListener('click', function (e) {
        // Look for closest ancestor with data-activity-code
        let target = e.target;
        while (target && target !== document.body) {
            if (target.dataset && target.dataset.activityCode) {
                e.preventDefault();
                openDrawer(target.dataset.activityCode);
                return;
            }
            if (target.classList && target.classList.contains('activity-inspect-link')) {
                const code = target.textContent.trim();
                if (code) {
                    e.preventDefault();
                    openDrawer(code);
                    return;
                }
            }
            target = target.parentElement;
        }
    });

    // ESC to close
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && drawer && drawer.classList.contains('ai-drawer-open')) {
            closeDrawer();
        }
    });

    console.log('✅ Activity Inspector Drawer initialized');
})();
'''

os.makedirs("static", exist_ok=True)
with open("static/activity_inspector.js", "w", encoding="utf-8") as f:
    f.write(INSPECTOR_JS_CODE)
print("  ✅ Created static/activity_inspector.js")


# ==============================================================================
# FILE 4: static/activity_inspector.css (NEW)
# ==============================================================================

INSPECTOR_CSS_CODE = '''/*
    ACTIVITY INSPECTOR DRAWER STYLES
    =================================
*/

.ai-drawer-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.5);
    z-index: 9998;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
}
.ai-drawer-overlay.ai-drawer-open {
    opacity: 1;
    pointer-events: auto;
}

.ai-drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    max-width: 540px;
    background: #ffffff;
    box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15);
    z-index: 9999;
    transform: translateX(100%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.ai-drawer.ai-drawer-open {
    transform: translateX(0);
}

.ai-drawer-header {
    background: linear-gradient(135deg, #1e40af, #3730a3);
    color: #ffffff;
    padding: 1.25rem 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.ai-drawer-title {
    font-size: 1.1rem;
    font-weight: 700;
    line-height: 1.3;
    color: #ffffff;
    word-break: break-word;
}
.ai-drawer-subtitle {
    font-size: 0.82rem;
    color: rgba(255, 255, 255, 0.75);
    margin-top: 0.3rem;
}
.ai-drawer-actions {
    display: flex;
    gap: 0.4rem;
    flex-shrink: 0;
}
.ai-drawer-btn {
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    padding: 0.45rem 0.7rem;
    cursor: pointer;
    font-size: 0.95rem;
    transition: all 0.15s;
}
.ai-drawer-btn:hover {
    background: rgba(255, 255, 255, 0.25);
}
.ai-drawer-close {
    font-weight: 700;
}

.ai-code-chip {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
    font-size: 0.85rem;
    margin-right: 0.35rem;
}

.ai-drawer-body {
    flex: 1;
    overflow-y: auto;
    padding: 1.25rem 1.5rem;
    background: #f8fafc;
}

.ai-loading, .ai-error, .ai-empty {
    text-align: center;
    padding: 2rem 1rem;
    color: #64748b;
}
.ai-error { color: #dc2626; }
.ai-empty { font-size: 0.85rem; font-style: italic; padding: 0.75rem; }

.ai-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 1.25rem;
}
.ai-badge {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    background: #e2e8f0;
    color: #334155;
}
.ai-badge.lp { background: #ede9fe; color: #5b21b6; }
.ai-badge.critical { background: #fee2e2; color: #991b1b; }
.ai-badge.danger { background: #7f1d1d; color: #ffffff; }
.ai-badge.success { background: #d1fae5; color: #065f46; }
.ai-badge.warning { background: #fef3c7; color: #92400e; }
.ai-badge.muted { background: #e2e8f0; color: #475569; }

.ai-section {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
}
.ai-section-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: #1e40af;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #e2e8f0;
}

.ai-kv-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.5rem;
}
.ai-kv-row {
    display: flex;
    flex-direction: column;
    padding: 0.5rem 0.75rem;
    background: #f8fafc;
    border-radius: 6px;
    border-left: 3px solid #e2e8f0;
}
.ai-kv-row.warning { border-left-color: #f59e0b; background: #fffbeb; }
.ai-kv-row.danger { border-left-color: #dc2626; background: #fef2f2; }
.ai-kv-label {
    font-size: 0.7rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 600;
    margin-bottom: 0.2rem;
}
.ai-kv-value {
    font-size: 0.9rem;
    font-weight: 600;
    color: #1e293b;
    word-break: break-word;
}

.ai-violations {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
}
.ai-violation {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 0.75rem;
    border-radius: 6px;
    border-left: 3px solid #94a3b8;
    background: #f1f5f9;
    font-size: 0.85rem;
}
.ai-violation.sev-critical { background: #fef2f2; border-left-color: #7f1d1d; }
.ai-violation.sev-high { background: #fef2f2; border-left-color: #dc2626; }
.ai-violation.sev-medium { background: #fffbeb; border-left-color: #f59e0b; }
.ai-violation.sev-low { background: #f0f9ff; border-left-color: #3b82f6; }
.ai-violation-badge {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-family: 'SF Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    color: #1e293b;
    flex-shrink: 0;
}
.ai-violation-name { flex: 1; color: #1e293b; }
.ai-violation-value {
    font-weight: 700;
    color: #7f1d1d;
    font-family: 'SF Mono', monospace;
    font-size: 0.82rem;
}

.ai-rel-list {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    max-height: 300px;
    overflow-y: auto;
}
.ai-rel-item {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.6rem;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: #f8fafc;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
    cursor: pointer;
    transition: all 0.15s;
    font-size: 0.85rem;
}
.ai-rel-item:hover {
    background: #eff6ff;
    border-color: #3b82f6;
    transform: translateX(-2px);
}
.ai-rel-item.critical {
    background: #fef2f2;
    border-color: #fecaca;
}
.ai-rel-item.critical:hover {
    background: #fee2e2;
}
.ai-rel-code {
    font-family: 'SF Mono', monospace;
    font-size: 0.8rem;
    font-weight: 700;
    color: #1e40af;
}
.ai-rel-name {
    color: #334155;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.ai-rel-tag {
    font-size: 0.72rem;
    font-weight: 700;
    background: #dbeafe;
    color: #1e40af;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    font-family: 'SF Mono', monospace;
}

.ai-resource-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.ai-resource-item {
    padding: 0.65rem 0.85rem;
    background: #f8fafc;
    border-radius: 6px;
    border-left: 3px solid #3b82f6;
}
.ai-resource-name {
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.35rem;
    font-size: 0.9rem;
}
.ai-resource-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    font-size: 0.78rem;
    color: #64748b;
}
.ai-resource-metrics span { white-space: nowrap; }

.ai-toast {
    position: fixed;
    bottom: 2rem;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: #1e293b;
    color: #ffffff;
    padding: 0.75rem 1.25rem;
    border-radius: 8px;
    font-size: 0.85rem;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    z-index: 10000;
    opacity: 0;
    transition: all 0.25s;
}
.ai-toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
}

/* Make activity codes look clickable */
[data-activity-code] {
    cursor: pointer !important;
    transition: color 0.15s;
}
[data-activity-code]:hover {
    color: #3b82f6 !important;
    text-decoration: underline;
}

/* Responsive */
@media (max-width: 600px) {
    .ai-drawer { max-width: 100%; }
    .ai-kv-grid { grid-template-columns: 1fr; }
}
'''

with open("static/activity_inspector.css", "w", encoding="utf-8") as f:
    f.write(INSPECTOR_CSS_CODE)
print("  ✅ Created static/activity_inspector.css")


# ==============================================================================
# FILE 5-10: Inject Inspector CSS + JS into all templates
# ==============================================================================

INSPECTOR_INCLUDE = '''
    <!-- Activity Inspector Drawer (Global) -->
    <link rel="stylesheet" href="{{ url_for('static', filename='activity_inspector.css') }}">
    <script defer src="{{ url_for('static', filename='activity_inspector.js') }}"></script>
</head>'''


def inject_inspector(template_path):
    if not os.path.exists(template_path):
        return
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if 'activity_inspector.js' in content:
            return  # Already injected
        
        content = content.replace("</head>", INSPECTOR_INCLUDE, 1)
        
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ Injected Inspector into {template_path}")
    except Exception as e:
        print(f"  ⚠️ Could not inject into {template_path}: {e}")


for tpl in [
    "templates/index.html", "templates/gantt.html", "templates/evm.html",
    "templates/comparison.html", "templates/health.html", "templates/trends.html"
]:
    inject_inspector(tpl)


# ==============================================================================
# FILE 11-13: Make activity codes clickable in existing JS files
# ==============================================================================

# Patch dashboard.js — add data-activity-code to activity table rows
try:
    with open("static/dashboard.js", "r", encoding="utf-8") as f:
        js = f.read()
    
    # In activity render, wrap activity code in clickable span
    if 'data-activity-code' not in js:
        js = js.replace(
            "'<td><strong>' + esc(act.code) + '</strong></td>' +",
            "'<td><strong data-activity-code=\"' + esc(act.code) + '\">' + esc(act.code) + '</strong></td>' +",
        )
        with open("static/dashboard.js", "w", encoding="utf-8") as f:
            f.write(js)
        print("  ✅ Patched static/dashboard.js (activity codes now clickable)")
except Exception as e:
    print(f"  ⚠️ Could not patch dashboard.js: {e}")

# Patch comparison.js — make codes clickable in tables
try:
    with open("static/comparison.js", "r", encoding="utf-8") as f:
        js = f.read()
    
    if 'data-activity-code' not in js:
        js = js.replace(
            "'<td><strong>' + esc(item.code) + '</strong></td>' +",
            "'<td><strong data-activity-code=\"' + esc(item.code) + '\">' + esc(item.code) + '</strong></td>' +",
        )
        js = js.replace(
            "'<td><strong>' + esc(a.code) + '</strong></td>' +",
            "'<td><strong data-activity-code=\"' + esc(a.code) + '\">' + esc(a.code) + '</strong></td>' +",
        )
        js = js.replace(
            "'<div><strong>' + esc(a.code) + '</strong> - '",
            "'<div><strong data-activity-code=\"' + esc(a.code) + '\">' + esc(a.code) + '</strong> - '"
        )
        with open("static/comparison.js", "w", encoding="utf-8") as f:
            f.write(js)
        print("  ✅ Patched static/comparison.js (activity codes now clickable)")
except Exception as e:
    print(f"  ⚠️ Could not patch comparison.js: {e}")

# Patch health.js — activity codes in failed_items list
try:
    with open("static/health.js", "r", encoding="utf-8") as f:
        js = f.read()
    
    if 'data-activity-code' not in js:
        js = js.replace(
            "'<strong>' + code + '</strong>'",
            "'<strong data-activity-code=\"' + code + '\">' + code + '</strong>'"
        )
        with open("static/health.js", "w", encoding="utf-8") as f:
            f.write(js)
        print("  ✅ Patched static/health.js (activity codes now clickable)")
except Exception as e:
    print(f"  ⚠️ Could not patch health.js: {e}")

# Patch trends.js — chronic critical table
try:
    with open("static/trends.js", "r", encoding="utf-8") as f:
        js = f.read()
    
    if 'data-activity-code' not in js:
        js = js.replace(
            "'<td><strong>' + esc(c.code) + '</strong></td>' +",
            "'<td><strong data-activity-code=\"' + esc(c.code) + '\">' + esc(c.code) + '</strong></td>' +",
        )
        with open("static/trends.js", "w", encoding="utf-8") as f:
            f.write(js)
        print("  ✅ Patched static/trends.js (activity codes now clickable)")
except Exception as e:
    print(f"  ⚠️ Could not patch trends.js: {e}")


print("\n🎉 Phase 2 - Step 6 (Activity Inspector Drawer) Applied Successfully!")
print("✨ Restart Flask (python app.py) and click any activity code")
print("   on Dashboard, Gantt, Comparison, Health, or Trends pages.")
print("   The Inspector Drawer will slide in from the right!")
print("   Press ESC to close, or click the 📋 button to copy the activity code.")
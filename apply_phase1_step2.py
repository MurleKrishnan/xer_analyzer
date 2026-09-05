import os
import shutil
from datetime import datetime

print("🚀 Applying Phase 1 - Step 2: Dual-Bar Variance Gantt Feature...")

# 1. Create Backup Folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = f"_backup_phase1_step2_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
print(f"📦 Created backup folder: {backup_dir}")

files_to_backup = [
    "comparison_engine.py",
    "templates/comparison.html",
    "static/comparison.js",
]

for file_path in files_to_backup:
    if os.path.exists(file_path):
        dest = os.path.join(backup_dir, os.path.basename(file_path.replace("/", os.sep)))
        shutil.copy2(file_path, dest)
        print(f"   Backed up {file_path}")


# ==============================================================================
# FILE 1: comparison_engine.py (Enhanced with Variance Gantt Data)
# ==============================================================================

COMPARISON_ENGINE_CODE = '''"""
XER COMPARISON ENGINE (with Dual-Bar Variance Gantt Support)
=============================================================
"""

from parser import XERParser
from data_engine import ScheduleEngine
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ScheduleComparator:
    def __init__(self):
        self.baseline_engine = None
        self.current_engine = None
        self.comparison_results = {}

    def load_baseline(self, file_path_or_stream):
        logger.info(f"📊 Loading Baseline: {file_path_or_stream}")
        parser = XERParser()
        tables = parser.parse(file_path_or_stream)
        if tables is None:
            raise Exception("Failed to parse baseline schedule file.")
        self.baseline_engine = ScheduleEngine()
        self.baseline_engine.load_data(tables)
        self.baseline_engine.analyze()

    def load_current(self, file_path_or_stream):
        logger.info(f"📊 Loading Current: {file_path_or_stream}")
        parser = XERParser()
        tables = parser.parse(file_path_or_stream)
        if tables is None:
            raise Exception("Failed to parse current schedule file.")
        self.current_engine = ScheduleEngine()
        self.current_engine.load_data(tables)
        self.current_engine.analyze()

    def compare(self):
        if not self.baseline_engine or not self.current_engine:
            raise Exception("Both baseline and current schedules must be loaded first.")
        
        logger.info("🔍 Comparing schedules...")
        
        baseline_acts = {a.get('task_code', ''): a for a in self.baseline_engine.activities if a.get('task_code')}
        current_acts = {a.get('task_code', ''): a for a in self.current_engine.activities if a.get('task_code')}
        
        baseline_codes = set(baseline_acts.keys())
        current_codes = set(current_acts.keys())
        
        added_codes = current_codes - baseline_codes
        deleted_codes = baseline_codes - current_codes
        common_codes = baseline_codes & current_codes
        
        added = [self._format_activity(current_acts[code], 'added') for code in added_codes]
        deleted = [self._format_activity(baseline_acts[code], 'deleted') for code in deleted_codes]
        
        changed = []
        unchanged_count = 0
        
        for code in common_codes:
            baseline_act = baseline_acts[code]
            current_act = current_acts[code]
            changes = self._detect_changes(baseline_act, current_act)
            
            if changes:
                changed.append({
                    'code': code,
                    'name': current_act.get('task_name', ''),
                    'wbs': current_act.get('wbs_name', ''),
                    'changes': changes,
                    'baseline': self._format_activity(baseline_act, 'baseline'),
                    'current': self._format_activity(current_act, 'current'),
                })
            else:
                unchanged_count += 1
        
        summary = self._calculate_summary(added, deleted, changed, unchanged_count)
        critical_changes = self._analyze_critical_path_changes(baseline_acts, current_acts, common_codes)
        relationship_changes = self._compare_relationships()
        variance_gantt = self._build_variance_gantt(baseline_acts, current_acts, added_codes, deleted_codes, common_codes)
        
        self.comparison_results = {
            'summary': summary,
            'added': added,
            'deleted': deleted,
            'changed': changed,
            'critical_changes': critical_changes,
            'relationship_changes': relationship_changes,
            'variance_gantt': variance_gantt,
            'baseline_info': self._get_schedule_info(self.baseline_engine),
            'current_info': self._get_schedule_info(self.current_engine),
        }
        
        return self.comparison_results

    # ═══════════════════════════════════════════════════════
    # DUAL-BAR VARIANCE GANTT DATA BUILDER
    # ═══════════════════════════════════════════════════════
    
    def _build_variance_gantt(self, baseline_acts, current_acts, added_codes, deleted_codes, common_codes):
        """
        Build dual-bar Gantt data for baseline vs current comparison.
        Each row contains both baseline and current dates + variance info.
        """
        rows = []

        # Common activities (changed and unchanged)
        for code in sorted(common_codes):
            b = baseline_acts[code]
            c = current_acts[code]
            
            b_start = self._get_best_start_date(b)
            b_end = self._get_best_finish_date(b)
            c_start = self._get_best_start_date(c)
            c_end = self._get_best_finish_date(c)
            
            if not (b_start and b_end and c_start and c_end):
                continue
            
            finish_delta_days = (c_end - b_end).days
            start_delta_days = (c_start - b_start).days
            
            # Classify variance
            if finish_delta_days > 0:
                variance_class = 'slipped'
            elif finish_delta_days < 0:
                variance_class = 'improved'
            else:
                variance_class = 'unchanged'
            
            is_critical = bool(c.get('is_critical', False))
            is_milestone = c.get('task_type') in ['TT_Mile', 'TT_FinMile']
            is_completed = c.get('status_code') == 'TK_Complete'
            
            rows.append({
                'code': code,
                'name': c.get('task_name', ''),
                'wbs': c.get('wbs_name', ''),
                'baseline_start': b_start.strftime('%Y-%m-%d'),
                'baseline_end': b_end.strftime('%Y-%m-%d'),
                'current_start': c_start.strftime('%Y-%m-%d'),
                'current_end': c_end.strftime('%Y-%m-%d'),
                'baseline_duration': round(float(b.get('original_duration_days', 0) or 0), 1),
                'current_duration': round(float(c.get('original_duration_days', 0) or 0), 1),
                'start_delta': start_delta_days,
                'finish_delta': finish_delta_days,
                'variance_class': variance_class,
                'is_critical': is_critical,
                'is_milestone': is_milestone,
                'is_completed': is_completed,
                'status': c.get('status_text', ''),
                'source': 'common',
            })
        
        # Added activities (only current dates)
        for code in sorted(added_codes):
            a = current_acts[code]
            c_start = self._get_best_start_date(a)
            c_end = self._get_best_finish_date(a)
            if not (c_start and c_end):
                continue
            rows.append({
                'code': code,
                'name': a.get('task_name', ''),
                'wbs': a.get('wbs_name', ''),
                'baseline_start': None,
                'baseline_end': None,
                'current_start': c_start.strftime('%Y-%m-%d'),
                'current_end': c_end.strftime('%Y-%m-%d'),
                'baseline_duration': 0,
                'current_duration': round(float(a.get('original_duration_days', 0) or 0), 1),
                'start_delta': None,
                'finish_delta': None,
                'variance_class': 'added',
                'is_critical': bool(a.get('is_critical', False)),
                'is_milestone': a.get('task_type') in ['TT_Mile', 'TT_FinMile'],
                'is_completed': a.get('status_code') == 'TK_Complete',
                'status': a.get('status_text', ''),
                'source': 'added',
            })
        
        # Deleted activities (only baseline dates)
        for code in sorted(deleted_codes):
            d = baseline_acts[code]
            b_start = self._get_best_start_date(d)
            b_end = self._get_best_finish_date(d)
            if not (b_start and b_end):
                continue
            rows.append({
                'code': code,
                'name': d.get('task_name', ''),
                'wbs': d.get('wbs_name', ''),
                'baseline_start': b_start.strftime('%Y-%m-%d'),
                'baseline_end': b_end.strftime('%Y-%m-%d'),
                'current_start': None,
                'current_end': None,
                'baseline_duration': round(float(d.get('original_duration_days', 0) or 0), 1),
                'current_duration': 0,
                'start_delta': None,
                'finish_delta': None,
                'variance_class': 'deleted',
                'is_critical': bool(d.get('is_critical', False)),
                'is_milestone': d.get('task_type') in ['TT_Mile', 'TT_FinMile'],
                'is_completed': False,
                'status': d.get('status_text', ''),
                'source': 'deleted',
            })
        
        return {
            'rows': rows,
            'total_count': len(rows),
            'slipped_count': sum(1 for r in rows if r['variance_class'] == 'slipped'),
            'improved_count': sum(1 for r in rows if r['variance_class'] == 'improved'),
            'unchanged_count': sum(1 for r in rows if r['variance_class'] == 'unchanged'),
            'added_count': sum(1 for r in rows if r['variance_class'] == 'added'),
            'deleted_count': sum(1 for r in rows if r['variance_class'] == 'deleted'),
        }

    # ═══════════════════════════════════════════════════════
    # EXISTING METHODS (unchanged)
    # ═══════════════════════════════════════════════════════

    def _detect_changes(self, baseline, current):
        changes = []
        
        base_dur = float(baseline.get('original_duration_days', 0) or 0)
        curr_dur = float(current.get('original_duration_days', 0) or 0)
        dur_diff = curr_dur - base_dur
        if abs(dur_diff) > 0.1:
            changes.append({
                'field': 'Duration', 'baseline': f"{base_dur:.1f}d", 'current': f"{curr_dur:.1f}d",
                'delta': f"{dur_diff:+.1f}d", 'delta_days': dur_diff,
                'severity': 'high' if abs(dur_diff) > 5 else 'medium'
            })
        
        base_start = self._get_best_start_date(baseline)
        curr_start = self._get_best_start_date(current)
        if base_start and curr_start and base_start != curr_start:
            delta_days = (curr_start - base_start).days
            if delta_days != 0:
                changes.append({
                    'field': 'Start Date', 'baseline': base_start.strftime('%Y-%m-%d'),
                    'current': curr_start.strftime('%Y-%m-%d'), 'delta': f"{delta_days:+d}d",
                    'delta_days': delta_days, 'severity': 'high' if abs(delta_days) > 7 else 'medium'
                })
        
        base_end = self._get_best_finish_date(baseline)
        curr_end = self._get_best_finish_date(current)
        if base_end and curr_end and base_end != curr_end:
            delta_days = (curr_end - base_end).days
            if delta_days != 0:
                changes.append({
                    'field': 'Finish Date', 'baseline': base_end.strftime('%Y-%m-%d'),
                    'current': curr_end.strftime('%Y-%m-%d'), 'delta': f"{delta_days:+d}d",
                    'delta_days': delta_days, 'severity': 'high' if abs(delta_days) > 7 else 'medium'
                })
        
        base_float = float(baseline.get('total_float_days', 0) or 0)
        curr_float = float(current.get('total_float_days', 0) or 0)
        float_diff = curr_float - base_float
        if abs(float_diff) > 0.5:
            changes.append({
                'field': 'Total Float', 'baseline': f"{base_float:.1f}d", 'current': f"{curr_float:.1f}d",
                'delta': f"{float_diff:+.1f}d", 'delta_days': float_diff,
                'severity': 'high' if curr_float < 0 and base_float >= 0 else 'medium'
            })
        
        base_status = baseline.get('status_text', '')
        curr_status = current.get('status_text', '')
        if base_status != curr_status:
            changes.append({
                'field': 'Status', 'baseline': base_status, 'current': curr_status,
                'delta': '→', 'delta_days': 0, 'severity': 'low'
            })
        
        base_prog = self._to_float(baseline.get('phys_complete_pct', '0'))
        curr_prog = self._to_float(current.get('phys_complete_pct', '0'))
        prog_diff = curr_prog - base_prog
        if abs(prog_diff) > 0.5:
            changes.append({
                'field': 'Progress', 'baseline': f"{base_prog:.0f}%", 'current': f"{curr_prog:.0f}%",
                'delta': f"{prog_diff:+.0f}%", 'delta_days': prog_diff, 'severity': 'low'
            })
        
        return changes

    def _compare_relationships(self):
        base_rels = {f"{r.get('pred_code')}->{r.get('succ_code')}": r for r in self.baseline_engine.relationships if r.get('pred_code') and r.get('succ_code')}
        curr_rels = {f"{r.get('pred_code')}->{r.get('succ_code')}": r for r in self.current_engine.relationships if r.get('pred_code') and r.get('succ_code')}
        
        added_keys = set(curr_rels.keys()) - set(base_rels.keys())
        deleted_keys = set(base_rels.keys()) - set(curr_rels.keys())
        common_keys = set(base_rels.keys()) & set(curr_rels.keys())
        
        modified_logic = []
        for k in common_keys:
            b = base_rels[k]
            c = curr_rels[k]
            type_changed = b.get('pred_type') != c.get('pred_type')
            lag_diff = float(c.get('lag_days', 0) or 0) - float(b.get('lag_days', 0) or 0)
            if type_changed or abs(lag_diff) > 0.1:
                modified_logic.append({
                    'tie': k, 'pred_code': b.get('pred_code'), 'succ_code': b.get('succ_code'),
                    'pred_name': c.get('pred_name', ''), 'succ_name': c.get('succ_name', ''),
                    'baseline_type': b.get('type_text', ''), 'current_type': c.get('type_text', ''),
                    'baseline_lag': round(float(b.get('lag_days', 0) or 0), 1),
                    'current_lag': round(float(c.get('lag_days', 0) or 0), 1),
                    'lag_delta': f"{lag_diff:+.1f}d"
                })
        return {
            'added_count': len(added_keys), 'deleted_count': len(deleted_keys),
            'modified_count': len(modified_logic), 'modified_details': modified_logic
        }

    def _analyze_critical_path_changes(self, baseline_acts, current_acts, common):
        newly_critical = []
        no_longer_critical = []
        for code in common:
            base_crit = bool(baseline_acts[code].get('is_critical', False))
            curr_crit = bool(current_acts[code].get('is_critical', False))
            if not base_crit and curr_crit:
                newly_critical.append({
                    'code': code, 'name': current_acts[code].get('task_name', ''),
                    'wbs': current_acts[code].get('wbs_name', ''),
                    'float': round(float(current_acts[code].get('total_float_days', 0) or 0), 1),
                })
            elif base_crit and not curr_crit:
                no_longer_critical.append({
                    'code': code, 'name': current_acts[code].get('task_name', ''),
                    'wbs': current_acts[code].get('wbs_name', ''),
                    'float': round(float(current_acts[code].get('total_float_days', 0) or 0), 1),
                })
        return {'newly_critical': newly_critical, 'no_longer_critical': no_longer_critical}

    def _calculate_summary(self, added, deleted, changed, unchanged):
        slipped = 0
        improved = 0
        for change_item in changed:
            for c in change_item['changes']:
                if c['field'] == 'Finish Date':
                    delta_days = c.get('delta_days', 0)
                    if delta_days > 0: slipped += 1
                    elif delta_days < 0: improved += 1
                    break
        return {
            'total_baseline': len(deleted) + len(changed) + unchanged,
            'total_current': len(added) + len(changed) + unchanged,
            'added_count': len(added), 'deleted_count': len(deleted),
            'changed_count': len(changed), 'unchanged_count': unchanged,
            'slipped_count': slipped, 'improved_count': improved,
        }

    def _format_activity(self, act, source):
        start = self._get_best_start_date(act)
        finish = self._get_best_finish_date(act)
        return {
            'code': act.get('task_code', ''), 'name': act.get('task_name', ''),
            'wbs': act.get('wbs_name', ''),
            'duration': round(float(act.get('original_duration_days', 0) or 0), 1),
            'float': round(float(act.get('total_float_days', 0) or 0), 1),
            'start': start.strftime('%Y-%m-%d') if start else '',
            'finish': finish.strftime('%Y-%m-%d') if finish else '',
            'status': act.get('status_text', ''),
            'critical': bool(act.get('is_critical', False)),
            'source': source,
        }

    def _get_best_start_date(self, act):
        return act.get('act_start_date_parsed') or act.get('early_start_date_parsed') or act.get('target_start_date_parsed')

    def _get_best_finish_date(self, act):
        return act.get('act_end_date_parsed') or act.get('early_end_date_parsed') or act.get('target_end_date_parsed')

    def _get_schedule_info(self, engine):
        info = engine._get_project_info() if hasattr(engine, '_get_project_info') else {}
        return {
            'name': info.get('name', 'Unknown'),
            'total_activities': len(engine.activities),
            'critical_count': len(engine.critical_activities),
            'total_relationships': len(engine.relationships),
        }

    def _to_float(self, value):
        try: return float(value)
        except (ValueError, TypeError): return 0.0
'''

with open("comparison_engine.py", "w", encoding="utf-8") as f:
    f.write(COMPARISON_ENGINE_CODE)
print("  ✅ Updated comparison_engine.py")


# ==============================================================================
# FILE 2: templates/comparison.html (Full Rewrite with Variance Gantt Section)
# ==============================================================================

COMPARISON_HTML_CODE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compare Schedules | {{ config.app_title }}</title>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>

    <style>
        :root {
            --color-primary: {{ config.theme.primary }};
            --color-primary-dark: {{ config.theme.primary_dark }};
            --color-accent: {{ config.theme.accent }};
            --color-success: {{ config.theme.success }};
            --color-warning: {{ config.theme.warning }};
            --color-danger: {{ config.theme.danger }};
            --color-bg: {{ config.theme.bg }};
            --color-surface: {{ config.theme.surface }};
            --color-text: {{ config.theme.text }};
            --color-muted: {{ config.theme.muted }};
            --color-border: {{ config.theme.border }};
        }
    </style>
    
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    
    <style>
        .compare-upload { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin: 2rem 0; }
        .file-drop {
            background: var(--color-surface); border: 3px dashed var(--color-border);
            border-radius: 12px; padding: 2rem; text-align: center;
            cursor: pointer; transition: all 0.2s;
        }
        .file-drop:hover, .file-drop.dragover {
            border-color: var(--color-accent); background: rgba(59, 130, 246, 0.05);
        }
        .file-drop.has-file {
            border-color: var(--color-success); background: rgba(16, 185, 129, 0.05);
        }
        .file-drop h3 { margin-bottom: 0.5rem; }
        .comparison-summary {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 1rem; margin: 2rem 0;
        }
        .change-badge {
            padding: 0.15rem 0.5rem; border-radius: 8px;
            font-size: 0.75rem; font-weight: 700; display: inline-block;
        }
        .change-badge.high { background: #fee2e2; color: #991b1b; }
        .change-badge.medium { background: #fef3c7; color: #92400e; }
        .change-badge.low { background: #dbeafe; color: #1e40af; }
        .delta-positive { color: var(--color-danger); font-weight: 600; }
        .delta-negative { color: var(--color-success); font-weight: 600; }

        a.btn { text-decoration: none; }
        .app-header .btn-secondary[aria-current="page"] {
            background: rgba(255, 255, 255, 0.4); border-color: #fff; font-weight: 700;
        }

        @media (max-width: 768px) {
            .compare-upload { grid-template-columns: 1fr; }
        }

        /* ═══════════════════════════════════════ */
        /* DUAL-BAR VARIANCE GANTT STYLES        */
        /* ═══════════════════════════════════════ */
        .variance-gantt-section {
            background: var(--color-surface); border: 1px solid var(--color-border);
            border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem;
        }
        .variance-gantt-toolbar {
            display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;
            margin-bottom: 1rem; padding: 0.75rem;
            background: #f8fafc; border: 1px solid var(--color-border); border-radius: 8px;
        }
        .variance-gantt-toolbar select, .variance-gantt-toolbar input {
            padding: 0.4rem 0.6rem; border: 1px solid var(--color-border);
            border-radius: 6px; font-size: 0.85rem; background: #fff;
        }
        .variance-gantt-toolbar label {
            font-size: 0.8rem; color: var(--color-muted); font-weight: 600;
        }
        .variance-gantt-container {
            width: 100%; overflow-x: auto;
            border: 1px solid var(--color-border); border-radius: 8px; background: #fff;
        }
        .variance-gantt-table {
            width: 100%; border-collapse: collapse; font-size: 0.82rem;
        }
        .variance-gantt-table thead {
            background: var(--color-primary); color: #fff; position: sticky; top: 0;
        }
        .variance-gantt-table th {
            padding: 0.55rem 0.6rem; text-align: left; font-weight: 600;
            border-right: 1px solid rgba(255,255,255,0.15);
        }
        .variance-gantt-table td {
            padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--color-border);
            vertical-align: middle;
        }
        .variance-gantt-table tbody tr:hover { background: #f1f5f9; }
        .variance-gantt-table tbody tr.critical-row { background: #fef2f2; }
        .variance-gantt-table tbody tr.critical-row:hover { background: #fee2e2; }
        
        .var-bars-cell {
            position: relative; min-width: 300px; padding: 0.5rem 0.75rem !important;
        }
        .var-bar-row {
            position: relative; height: 14px; margin: 3px 0; border-radius: 3px;
            display: flex; align-items: center; overflow: hidden;
        }
        .var-bar-baseline { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
        .var-bar-current-slipped { background: linear-gradient(90deg, #dc2626, #ef4444); }
        .var-bar-current-improved { background: linear-gradient(90deg, #10b981, #34d399); }
        .var-bar-current-unchanged { background: linear-gradient(90deg, #64748b, #94a3b8); }
        .var-bar-added { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
        .var-bar-deleted { background: linear-gradient(90deg, #94a3b8, #cbd5e1); opacity: 0.6; }
        .var-bar-label {
            font-size: 0.65rem; color: #fff; font-weight: 600;
            padding: 0 0.4rem; white-space: nowrap; text-shadow: 0 1px 1px rgba(0,0,0,0.3);
        }
        .var-milestone {
            width: 12px; height: 12px; transform: rotate(45deg);
            display: inline-block; margin: 3px 0;
        }
        .var-milestone.baseline { background: #3b82f6; }
        .var-milestone.slipped { background: #dc2626; }
        .var-milestone.improved { background: #10b981; }
        .var-milestone.unchanged { background: #64748b; }
        
        .var-legend {
            display: flex; gap: 1rem; flex-wrap: wrap;
            padding: 0.75rem; margin-bottom: 1rem;
            background: #f8fafc; border: 1px solid var(--color-border); border-radius: 8px;
            font-size: 0.8rem;
        }
        .var-legend-item { display: flex; align-items: center; gap: 0.4rem; }
        .var-legend-swatch { width: 20px; height: 12px; border-radius: 2px; }
        
        .variance-badge {
            display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px;
            font-size: 0.72rem; font-weight: 700; white-space: nowrap;
        }
        .variance-badge.slipped { background: #fee2e2; color: #991b1b; }
        .variance-badge.improved { background: #d1fae5; color: #065f46; }
        .variance-badge.unchanged { background: #e2e8f0; color: #475569; }
        .variance-badge.added { background: #ede9fe; color: #5b21b6; }
        .variance-badge.deleted { background: #f1f5f9; color: #475569; }
    </style>
</head>
<body>
    <header class="app-header">
        <div class="header-content">
            <div class="logo-section">
                {% if config.use_logo_image %}
                    <img src="{{ url_for('static', filename=config.logo_path) }}" alt="Logo" style="height: 45px;">
                {% else %}
                    <span class="logo-icon">🔄</span>
                {% endif %}
                <div>
                    <h1>{{ config.app_title }} — Compare</h1>
                    <p class="subtitle">Baseline vs Current Analysis</p>
                </div>
            </div>
            <div class="header-actions">
                <a href="/" class="btn btn-secondary">📊 Dashboard</a>
                <a href="/gantt" class="btn btn-secondary">📅 Gantt</a>
                <a href="/comparison" class="btn btn-secondary" aria-current="page">🔄 Compare</a>
                <a href="/evm" class="btn btn-secondary">📈 EVM</a>
                <a href="/health" class="btn btn-secondary">🏥 Health</a>
            </div>
        </div>
    </header>

    <main class="app-main">
        <div id="uploadSection">
            <h2>Upload Two XER Files to Compare</h2>
            <p style="color:var(--color-muted); margin-bottom:1rem;">
                Compare a baseline schedule with an updated update to track slippage, added/deleted scope, and logic changes.
            </p>
            <div class="compare-upload">
                <div class="file-drop" id="baselineDrop">
                    <h3>📊 Baseline</h3>
                    <p>Original / Approved Schedule</p>
                    <p id="baselineFileName" style="margin-top:1rem; font-weight:600; color:var(--color-accent);"></p>
                    <input type="file" id="baselineInput" accept=".xer" style="display:none;">
                </div>
                <div class="file-drop" id="currentDrop">
                    <h3>📈 Current</h3>
                    <p>Updated / Latest Schedule</p>
                    <p id="currentFileName" style="margin-top:1rem; font-weight:600; color:var(--color-accent);"></p>
                    <input type="file" id="currentInput" accept=".xer" style="display:none;">
                </div>
            </div>
            <div style="text-align:center;">
                <button id="compareBtn" class="btn btn-primary" disabled 
                        style="padding: 0.85rem 3rem; font-size: 1.1rem;">
                    🔍 Compare Schedules
                </button>
            </div>
        </div>

        <div id="loadingSection" class="loading-screen" style="display:none;">
            <div class="spinner"></div>
            <p style="margin-top:1rem;">Comparing schedules...</p>
        </div>

        <div id="resultsSection" style="display:none;">
            <div class="file-info-bar">
                <span>📊 Baseline: <strong id="baselineName">--</strong></span>
                <span>📈 Current: <strong id="currentName">--</strong></span>
                <button onclick="resetComparison()" class="btn btn-secondary" style="margin-left:auto;">
                    🔄 New Comparison
                </button>
            </div>

            <div class="comparison-summary" id="summaryCards"></div>

            <div class="chart-card" style="margin-bottom:2rem;">
                <h3>📊 Scope &amp; Variance Breakdown</h3>
                <div style="height: 300px; position: relative;">
                    <canvas id="changeChart"></canvas>
                </div>
            </div>

            <!-- ═══════════════════════════════════════ -->
            <!-- 🎯 DUAL-BAR VARIANCE GANTT SECTION -->
            <!-- ═══════════════════════════════════════ -->
            <div class="variance-gantt-section" id="varianceGanttSection" style="display:none;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
                    <h2 style="margin: 0;">🎯 Dual-Bar Variance Gantt</h2>
                    <span id="varianceGanttStats" style="font-size: 0.85rem; color: var(--color-muted);"></span>
                </div>
                
                <div class="var-legend">
                    <div class="var-legend-item"><div class="var-legend-swatch" style="background: #3b82f6;"></div>Baseline</div>
                    <div class="var-legend-item"><div class="var-legend-swatch" style="background: #dc2626;"></div>Slipped</div>
                    <div class="var-legend-item"><div class="var-legend-swatch" style="background: #10b981;"></div>Improved</div>
                    <div class="var-legend-item"><div class="var-legend-swatch" style="background: #64748b;"></div>Unchanged</div>
                    <div class="var-legend-item"><div class="var-legend-swatch" style="background: #8b5cf6;"></div>Added</div>
                    <div class="var-legend-item"><div class="var-legend-swatch" style="background: #94a3b8;"></div>Deleted</div>
                </div>

                <div class="variance-gantt-toolbar">
                    <label>Filter:</label>
                    <select id="varianceFilter" onchange="renderVarianceGantt()">
                        <option value="all">All Activities</option>
                        <option value="slipped">Slipped Only</option>
                        <option value="improved">Improved Only</option>
                        <option value="critical">Critical Only</option>
                        <option value="added">Added Only</option>
                        <option value="deleted">Deleted Only</option>
                    </select>
                    
                    <label>Sort:</label>
                    <select id="varianceSort" onchange="renderVarianceGantt()">
                        <option value="delta_desc">Slippage (Highest First)</option>
                        <option value="delta_asc">Improvement (Highest First)</option>
                        <option value="code_asc">Activity Code (A-Z)</option>
                        <option value="start_asc">Baseline Start Date</option>
                    </select>
                    
                    <label>Search:</label>
                    <input type="search" id="varianceSearch" placeholder="Code or name…" oninput="debouncedVarianceRender()">
                    
                    <label>Max:</label>
                    <select id="varianceLimit" onchange="renderVarianceGantt()">
                        <option value="50">50 rows</option>
                        <option value="100" selected>100 rows</option>
                        <option value="250">250 rows</option>
                        <option value="500">500 rows</option>
                        <option value="9999">All</option>
                    </select>
                </div>

                <div class="variance-gantt-container">
                    <table class="variance-gantt-table" id="varianceGanttTable">
                        <thead>
                            <tr>
                                <th style="width: 100px;">Code</th>
                                <th style="width: 200px;">Activity</th>
                                <th style="width: 130px;">WBS</th>
                                <th style="width: 90px;">Baseline Finish</th>
                                <th style="width: 90px;">Current Finish</th>
                                <th style="width: 80px;">Variance</th>
                                <th>Timeline (Top: Baseline / Bottom: Current)</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>

            <div class="dcma-section">
                <h2>🔴 Critical Path Shifts</h2>
                <div class="charts-grid">
                    <div>
                        <h3 style="color:var(--color-danger); margin-bottom: 0.75rem;">➕ Newly Critical</h3>
                        <div id="newlyCriticalList"></div>
                    </div>
                    <div>
                        <h3 style="color:var(--color-success); margin-bottom: 0.75rem;">➖ No Longer Critical</h3>
                        <div id="noLongerCriticalList"></div>
                    </div>
                </div>
            </div>

            <div class="dcma-section" id="relationshipSection" style="display:none;">
                <h2>🔗 Logic &amp; Relationship Changes</h2>
                <div class="comparison-summary" id="relSummaryCards"></div>
                <table id="relChangedTable" class="data-table" style="margin-top: 1rem;">
                    <thead>
                        <tr>
                            <th>Relationship (Pred → Succ)</th>
                            <th>Baseline Type</th>
                            <th>Current Type</th>
                            <th>Baseline Lag</th>
                            <th>Current Lag</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>

            <div class="dcma-section">
                <h2>🔄 Changed Activities</h2>
                <table id="changedTable" class="data-table">
                    <thead>
                        <tr>
                            <th>Code</th><th>Name</th><th>WBS</th><th>Field</th>
                            <th>Baseline</th><th>Current</th><th>Delta</th><th>Impact</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>

            <div class="dcma-section">
                <h2>➕ Added Activities</h2>
                <table id="addedTable" class="data-table">
                    <thead>
                        <tr>
                            <th>Code</th><th>Name</th><th>WBS</th>
                            <th>Duration</th><th>Start</th><th>Finish</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>

            <div class="dcma-section">
                <h2>➖ Deleted Activities</h2>
                <table id="deletedTable" class="data-table">
                    <thead>
                        <tr>
                            <th>Code</th><th>Name</th><th>WBS</th>
                            <th>Duration</th><th>Start</th><th>Finish</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </main>

    <footer class="app-footer">
        <p>&copy; {{ config.footer_year }} {{ config.company_name }} | {{ config.footer_text }}</p>
    </footer>

    <script src="{{ url_for('static', filename='comparison.js') }}"></script>
</body>
</html>
'''

os.makedirs("templates", exist_ok=True)
with open("templates/comparison.html", "w", encoding="utf-8") as f:
    f.write(COMPARISON_HTML_CODE)
print("  ✅ Updated templates/comparison.html")


# ==============================================================================
# FILE 3: static/comparison.js (Full Rewrite with Variance Gantt Renderer)
# ==============================================================================

COMPARISON_JS_CODE = '''/*
    COMPARISON PAGE LOGIC + DUAL-BAR VARIANCE GANTT
    ================================================
*/

let baselineFile = null;
let currentFile = null;
let changeChart = null;
let varianceGanttData = null;
let varianceRenderTimer = null;

const MAX_UPLOAD_MB = 100;
const MAX_COMPARE_ROWS = 2000;

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

function deltaClassFor(field, change) {
    const f = (field || '').toLowerCase();
    let n = change.delta_days;
    if (n == null && typeof change.delta === 'string') {
        const m = String(change.delta).match(/^([+-]?\\d+(?:\\.\\d+)?)/);
        n = m ? parseFloat(m[1]) : 0;
    }
    if (!n || isNaN(n)) return '';
    const moreIsBad = ['finish date', 'start date', 'duration'].indexOf(f) >= 0;
    const moreIsGood = ['progress', 'total float', 'free float'].indexOf(f) >= 0;
    if (moreIsBad) return n > 0 ? 'delta-positive' : 'delta-negative';
    if (moreIsGood) return n > 0 ? 'delta-negative' : 'delta-positive';
    return '';
}

function destroyTable(selector) {
    try {
        if (window.jQuery && $.fn.DataTable && $.fn.DataTable.isDataTable(selector)) {
            $(selector).DataTable().clear().destroy();
        }
    } catch (e) { console.warn('DataTable destroy error on ' + selector, e); }
    const tbody = document.querySelector(selector + ' tbody');
    if (tbody) tbody.innerHTML = '';
}

async function safeFetchJSON(url, options) {
    const res = await fetch(url, options || {});
    let data = {};
    try { data = await res.json(); }
    catch (e) {
        if (!res.ok) throw new Error('Request failed (' + res.status + ')');
        throw new Error('Invalid JSON response from server');
    }
    if (!res.ok || data.error) {
        throw new Error(data.error || ('Request failed (' + res.status + ')'));
    }
    return data;
}

// ═══════════════════════════════════════════
// BOOT & HANDLERS
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
    setupFileHandlers('baseline');
    setupFileHandlers('current');
    const compareBtn = document.getElementById('compareBtn');
    if (compareBtn) compareBtn.addEventListener('click', runComparison);
    checkExistingComparison();
});

function setupFileHandlers(type) {
    const dropZone = document.getElementById(type + 'Drop');
    const input = document.getElementById(type + 'Input');
    if (!dropZone || !input) return;

    dropZone.addEventListener('click', function () { input.click(); });
    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', function () { dropZone.classList.remove('dragover'); });
    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileSelected(type, e.dataTransfer.files[0]);
        }
    });
    input.addEventListener('change', function (e) {
        if (e.target.files && e.target.files.length > 0) {
            handleFileSelected(type, e.target.files[0]);
        }
    });
}

function handleFileSelected(type, file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.xer')) {
        alert('❌ Please select a .xer file');
        return;
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
        alert('❌ File exceeds ' + MAX_UPLOAD_MB + ' MB limit');
        return;
    }
    if (type === 'baseline') baselineFile = file;
    else currentFile = file;

    const nameLabel = document.getElementById(type + 'FileName');
    const dropBox = document.getElementById(type + 'Drop');
    if (nameLabel) nameLabel.textContent = '✅ ' + file.name;
    if (dropBox) dropBox.classList.add('has-file');

    const compareBtn = document.getElementById('compareBtn');
    if (compareBtn && baselineFile && currentFile) compareBtn.disabled = false;
}

async function runComparison() {
    if (!baselineFile || !currentFile) return;
    const uploadSec = document.getElementById('uploadSection');
    const loadingSec = document.getElementById('loadingSection');
    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'block';

    const formData = new FormData();
    formData.append('baseline', baselineFile);
    formData.append('current', currentFile);

    try {
        const response = await safeFetchJSON('/api/compare', { method: 'POST', body: formData });
        showResults(response);
    } catch (err) {
        console.error('Comparison error:', err);
        alert('❌ ' + (err.message || 'Comparison failed'));
        if (loadingSec) loadingSec.style.display = 'none';
        if (uploadSec) uploadSec.style.display = 'block';
    }
}

async function checkExistingComparison() {
    try {
        const res = await fetch('/api/comparison-data');
        const data = await res.json().catch(function () { return {}; });
        if (res.ok && data.has_data) showResults(data);
    } catch (e) { console.warn('No existing comparison found', e); }
}

function showResults(response) {
    const loadingSec = document.getElementById('loadingSection');
    const resultsSec = document.getElementById('resultsSection');
    const uploadSec = document.getElementById('uploadSection');
    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'none';
    if (resultsSec) resultsSec.style.display = 'block';

    const baseName = document.getElementById('baselineName');
    const currName = document.getElementById('currentName');
    if (baseName) baseName.textContent = response.baseline_file || '--';
    if (currName) currName.textContent = response.current_file || '--';

    const results = response.results || {};
    renderSummary(results.summary || {});
    renderChart(results.summary || {});
    renderCriticalChanges(results.critical_changes || {});
    renderRelationshipChanges(results.relationship_changes || {});
    renderChangedActivities(results.changed || []);
    renderAddedActivities(results.added || []);
    renderDeletedActivities(results.deleted || []);
    
    // NEW: Dual-Bar Variance Gantt
    varianceGanttData = results.variance_gantt || null;
    renderVarianceGantt();
}

// ═══════════════════════════════════════════
// STANDARD RENDERERS
// ═══════════════════════════════════════════

function renderSummary(summary) {
    const container = document.getElementById('summaryCards');
    if (!container) return;
    const cards = [
        { icon: '➕', label: 'Added', value: summary.added_count || 0, color: 'blue' },
        { icon: '➖', label: 'Deleted', value: summary.deleted_count || 0, color: 'red' },
        { icon: '🔄', label: 'Changed', value: summary.changed_count || 0, color: 'orange' },
        { icon: '✓', label: 'Unchanged', value: summary.unchanged_count || 0, color: 'green' },
        { icon: '📉', label: 'Slipped', value: summary.slipped_count || 0, color: 'red' },
        { icon: '📈', label: 'Improved', value: summary.improved_count || 0, color: 'green' },
    ];
    container.innerHTML = cards.map(function (c) {
        return (
            '<div class="summary-card ' + esc(c.color) + '">' +
            '<div class="card-icon">' + esc(c.icon) + '</div>' +
            '<div class="card-value">' + esc(c.value) + '</div>' +
            '<div class="card-label">' + esc(c.label) + '</div>' +
            '</div>'
        );
    }).join('');
}

function renderChart(summary) {
    const canvas = document.getElementById('changeChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (changeChart) { changeChart.destroy(); changeChart = null; }
    changeChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Added', 'Deleted', 'Changed', 'Unchanged'],
            datasets: [{
                data: [
                    summary.added_count || 0, summary.deleted_count || 0,
                    summary.changed_count || 0, summary.unchanged_count || 0
                ],
                backgroundColor: ['#3b82f6', '#dc2626', '#f59e0b', '#10b981'],
                borderWidth: 2, borderColor: '#fff'
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } }
        }
    });
}

function renderCriticalChanges(criticalData) {
    const newly = (criticalData && criticalData.newly_critical) || [];
    const noLonger = (criticalData && criticalData.no_longer_critical) || [];
    const newlyDiv = document.getElementById('newlyCriticalList');
    if (newlyDiv) {
        if (!newly.length) {
            newlyDiv.innerHTML = '<p style="color:#64748b;">None</p>';
        } else {
            newlyDiv.innerHTML = newly.slice(0, 50).map(function (a) {
                return (
                    '<div class="issue-item high" style="margin-bottom:0.5rem;">' +
                    '<div><strong>' + esc(a.code) + '</strong> - ' + esc(a.name) +
                    '<div style="font-size:0.85rem; color:#64748b;">Float: ' + esc(a.float) + 'd</div>' +
                    '</div></div>'
                );
            }).join('') + (newly.length > 50 ? '<p style="font-size:0.8rem;color:#64748b;">… and ' + (newly.length - 50) + ' more</p>' : '');
        }
    }
    const noLongerDiv = document.getElementById('noLongerCriticalList');
    if (noLongerDiv) {
        if (!noLonger.length) {
            noLongerDiv.innerHTML = '<p style="color:#64748b;">None</p>';
        } else {
            noLongerDiv.innerHTML = noLonger.slice(0, 50).map(function (a) {
                return (
                    '<div class="issue-item medium" style="margin-bottom:0.5rem;">' +
                    '<div><strong>' + esc(a.code) + '</strong> - ' + esc(a.name) +
                    '<div style="font-size:0.85rem; color:#64748b;">Float: ' + esc(a.float) + 'd</div>' +
                    '</div></div>'
                );
            }).join('') + (noLonger.length > 50 ? '<p style="font-size:0.8rem;color:#64748b;">… and ' + (noLonger.length - 50) + ' more</p>' : '');
        }
    }
}

function renderRelationshipChanges(relData) {
    const section = document.getElementById('relationshipSection');
    if (!section) return;
    if (!relData || (!relData.added_count && !relData.deleted_count && !relData.modified_count)) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';
    const cardsContainer = document.getElementById('relSummaryCards');
    if (cardsContainer) {
        cardsContainer.innerHTML =
            '<div class="summary-card blue">' +
            '<div class="card-icon">➕</div>' +
            '<div class="card-value">' + esc(relData.added_count || 0) + '</div>' +
            '<div class="card-label">Added Logic Ties</div></div>' +
            '<div class="summary-card red">' +
            '<div class="card-icon">➖</div>' +
            '<div class="card-value">' + esc(relData.deleted_count || 0) + '</div>' +
            '<div class="card-label">Deleted Logic Ties</div></div>' +
            '<div class="summary-card orange">' +
            '<div class="card-icon">🔄</div>' +
            '<div class="card-value">' + esc(relData.modified_count || 0) + '</div>' +
            '<div class="card-label">Modified Logic/Lags</div></div>';
    }
    destroyTable('#relChangedTable');
    const tbody = document.querySelector('#relChangedTable tbody');
    if (!tbody) return;
    const details = relData.modified_details || [];
    details.slice(0, MAX_COMPARE_ROWS).forEach(function (r) {
        const tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + esc(r.tie || (r.pred_code + ' → ' + r.succ_code)) + '</strong></td>' +
            '<td>' + esc(r.baseline_type || '') + '</td>' +
            '<td>' + esc(r.current_type || '') + '</td>' +
            '<td>' + esc(r.baseline_lag || 0) + 'd</td>' +
            '<td>' + esc(r.current_lag || 0) + 'd</td>';
        tbody.appendChild(tr);
    });
    if (window.jQuery && $.fn.DataTable && details.length > 0) {
        $('#relChangedTable').DataTable({ pageLength: 25, deferRender: true });
    }
}

function renderChangedActivities(changed) {
    destroyTable('#changedTable');
    const tbody = document.querySelector('#changedTable tbody');
    if (!tbody) return;
    const list = Array.isArray(changed) ? changed : [];
    list.slice(0, MAX_COMPARE_ROWS).forEach(function (item) {
        const changes = item.changes || [];
        changes.forEach(function (change) {
            const tr = document.createElement('tr');
            const deltaClass = deltaClassFor(change.field, change);
            const sev = esc((change.severity || 'low').toLowerCase());
            tr.innerHTML =
                '<td><strong>' + esc(item.code) + '</strong></td>' +
                '<td>' + esc(item.name) + '</td>' +
                '<td>' + esc(item.wbs) + '</td>' +
                '<td><strong>' + esc(change.field) + '</strong></td>' +
                '<td>' + esc(change.baseline) + '</td>' +
                '<td>' + esc(change.current) + '</td>' +
                '<td class="' + deltaClass + '">' + esc(change.delta) + '</td>' +
                '<td><span class="change-badge ' + sev + '">' + esc(sev.toUpperCase()) + '</span></td>';
            tbody.appendChild(tr);
        });
    });
    if (window.jQuery && $.fn.DataTable) {
        $('#changedTable').DataTable({ pageLength: 25, order: [[0, 'asc']], deferRender: true });
    }
}

function renderAddedActivities(added) {
    destroyTable('#addedTable');
    const tbody = document.querySelector('#addedTable tbody');
    if (!tbody) return;
    const list = Array.isArray(added) ? added : [];
    list.slice(0, MAX_COMPARE_ROWS).forEach(function (a) {
        const tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + esc(a.code) + '</strong></td>' +
            '<td>' + esc(a.name) + '</td>' +
            '<td>' + esc(a.wbs) + '</td>' +
            '<td>' + esc(a.duration) + 'd</td>' +
            '<td>' + esc(a.start) + '</td>' +
            '<td>' + esc(a.finish) + '</td>';
        tbody.appendChild(tr);
    });
    if (window.jQuery && $.fn.DataTable) {
        $('#addedTable').DataTable({ pageLength: 25, deferRender: true });
    }
}

function renderDeletedActivities(deleted) {
    destroyTable('#deletedTable');
    const tbody = document.querySelector('#deletedTable tbody');
    if (!tbody) return;
    const list = Array.isArray(deleted) ? deleted : [];
    list.slice(0, MAX_COMPARE_ROWS).forEach(function (a) {
        const tr = document.createElement('tr');
        tr.innerHTML =
            '<td><strong>' + esc(a.code) + '</strong></td>' +
            '<td>' + esc(a.name) + '</td>' +
            '<td>' + esc(a.wbs) + '</td>' +
            '<td>' + esc(a.duration) + 'd</td>' +
            '<td>' + esc(a.start) + '</td>' +
            '<td>' + esc(a.finish) + '</td>';
        tbody.appendChild(tr);
    });
    if (window.jQuery && $.fn.DataTable) {
        $('#deletedTable').DataTable({ pageLength: 25, deferRender: true });
    }
}

function resetComparison() {
    baselineFile = null;
    currentFile = null;
    varianceGanttData = null;
    const bInput = document.getElementById('baselineInput');
    const cInput = document.getElementById('currentInput');
    if (bInput) bInput.value = '';
    if (cInput) cInput.value = '';
    const bName = document.getElementById('baselineFileName');
    const cName = document.getElementById('currentFileName');
    const bDrop = document.getElementById('baselineDrop');
    const cDrop = document.getElementById('currentDrop');
    const compareBtn = document.getElementById('compareBtn');
    if (bName) bName.textContent = '';
    if (cName) cName.textContent = '';
    if (bDrop) bDrop.classList.remove('has-file');
    if (cDrop) cDrop.classList.remove('has-file');
    if (compareBtn) compareBtn.disabled = true;
    if (changeChart) { changeChart.destroy(); changeChart = null; }
    destroyTable('#changedTable');
    destroyTable('#addedTable');
    destroyTable('#deletedTable');
    destroyTable('#relChangedTable');
    const resultsSec = document.getElementById('resultsSection');
    const loadingSec = document.getElementById('loadingSection');
    const uploadSec = document.getElementById('uploadSection');
    if (resultsSec) resultsSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'none';
    if (uploadSec) uploadSec.style.display = 'block';
}


// ═══════════════════════════════════════════
// 🎯 DUAL-BAR VARIANCE GANTT RENDERER
// ═══════════════════════════════════════════

function debouncedVarianceRender() {
    clearTimeout(varianceRenderTimer);
    varianceRenderTimer = setTimeout(renderVarianceGantt, 250);
}

function renderVarianceGantt() {
    const section = document.getElementById('varianceGanttSection');
    if (!section) return;
    
    if (!varianceGanttData || !varianceGanttData.rows || !varianceGanttData.rows.length) {
        section.style.display = 'none';
        return;
    }
    
    section.style.display = 'block';
    
    const rows = varianceGanttData.rows;
    const filter = document.getElementById('varianceFilter').value;
    const sort = document.getElementById('varianceSort').value;
    const search = document.getElementById('varianceSearch').value.trim().toLowerCase();
    const limit = parseInt(document.getElementById('varianceLimit').value, 10);
    
    // 1. Filter
    let filtered = rows.filter(function (r) {
        if (filter === 'slipped' && r.variance_class !== 'slipped') return false;
        if (filter === 'improved' && r.variance_class !== 'improved') return false;
        if (filter === 'critical' && !r.is_critical) return false;
        if (filter === 'added' && r.variance_class !== 'added') return false;
        if (filter === 'deleted' && r.variance_class !== 'deleted') return false;
        if (search) {
            const code = String(r.code || '').toLowerCase();
            const name = String(r.name || '').toLowerCase();
            if (code.indexOf(search) < 0 && name.indexOf(search) < 0) return false;
        }
        return true;
    });
    
    // 2. Sort
    filtered.sort(function (a, b) {
        if (sort === 'delta_desc') return (b.finish_delta || 0) - (a.finish_delta || 0);
        if (sort === 'delta_asc') return (a.finish_delta || 0) - (b.finish_delta || 0);
        if (sort === 'code_asc') return String(a.code).localeCompare(String(b.code));
        if (sort === 'start_asc') return String(a.baseline_start || '9999').localeCompare(String(b.baseline_start || '9999'));
        return 0;
    });
    
    // 3. Limit
    const total = filtered.length;
    filtered = filtered.slice(0, limit);
    
    // 4. Determine timeline range
    let minDate = null, maxDate = null;
    filtered.forEach(function (r) {
        [r.baseline_start, r.baseline_end, r.current_start, r.current_end].forEach(function (d) {
            if (!d) return;
            const dt = new Date(d);
            if (!minDate || dt < minDate) minDate = dt;
            if (!maxDate || dt > maxDate) maxDate = dt;
        });
    });
    
    if (!minDate || !maxDate) {
        document.querySelector('#varianceGanttTable tbody').innerHTML = 
            '<tr><td colspan="7" style="text-align:center;padding:2rem;color:#64748b;">No date range available.</td></tr>';
        return;
    }
    
    const totalMs = maxDate.getTime() - minDate.getTime() || 1;
    
    // 5. Render Stats
    const statsEl = document.getElementById('varianceGanttStats');
    if (statsEl) {
        statsEl.innerHTML = 
            'Showing <strong>' + filtered.length + '</strong> of <strong>' + total + '</strong> activities | ' +
            '📉 ' + varianceGanttData.slipped_count + ' Slipped | ' +
            '📈 ' + varianceGanttData.improved_count + ' Improved | ' +
            '➕ ' + varianceGanttData.added_count + ' Added | ' +
            '➖ ' + varianceGanttData.deleted_count + ' Deleted';
    }
    
    // 6. Render Rows
    const tbody = document.querySelector('#varianceGanttTable tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    filtered.forEach(function (r) {
        const tr = document.createElement('tr');
        if (r.is_critical) tr.classList.add('critical-row');
        
        // Variance badge
        let varianceBadge = '';
        if (r.variance_class === 'slipped') {
            varianceBadge = '<span class="variance-badge slipped">+' + esc(r.finish_delta) + 'd</span>';
        } else if (r.variance_class === 'improved') {
            varianceBadge = '<span class="variance-badge improved">' + esc(r.finish_delta) + 'd</span>';
        } else if (r.variance_class === 'unchanged') {
            varianceBadge = '<span class="variance-badge unchanged">0d</span>';
        } else if (r.variance_class === 'added') {
            varianceBadge = '<span class="variance-badge added">ADDED</span>';
        } else if (r.variance_class === 'deleted') {
            varianceBadge = '<span class="variance-badge deleted">DELETED</span>';
        }
        
        // Build dual-bar timeline
        const barsCell = buildDualBarsCell(r, minDate, totalMs);
        
        tr.innerHTML =
            '<td><strong>' + esc(r.code) + '</strong>' + (r.is_critical ? ' 🔴' : '') + '</td>' +
            '<td>' + esc(r.name) + '</td>' +
            '<td style="font-size: 0.75rem; color: #64748b;">' + esc(r.wbs) + '</td>' +
            '<td>' + esc(r.baseline_end || '—') + '</td>' +
            '<td>' + esc(r.current_end || '—') + '</td>' +
            '<td>' + varianceBadge + '</td>' +
            '<td class="var-bars-cell">' + barsCell + '</td>';
        
        tbody.appendChild(tr);
    });
}

function buildDualBarsCell(r, minDate, totalMs) {
    let html = '';
    
    // Baseline bar
    if (r.baseline_start && r.baseline_end) {
        const bStart = new Date(r.baseline_start);
        const bEnd = new Date(r.baseline_end);
        const bLeft = ((bStart.getTime() - minDate.getTime()) / totalMs) * 100;
        const bWidth = Math.max(0.5, ((bEnd.getTime() - bStart.getTime()) / totalMs) * 100);
        
        if (r.is_milestone) {
            html += '<div style="position: relative; height: 18px; margin: 2px 0;">' +
                    '<div class="var-milestone baseline" style="position: absolute; left: ' + bLeft + '%;"></div>' +
                    '</div>';
        } else {
            html += '<div class="var-bar-row" style="margin-left: ' + bLeft + '%; width: ' + bWidth + '%;" ' +
                    'class="var-bar-row var-bar-baseline" data-tooltip="Baseline: ' + esc(r.baseline_start) + ' to ' + esc(r.baseline_end) + '">' +
                    '<div class="var-bar-baseline" style="width: 100%; height: 100%; display: flex; align-items: center;">' +
                    '<span class="var-bar-label">BL</span></div></div>';
        }
    }
    
    // Current bar
    if (r.current_start && r.current_end) {
        const cStart = new Date(r.current_start);
        const cEnd = new Date(r.current_end);
        const cLeft = ((cStart.getTime() - minDate.getTime()) / totalMs) * 100;
        const cWidth = Math.max(0.5, ((cEnd.getTime() - cStart.getTime()) / totalMs) * 100);
        
        const barClass = 'var-bar-current-' + r.variance_class;
        
        if (r.is_milestone) {
            const mClass = 'var-milestone ' + r.variance_class;
            html += '<div style="position: relative; height: 18px; margin: 2px 0;">' +
                    '<div class="' + mClass + '" style="position: absolute; left: ' + cLeft + '%;"></div>' +
                    '</div>';
        } else {
            html += '<div style="margin-left: ' + cLeft + '%; width: ' + cWidth + '%;" ' +
                    'class="var-bar-row ' + barClass + '" data-tooltip="Current: ' + esc(r.current_start) + ' to ' + esc(r.current_end) + '">' +
                    '<div style="width: 100%; height: 100%; display: flex; align-items: center;">' +
                    '<span class="var-bar-label">CUR</span></div></div>';
        }
    }
    
    // Deleted (baseline only) or Added (current only) placeholders
    if (r.variance_class === 'deleted' && !r.current_start) {
        html += '<div style="margin-left: 0; width: 100%;" class="var-bar-row var-bar-deleted">' +
                '<div style="width: 100%; height: 100%; display: flex; align-items: center;">' +
                '<span class="var-bar-label">DELETED</span></div></div>';
    }
    if (r.variance_class === 'added' && !r.baseline_start) {
        html = '<div style="height: 18px;"></div>' + html;  // Empty row for baseline
    }
    
    return html;
}
'''

os.makedirs("static", exist_ok=True)
with open("static/comparison.js", "w", encoding="utf-8") as f:
    f.write(COMPARISON_JS_CODE)
print("  ✅ Updated static/comparison.js")

print("\n🎉 Phase 1 - Step 2 (Dual-Bar Variance Gantt) Applied Successfully!")
print("✨ Restart Flask (python app.py), upload 2 XER files on /comparison, and see the new Variance Gantt!")
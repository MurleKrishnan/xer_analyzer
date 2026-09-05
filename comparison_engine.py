"""
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

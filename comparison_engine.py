"""
XER COMPARISON ENGINE
=====================
Compares two XER files (e.g., Baseline vs Current) and identifies all differences.

USE CASES:
- Baseline vs Current schedule comparison
- Update-to-update schedule variance analysis
- Forensic delay analysis (AACE RP 29R-03)
- Relationship & logic change tracking
- Slippage / acceleration identification
"""

from parser import XERParser
from data_engine import ScheduleEngine
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ScheduleComparator:
    """
    Compares two schedules and identifies differences across activities,
    dates, duration, float, progress, critical path, and relationships.
    """

    def __init__(self):
        self.baseline_engine = None
        self.current_engine = None
        self.comparison_results = {}

    def load_baseline(self, file_path_or_stream):
        """Load the baseline (original) schedule from path or stream."""
        logger.info(f"📊 Loading Baseline: {file_path_or_stream}")
        
        parser = XERParser()
        tables = parser.parse(file_path_or_stream)
        
        if tables is None:
            raise Exception("Failed to parse baseline schedule file.")
        
        self.baseline_engine = ScheduleEngine()
        self.baseline_engine.load_data(tables)
        self.baseline_engine.analyze()
        
        logger.info(f"  ✅ Baseline loaded: {len(self.baseline_engine.activities)} activities")

    def load_current(self, file_path_or_stream):
        """Load the current (updated) schedule from path or stream."""
        logger.info(f"📊 Loading Current: {file_path_or_stream}")
        
        parser = XERParser()
        tables = parser.parse(file_path_or_stream)
        
        if tables is None:
            raise Exception("Failed to parse current schedule file.")
        
        self.current_engine = ScheduleEngine()
        self.current_engine.load_data(tables)
        self.current_engine.analyze()
        
        logger.info(f"  ✅ Current loaded: {len(self.current_engine.activities)} activities")

    def compare(self):
        """
        Run full schedule comparison.
        
        RETURNS:
            Dictionary with summary, added, deleted, changed, critical shifts,
            and relationship modifications.
        """
        if not self.baseline_engine or not self.current_engine:
            raise Exception("Both baseline and current schedules must be loaded first.")
        
        logger.info("🔍 Comparing schedules...")
        
        # Match activities by task_code
        baseline_acts = {
            a.get('task_code', ''): a 
            for a in self.baseline_engine.activities
            if a.get('task_code')
        }
        current_acts = {
            a.get('task_code', ''): a 
            for a in self.current_engine.activities
            if a.get('task_code')
        }
        
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
        
        self.comparison_results = {
            'summary': summary,
            'added': added,
            'deleted': deleted,
            'changed': changed,
            'critical_changes': critical_changes,
            'relationship_changes': relationship_changes,
            'baseline_info': self._get_schedule_info(self.baseline_engine),
            'current_info': self._get_schedule_info(self.current_engine),
        }
        
        logger.info(
            f"  ✅ Comparison complete: {len(added)} Added, {len(deleted)} Deleted, "
            f"{len(changed)} Changed, {unchanged_count} Unchanged"
        )
        
        return self.comparison_results

    # ═══════════════════════════════════════════════════════
    # FIELD CHANGE DETECTION
    # ═══════════════════════════════════════════════════════

    def _detect_changes(self, baseline, current):
        """Detect field-level variances for matching activities."""
        changes = []
        
        # 1. Duration Change
        base_dur = float(baseline.get('original_duration_days', 0) or 0)
        curr_dur = float(current.get('original_duration_days', 0) or 0)
        dur_diff = curr_dur - base_dur
        if abs(dur_diff) > 0.1:
            changes.append({
                'field': 'Duration',
                'baseline': f"{base_dur:.1f}d",
                'current': f"{curr_dur:.1f}d",
                'delta': f"{dur_diff:+.1f}d",
                'delta_days': dur_diff,
                'severity': 'high' if abs(dur_diff) > 5 else 'medium'
            })
        
        # 2. Start Date Change (Prioritizes Actuals)
        base_start = self._get_best_start_date(baseline)
        curr_start = self._get_best_start_date(current)
        if base_start and curr_start and base_start != curr_start:
            delta_days = (curr_start - base_start).days
            if delta_days != 0:
                changes.append({
                    'field': 'Start Date',
                    'baseline': base_start.strftime('%Y-%m-%d'),
                    'current': curr_start.strftime('%Y-%m-%d'),
                    'delta': f"{delta_days:+d}d",
                    'delta_days': delta_days,
                    'severity': 'high' if abs(delta_days) > 7 else 'medium'
                })
        
        # 3. Finish Date Change (Prioritizes Actuals)
        base_end = self._get_best_finish_date(baseline)
        curr_end = self._get_best_finish_date(current)
        if base_end and curr_end and base_end != curr_end:
            delta_days = (curr_end - base_end).days
            if delta_days != 0:
                changes.append({
                    'field': 'Finish Date',
                    'baseline': base_end.strftime('%Y-%m-%d'),
                    'current': curr_end.strftime('%Y-%m-%d'),
                    'delta': f"{delta_days:+d}d",
                    'delta_days': delta_days,
                    'severity': 'high' if abs(delta_days) > 7 else 'medium'
                })
        
        # 4. Total Float Change
        base_float = float(baseline.get('total_float_days', 0) or 0)
        curr_float = float(current.get('total_float_days', 0) or 0)
        float_diff = curr_float - base_float
        if abs(float_diff) > 0.5:
            changes.append({
                'field': 'Total Float',
                'baseline': f"{base_float:.1f}d",
                'current': f"{curr_float:.1f}d",
                'delta': f"{float_diff:+.1f}d",
                'delta_days': float_diff,
                'severity': 'high' if curr_float < 0 and base_float >= 0 else 'medium'
            })
        
        # 5. Status Change
        base_status = baseline.get('status_text', '')
        curr_status = current.get('status_text', '')
        if base_status != curr_status:
            changes.append({
                'field': 'Status',
                'baseline': base_status,
                'current': curr_status,
                'delta': '→',
                'delta_days': 0,
                'severity': 'low'
            })
        
        # 6. Progress Change
        base_prog = self._to_float(baseline.get('phys_complete_pct', '0'))
        curr_prog = self._to_float(current.get('phys_complete_pct', '0'))
        prog_diff = curr_prog - base_prog
        if abs(prog_diff) > 0.5:
            changes.append({
                'field': 'Progress',
                'baseline': f"{base_prog:.0f}%",
                'current': f"{curr_prog:.0f}%",
                'delta': f"{prog_diff:+.0f}%",
                'delta_days': prog_diff,
                'severity': 'low'
            })
        
        return changes

    # ═══════════════════════════════════════════════════════
    # RELATIONSHIP & LOGIC VARIANCE
    # ═══════════════════════════════════════════════════════

    def _compare_relationships(self):
        """
        Compare network relationships between schedules by (pred_code -> succ_code).
        Identifies added, deleted, and modified logic ties.
        """
        base_rels = {
            f"{r.get('pred_code')}->{r.get('succ_code')}": r
            for r in self.baseline_engine.relationships
            if r.get('pred_code') and r.get('succ_code')
        }
        curr_rels = {
            f"{r.get('pred_code')}->{r.get('succ_code')}": r
            for r in self.current_engine.relationships
            if r.get('pred_code') and r.get('succ_code')
        }
        
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
                    'tie': k,
                    'pred_code': b.get('pred_code'),
                    'succ_code': b.get('succ_code'),
                    'pred_name': c.get('pred_name', ''),
                    'succ_name': c.get('succ_name', ''),
                    'baseline_type': b.get('type_text', ''),
                    'current_type': c.get('type_text', ''),
                    'baseline_lag': round(float(b.get('lag_days', 0) or 0), 1),
                    'current_lag': round(float(c.get('lag_days', 0) or 0), 1),
                    'lag_delta': f"{lag_diff:+.1f}d"
                })

        return {
            'added_count': len(added_keys),
            'deleted_count': len(deleted_keys),
            'modified_count': len(modified_logic),
            'modified_details': modified_logic
        }

    # ═══════════════════════════════════════════════════════
    # CRITICAL PATH SHIFTS
    # ═══════════════════════════════════════════════════════

    def _analyze_critical_path_changes(self, baseline_acts, current_acts, common):
        """Find activities that moved onto or off the critical path."""
        newly_critical = []
        no_longer_critical = []
        
        for code in common:
            base_crit = bool(baseline_acts[code].get('is_critical', False))
            curr_crit = bool(current_acts[code].get('is_critical', False))
            
            if not base_crit and curr_crit:
                newly_critical.append({
                    'code': code,
                    'name': current_acts[code].get('task_name', ''),
                    'wbs': current_acts[code].get('wbs_name', ''),
                    'float': round(float(current_acts[code].get('total_float_days', 0) or 0), 1),
                })
            elif base_crit and not curr_crit:
                no_longer_critical.append({
                    'code': code,
                    'name': current_acts[code].get('task_name', ''),
                    'wbs': current_acts[code].get('wbs_name', ''),
                    'float': round(float(current_acts[code].get('total_float_days', 0) or 0), 1),
                })
        
        return {
            'newly_critical': newly_critical,
            'no_longer_critical': no_longer_critical,
        }

    # ═══════════════════════════════════════════════════════
    # SUMMARY METRICS
    # ═══════════════════════════════════════════════════════

    def _calculate_summary(self, added, deleted, changed, unchanged):
        """
        Calculate summary counts.
        FIXED: Slipped / Improved relies on raw integer delta_days, NOT string matching.
        """
        slipped = 0
        improved = 0
        
        for change_item in changed:
            for c in change_item['changes']:
                if c['field'] == 'Finish Date':
                    delta_days = c.get('delta_days', 0)
                    if delta_days > 0:
                        slipped += 1
                    elif delta_days < 0:
                        improved += 1
                    break
        
        return {
            'total_baseline': len(deleted) + len(changed) + unchanged,
            'total_current': len(added) + len(changed) + unchanged,
            'added_count': len(added),
            'deleted_count': len(deleted),
            'changed_count': len(changed),
            'unchanged_count': unchanged,
            'slipped_count': slipped,
            'improved_count': improved,
        }

    # ═══════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════

    def _format_activity(self, act, source):
        """Format an activity for display in comparison tables."""
        start = self._get_best_start_date(act)
        finish = self._get_best_finish_date(act)
        return {
            'code': act.get('task_code', ''),
            'name': act.get('task_name', ''),
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
        """Returns actual start if present; otherwise early start or target start."""
        return act.get('act_start_date_parsed') or \
               act.get('early_start_date_parsed') or \
               act.get('target_start_date_parsed')

    def _get_best_finish_date(self, act):
        """Returns actual finish if present; otherwise early finish or target finish."""
        return act.get('act_end_date_parsed') or \
               act.get('early_end_date_parsed') or \
               act.get('target_end_date_parsed')

    def _get_schedule_info(self, engine):
        """Get project info dictionary."""
        info = engine._get_project_info() if hasattr(engine, '_get_project_info') else {}
        return {
            'name': info.get('name', 'Unknown'),
            'total_activities': len(engine.activities),
            'critical_count': len(engine.critical_activities),
            'total_relationships': len(engine.relationships),
        }

    def _to_float(self, value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
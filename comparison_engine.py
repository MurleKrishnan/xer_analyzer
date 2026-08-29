"""
XER COMPARISON ENGINE
=====================
Compares two XER files (e.g., Baseline vs Current)
and identifies all differences.

USE CASES:
- Baseline vs Current schedule comparison
- Month-over-month schedule variance analysis
- Change impact analysis
- Slippage identification
"""

from parser import XERParser
from data_engine import ScheduleEngine
from datetime import datetime


class ScheduleComparator:
    """
    Compares two schedules and identifies differences.
    
    HOW TO USE:
        comparator = ScheduleComparator()
        comparator.load_baseline("input/baseline.xer")
        comparator.load_current("input/current.xer")
        results = comparator.compare()
    """

    def __init__(self):
        self.baseline_engine = None
        self.current_engine = None
        self.comparison_results = {}

    def load_baseline(self, file_path):
        """Load the baseline (original) schedule."""
        print(f"📊 Loading Baseline: {file_path}")
        
        parser = XERParser()
        tables = parser.parse(file_path)
        
        if tables is None:
            raise Exception(f"Failed to parse baseline file: {file_path}")
        
        self.baseline_engine = ScheduleEngine()
        self.baseline_engine.load_data(tables)
        self.baseline_engine.analyze()
        
        print(f"  ✅ Baseline loaded: {len(self.baseline_engine.activities)} activities")

    def load_current(self, file_path):
        """Load the current (updated) schedule."""
        print(f"📊 Loading Current: {file_path}")
        
        parser = XERParser()
        tables = parser.parse(file_path)
        
        if tables is None:
            raise Exception(f"Failed to parse current file: {file_path}")
        
        self.current_engine = ScheduleEngine()
        self.current_engine.load_data(tables)
        self.current_engine.analyze()
        
        print(f"  ✅ Current loaded: {len(self.current_engine.activities)} activities")

    def compare(self):
        """
        Run the full comparison.
        
        Returns a dictionary with all comparison results.
        """
        if not self.baseline_engine or not self.current_engine:
            raise Exception("Both baseline and current must be loaded first")
        
        print("\n🔍 Comparing schedules...")
        
        # Build lookup dictionaries (by activity code)
        baseline_acts = {
            a.get('task_code'): a 
            for a in self.baseline_engine.activities
        }
        current_acts = {
            a.get('task_code'): a 
            for a in self.current_engine.activities
        }
        
        # Find added, deleted, and common activities
        baseline_codes = set(baseline_acts.keys())
        current_codes = set(current_acts.keys())
        
        added_codes = current_codes - baseline_codes
        deleted_codes = baseline_codes - current_codes
        common_codes = baseline_codes & current_codes
        
        # Analyze added activities
        added = [
            self._format_activity(current_acts[code], 'added')
            for code in added_codes
        ]
        
        # Analyze deleted activities
        deleted = [
            self._format_activity(baseline_acts[code], 'deleted')
            for code in deleted_codes
        ]
        
        # Analyze changed activities
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
        
        # Calculate summary metrics
        summary = self._calculate_summary(
            added, deleted, changed, unchanged_count
        )
        
        # Analyze critical path changes
        critical_changes = self._analyze_critical_path_changes(
            baseline_acts, current_acts, common_codes
        )
        
        self.comparison_results = {
            'summary': summary,
            'added': added,
            'deleted': deleted,
            'changed': changed,
            'critical_changes': critical_changes,
            'baseline_info': self._get_schedule_info(self.baseline_engine),
            'current_info': self._get_schedule_info(self.current_engine),
        }
        
        print(f"  ✅ Comparison complete")
        print(f"     Added: {len(added)}")
        print(f"     Deleted: {len(deleted)}")
        print(f"     Changed: {len(changed)}")
        print(f"     Unchanged: {unchanged_count}")
        
        return self.comparison_results

    def _detect_changes(self, baseline, current):
        """
        Detect what changed between two versions of the same activity.
        
        Returns a list of changes.
        """
        changes = []
        
        # Duration change
        base_dur = baseline.get('original_duration_days', 0)
        curr_dur = current.get('original_duration_days', 0)
        if abs(base_dur - curr_dur) > 0.1:
            changes.append({
                'field': 'Duration',
                'baseline': f"{base_dur:.1f}d",
                'current': f"{curr_dur:.1f}d",
                'delta': f"{curr_dur - base_dur:+.1f}d",
                'severity': 'high' if abs(curr_dur - base_dur) > 5 else 'medium'
            })
        
        # Start date change
        base_start = self._get_date(baseline, 'early_start_date') or \
                     self._get_date(baseline, 'target_start_date')
        curr_start = self._get_date(current, 'early_start_date') or \
                     self._get_date(current, 'target_start_date')
        
        if base_start and curr_start and base_start != curr_start:
            delta_days = (curr_start - base_start).days
            changes.append({
                'field': 'Start Date',
                'baseline': base_start.strftime('%Y-%m-%d'),
                'current': curr_start.strftime('%Y-%m-%d'),
                'delta': f"{delta_days:+d}d",
                'severity': 'high' if abs(delta_days) > 7 else 'medium'
            })
        
        # Finish date change
        base_end = self._get_date(baseline, 'early_end_date') or \
                   self._get_date(baseline, 'target_end_date')
        curr_end = self._get_date(current, 'early_end_date') or \
                   self._get_date(current, 'target_end_date')
        
        if base_end and curr_end and base_end != curr_end:
            delta_days = (curr_end - base_end).days
            changes.append({
                'field': 'Finish Date',
                'baseline': base_end.strftime('%Y-%m-%d'),
                'current': curr_end.strftime('%Y-%m-%d'),
                'delta': f"{delta_days:+d}d",
                'severity': 'high' if abs(delta_days) > 7 else 'medium'
            })
        
        # Total float change
        base_float = baseline.get('total_float_days', 0)
        curr_float = current.get('total_float_days', 0)
        if abs(base_float - curr_float) > 0.5:
            changes.append({
                'field': 'Total Float',
                'baseline': f"{base_float:.1f}d",
                'current': f"{curr_float:.1f}d",
                'delta': f"{curr_float - base_float:+.1f}d",
                'severity': 'high' if curr_float < 0 and base_float >= 0 else 'medium'
            })
        
        # Status change
        base_status = baseline.get('status_text', '')
        curr_status = current.get('status_text', '')
        if base_status != curr_status:
            changes.append({
                'field': 'Status',
                'baseline': base_status,
                'current': curr_status,
                'delta': '→',
                'severity': 'low'
            })
        
        # Progress change
        base_prog = self._to_float(baseline.get('phys_complete_pct', '0'))
        curr_prog = self._to_float(current.get('phys_complete_pct', '0'))
        if abs(base_prog - curr_prog) > 1:
            changes.append({
                'field': 'Progress',
                'baseline': f"{base_prog:.0f}%",
                'current': f"{curr_prog:.0f}%",
                'delta': f"{curr_prog - base_prog:+.0f}%",
                'severity': 'low'
            })
        
        return changes

    def _analyze_critical_path_changes(self, baseline_acts, current_acts, common):
        """Find activities that moved on/off the critical path."""
        newly_critical = []
        no_longer_critical = []
        
        for code in common:
            base_crit = baseline_acts[code].get('is_critical', False)
            curr_crit = current_acts[code].get('is_critical', False)
            
            if not base_crit and curr_crit:
                newly_critical.append({
                    'code': code,
                    'name': current_acts[code].get('task_name', ''),
                    'float': current_acts[code].get('total_float_days', 0),
                })
            elif base_crit and not curr_crit:
                no_longer_critical.append({
                    'code': code,
                    'name': current_acts[code].get('task_name', ''),
                    'float': current_acts[code].get('total_float_days', 0),
                })
        
        return {
            'newly_critical': newly_critical,
            'no_longer_critical': no_longer_critical,
        }

    def _calculate_summary(self, added, deleted, changed, unchanged):
        """Calculate summary statistics."""
        total_current = len(added) + len(changed) + unchanged
        
        # Count slippage vs improvement
        slipped = 0
        improved = 0
        
        for change_item in changed:
            for c in change_item['changes']:
                if c['field'] == 'Finish Date':
                    if '+' in c['delta']:
                        slipped += 1
                    elif '-' in c['delta']:
                        improved += 1
                    break
        
        return {
            'total_baseline': len(deleted) + len(changed) + unchanged,
            'total_current': total_current,
            'added_count': len(added),
            'deleted_count': len(deleted),
            'changed_count': len(changed),
            'unchanged_count': unchanged,
            'slipped_count': slipped,
            'improved_count': improved,
        }

    def _format_activity(self, act, source):
        """Format an activity for display."""
        return {
            'code': act.get('task_code', ''),
            'name': act.get('task_name', ''),
            'wbs': act.get('wbs_name', ''),
            'duration': round(act.get('original_duration_days', 0), 1),
            'float': round(act.get('total_float_days', 0), 1),
            'start': act.get('early_start_date', '') or act.get('target_start_date', ''),
            'finish': act.get('early_end_date', '') or act.get('target_end_date', ''),
            'status': act.get('status_text', ''),
            'critical': act.get('is_critical', False),
            'source': source,
        }

    def _get_schedule_info(self, engine):
        """Get basic info about a schedule."""
        info = engine._get_project_info() if hasattr(engine, '_get_project_info') else {}
        return {
            'name': info.get('name', 'Unknown'),
            'total_activities': len(engine.activities),
            'critical_count': len(engine.critical_activities),
            'total_relationships': len(engine.relationships),
        }

    def _get_date(self, act, field):
        """Get a parsed date from an activity."""
        return act.get(f'{field}_parsed', None)

    def _to_float(self, value):
        """Safely convert to float."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
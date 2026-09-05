"""
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

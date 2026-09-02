"""
SCHEDULE DATA ENGINE
====================
Processes and analyzes P6 XER data with full WBS hierarchy support.
"""

from datetime import datetime, timedelta
from collections import defaultdict


class ScheduleEngine:
    """The main schedule analysis engine."""

    def __init__(self):
        self.raw_tables = {}
        self.projects = []
        self.wbs_nodes = []
        self.activities = []
        self.relationships = []
        self.calendars = {}
        self.resources = []
        self.activity_by_id = {}
        self.activity_by_code = {}
        self.wbs_by_id = {}
        self.successors = defaultdict(list)
        self.predecessors = defaultdict(list)
        self.critical_activities = []
        self.dcma_results = {}
        self.schedule_stats = {}

    def load_data(self, parsed_tables):
        print("\n🔄 Loading data into Schedule Engine...")
        self.raw_tables = parsed_tables
        self.projects = parsed_tables.get('PROJECT', {}).get('rows', [])
        print(f"  📁 Projects loaded: {len(self.projects)}")

        self.wbs_nodes = parsed_tables.get('PROJWBS', {}).get('rows', [])
        for wbs in self.wbs_nodes:
            self.wbs_by_id[wbs.get('wbs_id', '')] = wbs
        print(f"  🌳 WBS nodes loaded: {len(self.wbs_nodes)}")

        self._load_activities(parsed_tables)
        self._load_relationships(parsed_tables)
        self._load_calendars(parsed_tables)

        self.resources = parsed_tables.get('TASKRSRC', {}).get('rows', [])
        print(f"  👷 Resource assignments loaded: {len(self.resources)}")
        print("  ✅ Data loading complete!")

    def _load_activities(self, parsed_tables):
        raw_activities = parsed_tables.get('TASK', {}).get('rows', [])
        for act in raw_activities:
            orig_dur_hrs = self._to_float(act.get('target_drtn_hr_cnt', '0'))
            remain_dur_hrs = self._to_float(act.get('remain_drtn_hr_cnt', '0'))
            act['original_duration_days'] = orig_dur_hrs / 8.0
            act['remaining_duration_days'] = remain_dur_hrs / 8.0

            total_float_hrs = self._to_float(act.get('total_float_hr_cnt', '0'))
            free_float_hrs = self._to_float(act.get('free_float_hr_cnt', '0'))
            act['total_float_days'] = total_float_hrs / 8.0
            act['free_float_days'] = free_float_hrs / 8.0

            for date_field in ['target_start_date', 'target_end_date',
                               'act_start_date', 'act_end_date',
                               'early_start_date', 'early_end_date',
                               'late_start_date', 'late_end_date']:
                act[f'{date_field}_parsed'] = self._parse_date(act.get(date_field, ''))

            status = act.get('status_code', '')
            act['status_text'] = {
                'TK_NotStart': 'Not Started', 'TK_Active': 'In Progress', 'TK_Complete': 'Completed'
            }.get(status, status)

            task_type = act.get('task_type', '')
            act['type_text'] = {
                'TT_Task': 'Task Dependent', 'TT_Rsrc': 'Resource Dependent',
                'TT_Mile': 'Milestone', 'TT_LOE': 'Level of Effort',
                'TT_WBS': 'WBS Summary', 'TT_FinMile': 'Finish Milestone'
            }.get(task_type, task_type)

            act['is_critical'] = act['total_float_days'] <= 0

            wbs_id = act.get('wbs_id', '')
            wbs_node = self.wbs_by_id.get(wbs_id, {})
            act['wbs_name'] = wbs_node.get('wbs_name', 'Unknown')
            act['wbs_code'] = wbs_node.get('wbs_short_name', 'Unknown')

            self.activities.append(act)
            self.activity_by_id[act.get('task_id', '')] = act
            self.activity_by_code[act.get('task_code', '')] = act
        print(f"  📌 Activities loaded: {len(self.activities)}")

    def _load_relationships(self, parsed_tables):
        raw_rels = parsed_tables.get('TASKPRED', {}).get('rows', [])
        for rel in raw_rels:
            pred_task_id = rel.get('pred_task_id', '')
            succ_task_id = rel.get('task_id', '')
            pred_type = rel.get('pred_type', '')
            rel['type_text'] = {
                'PR_FS': 'Finish-to-Start', 'PR_SS': 'Start-to-Start',
                'PR_FF': 'Finish-to-Finish', 'PR_SF': 'Start-to-Finish'
            }.get(pred_type, pred_type)

            lag_hrs = self._to_float(rel.get('lag_hr_cnt', '0'))
            rel['lag_days'] = lag_hrs / 8.0

            pred_act = self.activity_by_id.get(pred_task_id, {})
            succ_act = self.activity_by_id.get(succ_task_id, {})
            rel['pred_name'] = pred_act.get('task_name', 'Unknown')
            rel['pred_code'] = pred_act.get('task_code', 'Unknown')
            rel['succ_name'] = succ_act.get('task_name', 'Unknown')
            rel['succ_code'] = succ_act.get('task_code', 'Unknown')

            self.successors[pred_task_id].append({'task_id': succ_task_id, 'type': pred_type, 'lag_days': rel['lag_days']})
            self.predecessors[succ_task_id].append({'task_id': pred_task_id, 'type': pred_type, 'lag_days': rel['lag_days']})
            self.relationships.append(rel)
        print(f"  🔗 Relationships loaded: {len(self.relationships)}")

    def _load_calendars(self, parsed_tables):
        for cal in parsed_tables.get('CALENDAR', {}).get('rows', []):
            self.calendars[cal.get('clndr_id', '')] = cal
        print(f"  📅 Calendars loaded: {len(self.calendars)}")

    def analyze(self):
        print("\n🔍 Running Schedule Analysis...")
        self._calculate_statistics()
        self._identify_critical_path()
        self._run_dcma_checks()
        print("  ✅ Analysis complete!")

    def _calculate_statistics(self):
        total = len(self.activities)
        self.schedule_stats = {
            'total_activities': total,
            'not_started': sum(1 for a in self.activities if a.get('status_code') == 'TK_NotStart'),
            'in_progress': sum(1 for a in self.activities if a.get('status_code') == 'TK_Active'),
            'completed': sum(1 for a in self.activities if a.get('status_code') == 'TK_Complete'),
            'tasks': sum(1 for a in self.activities if a.get('task_type') in ['TT_Task', 'TT_Rsrc']),
            'milestones': sum(1 for a in self.activities if a.get('task_type') in ['TT_Mile', 'TT_FinMile']),
            'loe': sum(1 for a in self.activities if a.get('task_type') == 'TT_LOE'),
            'wbs_summary': sum(1 for a in self.activities if a.get('task_type') == 'TT_WBS'),
            'critical_count': sum(1 for a in self.activities if a.get('is_critical')),
            'negative_float': sum(1 for a in self.activities if a.get('total_float_days', 0) < 0),
            'zero_float': sum(1 for a in self.activities if a.get('total_float_days', 0) == 0),
            'positive_float': sum(1 for a in self.activities if a.get('total_float_days', 0) > 0),
            'high_float_gt_44d': sum(1 for a in self.activities if a.get('total_float_days', 0) > 44),
            'total_relationships': len(self.relationships),
            'total_calendars': len(self.calendars),
        }

    def _identify_critical_path(self):
        self.critical_activities = [a for a in self.activities if a.get('is_critical') and a.get('task_type') not in ['TT_LOE', 'TT_WBS']]
        print(f"     Found {len(self.critical_activities)} critical activities")

    def _run_dcma_checks(self):
        total = len(self.activities)
        if total == 0:
            return
        real_activities = [a for a in self.activities if a.get('task_type') not in ['TT_LOE', 'TT_WBS']]
        incomplete_activities = [a for a in real_activities if a.get('status_code') != 'TK_Complete']
        incomplete_count = len(incomplete_activities)

        missing_pred = [a for a in incomplete_activities if a.get('task_id', '') not in self.predecessors]
        missing_succ = [a for a in incomplete_activities if a.get('task_id', '') not in self.successors]
        leads = [r for r in self.relationships if r.get('lag_days', 0) < 0]
        lags = [r for r in self.relationships if r.get('lag_days', 0) > 0]
        non_fs = [r for r in self.relationships if r.get('pred_type') != 'PR_FS']

        hard_constraint_types = ['CS_ALAP', 'CS_MSO', 'CS_MFO', 'CS_MANDSTART', 'CS_MANDFIN']
        constrained = [a for a in incomplete_activities if a.get('cstr_type', '') in hard_constraint_types]
        high_float = [a for a in incomplete_activities if a.get('total_float_days', 0) > 44]
        neg_float = [a for a in incomplete_activities if a.get('total_float_days', 0) < 0]
        high_duration = [a for a in incomplete_activities if a.get('original_duration_days', 0) > 44 and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        invalid_dates = [a for a in self.activities if a.get('status_code') == 'TK_NotStart' and a.get('act_start_date', '')]

        tasks_with_resources = set(res.get('task_id', '') for res in self.resources)
        missing_resources = [a for a in incomplete_activities if a.get('task_id', '') not in tasks_with_resources and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        critical_pct = (len(self.critical_activities) / incomplete_count * 100) if incomplete_count > 0 else 0

        def calc_pct(count, base):
            return round((count / base * 100), 1) if base > 0 else 0

        self.dcma_results = {
            '01_Missing_Predecessors': {'count': len(missing_pred), 'total': incomplete_count, 'pct': calc_pct(len(missing_pred), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(missing_pred), incomplete_count) <= 5, 'activities': missing_pred},
            '02_Missing_Successors': {'count': len(missing_succ), 'total': incomplete_count, 'pct': calc_pct(len(missing_succ), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(missing_succ), incomplete_count) <= 5, 'activities': missing_succ},
            '03_Leads': {'count': len(leads), 'total': len(self.relationships), 'pct': calc_pct(len(leads), len(self.relationships)), 'threshold': '0%', 'pass': len(leads) == 0, 'items': leads},
            '04_Lags': {'count': len(lags), 'total': len(self.relationships), 'pct': calc_pct(len(lags), len(self.relationships)), 'threshold': '≤ 5%', 'pass': calc_pct(len(lags), len(self.relationships)) <= 5, 'items': lags},
            '05_Relationship_Types': {'count': len(non_fs), 'total': len(self.relationships), 'pct': calc_pct(len(non_fs), len(self.relationships)), 'threshold': '≤ 10%', 'pass': calc_pct(len(non_fs), len(self.relationships)) <= 10, 'items': non_fs},
            '06_Hard_Constraints': {'count': len(constrained), 'total': incomplete_count, 'pct': calc_pct(len(constrained), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(constrained), incomplete_count) <= 5, 'activities': constrained},
            '07_High_Float': {'count': len(high_float), 'total': incomplete_count, 'pct': calc_pct(len(high_float), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(high_float), incomplete_count) <= 5, 'activities': high_float},
            '08_Negative_Float': {'count': len(neg_float), 'total': incomplete_count, 'pct': calc_pct(len(neg_float), incomplete_count), 'threshold': '0%', 'pass': len(neg_float) == 0, 'activities': neg_float},
            '09_High_Duration': {'count': len(high_duration), 'total': incomplete_count, 'pct': calc_pct(len(high_duration), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(high_duration), incomplete_count) <= 5, 'activities': high_duration},
            '10_Invalid_Dates': {'count': len(invalid_dates), 'total': total, 'pct': calc_pct(len(invalid_dates), total), 'threshold': '0%', 'pass': len(invalid_dates) == 0, 'activities': invalid_dates},
            '11_Missing_Resources': {'count': len(missing_resources), 'total': incomplete_count, 'pct': calc_pct(len(missing_resources), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(missing_resources), incomplete_count) <= 5, 'activities': missing_resources},
            '12_CPLI': {'value': 'N/A', 'threshold': '≥ 1.0', 'pass': None},
            '13_BEI': {'value': 'N/A', 'threshold': '≥ 1.0', 'pass': None},
            '14_Critical_Path_Pct': {'value': round(critical_pct, 1), 'threshold': '5-25%', 'pass': 5 <= critical_pct <= 25 if critical_pct > 0 else None}
        }

    def get_dashboard_data(self):
        return {
            'project_info': self._get_project_info(),
            'summary_cards': self._get_summary_cards(),
            'status_distribution': self._get_status_distribution(),
            'float_distribution': self._get_float_distribution(),
            'dcma_summary': self._get_dcma_summary(),
            'wbs_breakdown': self._get_wbs_breakdown(),
            'critical_activities': self._get_critical_activities_data(),
            'top_issues': self._get_top_issues(),
            'activities_table': self._get_activities_table_data(),
            'schedule_timeline': self._get_timeline_data(),
        }

    def _get_project_info(self):
        if not self.projects:
            return {'name': 'Unknown', 'start': '', 'finish': ''}
        proj = self.projects[0]
        return {'name': proj.get('proj_short_name', 'Unnamed'), 'start': proj.get('plan_start_date', ''), 'finish': proj.get('plan_end_date', ''), 'data_date': proj.get('last_recalc_date', '')}

    def _get_summary_cards(self):
        stats = self.schedule_stats
        total_checks = sum(1 for r in self.dcma_results.values() if r.get('pass') is not None)
        passed_checks = sum(1 for r in self.dcma_results.values() if r.get('pass') is True)
        return [
            {'label': 'Total Activities', 'value': stats.get('total_activities', 0), 'icon': '📌', 'color': 'blue'},
            {'label': 'Critical', 'value': stats.get('critical_count', 0), 'icon': '🔴', 'color': 'red'},
            {'label': 'Completed', 'value': stats.get('completed', 0), 'icon': '✅', 'color': 'green'},
            {'label': 'In Progress', 'value': stats.get('in_progress', 0), 'icon': '🔄', 'color': 'orange'},
            {'label': 'Relationships', 'value': stats.get('total_relationships', 0), 'icon': '🔗', 'color': 'purple'},
            {'label': 'DCMA', 'value': f"{passed_checks}/{total_checks}", 'icon': '🏥', 'color': 'teal'},
        ]

    def _get_status_distribution(self):
        s = self.schedule_stats
        return {'labels': ['Not Started', 'In Progress', 'Completed'], 'values': [s.get('not_started', 0), s.get('in_progress', 0), s.get('completed', 0)], 'colors': ['#94a3b8', '#f59e0b', '#10b981']}

    def _get_float_distribution(self):
        s = self.schedule_stats
        return {'labels': ['Negative', 'Zero (Critical)', 'Positive', 'High (>44d)'], 'values': [s.get('negative_float', 0), s.get('zero_float', 0), s.get('positive_float', 0) - s.get('high_float_gt_44d', 0), s.get('high_float_gt_44d', 0)], 'colors': ['#dc2626', '#ef4444', '#3b82f6', '#f59e0b']}

    def _get_dcma_summary(self):
        results = []
        for name, r in self.dcma_results.items():
            if r.get('pass') is None:
                continue
            clean = name.replace('_', ' ').split(' ', 1)[1] if '_' in name else name
            results.append({'name': clean, 'value': f"{r.get('pct', 0)}%" if 'pct' in r else str(r.get('value', '')), 'threshold': r.get('threshold', ''), 'pass': r.get('pass', False), 'count': r.get('count', 0), 'total': r.get('total', 0)})
        return results

    def _get_wbs_breakdown(self):
        counts = {}
        for a in self.activities:
            w = a.get('wbs_name', 'Unknown')
            k = w[:30] + '...' if len(w) > 30 else w
            counts[k] = counts.get(k, 0) + 1
        s = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return {'labels': [i[0] for i in s], 'values': [i[1] for i in s]}

    def _get_critical_activities_data(self):
        return [{'code': a.get('task_code', ''), 'name': a.get('task_name', ''), 'wbs': a.get('wbs_name', ''), 'duration': round(a.get('original_duration_days', 0), 1), 'float': round(a.get('total_float_days', 0), 1), 'status': a.get('status_text', ''), 'start': a.get('early_start_date', ''), 'finish': a.get('early_end_date', '')} for a in self.critical_activities[:50]]

    def _get_top_issues(self):
        issues = []
        for name, r in self.dcma_results.items():
            if r.get('pass') is False:
                clean = name.replace('_', ' ').split(' ', 1)[1] if '_' in name else name
                issues.append({'check': clean, 'count': r.get('count', 0), 'percentage': r.get('pct', 0), 'severity': 'high' if r.get('pct', 0) > 15 else 'medium'})
        issues.sort(key=lambda x: x['count'], reverse=True)
        return issues

    def _get_activities_table_data(self):
        return [{'code': a.get('task_code', ''), 'name': a.get('task_name', ''), 'wbs': a.get('wbs_name', ''), 'type': a.get('type_text', ''), 'status': a.get('status_text', ''), 'duration': round(a.get('original_duration_days', 0), 1), 'remaining': round(a.get('remaining_duration_days', 0), 1), 'float': round(a.get('total_float_days', 0), 1), 'critical': a.get('is_critical', False), 'start': a.get('early_start_date', ''), 'finish': a.get('early_end_date', ''), 'progress': a.get('phys_complete_pct', '0')} for a in self.activities if a.get('task_type') != 'TT_WBS']

    def _get_timeline_data(self):
        results = []
        for a in self.activities[:100]:
            if a.get('task_type') in ['TT_WBS', 'TT_LOE']:
                continue
            start = a.get('early_start_date', '') or a.get('target_start_date', '')
            finish = a.get('early_end_date', '') or a.get('target_end_date', '')
            if start and finish:
                results.append({'code': a.get('task_code', ''), 'name': a.get('task_name', '')[:40], 'start': start, 'finish': finish, 'critical': a.get('is_critical', False), 'progress': self._to_float(a.get('phys_complete_pct', '0'))})
        return results

    # ═══════════════════════════════════════════════════════════
    # GANTT DATA - FULL WBS HIERARCHY WITH SAFE PARENT VALIDATION
    # ═══════════════════════════════════════════════════════════

    def get_gantt_data(self, max_activities=2000):
        """Build Gantt data with ALL parent+child WBS + valid parent links."""
        tasks = []
        links = []
        wbs_summary_tasks = []

        real_activities = [a for a in self.activities if a.get('task_type') not in ['TT_WBS']][:max_activities]
        data_date = self._get_project_data_date()
        wbs_paths = self._build_wbs_paths()
        activity_code_map = self._get_activity_code_map()

        resource_names = {}
        for r in self.raw_tables.get('RSRC', {}).get('rows', []):
            resource_names[str(r.get('rsrc_id', ''))] = r.get('rsrc_name', '') or r.get('rsrc_short_name', '')

        wbs_by_id = {str(w.get('wbs_id', '') or ''): w for w in self.wbs_nodes if w.get('wbs_id')}

        def get_parent_id(w):
            for key in ('parent_wbs_id', 'parent_id', 'parent_wbs', 'wbs_parent_id'):
                val = w.get(key, '')
                if val not in (None, '', '0', 0):
                    return str(val)
            return ''

        activities_by_wbs = {}
        for act in real_activities:
            wid = str(act.get('wbs_id', '') or '')
            if wid:
                activities_by_wbs.setdefault(wid, []).append(act)

        wbs_with_content = set()

        def mark_ancestors(wbs_id):
            current = str(wbs_id or '')
            seen = set()
            while current and current not in seen:
                seen.add(current)
                wbs_with_content.add(current)
                w = wbs_by_id.get(current)
                if not w:
                    break
                current = get_parent_id(w)

        for wid in activities_by_wbs.keys():
            mark_ancestors(wid)

        wbs_children_map = {}
        for wid, w in wbs_by_id.items():
            pid = get_parent_id(w)
            if pid:
                wbs_children_map.setdefault(pid, []).append(wid)

        def collect_all_acts_under_wbs(wbs_id, visited=None):
            if visited is None:
                visited = set()
            wbs_id = str(wbs_id or '')
            if not wbs_id or wbs_id in visited:
                return []
            visited.add(wbs_id)
            acts = list(activities_by_wbs.get(wbs_id, []))
            for child_id in wbs_children_map.get(wbs_id, []):
                acts.extend(collect_all_acts_under_wbs(child_id, visited))
            return acts

        def get_wbs_depth(wbs_id, visited=None):
            if visited is None:
                visited = set()
            wbs_id = str(wbs_id or '')
            if not wbs_id or wbs_id in visited:
                return 0
            visited.add(wbs_id)
            w = wbs_by_id.get(wbs_id)
            if not w:
                return 0
            pid = get_parent_id(w)
            if pid and pid in wbs_by_id:
                return 1 + get_wbs_depth(pid, visited)
            return 1

        sorted_wbs = sorted(
            [w for wid, w in wbs_by_id.items() if wid in wbs_with_content],
            key=lambda w: get_wbs_depth(str(w.get('wbs_id', '')))
        )

        for wbs in sorted_wbs:
            wbs_id = str(wbs.get('wbs_id', '') or '')
            if not wbs_id:
                continue

            child_acts = collect_all_acts_under_wbs(wbs_id)
            all_starts, all_ends = [], []
            total_dur = total_budget = total_progress = 0.0
            progress_count = 0
            min_float = float('inf')

            for act in child_acts:
                s = act.get('act_start_date') or act.get('early_start_date') or act.get('target_start_date') or ''
                e = act.get('act_end_date') or act.get('early_end_date') or act.get('target_end_date') or ''
                ps = self._parse_date(s)
                pe = self._parse_date(e)
                if ps: all_starts.append(ps)
                if pe: all_ends.append(pe)
                total_dur += float(act.get('original_duration_days', 0) or 0)
                tid = act.get('task_id', '')
                for res in self.resources:
                    if res.get('task_id') == tid:
                        total_budget += self._to_float(res.get('target_cost', '0'))
                fv = act.get('total_float_days', 0)
                try:
                    min_float = min(min_float, float(fv))
                except:
                    pass
                total_progress += self._to_float(act.get('phys_complete_pct', '0'))
                progress_count += 1

            if all_starts and all_ends:
                start_date = min(all_starts)
                end_date = max(all_ends)
            else:
                start_date = data_date or datetime.now()
                end_date = data_date or datetime.now()
            if end_date < start_date:
                end_date = start_date

            avg_progress = (total_progress / progress_count) if progress_count else 0.0
            wbs_depth = get_wbs_depth(wbs_id)
            parent_wbs_id = get_parent_id(wbs)
            parent_ref = f"wbs_{parent_wbs_id}" if parent_wbs_id in wbs_with_content else 0

            wbs_name = (wbs.get('wbs_name', '') or '').strip() or (wbs.get('wbs_short_name', '') or 'Unnamed WBS').strip()
            wbs_short = (wbs.get('wbs_short_name', '') or '').strip()

            wbs_task = {
                'id': f"wbs_{wbs_id}", 'activity_id': wbs_short, 'text': wbs_name,
                'wbs': wbs_name, 'wbs_code': wbs_short, 'wbs_id': wbs_id,
                'wbs_path': wbs_paths.get(wbs_id, {}).get('full_path', wbs_name),
                'activity_type': 'WBS Summary', 'status': 'WBS',
                'is_wbs': True, 'is_wbs_summary': True, 'wbs_depth': wbs_depth,
                'parent': parent_ref,
                'is_milestone': False, 'is_loe': False,
                'is_critical': (min_float <= 0) if min_float != float('inf') else False,
                'is_completed': avg_progress >= 100,
                'critical_text': 'Critical' if (min_float <= 0 and min_float != float('inf')) else 'Non-Critical',
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'original_duration': round(total_dur, 1),
                'remaining_duration': 0, 'actual_duration': 0,
                'early_start': start_date.strftime('%d-%b-%y') if all_starts else '',
                'early_finish': end_date.strftime('%d-%b-%y') if all_ends else '',
                'baseline_start': start_date.strftime('%d-%b-%y') if all_starts else '',
                'baseline_finish': end_date.strftime('%d-%b-%y') if all_ends else '',
                'late_start': '', 'late_finish': '', 'actual_start': '', 'actual_finish': '',
                'total_float': round(min_float, 1) if min_float != float('inf') else 0,
                'free_float': 0, 'progress': avg_progress / 100.0,
                'physical_percent': round(avg_progress, 1),
                'schedule_percent': 0, 'performance_percent': 0,
                'budgeted_units': 0, 'actual_units': 0, 'remaining_units': 0,
                'budgeted_cost': round(total_budget, 2),
                'actual_cost': 0, 'remaining_cost': 0, 'earned_value': 0,
                'at_completion_cost': round(total_budget, 2), 'variance_at_completion': 0,
                'spi': 0, 'cpi': 0,
                'constraint_type': '', 'constraint_date': '',
                'predecessors': '', 'successors': '',
                'predecessor_count': 0, 'successor_count': 0,
                'calendar': '', 'primary_resource': '',
                'float_band': '', 'duration_band': '', 'progress_band': '',
                'start_month': start_date.strftime('%Y-%m (%b)') if all_starts else '',
                'start_quarter': f"{start_date.year} Q{(start_date.month-1)//3 + 1}" if all_starts else '',
                'start_year': str(start_date.year) if all_starts else '',
                'finish_month': end_date.strftime('%Y-%m (%b)') if all_ends else '',
                'finish_quarter': f"{end_date.year} Q{(end_date.month-1)//3 + 1}" if all_ends else '',
                'finish_year': str(end_date.year) if all_ends else '',
                'activity_codes': {},
                'custom_class': f'gantt-wbs-l{min(wbs_depth, 12)}',
                'type': 'project', 'open': True, 'child_count': len(child_acts),
            }
            levels = wbs_paths.get(wbs_id, {}).get('levels', [])
            for i in range(12):
                wbs_task[f'wbs_level_{i+1}'] = levels[i] if i < len(levels) else ''
            wbs_summary_tasks.append(wbs_task)

        # Build groupable values
        groupable_values = {
            'wbs_paths': set(), 'status': set(), 'type': set(), 'calendar': set(),
            'critical': set(), 'primary_resource': set(),
            'float_band': set(), 'duration_band': set(), 'progress_band': set(),
            'start_month': set(), 'start_quarter': set(), 'start_year': set(),
            'finish_month': set(), 'finish_quarter': set(), 'finish_year': set(),
            'activity_codes': {},
        }
        for i in range(1, 13):
            groupable_values[f'wbs_level_{i}'] = set()

        for wbs_id, path_info in wbs_paths.items():
            if wbs_id not in wbs_with_content:
                continue
            groupable_values['wbs_paths'].add(path_info.get('full_path', ''))
            levels = path_info.get('levels', [])
            for i in range(12):
                v = levels[i] if i < len(levels) else ''
                if v:
                    groupable_values[f'wbs_level_{i+1}'].add(v)

        # Build activity tasks
        for act in real_activities:
            task_id = str(act.get('task_id', '') or '')
            if not task_id:
                continue

            start_str = act.get('act_start_date') or act.get('early_start_date') or act.get('target_start_date') or ''
            end_str = act.get('act_end_date') or act.get('early_end_date') or act.get('target_end_date') or ''
            start_clean = self._clean_date_for_gantt(start_str)
            end_clean = self._clean_date_for_gantt(end_str)

            if not start_clean and not end_clean:
                base = data_date or datetime.now()
                start_clean = base.strftime('%Y-%m-%d')
                end_clean = base.strftime('%Y-%m-%d')
            elif start_clean and not end_clean:
                end_clean = start_clean
            elif end_clean and not start_clean:
                start_clean = end_clean

            orig_dur = float(act.get('original_duration_days', 0) or 0)
            remain_dur = float(act.get('remaining_duration_days', 0) or 0)
            actual_dur = max(0, orig_dur - remain_dur) if act.get('status_code') != 'TK_NotStart' else 0
            progress_pct = self._to_float(act.get('phys_complete_pct', '0'))
            total_float = float(act.get('total_float_days', 0) or 0)

            budgeted_units = actual_units = remaining_units = 0.0
            budgeted_cost = actual_cost = remaining_cost = 0.0
            primary_resource = ''

            for res in self.resources:
                if str(res.get('task_id', '')) != task_id:
                    continue
                budgeted_units += self._to_float(res.get('target_qty', '0'))
                actual_units += self._to_float(res.get('act_reg_qty', '0'))
                remaining_units += self._to_float(res.get('remain_qty', '0'))
                budgeted_cost += self._to_float(res.get('target_cost', '0'))
                actual_cost += self._to_float(res.get('act_reg_cost', '0'))
                remaining_cost += self._to_float(res.get('remain_cost', '0'))
                if not primary_resource:
                    primary_resource = resource_names.get(str(res.get('rsrc_id', '')), '')

            if budgeted_cost == 0 and orig_dur > 0:
                budgeted_cost = orig_dur * 1000
                actual_cost = actual_dur * 1000
                remaining_cost = remain_dur * 1000

            earned_value_cost = budgeted_cost * (progress_pct / 100.0)
            schedule_pct = self._calculate_schedule_pct(start_clean, end_clean, data_date)
            performance_pct = (progress_pct / schedule_pct * 100) if schedule_pct > 0 else 0

            if total_float < 0: float_band = '4. Negative Float'
            elif total_float == 0: float_band = '1. Critical (0)'
            elif total_float <= 5: float_band = '2. Near Critical (1-5)'
            elif total_float <= 15: float_band = '3. Low Float (6-15)'
            elif total_float <= 44: float_band = '5. Normal (16-44)'
            else: float_band = '6. High Float (>44)'

            if orig_dur == 0: duration_band = '0. Milestone'
            elif orig_dur <= 5: duration_band = '1. Short (1-5d)'
            elif orig_dur <= 20: duration_band = '2. Medium (6-20d)'
            elif orig_dur <= 44: duration_band = '3. Long (21-44d)'
            else: duration_band = '4. Very Long (>44d)'

            if progress_pct == 0: progress_band = '0. Not Started'
            elif progress_pct < 25: progress_band = '1. 0-25%'
            elif progress_pct < 50: progress_band = '2. 25-50%'
            elif progress_pct < 75: progress_band = '3. 50-75%'
            elif progress_pct < 100: progress_band = '4. 75-99%'
            else: progress_band = '5. 100% Complete'

            start_parsed = self._parse_date(start_str)
            end_parsed = self._parse_date(end_str)
            start_month = start_parsed.strftime('%Y-%m (%b)') if start_parsed else '(Unknown)'
            start_quarter = f"{start_parsed.year} Q{(start_parsed.month-1)//3 + 1}" if start_parsed else '(Unknown)'
            start_year = str(start_parsed.year) if start_parsed else '(Unknown)'
            finish_month = end_parsed.strftime('%Y-%m (%b)') if end_parsed else '(Unknown)'
            finish_quarter = f"{end_parsed.year} Q{(end_parsed.month-1)//3 + 1}" if end_parsed else '(Unknown)'
            finish_year = str(end_parsed.year) if end_parsed else '(Unknown)'

            is_milestone = act.get('task_type') in ['TT_Mile', 'TT_FinMile']
            is_loe = act.get('task_type') == 'TT_LOE'
            is_critical = bool(act.get('is_critical', False))
            is_completed = act.get('status_code') == 'TK_Complete'

            pred_list = self.predecessors.get(task_id, [])
            succ_list = self.successors.get(task_id, [])
            if not pred_list:
                pred_list = self.predecessors.get(act.get('task_id', ''), [])
            if not succ_list:
                succ_list = self.successors.get(act.get('task_id', ''), [])

            pred_display = []
            for pred in pred_list[:5]:
                pred_act = self.activity_by_id.get(pred['task_id'], {})
                lag = pred.get('lag_days', 0) or 0
                lag_str = f"+{int(lag)}" if lag > 0 else (str(int(lag)) if lag < 0 else '')
                pred_display.append(f"{pred_act.get('task_code', '')}{str(pred.get('type', '')).replace('PR_', '')}{lag_str}")

            succ_display = []
            for succ in succ_list[:5]:
                succ_act = self.activity_by_id.get(succ['task_id'], {})
                lag = succ.get('lag_days', 0) or 0
                lag_str = f"+{int(lag)}" if lag > 0 else (str(int(lag)) if lag < 0 else '')
                succ_display.append(f"{succ_act.get('task_code', '')}{str(succ.get('type', '')).replace('PR_', '')}{lag_str}")

            wbs_id = str(act.get('wbs_id', '') or '')
            wbs_path_info = wbs_paths.get(wbs_id, {'full_path': 'Unassigned', 'levels': []})
            wbs_levels = wbs_path_info.get('levels', [])
            act_codes = activity_code_map.get(act.get('task_id', ''), {}) or activity_code_map.get(task_id, {})

            parent_id = f"wbs_{wbs_id}" if wbs_id in wbs_with_content else 0

            task = {
                'id': task_id, 'activity_id': act.get('task_code', ''),
                'text': act.get('task_name', ''),
                'wbs': act.get('wbs_name', ''), 'wbs_code': act.get('wbs_code', ''),
                'wbs_id': wbs_id, 'wbs_path': wbs_path_info.get('full_path', 'Unassigned'),
                'activity_codes': act_codes,
                'activity_type': act.get('type_text', ''), 'status': act.get('status_text', ''),
                'is_wbs': False, 'is_wbs_summary': False,
                'is_milestone': is_milestone, 'is_loe': is_loe,
                'is_critical': is_critical, 'is_completed': is_completed,
                'critical_text': 'Critical' if is_critical else 'Non-Critical',
                'start_date': start_clean, 'end_date': end_clean,
                'original_duration': round(orig_dur, 1),
                'remaining_duration': round(remain_dur, 1),
                'actual_duration': round(actual_dur, 1),
                'at_completion_duration': round(orig_dur, 1),
                'early_start': self._format_date(act.get('early_start_date', '')),
                'early_finish': self._format_date(act.get('early_end_date', '')),
                'late_start': self._format_date(act.get('late_start_date', '')),
                'late_finish': self._format_date(act.get('late_end_date', '')),
                'actual_start': self._format_date(act.get('act_start_date', '')),
                'actual_finish': self._format_date(act.get('act_end_date', '')),
                'baseline_start': self._format_date(act.get('target_start_date', '')),
                'baseline_finish': self._format_date(act.get('target_end_date', '')),
                'total_float': round(total_float, 1),
                'free_float': round(float(act.get('free_float_days', 0) or 0), 1),
                'progress': progress_pct / 100.0,
                'physical_percent': round(progress_pct, 1),
                'schedule_percent': round(schedule_pct, 1),
                'performance_percent': round(performance_pct, 1),
                'budgeted_units': round(budgeted_units, 2),
                'actual_units': round(actual_units, 2),
                'remaining_units': round(remaining_units, 2),
                'budgeted_cost': round(budgeted_cost, 2),
                'actual_cost': round(actual_cost, 2),
                'remaining_cost': round(remaining_cost, 2),
                'earned_value': round(earned_value_cost, 2),
                'at_completion_cost': round(actual_cost + remaining_cost, 2),
                'variance_at_completion': round(budgeted_cost - (actual_cost + remaining_cost), 2),
                'spi': round(earned_value_cost / (budgeted_cost * (schedule_pct/100)) if (budgeted_cost * schedule_pct) > 0 else 0, 3),
                'cpi': round(earned_value_cost / actual_cost if actual_cost > 0 else 0, 3),
                'constraint_type': self._format_constraint(act.get('cstr_type', '')),
                'constraint_date': self._format_date(act.get('cstr_date', '')),
                'predecessors': ', '.join(pred_display),
                'successors': ', '.join(succ_display),
                'predecessor_count': len(pred_list),
                'successor_count': len(succ_list),
                'calendar': self._get_calendar_name(act.get('clndr_id', '')),
                'primary_resource': primary_resource or '(No Resource)',
                'float_band': float_band, 'duration_band': duration_band, 'progress_band': progress_band,
                'start_month': start_month, 'start_quarter': start_quarter, 'start_year': start_year,
                'finish_month': finish_month, 'finish_quarter': finish_quarter, 'finish_year': finish_year,
                'custom_class': self._get_task_class(is_critical, is_completed, is_milestone, is_loe),
                'type': 'milestone' if is_milestone else 'task',
                'parent': parent_id, 'open': True,
            }
            for i in range(12):
                task[f'wbs_level_{i+1}'] = wbs_levels[i] if i < len(wbs_levels) else ''
            tasks.append(task)

            groupable_values['status'].add(task['status'])
            groupable_values['type'].add(task['activity_type'])
            groupable_values['calendar'].add(task['calendar'])
            groupable_values['critical'].add(task['critical_text'])
            groupable_values['primary_resource'].add(task['primary_resource'])
            groupable_values['float_band'].add(task['float_band'])
            groupable_values['duration_band'].add(task['duration_band'])
            groupable_values['progress_band'].add(task['progress_band'])
            groupable_values['start_month'].add(task['start_month'])
            groupable_values['start_quarter'].add(task['start_quarter'])
            groupable_values['start_year'].add(task['start_year'])
            groupable_values['finish_month'].add(task['finish_month'])
            groupable_values['finish_quarter'].add(task['finish_quarter'])
            groupable_values['finish_year'].add(task['finish_year'])

            for code_type, code_value in act_codes.items():
                groupable_values['activity_codes'].setdefault(code_type, set()).add(code_value)

            for pred in pred_list:
                pred_id = str(pred.get('task_id', ''))
                if any(str(t['id']) == pred_id for t in tasks):
                    link_type_map = {'PR_FS': '0', 'PR_SS': '1', 'PR_FF': '2', 'PR_SF': '3'}
                    links.append({'id': f"{pred_id}-{task_id}", 'source': pred_id, 'target': task_id, 'type': link_type_map.get(pred.get('type'), '0'), 'lag': pred.get('lag_days', 0)})

        # Combine & sanitize parents
        all_tasks = wbs_summary_tasks + tasks
        valid_ids = set(str(t['id']) for t in all_tasks)
        for t in all_tasks:
            p = t.get('parent', 0)
            if p in (None, '', 0, '0'):
                t['parent'] = 0
            else:
                p = str(p)
                t['parent'] = p if p in valid_ids else 0
            try:
                if t.get('start_date') and t.get('end_date') and t['end_date'] < t['start_date']:
                    t['end_date'] = t['start_date']
            except:
                pass

        groupable_output = {}
        for k, v in groupable_values.items():
            if k == 'activity_codes':
                groupable_output[k] = {kk: sorted(list(vv)) for kk, vv in v.items()}
            else:
                groupable_output[k] = sorted(list(v))

        print(f"  📊 Gantt: {len(tasks)} activities, {len(wbs_summary_tasks)} WBS, {len(links)} links")

        return {
            'tasks': all_tasks, 'links': links,
            'total': len(tasks), 'wbs_summary_count': len(wbs_summary_tasks),
            'critical_count': sum(1 for t in tasks if t.get('is_critical')),
            'data_date': data_date.strftime('%Y-%m-%d') if data_date else '',
            'groupable_values': groupable_output,
        }

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    def _build_wbs_paths(self):
        wbs_paths = {}
        wbs_dict = {str(w.get('wbs_id', '')): w for w in self.wbs_nodes if w.get('wbs_id')}

        def get_parent_id(w):
            for key in ('parent_wbs_id', 'parent_id', 'parent_wbs', 'wbs_parent_id'):
                val = w.get(key, '')
                if val not in (None, '', '0', 0):
                    return str(val)
            return ''

        def build_path(wbs_id, visited=None):
            if visited is None:
                visited = set()
            wbs_id = str(wbs_id or '')
            if not wbs_id or wbs_id in visited:
                return []
            visited.add(wbs_id)
            w = wbs_dict.get(wbs_id)
            if not w:
                return []
            name = (w.get('wbs_name', '') or '').strip() or (w.get('wbs_short_name', '') or '').strip()
            parent_id = get_parent_id(w)
            if parent_id and parent_id in wbs_dict:
                return build_path(parent_id, visited) + ([name] if name else [])
            return [name] if name else []

        for wbs_id in wbs_dict.keys():
            levels = build_path(wbs_id)
            wbs_paths[wbs_id] = {'full_path': ' > '.join(levels) if levels else 'Unassigned', 'levels': levels}
        return wbs_paths

    def _get_activity_code_map(self):
        code_map = {}
        code_types = {}
        for row in self.raw_tables.get('ACTVTYPE', {}).get('rows', []):
            code_types[row.get('actv_code_type_id', '')] = row.get('actv_code_type', 'Code')
        code_values = {}
        for row in self.raw_tables.get('ACTVCODE', {}).get('rows', []):
            code_id = row.get('actv_code_id', '')
            code_type_id = row.get('actv_code_type_id', '')
            code_values[code_id] = {'type_id': code_type_id, 'type_name': code_types.get(code_type_id, 'Code'), 'value': (row.get('short_name', '') or '') + ' - ' + (row.get('actv_code_name', '') or '')}
        for row in self.raw_tables.get('TASKACTV', {}).get('rows', []):
            task_id = row.get('task_id', '')
            code_id = row.get('actv_code_id', '')
            if code_id in code_values:
                code_map.setdefault(task_id, {})[code_values[code_id]['type_name']] = code_values[code_id]['value']
        return code_map

    def _clean_date_for_gantt(self, date_string):
        if not date_string:
            return None
        parsed = self._parse_date(date_string)
        return parsed.strftime('%Y-%m-%d') if parsed else None

    def _format_date(self, date_string):
        if not date_string:
            return ''
        parsed = self._parse_date(date_string)
        return parsed.strftime('%d-%b-%y') if parsed else ''

    def _format_constraint(self, cstr_type):
        return {'CS_MSO': 'Start On', 'CS_MSOA': 'Start On or After', 'CS_MSOB': 'Start On or Before', 'CS_MEO': 'Finish On', 'CS_MEOA': 'Finish On or After', 'CS_MEOB': 'Finish On or Before', 'CS_MANDSTART': 'Mandatory Start', 'CS_MANDFIN': 'Mandatory Finish', 'CS_ALAP': 'As Late As Possible'}.get(cstr_type, '')

    def _get_calendar_name(self, clndr_id):
        return self.calendars.get(clndr_id, {}).get('clndr_name', 'Default')

    def _get_task_class(self, is_critical, is_completed, is_milestone, is_loe):
        if is_completed: return 'gantt-completed'
        if is_milestone: return 'gantt-milestone-critical' if is_critical else 'gantt-milestone-normal'
        if is_loe: return 'gantt-loe'
        if is_critical: return 'gantt-critical'
        return 'gantt-normal'

    def _calculate_schedule_pct(self, start, end, data_date):
        try:
            s = datetime.strptime(start, '%Y-%m-%d')
            e = datetime.strptime(end, '%Y-%m-%d')
            if not data_date: return 0
            if data_date <= s: return 0
            if data_date >= e: return 100
            total = (e - s).days
            elapsed = (data_date - s).days
            return (elapsed / total) * 100 if total > 0 else 0
        except:
            return 0

    def _get_project_data_date(self):
        if not self.projects:
            return None
        return self._parse_date(self.projects[0].get('last_recalc_date', ''))

    def _to_float(self, value):
        try:
            return float(value)
        except:
            return 0.0

    def _parse_date(self, date_string):
        if not date_string or not str(date_string).strip():
            return None
        for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d', '%d-%b-%y', '%d-%b-%Y', '%m/%d/%Y', '%m/%d/%Y %H:%M']:
            try:
                return datetime.strptime(str(date_string).strip(), fmt)
            except ValueError:
                continue
        return None

    def find_activity(self, search_term):
        s = search_term.lower()
        return [a for a in self.activities if s in a.get('task_code', '').lower() or s in a.get('task_name', '').lower()]

    def get_predecessors(self, task_code):
        act = self.activity_by_code.get(task_code)
        if not act:
            return []
        results = []
        for pred in self.predecessors.get(act.get('task_id', ''), []):
            pa = self.activity_by_id.get(pred['task_id'], {})
            results.append({'code': pa.get('task_code', ''), 'name': pa.get('task_name', ''), 'type': pred['type'], 'lag': pred['lag_days']})
        return results

    def get_successors(self, task_code):
        act = self.activity_by_code.get(task_code)
        if not act:
            return []
        results = []
        for succ in self.successors.get(act.get('task_id', ''), []):
            sa = self.activity_by_id.get(succ['task_id'], {})
            results.append({'code': sa.get('task_code', ''), 'name': sa.get('task_name', ''), 'type': succ['type'], 'lag': succ['lag_days']})
        return results

    def get_activities_dataframe(self):
        try:
            import pandas as pd
            cols = ['task_code', 'task_name', 'wbs_code', 'wbs_name', 'status_text', 'type_text', 'original_duration_days', 'remaining_duration_days', 'total_float_days', 'free_float_days', 'is_critical', 'early_start_date', 'early_end_date', 'late_start_date', 'late_end_date', 'target_start_date', 'target_end_date', 'act_start_date', 'act_end_date', 'phys_complete_pct']
            return pd.DataFrame([{c: a.get(c, '') for c in cols} for a in self.activities])
        except ImportError:
            return None
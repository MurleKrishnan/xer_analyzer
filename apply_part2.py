import os
import shutil
from datetime import datetime

print("🚀 Starting Patch Application via Python (Part 2/3)...")

# 1. Create Backup Folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = f"_backup_part2_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
print(f"📦 Created backup folder: {backup_dir}")

files_to_backup = [
    "data_engine.py",
    "advanced_health_engine.py",
    "health_standards/dcma_checks.py",
    "health_standards/doe_checks.py",
    "health_standards/gao_checks.py",
]

for file_path in files_to_backup:
    if os.path.exists(file_path):
        dest = os.path.join(
            backup_dir, os.path.basename(file_path.replace("/", os.sep))
        )
        shutil.copy2(file_path, dest)
        print(f"   Backed up {file_path}")

os.makedirs("health_standards", exist_ok=True)


# ------------------------------------------------------------------------------
# 1. data_engine.py
# ------------------------------------------------------------------------------
DATA_ENGINE_CODE = '''"""
SCHEDULE DATA ENGINE
====================
Processes and analyzes P6 XER data with full WBS hierarchy support.
"""

from datetime import datetime
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
        self.resources_by_task = defaultdict(list)
        self.activity_by_id = {}
        self.activity_by_code = {}
        self.wbs_by_id = {}
        self.successors = defaultdict(list)
        self.predecessors = defaultdict(list)
        self.critical_activities = []
        self.dcma_results = {}
        self.schedule_stats = {}

    def load_data(self, parsed_tables):
        print("\\n🔄 Loading data into Schedule Engine...")
        self.raw_tables = parsed_tables
        self.projects = parsed_tables.get('PROJECT', {}).get('rows', [])
        print(f"  📁 Projects loaded: {len(self.projects)}")

        self.wbs_nodes = parsed_tables.get('PROJWBS', {}).get('rows', [])
        for wbs in self.wbs_nodes:
            self.wbs_by_id[wbs.get('wbs_id', '')] = wbs
        print(f"  🌳 WBS nodes loaded: {len(self.wbs_nodes)}")

        self._load_calendars(parsed_tables)
        self._load_activities(parsed_tables)
        self._load_relationships(parsed_tables)

        self.resources = parsed_tables.get('TASKRSRC', {}).get('rows', [])
        for res in self.resources:
            self.resources_by_task[str(res.get('task_id', ''))].append(res)
        print(f"  👷 Resource assignments loaded: {len(self.resources)}")
        
        print("  ✅ Data loading complete!")

    def _load_calendars(self, parsed_tables):
        for cal in parsed_tables.get('CALENDAR', {}).get('rows', []):
            self.calendars[cal.get('clndr_id', '')] = cal
        print(f"  📅 Calendars loaded: {len(self.calendars)}")

    def _get_hrs_per_day(self, clndr_id):
        cal = self.calendars.get(clndr_id, {})
        hrs = self._to_float(cal.get('day_hr_cnt', 8.0))
        return hrs if hrs > 0 else 8.0

    def _load_activities(self, parsed_tables):
        raw_activities = parsed_tables.get('TASK', {}).get('rows', [])
        for act in raw_activities:
            clndr_id = act.get('clndr_id', '')
            hrs_per_day = self._get_hrs_per_day(clndr_id)

            orig_dur_hrs = self._to_float(act.get('target_drtn_hr_cnt', '0'))
            remain_dur_hrs = self._to_float(act.get('remain_drtn_hr_cnt', '0'))
            act['original_duration_days'] = orig_dur_hrs / hrs_per_day
            act['remaining_duration_days'] = remain_dur_hrs / hrs_per_day

            total_float_hrs = self._to_float(act.get('total_float_hr_cnt', '0'))
            free_float_hrs = self._to_float(act.get('free_float_hr_cnt', '0'))
            act['total_float_days'] = total_float_hrs / hrs_per_day
            act['free_float_days'] = free_float_hrs / hrs_per_day

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

            tf = act['total_float_days']
            act['is_critical'] = (tf <= 0) and (status != 'TK_Complete')

            wbs_id = act.get('wbs_id', '')
            wbs_node = self.wbs_by_id.get(wbs_id, {})
            act['wbs_name'] = wbs_node.get('wbs_name', 'Unknown')
            act['wbs_code'] = wbs_node.get('wbs_short_name', 'Unknown')

            self.activities.append(act)
            self.activity_by_id[str(act.get('task_id', ''))] = act
            self.activity_by_code[act.get('task_code', '')] = act
            
        print(f"  📌 Activities loaded: {len(self.activities)}")

    def _load_relationships(self, parsed_tables):
        raw_rels = parsed_tables.get('TASKPRED', {}).get('rows', [])
        for rel in raw_rels:
            pred_task_id = str(rel.get('pred_task_id', ''))
            succ_task_id = str(rel.get('task_id', ''))
            pred_type = rel.get('pred_type', '')
            
            rel['type_text'] = {
                'PR_FS': 'Finish-to-Start', 'PR_SS': 'Start-to-Start',
                'PR_FF': 'Finish-to-Finish', 'PR_SF': 'Start-to-Finish'
            }.get(pred_type, pred_type)

            pred_act = self.activity_by_id.get(pred_task_id, {})
            hrs_per_day = self._get_hrs_per_day(pred_act.get('clndr_id', ''))
            
            lag_hrs = self._to_float(rel.get('lag_hr_cnt', '0'))
            rel['lag_days'] = lag_hrs / hrs_per_day

            succ_act = self.activity_by_id.get(succ_task_id, {})
            rel['pred_name'] = pred_act.get('task_name', 'Unknown')
            rel['pred_code'] = pred_act.get('task_code', 'Unknown')
            rel['succ_name'] = succ_act.get('task_name', 'Unknown')
            rel['succ_code'] = succ_act.get('task_code', 'Unknown')

            rel_summary = {'task_id': succ_task_id, 'type': pred_type, 'lag_days': rel['lag_days']}
            self.successors[pred_task_id].append(rel_summary)
            
            rel_summary_pred = {'task_id': pred_task_id, 'type': pred_type, 'lag_days': rel['lag_days']}
            self.predecessors[succ_task_id].append(rel_summary_pred)
            
            self.relationships.append(rel)
            
        print(f"  🔗 Relationships loaded: {len(self.relationships)}")

    def analyze(self):
        print("\\n🔍 Running Schedule Analysis...")
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
        self.critical_activities = [
            a for a in self.activities 
            if a.get('is_critical') and a.get('task_type') not in ['TT_LOE', 'TT_WBS']
        ]

    def _run_dcma_checks(self):
        total = len(self.activities)
        if total == 0:
            return
            
        real_activities = [a for a in self.activities if a.get('task_type') not in ['TT_LOE', 'TT_WBS']]
        incomplete_activities = [a for a in real_activities if a.get('status_code') != 'TK_Complete']
        incomplete_count = len(incomplete_activities)
        
        milestones = {'TT_Mile', 'TT_FinMile'}

        missing_pred = [a for a in incomplete_activities 
                       if a.get('task_id', '') not in self.predecessors
                       and a.get('task_type') not in milestones]
                       
        missing_succ = [a for a in incomplete_activities 
                       if a.get('task_id', '') not in self.successors
                       and a.get('task_type') not in milestones]
                       
        active_rels = [r for r in self.relationships 
                      if self.activity_by_id.get(r.get('task_id', ''), {}).get('status_code') != 'TK_Complete']
                      
        leads = [r for r in active_rels if r.get('lag_days', 0) < 0]
        lags = [r for r in active_rels if r.get('lag_days', 0) > 0]
        non_fs = [r for r in active_rels if r.get('pred_type') != 'PR_FS']

        hard_codes = {'CS_ALAP', 'CS_MSO', 'CS_MEO', 'CS_MANDSTART', 'CS_MANDFIN'}
        constrained = [a for a in incomplete_activities 
                      if a.get('cstr_type', '') in hard_codes or a.get('cstr_type2', '') in hard_codes]
                      
        high_float = [a for a in incomplete_activities if a.get('total_float_days', 0) > 44]
        neg_float = [a for a in incomplete_activities if a.get('total_float_days', 0) < 0]
        high_duration = [a for a in incomplete_activities 
                        if a.get('original_duration_days', 0) > 44 and a.get('task_type') not in milestones]
                        
        invalid_dates = [a for a in self.activities 
                        if a.get('status_code') == 'TK_NotStart' and a.get('act_start_date', '')]

        missing_resources = [a for a in incomplete_activities 
                            if not self.resources_by_task.get(a.get('task_id', ''))
                            and a.get('task_type') not in milestones]
                            
        critical_pct = (len(self.critical_activities) / incomplete_count * 100) if incomplete_count > 0 else 0

        def calc_pct(count, base):
            return round((count / base * 100), 1) if base > 0 else 0

        rel_total = len(active_rels) if active_rels else 1

        self.dcma_results = {
            '01_Missing_Predecessors': {'count': len(missing_pred), 'total': incomplete_count, 'pct': calc_pct(len(missing_pred), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(missing_pred), incomplete_count) <= 5, 'activities': missing_pred},
            '02_Missing_Successors': {'count': len(missing_succ), 'total': incomplete_count, 'pct': calc_pct(len(missing_succ), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(missing_succ), incomplete_count) <= 5, 'activities': missing_succ},
            '03_Leads': {'count': len(leads), 'total': rel_total, 'pct': calc_pct(len(leads), rel_total), 'threshold': '0%', 'pass': len(leads) == 0, 'items': leads},
            '04_Lags': {'count': len(lags), 'total': rel_total, 'pct': calc_pct(len(lags), rel_total), 'threshold': '≤ 5%', 'pass': calc_pct(len(lags), rel_total) <= 5, 'items': lags},
            '05_Relationship_Types': {'count': len(non_fs), 'total': rel_total, 'pct': calc_pct(len(non_fs), rel_total), 'threshold': '≤ 10%', 'pass': calc_pct(len(non_fs), rel_total) <= 10, 'items': non_fs},
            '06_Hard_Constraints': {'count': len(constrained), 'total': incomplete_count, 'pct': calc_pct(len(constrained), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(constrained), incomplete_count) <= 5, 'activities': constrained},
            '07_High_Float': {'count': len(high_float), 'total': incomplete_count, 'pct': calc_pct(len(high_float), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(high_float), incomplete_count) <= 5, 'activities': high_float},
            '08_Negative_Float': {'count': len(neg_float), 'total': incomplete_count, 'pct': calc_pct(len(neg_float), incomplete_count), 'threshold': '0%', 'pass': len(neg_float) == 0, 'activities': neg_float},
            '09_High_Duration': {'count': len(high_duration), 'total': incomplete_count, 'pct': calc_pct(len(high_duration), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(high_duration), incomplete_count) <= 5, 'activities': high_duration},
            '10_Invalid_Dates': {'count': len(invalid_dates), 'total': total, 'pct': calc_pct(len(invalid_dates), total), 'threshold': '0%', 'pass': len(invalid_dates) == 0, 'activities': invalid_dates},
            '11_Missing_Resources': {'count': len(missing_resources), 'total': incomplete_count, 'pct': calc_pct(len(missing_resources), incomplete_count), 'threshold': '≤ 5%', 'pass': calc_pct(len(missing_resources), incomplete_count) <= 5, 'activities': missing_resources},
            '12_CPLI': {'value': 'N/A', 'threshold': '≥ 0.95', 'pass': None},
            '13_BEI': {'value': 'N/A', 'threshold': '≥ 0.95', 'pass': None},
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
        return {
            'name': proj.get('proj_short_name', 'Unnamed'),
            'start': proj.get('plan_start_date', ''),
            'finish': proj.get('plan_end_date', ''),
            'data_date': proj.get('last_recalc_date', '')
        }

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
        return {
            'labels': ['Not Started', 'In Progress', 'Completed'],
            'values': [s.get('not_started', 0), s.get('in_progress', 0), s.get('completed', 0)],
            'colors': ['#94a3b8', '#f59e0b', '#10b981']
        }

    def _get_float_distribution(self):
        s = self.schedule_stats
        return {
            'labels': ['Negative', 'Zero (Critical)', 'Positive', 'High (>44d)'],
            'values': [s.get('negative_float', 0), s.get('zero_float', 0),
                       s.get('positive_float', 0) - s.get('high_float_gt_44d', 0),
                       s.get('high_float_gt_44d', 0)],
            'colors': ['#dc2626', '#ef4444', '#3b82f6', '#f59e0b']
        }

    def _get_dcma_summary(self):
        results = []
        for name, r in self.dcma_results.items():
            if r.get('pass') is None:
                continue
            clean = name.replace('_', ' ').split(' ', 1)[1] if '_' in name else name
            results.append({
                'name': clean,
                'value': f"{r.get('pct', 0)}%" if 'pct' in r else str(r.get('value', '')),
                'threshold': r.get('threshold', ''), 'pass': r.get('pass', False),
                'count': r.get('count', 0), 'total': r.get('total', 0)
            })
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
        return [{
            'code': a.get('task_code', ''), 'name': a.get('task_name', ''),
            'wbs': a.get('wbs_name', ''), 'duration': round(a.get('original_duration_days', 0), 1),
            'float': round(a.get('total_float_days', 0), 1), 'status': a.get('status_text', ''),
            'start': a.get('early_start_date', ''), 'finish': a.get('early_end_date', '')
        } for a in self.critical_activities[:50]]

    def _get_top_issues(self):
        issues = []
        for name, r in self.dcma_results.items():
            if r.get('pass') is False:
                clean = name.replace('_', ' ').split(' ', 1)[1] if '_' in name else name
                issues.append({
                    'check': clean, 'count': r.get('count', 0), 'percentage': r.get('pct', 0),
                    'severity': 'high' if r.get('pct', 0) > 15 else 'medium'
                })
        issues.sort(key=lambda x: x['count'], reverse=True)
        return issues

    def _get_activities_table_data(self):
        return [{
            'code': a.get('task_code', ''), 'name': a.get('task_name', ''),
            'wbs': a.get('wbs_name', ''), 'type': a.get('type_text', ''),
            'status': a.get('status_text', ''), 'duration': round(a.get('original_duration_days', 0), 1),
            'remaining': round(a.get('remaining_duration_days', 0), 1), 'float': round(a.get('total_float_days', 0), 1),
            'critical': a.get('is_critical', False), 'start': a.get('early_start_date', ''),
            'finish': a.get('early_end_date', ''), 'progress': a.get('phys_complete_pct', '0')
        } for a in self.activities if a.get('task_type') != 'TT_WBS']

    def _get_timeline_data(self):
        results = []
        for a in self.activities[:100]:
            if a.get('task_type') in ['TT_WBS', 'TT_LOE']: continue
            start = a.get('early_start_date', '') or a.get('target_start_date', '')
            finish = a.get('early_end_date', '') or a.get('target_end_date', '')
            if start and finish:
                results.append({
                    'code': a.get('task_code', ''), 'name': a.get('task_name', '')[:40],
                    'start': start, 'finish': finish, 'critical': a.get('is_critical', False),
                    'progress': self._to_float(a.get('phys_complete_pct', '0'))
                })
        return results

    def get_gantt_data(self, max_activities=2000):
        tasks = []
        links = []
        wbs_summary_tasks = []

        real_activities = [a for a in self.activities if a.get('task_type') not in ['TT_WBS']][:max_activities]
        data_date = self._get_project_data_date()
        wbs_paths = self._build_wbs_paths()
        activity_code_map = self._get_activity_code_map()

        resource_names = {str(r.get('rsrc_id', '')): r.get('rsrc_name', '') or r.get('rsrc_short_name', '')
                          for r in self.raw_tables.get('RSRC', {}).get('rows', [])}

        wbs_by_id = {str(w.get('wbs_id', '')): w for w in self.wbs_nodes if w.get('wbs_id')}

        def get_parent_id(w):
            for key in ('parent_wbs_id', 'parent_id', 'parent_wbs', 'wbs_parent_id'):
                val = w.get(key, '')
                if val not in (None, '', '0', 0): return str(val)
            return ''

        activities_by_wbs = defaultdict(list)
        for act in real_activities:
            wid = str(act.get('wbs_id', ''))
            if wid: activities_by_wbs[wid].append(act)

        wbs_with_content = set()
        for wid in activities_by_wbs.keys():
            current = wid
            seen = set()
            while current and current not in seen:
                seen.add(current)
                wbs_with_content.add(current)
                w = wbs_by_id.get(current)
                if not w: break
                current = get_parent_id(w)

        wbs_children_map = defaultdict(list)
        for wid, w in wbs_by_id.items():
            pid = get_parent_id(w)
            if pid: wbs_children_map[pid].append(wid)

        def collect_all_acts_under_wbs(wbs_id, visited=None):
            if visited is None: visited = set()
            wbs_id = str(wbs_id)
            if not wbs_id or wbs_id in visited: return []
            visited.add(wbs_id)
            acts = list(activities_by_wbs.get(wbs_id, []))
            for child_id in wbs_children_map.get(wbs_id, []):
                acts.extend(collect_all_acts_under_wbs(child_id, visited))
            return acts

        def get_wbs_depth(wbs_id, visited=None):
            if visited is None: visited = set()
            wbs_id = str(wbs_id)
            if not wbs_id or wbs_id in visited: return 0
            visited.add(wbs_id)
            w = wbs_by_id.get(wbs_id)
            if not w: return 0
            pid = get_parent_id(w)
            if pid and pid in wbs_by_id: return 1 + get_wbs_depth(pid, visited)
            return 1

        sorted_wbs = sorted(
            [w for wid, w in wbs_by_id.items() if wid in wbs_with_content],
            key=lambda w: get_wbs_depth(str(w.get('wbs_id', '')))
        )

        for wbs in sorted_wbs:
            wbs_id = str(wbs.get('wbs_id', ''))
            if not wbs_id: continue

            child_acts = collect_all_acts_under_wbs(wbs_id)
            all_starts, all_ends = [], []
            total_dur = total_budget = total_progress = 0.0
            progress_count = 0
            min_float = float('inf')

            for act in child_acts:
                ps = self._parse_date(act.get('act_start_date') or act.get('early_start_date') or act.get('target_start_date') or '')
                pe = self._parse_date(act.get('act_end_date') or act.get('early_end_date') or act.get('target_end_date') or '')
                if ps: all_starts.append(ps)
                if pe: all_ends.append(pe)
                
                total_dur += float(act.get('original_duration_days', 0) or 0)
                
                for res in self.resources_by_task.get(str(act.get('task_id', '')), []):
                    total_budget += self._to_float(res.get('target_cost', '0'))
                    
                fv = act.get('total_float_days', 0)
                try: min_float = min(min_float, float(fv))
                except: pass
                
                total_progress += self._to_float(act.get('phys_complete_pct', '0'))
                progress_count += 1

            start_date = min(all_starts) if all_starts else data_date or datetime.now()
            end_date = max(all_ends) if all_ends else data_date or datetime.now()
            if end_date < start_date: end_date = start_date

            avg_progress = (total_progress / progress_count) if progress_count else 0.0
            wbs_depth = get_wbs_depth(wbs_id)
            parent_wbs_id = get_parent_id(wbs)
            parent_ref = f"wbs_{parent_wbs_id}" if parent_wbs_id in wbs_with_content else 0

            wbs_name = (wbs.get('wbs_name', '') or wbs.get('wbs_short_name', '') or 'Unnamed WBS').strip()
            wbs_task = {
                'id': f"wbs_{wbs_id}", 'activity_id': wbs.get('wbs_short_name', ''), 'text': wbs_name,
                'wbs': wbs_name, 'wbs_code': wbs.get('wbs_short_name', ''), 'wbs_id': wbs_id,
                'wbs_path': wbs_paths.get(wbs_id, {}).get('full_path', wbs_name),
                'activity_type': 'WBS Summary', 'status': 'WBS', 'is_wbs': True, 'is_wbs_summary': True,
                'wbs_depth': wbs_depth, 'parent': parent_ref, 'is_milestone': False, 'is_loe': False,
                'is_critical': (min_float <= 0) if min_float != float('inf') else False,
                'is_completed': avg_progress >= 100,
                'start_date': start_date.strftime('%Y-%m-%d'), 'end_date': end_date.strftime('%Y-%m-%d'),
                'original_duration': round(total_dur, 1),
                'total_float': round(min_float, 1) if min_float != float('inf') else 0,
                'progress': avg_progress / 100.0, 'physical_percent': round(avg_progress, 1),
                'budgeted_cost': round(total_budget, 2),
                'custom_class': f'gantt-wbs-l{min(wbs_depth, 12)}', 'type': 'project', 'open': True,
                'child_count': len(child_acts),
            }
            wbs_summary_tasks.append(wbs_task)

        for act in real_activities:
            task_id = str(act.get('task_id', ''))
            start_str = act.get('act_start_date') or act.get('early_start_date') or act.get('target_start_date') or ''
            end_str = act.get('act_end_date') or act.get('early_end_date') or act.get('target_end_date') or ''
            start_clean = self._clean_date_for_gantt(start_str)
            end_clean = self._clean_date_for_gantt(end_str)

            if not start_clean and not end_clean:
                base = data_date or datetime.now()
                start_clean = end_clean = base.strftime('%Y-%m-%d')
            elif start_clean and not end_clean: end_clean = start_clean
            elif end_clean and not start_clean: start_clean = end_clean

            orig_dur = float(act.get('original_duration_days', 0) or 0)
            remain_dur = float(act.get('remaining_duration_days', 0) or 0)
            actual_dur = max(0, orig_dur - remain_dur) if act.get('status_code') != 'TK_NotStart' else 0
            progress_pct = self._to_float(act.get('phys_complete_pct', '0'))
            total_float = float(act.get('total_float_days', 0) or 0)

            budgeted_cost = 0.0
            primary_resource = ''
            
            for res in self.resources_by_task.get(task_id, []):
                budgeted_cost += self._to_float(res.get('target_cost', '0'))
                if not primary_resource:
                    primary_resource = resource_names.get(str(res.get('rsrc_id', '')), '')

            is_milestone = act.get('task_type') in ['TT_Mile', 'TT_FinMile']
            is_loe = act.get('task_type') == 'TT_LOE'
            is_critical = bool(act.get('is_critical', False))
            is_completed = act.get('status_code') == 'TK_Complete'

            wbs_id = str(act.get('wbs_id', ''))
            wbs_path_info = wbs_paths.get(wbs_id, {'full_path': 'Unassigned', 'levels': []})
            act_codes = activity_code_map.get(task_id, {})
            parent_id = f"wbs_{wbs_id}" if wbs_id in wbs_with_content else 0

            task = {
                'id': task_id, 'activity_id': act.get('task_code', ''), 'text': act.get('task_name', ''),
                'wbs': act.get('wbs_name', ''), 'wbs_code': act.get('wbs_code', ''),
                'wbs_path': wbs_path_info.get('full_path', 'Unassigned'),
                'activity_codes': act_codes, 'activity_type': act.get('type_text', ''),
                'status': act.get('status_text', ''), 'is_wbs': False, 'is_wbs_summary': False,
                'is_milestone': is_milestone, 'is_loe': is_loe, 'is_critical': is_critical,
                'start_date': start_clean, 'end_date': end_clean,
                'original_duration': round(orig_dur, 1), 'remaining_duration': round(remain_dur, 1),
                'actual_duration': round(actual_dur, 1),
                'early_start': self._format_date(act.get('early_start_date', '')),
                'early_finish': self._format_date(act.get('early_end_date', '')),
                'total_float': round(total_float, 1), 'progress': progress_pct / 100.0,
                'physical_percent': round(progress_pct, 1),
                'budgeted_cost': round(budgeted_cost, 2),
                'constraint_type': self._format_constraint(act.get('cstr_type', '')),
                'calendar': self._get_calendar_name(act.get('clndr_id', '')),
                'primary_resource': primary_resource or '(No Resource)',
                'custom_class': self._get_task_class(is_critical, is_completed, is_milestone, is_loe),
                'type': 'milestone' if is_milestone else 'task', 'parent': parent_id, 'open': True,
            }
            tasks.append(task)

        task_ids = {str(t['id']) for t in tasks}
        link_type_map = {'PR_FS': '0', 'PR_SS': '1', 'PR_FF': '2', 'PR_SF': '3'}
        
        for act in real_activities:
            tid = str(act.get('task_id', ''))
            if tid not in task_ids: continue
            for pred in self.predecessors.get(tid, []):
                pid = str(pred.get('task_id', ''))
                if pid in task_ids:
                    links.append({
                        'id': f"{pid}-{tid}", 'source': pid, 'target': tid,
                        'type': link_type_map.get(pred.get('type'), '0'),
                        'lag': pred.get('lag_days', 0)
                    })

        all_tasks = wbs_summary_tasks + tasks
        
        return {
            'tasks': all_tasks, 'links': links,
            'total': len(tasks), 'wbs_summary_count': len(wbs_summary_tasks),
            'critical_count': sum(1 for t in tasks if t.get('is_critical')),
            'data_date': data_date.strftime('%Y-%m-%d') if data_date else '',
            'groupable_values': {},
        }

    def _build_wbs_paths(self):
        wbs_paths = {}
        wbs_dict = {str(w.get('wbs_id', '')): w for w in self.wbs_nodes if w.get('wbs_id')}
        
        def get_parent_id(w):
            for key in ('parent_wbs_id', 'parent_id', 'parent_wbs', 'wbs_parent_id'):
                val = w.get(key, '')
                if val not in (None, '', '0', 0): return str(val)
            return ''
            
        def build_path(wbs_id, visited=None):
            if visited is None: visited = set()
            wbs_id = str(wbs_id)
            if not wbs_id or wbs_id in visited: return []
            visited.add(wbs_id)
            w = wbs_dict.get(wbs_id)
            if not w: return []
            name = (w.get('wbs_name', '') or w.get('wbs_short_name', '')).strip()
            parent_id = get_parent_id(w)
            if parent_id and parent_id in wbs_dict: return build_path(parent_id, visited) + ([name] if name else [])
            return [name] if name else []

        for wbs_id in wbs_dict.keys():
            levels = build_path(wbs_id)
            wbs_paths[wbs_id] = {'full_path': ' > '.join(levels) if levels else 'Unassigned', 'levels': levels}
        return wbs_paths

    def _get_activity_code_map(self):
        code_map = defaultdict(dict)
        code_types = {r.get('actv_code_type_id', ''): r.get('actv_code_type', 'Code') for r in self.raw_tables.get('ACTVTYPE', {}).get('rows', [])}
        code_values = {r.get('actv_code_id', ''): {'type_name': code_types.get(r.get('actv_code_type_id', ''), 'Code'), 'value': r.get('actv_code_name', '')} for r in self.raw_tables.get('ACTVCODE', {}).get('rows', [])}
        
        for r in self.raw_tables.get('TASKACTV', {}).get('rows', []):
            code_id = r.get('actv_code_id', '')
            if code_id in code_values:
                code_map[r.get('task_id', '')][code_values[code_id]['type_name']] = code_values[code_id]['value']
        return dict(code_map)

    def _clean_date_for_gantt(self, date_string):
        parsed = self._parse_date(date_string)
        return parsed.strftime('%Y-%m-%d') if parsed else None

    def _format_date(self, date_string):
        parsed = self._parse_date(date_string)
        return parsed.strftime('%d-%b-%y') if parsed else ''

    def _format_constraint(self, cstr_type):
        return {'CS_MSO': 'Start On', 'CS_MSOA': 'Start On or After', 'CS_MSOB': 'Start On or Before', 
                'CS_MEO': 'Finish On', 'CS_MEOA': 'Finish On or After', 'CS_MEOB': 'Finish On or Before', 
                'CS_MANDSTART': 'Mandatory Start', 'CS_MANDFIN': 'Mandatory Finish', 'CS_ALAP': 'As Late As Possible'}.get(cstr_type, '')

    def _get_calendar_name(self, clndr_id):
        return self.calendars.get(clndr_id, {}).get('clndr_name', 'Default')

    def _get_task_class(self, is_critical, is_completed, is_milestone, is_loe):
        if is_completed: return 'gantt-completed'
        if is_milestone: return 'gantt-milestone-critical' if is_critical else 'gantt-milestone-normal'
        if is_loe: return 'gantt-loe'
        if is_critical: return 'gantt-critical'
        return 'gantt-normal'

    def _get_project_data_date(self):
        return self._parse_date(self.projects[0].get('last_recalc_date', '')) if self.projects else None

    def _to_float(self, value):
        try: return float(value)
        except: return 0.0

    def _parse_date(self, date_string):
        if not date_string or not str(date_string).strip(): return None
        for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d', '%d-%b-%y', '%d-%b-%Y', '%m/%d/%Y', '%m/%d/%Y %H:%M']:
            try: return datetime.strptime(str(date_string).strip(), fmt)
            except ValueError: continue
        return None

    def get_activities_dataframe(self):
        try:
            import pandas as pd
            cols = ['task_code', 'task_name', 'wbs_code', 'wbs_name', 'status_text', 'type_text', 
                    'original_duration_days', 'remaining_duration_days', 'total_float_days', 
                    'free_float_days', 'is_critical', 'early_start_date', 'early_end_date', 
                    'late_start_date', 'late_end_date', 'target_start_date', 'target_end_date', 
                    'act_start_date', 'act_end_date', 'phys_complete_pct']
            return pd.DataFrame([{c: a.get(c, '') for c in cols} for a in self.activities])
        except ImportError:
            return None
'''

with open("data_engine.py", "w", encoding="utf-8") as f:
    f.write(DATA_ENGINE_CODE)
print("  ✅ Updated data_engine.py")


# ------------------------------------------------------------------------------
# 2. advanced_health_engine.py
# ------------------------------------------------------------------------------
ADVANCED_HEALTH_ENGINE_CODE = '''"""
COMPREHENSIVE SCHEDULE HEALTH ANALYTICS ENGINE
================================================
622+ discrete checks across 6 major standards:
- DCMA 14-Point Assessment
- DOE PM-30 Order Requirements
- NASA NPR 7120.5 & PM Handbook
- GAO Schedule Assessment Guide
- AACE International RP 29R-03, 32R-04
- Industry Best Practices
"""

from collections import defaultdict, Counter
from datetime import datetime
import logging

from health_standards.dcma_checks import DCMAChecks
from health_standards.doe_checks import DOEChecks
from health_standards.nasa_checks import NASAChecks
from health_standards.gao_checks import GAOChecks
from health_standards.aace_checks import AACEChecks
from health_standards.industry_checks import IndustryChecks

logger = logging.getLogger(__name__)


class AdvancedHealthEngine:
    """Master engine coordinating all standard-specific check modules."""

    def __init__(self, engine):
        self.engine = engine
        self.activities = engine.activities
        self.relationships = engine.relationships
        self.calendars = engine.calendars
        self.resources = engine.resources
        self.projects = engine.projects
        self.wbs_nodes = engine.wbs_nodes
        
        self.real_including_loe = [
            a for a in self.activities if a.get('task_type') != 'TT_WBS'
        ]
        self.real_activities = [
            a for a in self.real_including_loe if a.get('task_type') != 'TT_LOE'
        ]
        
        self.incomplete = [
            a for a in self.real_activities if a.get('status_code') != 'TK_Complete'
        ]
        self.completed = [
            a for a in self.real_activities if a.get('status_code') == 'TK_Complete'
        ]
        self.in_progress = [
            a for a in self.real_activities if a.get('status_code') == 'TK_Active'
        ]
        self.not_started = [
            a for a in self.real_activities if a.get('status_code') == 'TK_NotStart'
        ]
        self.milestones = [
            a for a in self.activities if a.get('task_type') in ['TT_Mile', 'TT_FinMile']
        ]
        
        self.data_date = self._get_data_date()
        self.results = {}

    def _get_data_date(self):
        if not self.projects:
            return None
        date_str = self.projects[0].get('last_recalc_date', '')
        return self.engine._parse_date(date_str)

    def run_all_checks(self, selected_standard='all', force=False):
        if not hasattr(self.engine, 'health_cache'):
            self.engine.health_cache = {}
            
        cache_key = selected_standard
        if not force and cache_key in self.engine.health_cache:
            logger.info(f"⚡ Returning cached health data for: {selected_standard}")
            return self.engine.health_cache[cache_key]

        logger.info(f"🏥 Running Advanced Health Analytics (Standard: {selected_standard})")
        
        standard_modules = {
            'DCMA': DCMAChecks,
            'DOE': DOEChecks,
            'NASA': NASAChecks,
            'GAO': GAOChecks,
            'AACE': AACEChecks,
            'Industry': IndustryChecks,
        }
        
        if selected_standard == 'all':
            standards_to_run = list(standard_modules.keys())
        elif selected_standard in standard_modules:
            standards_to_run = [selected_standard]
        else:
            standards_to_run = list(standard_modules.keys())
        
        for std_name in standards_to_run:
            logger.info(f"  Running {std_name} checks...")
            checker = standard_modules[std_name](self)
            self.results[std_name] = checker.run_checks()
        
        report = self._compile_full_report(selected_standard)
        self.engine.health_cache[cache_key] = report
        return report

    def _compile_full_report(self, selected_standard):
        for std_data in self.results.values():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    if check.get('status') == 'fail':
                        check['passed'] = False
                    elif check.get('status') == 'pass':
                        check['passed'] = True

        standard_scores = {}
        for std_name, std_data in self.results.items():
            standard_scores[std_name] = self._calculate_standard_score(std_data)
        
        total_checks = 0
        total_passed = 0
        total_failed = 0
        critical_failures = 0
        high_failures = 0
        
        weights = {'critical': 5, 'high': 3, 'medium': 2, 'low': 1, 'info': 0}
        earned_points = 0
        possible_points = 0
        
        for std_data in self.results.values():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    if check.get('status') in ['info', 'na']:
                        continue
                        
                    total_checks += 1
                    weight = weights.get(check.get('severity', 'low'), 1)
                    possible_points += weight
                    
                    if check.get('passed'):
                        total_passed += 1
                        earned_points += weight
                    else:
                        total_failed += 1
                        if check.get('severity') == 'critical':
                            critical_failures += 1
                        elif check.get('severity') == 'high':
                            high_failures += 1
        
        overall_score = (earned_points / possible_points * 100) if possible_points > 0 else 100.0
        overall_score = round(overall_score, 1)
        
        all_actions = self._get_top_actions(limit=None)
        
        return {
            'selected_standard': selected_standard,
            'overall_score': overall_score,
            'total_checks': total_checks,
            'passed_checks': total_passed,
            'failed_checks': total_failed,
            'critical_failures': critical_failures,
            'high_failures': high_failures,
            'pass_rate': round(total_passed / total_checks * 100, 1) if total_checks else 0,
            'standard_scores': standard_scores,
            'standards': self.results,
            'top_actions': all_actions,
            'project_info': self._get_project_info(),
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    def _calculate_standard_score(self, std_data):
        total = 0
        passed = 0
        critical_fail = 0
        high_fail = 0
        
        weights = {'critical': 5, 'high': 3, 'medium': 2, 'low': 1, 'info': 0}
        earned = 0
        possible = 0
        
        for category in std_data.get('categories', []):
            for check in category.get('checks', []):
                if check.get('status') in ['info', 'na']:
                    continue
                    
                total += 1
                w = weights.get(check.get('severity', 'low'), 1)
                possible += w
                
                if check.get('passed'):
                    passed += 1
                    earned += w
                else:
                    if check.get('severity') == 'critical':
                        critical_fail += 1
                    elif check.get('severity') == 'high':
                        high_fail += 1
        
        score = (earned / possible * 100) if possible > 0 else 100.0
        score = round(score, 1)
        
        if score >= 90:
            grade, color = 'A', 'green'
        elif score >= 80:
            grade, color = 'B', 'blue'
        elif score >= 70:
            grade, color = 'C', 'orange'
        elif score >= 60:
            grade, color = 'D', 'orange'
        else:
            grade, color = 'F', 'red'
        
        return {
            'name': std_data.get('name', ''),
            'description': std_data.get('description', ''),
            'total_checks': total,
            'passed': passed,
            'failed': total - passed,
            'critical_failures': critical_fail,
            'high_failures': high_fail,
            'score': score,
            'grade': grade,
            'color': color,
        }

    def _get_top_actions(self, limit=None):
        all_failed = []

        for std_name, std_data in self.results.items():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    if check.get('status') != 'fail':
                        continue

                    severity_weight = {
                        'critical': 100,
                        'high': 50,
                        'medium': 20,
                        'low': 5,
                    }.get(check.get('severity', 'low'), 5)

                    count = check.get('count', 0) or 0
                    priority = severity_weight + min(count, 100)

                    all_failed.append({
                        'standard': std_name,
                        'id': check.get('id'),
                        'name': check.get('name'),
                        'severity': check.get('severity'),
                        'count': count,
                        'total': check.get('total', 0),
                        'percentage': check.get('percentage', 0),
                        'value': check.get('value', None),
                        'threshold': check.get('threshold', ''),
                        'description': check.get('description', ''),
                        'recommendation': check.get('recommendation', ''),
                        'priority': priority,
                        'category': category.get('name', ''),
                        'failed_items': check.get('failed_items', []),
                    })

        all_failed.sort(key=lambda x: x['priority'], reverse=True)
        
        if limit is not None:
            return all_failed[:limit]
        return all_failed

    def _get_project_info(self):
        if not self.projects:
            return {}
        proj = self.projects[0]
        return {
            'name': proj.get('proj_short_name', 'Unknown'),
            'start': proj.get('plan_start_date', ''),
            'finish': proj.get('plan_end_date', ''),
            'data_date': self.data_date.strftime('%Y-%m-%d') if self.data_date else '',
            'activity_count': len(self.activities),
            'relationship_count': len(self.relationships),
        }
'''

with open("advanced_health_engine.py", "w", encoding="utf-8") as f:
    f.write(ADVANCED_HEALTH_ENGINE_CODE)
print("  ✅ Updated advanced_health_engine.py")


# ------------------------------------------------------------------------------
# 3. health_standards/dcma_checks.py
# ------------------------------------------------------------------------------
DCMA_CHECKS_CODE = '''"""
DCMA 14-POINT ASSESSMENT (Enhanced)
====================================
"""

from health_standards.base_checker import BaseChecker


class DCMAChecks(BaseChecker):
    """DCMA 14-Point comprehensive check suite."""

    def run_checks(self):
        return {
            'name': 'DCMA 14-Point Assessment',
            'description': 'Defense Contract Management Agency standard schedule health metrics with detailed sub-metrics',
            'categories': [
                self._logic_checks(),
                self._lag_lead_checks(),
                self._constraint_checks(),
                self._float_duration_checks(),
                self._date_progress_checks(),
                self._resource_metric_checks(),
            ]
        }

    def _logic_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        
        open_start = self.open_start_activities()
        open_end = self.open_end_activities()
        
        checks.append(self.make_check(
            'DCMA-01', 'Missing Predecessors',
            'Every activity (except start milestones) should have a predecessor',
            len(open_start), total, 5, 'DCMA', 'high', 'Logic',
            'Add logical predecessors to activities. Only project start milestones may have none.',
            open_start
        ))
        
        crit_incomplete = [a for a in self.incomplete if a.get('is_critical')]
        crit_missing_pred = [a for a in open_start if a.get('is_critical')]
        checks.append(self.make_check(
            'DCMA-01a', 'Critical Path Missing Predecessors',
            'Critical activities without predecessors',
            len(crit_missing_pred), max(len(crit_incomplete), 1), 0, 'DCMA', 'critical', 'Logic',
            'Critical activities MUST have predecessors.',
            crit_missing_pred
        ))
        
        checks.append(self.make_check(
            'DCMA-02', 'Missing Successors',
            'Every activity (except finish milestones) should have a successor',
            len(open_end), total, 5, 'DCMA', 'high', 'Logic',
            'Add logical successors to activities. Only project finish milestones may have none.',
            open_end
        ))
        
        crit_missing_succ = [a for a in open_end if a.get('is_critical')]
        checks.append(self.make_check(
            'DCMA-02a', 'Critical Path Missing Successors',
            'Critical activities without successors',
            len(crit_missing_succ), max(len(crit_incomplete), 1), 0, 'DCMA', 'critical', 'Logic',
            'Critical activities MUST have successors.',
            crit_missing_succ
        ))
        
        checks.append(self.make_check(
            'DCMA-OPEN-01', 'Open Start Activities',
            'Non-milestone activities without predecessors',
            len(open_start), total, 0, 'DCMA', 'high', 'Logic',
            'Only start milestones should have no predecessors.',
            open_start
        ))
        
        checks.append(self.make_check(
            'DCMA-OPEN-02', 'Open End Activities',
            'Non-milestone activities without successors',
            len(open_end), total, 0, 'DCMA', 'high', 'Logic',
            'Only finish milestones should have no successors.',
            open_end
        ))
        
        return {'name': 'Logic Checks', 'checks': checks}

    def _lag_lead_checks(self):
        checks = []
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1
        
        leads = [r for r in active_rels if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'DCMA-03', 'Leads (Negative Lag)',
            'No relationships should have negative lag',
            len(leads), rel_total, 0, 'DCMA', 'high', 'Logic',
            'Remove all negative lags. Leads distort CPM calculations.',
            leads
        ))
        
        large_leads = [r for r in leads if r.get('lag_days', 0) < -5]
        checks.append(self.make_check(
            'DCMA-03a', 'Large Leads (>5 days)',
            'Leads greater than 5 days',
            len(large_leads), rel_total, 0, 'DCMA', 'high', 'Logic',
            'Large leads (>5 days) significantly distort schedule.',
            large_leads
        ))
        
        lags = [r for r in active_rels if r.get('lag_days', 0) > 0]
        checks.append(self.make_check(
            'DCMA-04', 'Excessive Lags',
            'Minimize use of positive lags',
            len(lags), rel_total, 5, 'DCMA', 'medium', 'Logic',
            'Replace lags with work activities or hammocks.',
            lags
        ))
        
        large_lags = [r for r in lags if r.get('lag_days', 0) > 10]
        checks.append(self.make_check(
            'DCMA-04a', 'Large Lags (>10 days)',
            'Lags greater than 10 days',
            len(large_lags), rel_total, 2, 'DCMA', 'high', 'Logic',
            'Large lags may hide activities or duration.',
            large_lags
        ))
        
        non_fs = [r for r in active_rels if r.get('pred_type') != 'PR_FS']
        checks.append(self.make_check(
            'DCMA-05', 'Non-FS Relationships',
            'Minimize SS, FF, SF relationships',
            len(non_fs), rel_total, 10, 'DCMA', 'medium', 'Logic',
            'Use Finish-to-Start relationships whenever possible.',
            non_fs
        ))
        
        sf_rels = [r for r in active_rels if r.get('pred_type') == 'PR_SF']
        checks.append(self.make_check(
            'DCMA-05a', 'Start-to-Finish Relationships',
            'SF relationships should be avoided',
            len(sf_rels), rel_total, 1, 'DCMA', 'high', 'Logic',
            'SF relationships are counterintuitive and often incorrect.',
            sf_rels
        ))
        
        fs_lag_rels = self.fs_with_lag()
        checks.append(self.make_check(
            'DCMA-FS-LAG', 'FS Relationships with Lag',
            'Finish-to-Start relationships with positive lag (waiting periods)',
            len(fs_lag_rels), rel_total, 3, 'DCMA', 'medium', 'Logic',
            'Replace lags with real activities (e.g., "Cure Time", "Waiting Approval") for transparency.',
            fs_lag_rels
        ))
        
        return {'name': 'Lag/Lead Analysis', 'checks': checks}

    def _constraint_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        
        constrained = [a for a in self.incomplete if self.has_hard_constraint(a)]
        checks.append(self.make_check(
            'DCMA-06', 'Hard Constraints',
            'Minimize hard constraints that override CPM',
            len(constrained), total, 5, 'DCMA', 'high', 'Constraints',
            'Replace hard constraints with logical relationships.',
            constrained
        ))
        
        mand_start = [a for a in self.incomplete 
                      if a.get('cstr_type') == 'CS_MANDSTART' or a.get('cstr_type2') == 'CS_MANDSTART']
        checks.append(self.make_check(
            'DCMA-06a', 'Mandatory Start Constraints',
            'Mandatory start prevents proper CPM',
            len(mand_start), total, 1, 'DCMA', 'critical', 'Constraints',
            'Mandatory Start constraints prevent CPM. Use logic instead.',
            mand_start
        ))
        
        mand_fin = [a for a in self.incomplete 
                    if a.get('cstr_type') == 'CS_MANDFIN' or a.get('cstr_type2') == 'CS_MANDFIN']
        checks.append(self.make_check(
            'DCMA-06b', 'Mandatory Finish Constraints',
            'Mandatory finish prevents proper CPM',
            len(mand_fin), total, 1, 'DCMA', 'critical', 'Constraints',
            'Mandatory Finish constraints prevent CPM. Use logic instead.',
            mand_fin
        ))
        
        must_start = [a for a in self.incomplete 
                      if a.get('cstr_type') == 'CS_MSO' or a.get('cstr_type2') == 'CS_MSO']
        checks.append(self.make_check(
            'DCMA-06c', 'Must Start On Constraints',
            'Must Start On constraints',
            len(must_start), total, 2, 'DCMA', 'high', 'Constraints',
            'Prefer logical relationships over date constraints.',
            must_start
        ))
        
        must_fin = [a for a in self.incomplete 
                    if a.get('cstr_type') == 'CS_MEO' or a.get('cstr_type2') == 'CS_MEO']
        checks.append(self.make_check(
            'DCMA-06d', 'Must Finish On Constraints',
            'Must Finish On constraints',
            len(must_fin), total, 2, 'DCMA', 'high', 'Constraints',
            'Prefer logical relationships over date constraints.',
            must_fin
        ))
        
        alap = [a for a in self.incomplete 
                if a.get('cstr_type') == 'CS_ALAP' or a.get('cstr_type2') == 'CS_ALAP']
        checks.append(self.make_check(
            'DCMA-06e', 'As Late As Possible',
            'ALAP constraints eliminate float',
            len(alap), total, 1, 'DCMA', 'high', 'Constraints',
            'ALAP consumes all float, hiding schedule risk.',
            alap
        ))
        
        return {'name': 'Constraint Analysis', 'checks': checks}

    def _float_duration_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        milestones = {'TT_Mile', 'TT_FinMile'}
        
        high_float = [a for a in self.incomplete if a.get('total_float_days', 0) > 44]
        checks.append(self.make_check(
            'DCMA-07', 'High Float (>44 days)',
            'Activities should not have excessive float',
            len(high_float), total, 5, 'DCMA', 'medium', 'Float',
            'High float often indicates missing successors.',
            high_float
        ))
        
        very_high_float = [a for a in self.incomplete if a.get('total_float_days', 0) > 132]
        checks.append(self.make_check(
            'DCMA-07a', 'Very High Float (>132 days)',
            'Excessive float beyond 6 months',
            len(very_high_float), total, 2, 'DCMA', 'high', 'Float',
            'Very high float almost always indicates broken logic.',
            very_high_float
        ))
        
        neg_float = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'DCMA-08', 'Negative Float',
            'No activities should have negative total float',
            len(neg_float), total, 0, 'DCMA', 'critical', 'Float',
            'Negative float means the schedule cannot meet constraints.',
            neg_float
        ))
        
        severe_neg = [a for a in self.incomplete if a.get('total_float_days', 0) < -10]
        checks.append(self.make_check(
            'DCMA-08a', 'Severe Negative Float (<-10 days)',
            'Critical schedule issues',
            len(severe_neg), total, 0, 'DCMA', 'critical', 'Float',
            'Immediate action required to recover schedule.',
            severe_neg
        ))
        
        high_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) > 44 
                   and a.get('task_type') not in milestones]
        checks.append(self.make_check(
            'DCMA-09', 'High Duration Activities',
            'Activities should be broken down to <44 days',
            len(high_dur), total, 5, 'DCMA', 'medium', 'Duration',
            'Decompose long-duration activities for better visibility.',
            high_dur
        ))
        
        very_high_dur = [a for a in self.incomplete 
                        if a.get('original_duration_days', 0) > 88
                        and a.get('task_type') not in milestones]
        checks.append(self.make_check(
            'DCMA-09a', 'Very High Duration (>88 days)',
            'Activities over 4 months',
            len(very_high_dur), total, 2, 'DCMA', 'high', 'Duration',
            'Activities >88 days almost always need decomposition.',
            very_high_dur
        ))
        
        return {'name': 'Float & Duration Analysis', 'checks': checks}

    def _date_progress_checks(self):
        checks = []
        total = len(self.activities) or 1
        
        invalid = [a for a in self.activities
                  if a.get('status_code') == 'TK_NotStart' and a.get('act_start_date', '')]
        checks.append(self.make_check(
            'DCMA-10', 'Invalid Dates (Not Started with Actual)',
            'Unstarted activities should not have actual dates',
            len(invalid), total, 0, 'DCMA', 'critical', 'Dates',
            'Remove actual dates from unstarted activities.',
            invalid
        ))
        
        future_actuals = []
        if self.data_date:
            for a in self.activities:
                act_end = a.get('act_end_date_parsed')
                if act_end and act_end > self.data_date:
                    future_actuals.append(a)
        checks.append(self.make_check(
            'DCMA-10a', 'Actual Finish After Data Date',
            'Actual dates cannot be after data date',
            len(future_actuals), total, 0, 'DCMA', 'critical', 'Dates',
            'Correct actual dates in the future.',
            future_actuals
        ))
        
        future_starts = []
        if self.data_date:
            for a in self.activities:
                act_start = a.get('act_start_date_parsed')
                if act_start and act_start > self.data_date:
                    future_starts.append(a)
        checks.append(self.make_check(
            'DCMA-10b', 'Actual Start After Data Date',
            'Actual start dates cannot be after data date',
            len(future_starts), total, 0, 'DCMA', 'critical', 'Dates',
            'Correct future actual start dates.',
            future_starts
        ))
        
        reversed_dates = []
        for a in self.activities:
            s = a.get('act_start_date_parsed')
            e = a.get('act_end_date_parsed')
            if s and e and e < s:
                reversed_dates.append(a)
        checks.append(self.make_check(
            'DCMA-10c', 'Actual Finish Before Actual Start',
            'Finish dates must be after start dates',
            len(reversed_dates), total, 0, 'DCMA', 'critical', 'Dates',
            'Fix inverted actual dates.',
            reversed_dates
        ))
        
        complete_no_finish = [a for a in self.activities
                             if a.get('status_code') == 'TK_Complete' 
                             and not a.get('act_end_date', '')]
        checks.append(self.make_check(
            'DCMA-10d', 'Complete Without Actual Finish',
            'Completed activities must have actual finish dates',
            len(complete_no_finish), total, 0, 'DCMA', 'high', 'Dates',
            'Add actual finish dates to completed activities.',
            complete_no_finish
        ))
        
        return {'name': 'Date Validity', 'checks': checks}

    def _resource_metric_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        milestones = {'TT_Mile', 'TT_FinMile', 'TT_LOE'}
        
        tasks_with_res = set(r.get('task_id') for r in self.resources)
        missing_res = [a for a in self.incomplete 
                      if a.get('task_id', '') not in tasks_with_res
                      and a.get('task_type') not in milestones]
        checks.append(self.make_check(
            'DCMA-11', 'Missing Resources',
            'Work activities should have resources',
            len(missing_res), total, 5, 'DCMA', 'medium', 'Resources',
            'Assign resources for cost/schedule integration.',
            missing_res
        ))
        
        cpli = self._calculate_cpli()
        checks.append(self.make_metric(
            'DCMA-12', 'CPLI (Critical Path Length Index)',
            'CPLI ≥ 0.95 indicates achievable schedule',
            cpli, 'DCMA', 'Metrics',
            threshold_min=0.95, severity='high',
            recommendation='CPLI < 0.95 means critical path exceeds remaining time to baseline finish.',
            unit=''
        ))
        
        bei = self._calculate_bei()
        checks.append(self.make_metric(
            'DCMA-13', 'BEI (Baseline Execution Index)',
            'BEI ≥ 0.95 indicates on-track execution',
            bei, 'DCMA', 'Metrics',
            threshold_min=0.95, severity='high',
            recommendation='BEI < 0.95 means tasks completing later than baseline.',
            unit=''
        ))
        
        cp_continuity = self._calculate_cp_continuity()
        checks.append(self.make_metric(
            'DCMA-14', 'Critical Path Test (Continuity)',
            'Fraction of critical activities linked to another critical activity',
            cp_continuity, 'DCMA', 'Metrics',
            threshold_min=0.9, severity='critical',
            recommendation='Critical path must be continuous. Isolated critical activities indicate broken logic.',
            unit=''
        ))
        
        return {'name': 'Resources & Metrics', 'checks': checks}

    def _calculate_cpli(self):
        try:
            if not self.data_date or not self.projects:
                return None
                
            proj = self.projects[0]
            baseline_finish = self.engine._parse_date(proj.get('plan_end_date', ''))
            if not baseline_finish:
                return None
            
            crit_incomplete = [a for a in self.incomplete if a.get('is_critical')]
            if not crit_incomplete:
                return None
            
            cp_ends = [a.get('early_end_date_parsed') for a in crit_incomplete 
                       if a.get('early_end_date_parsed')]
            if not cp_ends:
                return None
            
            cp_finish = max(cp_ends)
            
            time_available = max(1, (baseline_finish - self.data_date).days)
            cp_length = max(1, (cp_finish - self.data_date).days)
            
            return round(time_available / cp_length, 3)
        except Exception:
            return None

    def _calculate_bei(self):
        try:
            if not self.data_date:
                return None
            
            should_be_complete = 0
            actually_complete = 0
            
            for a in self.real_activities:
                bl_end = a.get('target_end_date_parsed')
                if bl_end and bl_end <= self.data_date:
                    should_be_complete += 1
                    if a.get('status_code') == 'TK_Complete':
                        actually_complete += 1
            
            if should_be_complete == 0:
                return None
            
            return round(actually_complete / should_be_complete, 3)
        except Exception:
            return None

    def _calculate_cp_continuity(self):
        try:
            crit_ids = {str(a.get('task_id', '')) for a in self.incomplete if a.get('is_critical')}
            if not crit_ids:
                return None
            
            connected = 0
            for cid in crit_ids:
                succs = self.engine.successors.get(cid, [])
                if any(str(s.get('task_id')) in crit_ids for s in succs):
                    connected += 1
                    continue
                preds = self.engine.predecessors.get(cid, [])
                if any(str(p.get('task_id')) in crit_ids for p in preds):
                    connected += 1
            
            return round(connected / len(crit_ids), 3)
        except Exception:
            return None
'''

dcma_path = os.path.join("health_standards", "dcma_checks.py")
with open(dcma_path, "w", encoding="utf-8") as f:
    f.write(DCMA_CHECKS_CODE)
print("  ✅ Updated health_standards/dcma_checks.py")


# ------------------------------------------------------------------------------
# 4. health_standards/doe_checks.py
# ------------------------------------------------------------------------------
DOE_CHECKS_CODE = '''"""
DOE PM-30 SCHEDULE ASSESSMENT
==============================
"""

from health_standards.base_checker import BaseChecker
from collections import Counter, defaultdict
import statistics


class DOEChecks(BaseChecker):
    """DOE PM-30 comprehensive check suite."""

    def run_checks(self):
        return {
            'name': 'DOE PM-30 Assessment',
            'description': 'Department of Energy schedule management requirements',
            'categories': [
                self._project_structure(),
                self._schedule_integrity(),
                self._resource_management(),
                self._progress_measurement(),
                self._risk_management(),
                self._earned_value_checks(),
                self._logic_network_quality(),
            ]
        }

    def _build_wbs_hierarchy(self):
        by_id = {str(w.get('wbs_id', '')): w for w in self.wbs_nodes if w.get('wbs_id')}
        
        def parent_of(w):
            for k in ('parent_wbs_id', 'parent_id', 'parent_wbs', 'wbs_parent_id'):
                v = w.get(k, '')
                if v not in (None, '', '0', 0): 
                    return str(v)
            return ''
            
        def get_depth(wid, seen=None):
            seen = seen or set()
            if not wid or wid in seen: return 0
            seen.add(wid)
            w = by_id.get(wid)
            if not w: return 0
            p = parent_of(w)
            return 1 + (get_depth(p, seen) if p in by_id else 0)
            
        max_depth = max((get_depth(wid) for wid in by_id), default=0)
        
        children = defaultdict(list)
        for wid, w in by_id.items():
            p = parent_of(w)
            if p: children[p].append(wid)
            
        acts_by_wbs = defaultdict(list)
        for a in self.activities:
            wid = str(a.get('wbs_id', ''))
            if wid: acts_by_wbs[wid].append(a)
            
        def has_activities(wid, seen=None):
            seen = seen or set()
            if wid in seen: return False
            seen.add(wid)
            if acts_by_wbs[wid]: return True
            return any(has_activities(child, seen) for child in children.get(wid, []))
            
        empty_wbs = [w for wid, w in by_id.items() if not has_activities(wid)]
        
        return max_depth, empty_wbs, acts_by_wbs

    def _project_structure(self):
        checks = []
        
        max_depth, empty_wbs, acts_by_wbs = self._build_wbs_hierarchy()
        
        wbs_ids = set(a.get('wbs_id', '') for a in self.activities if a.get('wbs_id'))
        checks.append(self.make_metric(
            'DOE-101', 'WBS Nodes with Activities',
            f'{len(wbs_ids)} WBS nodes contain direct activities',
            len(wbs_ids), 'DOE', 'WBS Structure',
            threshold_min=1, severity='medium',
            recommendation='All work should be organized under WBS.'
        ))
        
        checks.append(self.make_check(
            'DOE-102', 'Empty WBS Nodes (Subtree)',
            'WBS nodes with no activities in their entire branch',
            len(empty_wbs), len(self.wbs_nodes) or 1, 5, 'DOE', 'low', 'WBS Structure',
            'Remove empty WBS nodes or add planned activities.',
            empty_wbs
        ))
        
        checks.append(self.make_metric(
            'DOE-103', 'Maximum WBS Depth',
            f'{max_depth} levels deep',
            max_depth, 'DOE', 'WBS Structure',
            threshold_min=3, threshold_max=7, severity='medium',
            recommendation='WBS depth should be 3-7 levels for healthy reporting.'
        ))
        
        if acts_by_wbs:
            counts = [len(v) for v in acts_by_wbs.values() if len(v) > 0]
            if counts:
                max_activities = max(counts)
                avg_activities = sum(counts) / len(counts)
                
                checks.append(self.make_metric(
                    'DOE-104', 'Max Activities per WBS Node',
                    f'{max_activities} activities in largest WBS',
                    max_activities, 'DOE', 'WBS Structure',
                    threshold_max=100, severity='medium',
                    recommendation='WBS nodes >100 activities need decomposition.'
                ))
                
                checks.append(self.make_metric(
                    'DOE-105', 'Average Activities per WBS Node',
                    f'{avg_activities:.1f} avg activities',
                    avg_activities, 'DOE', 'WBS Structure',
                    threshold_min=1, threshold_max=25, severity='low',
                    info_only=True
                ))
        
        return {'name': 'Project Structure', 'checks': checks}

    def _schedule_integrity(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        
        checks.append(self.make_metric(
            'DOE-201', 'Total Activities',
            f'{len(self.activities)} activities in schedule',
            len(self.activities), 'DOE', 'Schedule Integrity',
            threshold_min=10, severity='low', info_only=True
        ))
        
        mile_pct = len(self.milestones) / len(self.activities) * 100 if self.activities else 0
        checks.append(self.make_metric(
            'DOE-202', 'Milestone Percentage',
            f'{mile_pct:.1f}% are milestones',
            mile_pct, 'DOE', 'Schedule Integrity',
            threshold_min=2, threshold_max=15, severity='medium',
            recommendation='Milestones should be 2-15% of activities.'
        ))
        
        loe_count = sum(1 for a in self.activities if a.get('task_type') == 'TT_LOE')
        loe_pct = loe_count / len(self.activities) * 100 if self.activities else 0
        checks.append(self.make_metric(
            'DOE-203', 'Level of Effort Percentage',
            f'{loe_pct:.1f}% are LOE',
            loe_pct, 'DOE', 'Schedule Integrity',
            threshold_max=15, severity='medium',
            recommendation='LOE should be <15% of schedule.'
        ))
        
        zero_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) == 0
                   and not self.is_milestone(a)]
        checks.append(self.make_check(
            'DOE-204', 'Zero Duration Non-Milestones',
            'Only milestones should have zero duration',
            len(zero_dur), total_inc, 1, 'DOE', 'high', 'Schedule Integrity',
            'Convert to milestones or add duration.',
            zero_dur
        ))
        
        long_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) > 60
                   and not self.is_milestone(a) and a.get('task_type') != 'TT_LOE']
        checks.append(self.make_check(
            'DOE-205', 'Long Duration Activities (>60 days)',
            'DOE recommends max 60-day activities (excluding LOE)',
            len(long_dur), total_inc, 5, 'DOE', 'medium', 'Schedule Integrity',
            'Break down activities over 60 days.',
            long_dur
        ))
        
        coded = sum(1 for a in self.activities if a.get('task_code', ''))
        code_pct = coded / len(self.activities) * 100 if self.activities else 0
        checks.append(self.make_metric(
            'DOE-206', 'Activity ID Coverage',
            f'{code_pct:.1f}% have activity IDs',
            code_pct, 'DOE', 'Schedule Integrity',
            threshold_min=100, severity='high',
            recommendation='All activities must have unique IDs.'
        ))
        
        code_counts = Counter(a.get('task_code', '') for a in self.activities if a.get('task_code'))
        dup_codes = {c for c, count in code_counts.items() if count > 1}
        dup_acts = [a for a in self.activities if a.get('task_code') in dup_codes]
        
        checks.append(self.make_check(
            'DOE-207', 'Duplicate Activity IDs',
            'Activity IDs must be unique across the schedule',
            len(dup_acts), len(self.activities) or 1, 0, 'DOE', 'critical', 'Schedule Integrity',
            'Fix duplicate activity IDs immediately (or filter multi-project XERs).',
            dup_acts
        ))
        
        return {'name': 'Schedule Integrity', 'checks': checks}

    def _resource_management(self):
        checks = []
        
        if not self.resources:
            checks.append(self.make_metric(
                'DOE-300', 'Schedule is Resource Loaded',
                'No resource assignments found in XER.',
                None, 'DOE', 'Resources', info_only=True,
                recommendation='DOE requires resource-loaded schedules for EVM compliance.'
            ))
            return {'name': 'Resource Management', 'checks': checks}
            
        tasks_with_res = set(r.get('task_id') for r in self.resources)
        work_acts = [a for a in self.incomplete if not self.is_milestone(a) and a.get('task_type') != 'TT_LOE']
        work_total = len(work_acts) or 1
        
        unresourced = [a for a in work_acts if a.get('task_id', '') not in tasks_with_res]
        checks.append(self.make_check(
            'DOE-301', 'Unresourced Work Activities',
            'DOE requires resource-loaded schedules',
            len(unresourced), work_total, 10, 'DOE', 'high', 'Resources',
            'Assign resources to all work activities.',
            unresourced
        ))
        
        costed = [r for r in self.resources if self.to_float(r.get('target_cost', '0')) > 0]
        cost_pct = len(costed) / len(self.resources) * 100
        checks.append(self.make_metric(
            'DOE-302', 'Cost-Loaded Assignments',
            f'{cost_pct:.1f}% have costs assigned',
            cost_pct, 'DOE', 'Resources',
            threshold_min=90, severity='high',
            recommendation='DOE requires cost-loaded schedules.'
        ))
        
        zero_cost_with_hours = [r for r in self.resources 
                               if self.to_float(r.get('target_cost', '0')) == 0
                               and self.to_float(r.get('target_qty', '0')) > 0]
        
        zc_act_ids = {str(r.get('task_id')) for r in zero_cost_with_hours}
        zc_acts = [a for a in self.activities if str(a.get('task_id')) in zc_act_ids]
        
        checks.append(self.make_check(
            'DOE-303', 'Zero-Cost Resources with Hours',
            'Resources with hours must have costs',
            len(zero_cost_with_hours), len(self.resources) or 1, 5, 'DOE', 'medium', 'Resources',
            'Add rates/costs to all resource assignments.',
            zc_acts
        ))
        
        mile_with_res = [a for a in self.milestones if str(a.get('task_id', '')) in tasks_with_res]
        checks.append(self.make_check(
            'DOE-304', 'Milestones with Resources',
            'Milestones should not have resource assignments',
            len(mile_with_res), max(len(self.milestones), 1), 5, 'DOE', 'medium', 'Resources',
            'Remove resources from milestones.',
            mile_with_res
        ))
        
        return {'name': 'Resource Management', 'checks': checks}

    def _progress_measurement(self):
        checks = []
        total = len(self.activities) or 1
        
        prog_no_start = [a for a in self.activities
                        if self.to_float(a.get('phys_complete_pct', '0')) > 0
                        and not a.get('act_start_date', '')]
        checks.append(self.make_check(
            'DOE-401', 'Progress Without Actual Start',
            'Progress requires actual start date',
            len(prog_no_start), total, 0, 'DOE', 'critical', 'Progress',
            'Add actual start dates to progressing activities.',
            prog_no_start
        ))
        
        complete_no_finish = [a for a in self.activities
                             if self.to_float(a.get('phys_complete_pct', '0')) >= 100
                             and not a.get('act_end_date', '')]
        checks.append(self.make_check(
            'DOE-402', '100% Without Actual Finish',
            'Completed activities need actual finish dates',
            len(complete_no_finish), total, 0, 'DOE', 'critical', 'Progress',
            'Add actual finish dates.',
            complete_no_finish
        ))
        
        finish_no_complete = [a for a in self.activities
                             if a.get('act_end_date', '')
                             and self.to_float(a.get('phys_complete_pct', '0')) < 100]
        checks.append(self.make_check(
            'DOE-403', 'Actual Finish Without 100%',
            'Finished activities must be 100% complete',
            len(finish_no_complete), total, 0, 'DOE', 'high', 'Progress',
            'Set progress to 100% for finished activities.',
            finish_no_complete
        ))
        
        remain_issues = [a for a in self.in_progress
                        if a.get('remaining_duration_days', 0) == a.get('original_duration_days', 0)
                        and a.get('original_duration_days', 0) > 0
                        and self.to_float(a.get('phys_complete_pct', '0')) > 0]
        checks.append(self.make_check(
            'DOE-404', 'Progress vs Remaining Duration',
            'Progress usually reduces remaining duration',
            len(remain_issues), max(len(self.in_progress), 1), 5, 'DOE', 'medium', 'Progress',
            'Review activities with progress but identical remaining duration.',
            remain_issues
        ))
        
        checks.append(self.make_boolean(
            'DOE-405', 'Data Date Set',
            'Schedule must have a data date',
            self.data_date is not None, 'DOE', 'Progress',
            severity='critical',
            recommendation='Set a valid data date before analysis.'
        ))
        
        return {'name': 'Progress Measurement', 'checks': checks}

    def _risk_management(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        
        crit_inc = [a for a in self.incomplete if a.get('is_critical')]
        cp_pct = len(crit_inc) / total_inc * 100
        checks.append(self.make_metric(
            'DOE-501', 'Critical Path Percentage',
            f'{cp_pct:.1f}% on critical path',
            cp_pct, 'DOE', 'Risk',
            threshold_min=5, threshold_max=25, severity='medium',
            recommendation='CP should be 5-25%. Too few = slack; too many = high risk.'
        ))
        
        near_crit = [a for a in self.incomplete if 0 < a.get('total_float_days', 0) <= 10]
        checks.append(self.make_metric(
            'DOE-502', 'Near-Critical Activities',
            f'{len(near_crit)} activities with <10 days float',
            len(near_crit), 'DOE', 'Risk',
            threshold_max=None, severity='medium', info_only=True,
            recommendation='Near-critical activities can quickly become critical.'
        ))
        
        floats = [a.get('total_float_days', 0) for a in self.incomplete]
        if floats:
            median_float = statistics.median(floats)
            checks.append(self.make_metric(
                'DOE-503', 'Median Total Float',
                f'{median_float:.1f} days median float',
                median_float, 'DOE', 'Risk',
                threshold_min=5, threshold_max=60, severity='medium',
                recommendation='Very low = tight schedule; very high = broken logic.'
            ))
            
            avg_float = sum(floats) / len(floats)
            checks.append(self.make_metric(
                'DOE-504', 'Average Total Float (Contingency)',
                f'{avg_float:.1f} days average',
                avg_float, 'DOE', 'Risk',
                threshold_min=0, severity='low', info_only=True
            ))
        
        neg_float = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'DOE-505', 'Negative Float Activities',
            'Activities behind schedule constraints',
            len(neg_float), total_inc, 0, 'DOE', 'critical', 'Risk',
            'Immediate recovery planning required for negative float.',
            neg_float
        ))
        
        return {'name': 'Risk Management', 'checks': checks}

    def _earned_value_checks(self):
        checks = []
        
        with_target = sum(1 for a in self.real_activities if a.get('target_start_date', ''))
        target_pct = with_target / max(len(self.real_activities), 1) * 100
        checks.append(self.make_metric(
            'DOE-601', 'Activities with Target Dates',
            f'{target_pct:.1f}% have target (baseline) dates',
            target_pct, 'DOE', 'Earned Value',
            threshold_min=100, severity='high',
            recommendation='All activities need baseline/target dates for EVM.'
        ))
        
        max_depth, _, _ = self._build_wbs_hierarchy()
        checks.append(self.make_metric(
            'DOE-602', 'WBS Depth for EV Reporting',
            f'{max_depth} levels',
            max_depth, 'DOE', 'Earned Value',
            threshold_min=3, severity='medium',
            recommendation='EV reporting needs at least 3 WBS levels.'
        ))
        
        return {'name': 'Earned Value Compliance', 'checks': checks}

    def _logic_network_quality(self):
        checks = []
        total = len(self.incomplete) or 1
        
        open_start = self.open_start_activities()
        open_end = self.open_end_activities()
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1
        
        checks.append(self.make_check(
            'DOE-701', 'Open Start Activities',
            'Non-milestone activities without predecessors',
            len(open_start), total, 1, 'DOE', 'high', 'Logic Network',
            'DOE PM-30 requires closed-loop logic. Only start milestones should have no predecessors.',
            open_start
        ))
        
        checks.append(self.make_check(
            'DOE-702', 'Open End Activities',
            'Non-milestone activities without successors',
            len(open_end), total, 1, 'DOE', 'high', 'Logic Network',
            'DOE PM-30 requires closed-loop logic. Only finish milestones should have no successors.',
            open_end
        ))
        
        neg_lags = [r for r in active_rels if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'DOE-703', 'Negative Lags (Leads)',
            'DOE does not permit negative lags',
            len(neg_lags), rel_total, 0, 'DOE', 'high', 'Logic Network',
            'Remove all negative lags per DOE guidelines.',
            neg_lags
        ))
        
        big_lags = [r for r in active_rels if r.get('lag_days', 0) > 15]
        checks.append(self.make_check(
            'DOE-704', 'Large Lags (>15 days)',
            'DOE recommends minimizing lags',
            len(big_lags), rel_total, 3, 'DOE', 'medium', 'Logic Network',
            'Convert large lags into schedule activities.',
            big_lags
        ))
        
        non_fs = [r for r in active_rels if r.get('pred_type') != 'PR_FS']
        checks.append(self.make_check(
            'DOE-705', 'Non-FS Relationships',
            'DOE prefers Finish-to-Start relationships',
            len(non_fs), rel_total, 10, 'DOE', 'medium', 'Logic Network',
            'Use FS relationships wherever possible.',
            non_fs
        ))
        
        fs_lag = self.fs_with_lag()
        checks.append(self.make_check(
            'DOE-FS-LAG', 'FS + Lag Relationships',
            'Finish-to-Start relationships with lag',
            len(fs_lag), rel_total, 3, 'DOE', 'medium', 'Logic Network',
            'DOE PM-30 discourages lags. Replace with real activities (e.g., "Cure Time").',
            fs_lag
        ))
        
        return {'name': 'Logic Network Quality', 'checks': checks}
'''

doe_path = os.path.join("health_standards", "doe_checks.py")
with open(doe_path, "w", encoding="utf-8") as f:
    f.write(DOE_CHECKS_CODE)
print("  ✅ Updated health_standards/doe_checks.py")


# ------------------------------------------------------------------------------
# 4. health_standards/gao_checks.py
# ------------------------------------------------------------------------------
GAO_CHECKS_CODE = '''"""
GAO SCHEDULE ASSESSMENT GUIDE
==============================
"""

from health_standards.base_checker import BaseChecker
from collections import Counter, defaultdict
from datetime import datetime
import statistics


class GAOChecks(BaseChecker):
    """GAO Best Practices comprehensive check suite."""

    def run_checks(self):
        return {
            'name': 'GAO Schedule Assessment Guide',
            'description': 'US Government Accountability Office schedule best practices',
            'categories': [
                self._bp1_capturing_work(),
                self._bp2_sequencing_activities(),
                self._bp3_resources_established(),
                self._bp4_durations_established(),
                self._bp5_schedule_verified(),
                self._bp6_critical_path_traced(),
                self._bp7_float_analyzed(),
                self._bp8_baseline_established(),
                self._bp9_updates_maintained(),
                self._bp10_risk_managed(),
            ]
        }

    def _bp1_capturing_work(self):
        checks = []
        total = len(self.activities) or 1

        checks.append(self.make_metric(
            'GAO-101', 'Total Activities in Schedule',
            f'{len(self.activities)} activities',
            len(self.activities), 'GAO', 'BP1: Capturing Work',
            threshold_min=1, severity='critical',
            recommendation='Schedule must contain activities.',
            info_only=True
        ))

        no_name = [a for a in self.activities if not str(a.get('task_name', '')).strip()]
        checks.append(self.make_check(
            'GAO-102', 'Missing Activity Names',
            'All activities must be named',
            len(no_name), total, 0, 'GAO', 'critical', 'BP1: Capturing Work',
            'Add names to all activities.',
            no_name
        ))

        no_wbs = [a for a in self.activities if not a.get('wbs_id', '')]
        checks.append(self.make_check(
            'GAO-103', 'Activities Without WBS',
            'All activities must be assigned to WBS',
            len(no_wbs), total, 0, 'GAO', 'high', 'BP1: Capturing Work',
            'Assign activities to appropriate WBS nodes.',
            no_wbs
        ))

        no_type = [a for a in self.activities if not a.get('task_type', '')]
        checks.append(self.make_check(
            'GAO-104', 'Missing Activity Types',
            'All activities need type designation',
            len(no_type), total, 0, 'GAO', 'high', 'BP1: Capturing Work',
            'Assign type: Task, Milestone, LOE, etc.',
            no_type
        ))

        return {'name': 'BP1: Capturing All Work', 'checks': checks}

    def _bp2_sequencing_activities(self):
        checks = []
        total = len(self.incomplete) or 1
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1

        checks.append(self.make_metric(
            'GAO-201', 'Total Relationships',
            f'{len(self.relationships)} logic ties',
            len(self.relationships), 'GAO', 'BP2: Sequencing',
            threshold_min=1, severity='critical',
            recommendation='Schedule must have relationships defined.'
        ))

        open_start = self.open_start_activities()
        open_end = self.open_end_activities()

        checks.append(self.make_check(
            'GAO-202', 'Open Start Activities',
            'Incomplete non-milestone activities without predecessors',
            len(open_start), total, 1, 'GAO', 'high', 'BP2: Sequencing',
            'Add predecessor logic to eliminate dangling starts.',
            open_start
        ))

        checks.append(self.make_check(
            'GAO-203', 'Open End Activities',
            'Incomplete non-milestone activities without successors',
            len(open_end), total, 1, 'GAO', 'high', 'BP2: Sequencing',
            'Add successor logic to eliminate dangling ends.',
            open_end
        ))

        fs = [r for r in active_rels if r.get('pred_type') == 'PR_FS']
        fs_pct = len(fs) / rel_total * 100
        checks.append(self.make_metric(
            'GAO-204', 'FS Relationships %',
            f'{fs_pct:.1f}% are FS (active logic)',
            fs_pct, 'GAO', 'BP2: Sequencing',
            threshold_min=90, severity='medium',
            recommendation='GAO recommends 90%+ Finish-to-Start.'
        ))

        sf = [r for r in active_rels if r.get('pred_type') == 'PR_SF']
        checks.append(self.make_check(
            'GAO-205', 'Start-to-Finish Relationships',
            'SF relationships should be avoided',
            len(sf), rel_total, 0, 'GAO', 'high', 'BP2: Sequencing',
            'Convert SF to standard FS relationships.',
            sf
        ))

        leads = [r for r in active_rels if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'GAO-206', 'Negative Lags (Leads)',
            'No relationships should have leads',
            len(leads), rel_total, 0, 'GAO', 'high', 'BP2: Sequencing',
            'Remove all negative lags.',
            leads
        ))

        big_lags = [r for r in active_rels if r.get('lag_days', 0) > 20]
        checks.append(self.make_check(
            'GAO-207', 'Large Lags (>20 days)',
            'Large lags may hide work',
            len(big_lags), rel_total, 3, 'GAO', 'medium', 'BP2: Sequencing',
            'Consider replacing large lags with activities.',
            big_lags
        ))

        denom = len(self.real_activities) or 1
        density = len(self.relationships) / denom
        checks.append(self.make_metric(
            'GAO-208', 'Logic Density (Rel/Real Act)',
            f'{density:.2f}',
            density, 'GAO', 'BP2: Sequencing',
            threshold_min=1.5, threshold_max=4.0, severity='medium',
            recommendation='Density 1.5-4.0 indicates healthy network.'
        ))

        fs_lag = self.fs_with_lag()
        checks.append(self.make_check(
            'GAO-FS-LAG', 'FS + Lag Relationships',
            'Finish-to-Start relationships using lag',
            len(fs_lag), rel_total, 3, 'GAO', 'medium', 'BP2: Sequencing',
            'Use activities instead of lags for waiting periods (transparency).',
            fs_lag
        ))

        return {'name': 'BP2: Sequencing Activities', 'checks': checks}

    def _bp3_resources_established(self):
        checks = []

        if not self.resources:
            checks.append(self.make_metric(
                'GAO-300', 'Resource Loading Present',
                'No resource assignments in XER',
                None, 'GAO', 'BP3: Resources',
                info_only=True,
                recommendation='GAO BP3 prefers resource-loaded schedules when cost/EVM applies.'
            ))
            return {'name': 'BP3: Resources Established', 'checks': checks}

        tasks_with_res = set(str(r.get('task_id')) for r in self.resources)
        work_acts = [
            a for a in self.incomplete
            if not self.is_milestone(a) and a.get('task_type') != 'TT_LOE'
        ]
        work_total = max(len(work_acts), 1)

        no_res = [a for a in work_acts if str(a.get('task_id', '')) not in tasks_with_res]
        checks.append(self.make_check(
            'GAO-301', 'Work Activities Without Resources',
            'GAO best practice: resource-loaded schedules',
            len(no_res), work_total, 10, 'GAO', 'medium', 'BP3: Resources',
            'Assign resources to work activities.',
            no_res
        ))

        with_cost = [r for r in self.resources if self.to_float(r.get('target_cost', '0')) > 0]
        cost_pct = len(with_cost) / max(len(self.resources), 1) * 100
        checks.append(self.make_metric(
            'GAO-302', 'Cost-Loaded Assignments',
            f'{cost_pct:.1f}% have costs',
            cost_pct, 'GAO', 'BP3: Resources',
            threshold_min=80, severity='medium',
            recommendation='Cost-loaded schedules enable EVM.'
        ))

        role_ids = set(r.get('role_id', '') for r in self.resources if r.get('role_id'))
        checks.append(self.make_metric(
            'GAO-303', 'Unique Resource Roles',
            f'{len(role_ids)} roles used',
            len(role_ids), 'GAO', 'BP3: Resources',
            threshold_min=0, severity='low', info_only=True
        ))

        return {'name': 'BP3: Resources Established', 'checks': checks}

    def _bp4_durations_established(self):
        checks = []
        total = len(self.incomplete) or 1

        zero_dur = [
            a for a in self.incomplete
            if a.get('original_duration_days', 0) == 0 and not self.is_milestone(a)
        ]
        checks.append(self.make_check(
            'GAO-401', 'Zero Duration Tasks',
            'Only milestones may have zero duration',
            len(zero_dur), total, 1, 'GAO', 'high', 'BP4: Durations',
            'Add duration or convert to milestone.',
            zero_dur
        ))

        long_dur = [
            a for a in self.incomplete
            if a.get('original_duration_days', 0) > 44
            and not self.is_milestone(a)
            and a.get('task_type') != 'TT_LOE'
        ]
        checks.append(self.make_check(
            'GAO-402', 'Long Duration (>44 days)',
            'Heuristic: break down long-duration work packages (≈2 months)',
            len(long_dur), total, 5, 'GAO', 'medium', 'BP4: Durations',
            'Decompose long activities for better tracking (GAO-aligned heuristic).',
            long_dur
        ))

        durs = [
            a.get('original_duration_days', 0) for a in self.real_activities
            if a.get('original_duration_days', 0) > 0
        ]
        if durs:
            avg = statistics.mean(durs)
            checks.append(self.make_metric(
                'GAO-403', 'Average Activity Duration',
                f'{avg:.1f} days',
                avg, 'GAO', 'BP4: Durations',
                threshold_min=1, threshold_max=30, severity='low', info_only=True
            ))
            if len(durs) > 1:
                stdev = statistics.stdev(durs)
                checks.append(self.make_metric(
                    'GAO-404', 'Duration Standard Deviation',
                    f'{stdev:.1f} days',
                    stdev, 'GAO', 'BP4: Durations',
                    severity='low', info_only=True
                ))

        return {'name': 'BP4: Realistic Durations', 'checks': checks}

    def _bp5_schedule_verified(self):
        checks = []
        total = len(self.activities) or 1

        checks.append(self.make_boolean(
            'GAO-501', 'Data Date Established',
            'Schedule must have data date',
            self.data_date is not None, 'GAO', 'BP5: Verification',
            severity='critical',
            recommendation='Set data date for progress tracking.'
        ))

        invalid = [
            a for a in self.activities
            if a.get('status_code') == 'TK_NotStart' and a.get('act_start_date', '')
        ]
        checks.append(self.make_check(
            'GAO-502', 'Invalid Date Combinations',
            'Actual dates on unstarted tasks',
            len(invalid), total, 0, 'GAO', 'critical', 'BP5: Verification',
            'Fix invalid date combinations.',
            invalid
        ))

        rev_dates = []
        for a in self.activities:
            s = a.get('early_start_date_parsed')
            e = a.get('early_end_date_parsed')
            if s and e and e < s:
                rev_dates.append(a)
        checks.append(self.make_check(
            'GAO-503', 'Finish Before Start (Early Dates)',
            'Early finish must be on/after early start',
            len(rev_dates), total, 0, 'GAO', 'critical', 'BP5: Verification',
            'Fix inverted early dates.',
            rev_dates
        ))

        future_acts = []
        if self.data_date:
            for a in self.activities:
                for field in ('act_start_date_parsed', 'act_end_date_parsed'):
                    d = a.get(field)
                    if d and d > self.data_date:
                        future_acts.append(a)
                        break
        checks.append(self.make_check(
            'GAO-504', 'Actuals After Data Date',
            'Actual dates must not exceed data date',
            len(future_acts), total, 0, 'GAO', 'critical', 'BP5: Verification',
            'Correct actual dates beyond data date.',
            future_acts
        ))

        vertical_issues = self._vertical_integration_issues()
        checks.append(self.make_check(
            'GAO-505', 'Vertical Integration (WBS vs Detail)',
            'WBS/summary date envelope should cover child activities',
            len(vertical_issues), max(len(self.wbs_nodes), 1), 5, 'GAO', 'medium', 'BP5: Verification',
            'Align WBS/summary dates with detail schedule (horizontal/vertical integration).',
            vertical_issues
        ))

        return {'name': 'BP5: Schedule Verified', 'checks': checks}

    def _vertical_integration_issues(self):
        issues = []
        acts_by_wbs = defaultdict(list)
        for a in self.real_activities:
            wid = str(a.get('wbs_id', '') or '')
            if wid:
                acts_by_wbs[wid].append(a)

        wbs_summary_tasks = [
            a for a in self.activities if a.get('task_type') == 'TT_WBS'
        ]
        for wbs_task in wbs_summary_tasks:
            wid = str(wbs_task.get('wbs_id', '') or '')
            children = acts_by_wbs.get(wid, [])
            if not children:
                continue
            child_ends = [c.get('early_end_date_parsed') for c in children if c.get('early_end_date_parsed')]
            wbs_end = wbs_task.get('early_end_date_parsed')
            if child_ends and wbs_end and max(child_ends) > wbs_end:
                issues.append(wbs_task)
        return issues

    def _bp6_critical_path_traced(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        crit_inc = [a for a in self.incomplete if a.get('is_critical')]
        cp_count = len(crit_inc)
        cp_pct = cp_count / total_inc * 100

        checks.append(self.make_boolean(
            'GAO-601', 'Critical Path Exists',
            'Schedule must have critical path activities',
            cp_count > 0, 'GAO', 'BP6: Critical Path',
            severity='critical',
            recommendation='Must have valid critical path (TF ≤ 0 remaining work).'
        ))

        checks.append(self.make_metric(
            'GAO-602', 'Critical Path % (Incomplete)',
            f'{cp_pct:.1f}% of incomplete work is critical',
            cp_pct, 'GAO', 'BP6: Critical Path',
            threshold_min=5, threshold_max=25, severity='medium',
            recommendation='GAO guideline: roughly 5-25% critical (heuristic).'
        ))

        continuity = self._cp_continuity()
        checks.append(self.make_metric(
            'GAO-603', 'Critical Path Continuity',
            'Share of critical acts linked to other critical acts',
            continuity, 'GAO', 'BP6: Critical Path',
            threshold_min=0.85, severity='high',
            recommendation='Trace a continuous critical path to the finish objective.'
        ))

        near = [a for a in self.incomplete if 0 < a.get('total_float_days', 0) <= 5]
        checks.append(self.make_metric(
            'GAO-604', 'Near-Critical Activities',
            f'{len(near)} within 5 days of CP',
            len(near), 'GAO', 'BP6: Critical Path',
            severity='medium', info_only=True
        ))

        return {'name': 'BP6: Critical Path Traced', 'checks': checks}

    def _cp_continuity(self):
        try:
            crit_ids = {str(a.get('task_id', '')) for a in self.incomplete if a.get('is_critical')}
            if not crit_ids:
                return None
            connected = 0
            for cid in crit_ids:
                succs = self.engine.successors.get(cid, [])
                preds = self.engine.predecessors.get(cid, [])
                if any(str(s.get('task_id')) in crit_ids for s in succs):
                    connected += 1
                elif any(str(p.get('task_id')) in crit_ids for p in preds):
                    connected += 1
            return round(connected / len(crit_ids), 3)
        except Exception:
            return None

    def _bp7_float_analyzed(self):
        checks = []
        total = len(self.incomplete) or 1

        neg = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'GAO-701', 'Negative Float',
            'Schedule should not have negative float',
            len(neg), total, 0, 'GAO', 'critical', 'BP7: Float',
            'Address all negative float immediately.',
            neg
        ))

        high = [a for a in self.incomplete if a.get('total_float_days', 0) > 44]
        checks.append(self.make_check(
            'GAO-702', 'High Float (>44 days)',
            'Excessive float often indicates missing logic',
            len(high), total, 5, 'GAO', 'medium', 'BP7: Float',
            'Investigate high-float activities.',
            high
        ))

        extreme = [a for a in self.incomplete if a.get('total_float_days', 0) > 100]
        checks.append(self.make_check(
            'GAO-703', 'Extreme Float (>100 days)',
            'Extreme float almost always = broken logic',
            len(extreme), total, 2, 'GAO', 'high', 'BP7: Float',
            'Fix logic causing extreme float.',
            extreme
        ))

        floats = [a.get('total_float_days', 0) for a in self.incomplete]
        if floats:
            median = statistics.median(floats)
            checks.append(self.make_metric(
                'GAO-704', 'Median Float',
                f'{median:.1f} days',
                median, 'GAO', 'BP7: Float',
                severity='low', info_only=True
            ))

        return {'name': 'BP7: Float Analyzed', 'checks': checks}

    def _bp8_baseline_established(self):
        checks = []
        pool = self.real_activities
        total = len(pool) or 1

        with_bl = sum(1 for a in pool if a.get('target_start_date', ''))
        bl_pct = with_bl / total * 100
        checks.append(self.make_metric(
            'GAO-801', 'Target/Planned Start Coverage',
            f'{bl_pct:.1f}% have target start (baseline proxy in single XER)',
            bl_pct, 'GAO', 'BP8: Baseline',
            threshold_min=100, severity='high',
            recommendation='True GAO baseline is an approved PMB; here we check target dates in the XER.'
        ))

        with_bl_end = sum(1 for a in pool if a.get('target_end_date', ''))
        end_pct = with_bl_end / total * 100
        checks.append(self.make_metric(
            'GAO-802', 'Target/Planned Finish Coverage',
            f'{end_pct:.1f}% have target finish',
            end_pct, 'GAO', 'BP8: Baseline',
            threshold_min=100, severity='high',
            recommendation='Ensure planned finish dates exist; use comparison module for true BL XER.'
        ))

        return {'name': 'BP8: Baseline Established', 'checks': checks}

    def _bp9_updates_maintained(self):
        checks = []
        total = len(self.activities) or 1

        if self.data_date:
            ref = datetime.now()
            age = (ref - self.data_date).days
            info_only = age > 365
            checks.append(self.make_metric(
                'GAO-901', 'Data Date Age',
                f'{age} days (vs analysis time)',
                age, 'GAO', 'BP9: Updates',
                threshold_max=30, severity='medium',
                info_only=info_only,
                recommendation='Update schedule monthly for live control (data date <30 days).'
            ))

        prog_no_start = [
            a for a in self.activities
            if self.to_float(a.get('phys_complete_pct', '0')) > 0
            and not a.get('act_start_date', '')
        ]
        checks.append(self.make_check(
            'GAO-902', 'Progress Without Actual Start',
            'Update actuals with progress',
            len(prog_no_start), total, 0, 'GAO', 'critical', 'BP9: Updates',
            'Add actual dates for progressed work.',
            prog_no_start
        ))

        comp_no_end = [
            a for a in self.activities
            if self.to_float(a.get('phys_complete_pct', '0')) >= 100
            and not a.get('act_end_date', '')
        ]
        checks.append(self.make_check(
            'GAO-903', '100% Without Actual Finish',
            'Complete activities need finish dates',
            len(comp_no_end), total, 0, 'GAO', 'critical', 'BP9: Updates',
            'Add actual finish dates.',
            comp_no_end
        ))

        return {'name': 'BP9: Updates Maintained', 'checks': checks}

    def _bp10_risk_managed(self):
        checks = []
        total_inc = len(self.incomplete) or 1

        constrained = [a for a in self.incomplete if self.has_hard_constraint(a)]
        checks.append(self.make_check(
            'GAO-1001', 'Hard Constraints (Risk Indicator)',
            'Hard constraints override CPM and hinder risk analysis',
            len(constrained), total_inc, 2, 'GAO', 'high', 'BP10: Risk Indicators',
            'Remove hard constraints for proper CPM and schedule risk analysis.',
            constrained
        ))

        alap = [
            a for a in self.incomplete
            if a.get('cstr_type') == 'CS_ALAP' or a.get('cstr_type2') == 'CS_ALAP'
        ]
        checks.append(self.make_check(
            'GAO-1001b', 'ALAP Constraints',
            'ALAP consumes float and masks risk',
            len(alap), total_inc, 1, 'GAO', 'high', 'BP10: Risk Indicators',
            'Minimize ALAP usage.',
            alap
        ))

        near_crit_mile = [
            a for a in self.milestones
            if 0 < a.get('total_float_days', 0) <= 10
            and a.get('status_code') != 'TK_Complete'
        ]
        checks.append(self.make_metric(
            'GAO-1002', 'Near-Critical Milestones',
            f'{len(near_crit_mile)} at risk',
            len(near_crit_mile), 'GAO', 'BP10: Risk Indicators',
            severity='high', info_only=True,
            recommendation='Monitor near-critical milestones closely.'
        ))

        neg = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'GAO-1003', 'Slipped Activities (Negative Float)',
            'Indicators of schedule slippage',
            len(neg), total_inc, 0, 'GAO', 'critical', 'BP10: Risk Indicators',
            'Recovery planning required for negative float.',
            neg
        ))

        near = [a for a in self.incomplete if a.get('total_float_days', 0) <= 5]
        near_rem = sum(a.get('remaining_duration_days', 0) or 0 for a in near)
        all_rem = sum(a.get('remaining_duration_days', 0) or 0 for a in self.incomplete) or 1
        conc = (near_rem / all_rem) * 100
        checks.append(self.make_metric(
            'GAO-1004', 'Near-Critical Remaining Duration %',
            f'{conc:.1f}% of remaining duration is TF≤5d',
            conc, 'GAO', 'BP10: Risk Indicators',
            threshold_max=40, severity='medium',
            recommendation='High concentration of remaining work on thin float increases risk. (Not a full SRA.)'
        ))

        return {'name': 'BP10: Risk Indicators (Deterministic Proxies)', 'checks': checks}
'''

gao_path = os.path.join("health_standards", "gao_checks.py")
with open(gao_path, "w", encoding="utf-8") as f:
    f.write(GAO_CHECKS_CODE)
print("  ✅ Updated health_standards/gao_checks.py")

print("\n🎉 Part 2 Patches Applied Successfully via Python!")
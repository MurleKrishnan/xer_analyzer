"""
INDUSTRY BEST PRACTICES
========================
Consensus checks based on:
- PMI PMBOK Practice Standard for Scheduling
- Construction Industry Institute (CII) practices
- ISO 21500 & ISO 21502
- Industry consensus guidelines
"""

from health_standards.base_checker import BaseChecker
from collections import Counter, defaultdict, deque
from datetime import datetime
import statistics


class IndustryChecks(BaseChecker):
    """Industry best practices check suite."""

    def run_checks(self):
        return {
            'name': 'Industry Best Practices',
            'description': 'Consensus best practices from PMI, CII, ISO, and industry',
            'categories': [
                self._schedule_completeness(),
                self._logic_quality(),
                self._resource_realism(),
                self._progress_transparency(),
                self._schedule_optimization(),
                self._maintainability(),
            ]
        }

    # ═══════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════
    def _wbs_max_depth(self):
        by_id = {str(w.get('wbs_id', '')): w for w in self.wbs_nodes if w.get('wbs_id')}

        def parent_of(w):
            for k in ('parent_wbs_id', 'parent_id', 'parent_wbs', 'wbs_parent_id'):
                v = w.get(k, '')
                if v not in (None, '', '0', 0):
                    return str(v)
            return ''

        def depth(wid, seen=None):
            seen = seen or set()
            if not wid or wid in seen:
                return 0
            seen.add(wid)
            w = by_id.get(wid)
            if not w:
                return 0
            p = parent_of(w)
            return 1 + (depth(p, seen) if p in by_id else 0)

        return max((depth(wid) for wid in by_id), default=0)

    def _has_circular_logic(self):
        """
        Kahn's algorithm topological sort.
        Returns True if a cycle exists.
        """
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        nodes = set()

        for a in self.activities:
            tid = str(a.get('task_id', '') or '')
            if tid:
                nodes.add(tid)
                in_degree.setdefault(tid, 0)

        for r in self.relationships:
            p = str(r.get('pred_task_id', '') or '')
            s = str(r.get('task_id', '') or '')
            if not p or not s:
                continue
            if p not in nodes:
                nodes.add(p)
                in_degree.setdefault(p, 0)
            if s not in nodes:
                nodes.add(s)
                in_degree.setdefault(s, 0)
            graph[p].append(s)
            in_degree[s] += 1

        if not nodes:
            return False

        q = deque([n for n in nodes if in_degree[n] == 0])
        visited = 0
        while q:
            n = q.popleft()
            visited += 1
            for m in graph[n]:
                in_degree[m] -= 1
                if in_degree[m] == 0:
                    q.append(m)

        return visited != len(nodes)

    # ═══════════════════════════════════════════════════════
    # 1. COMPLETENESS
    # ═══════════════════════════════════════════════════════
    def _schedule_completeness(self):
        checks = []
        total = len(self.activities) or 1

        checks.append(self.make_metric(
            'IND-101', 'Project Activities Defined',
            f'{len(self.activities)}',
            len(self.activities), 'Industry', 'Completeness',
            threshold_min=1, severity='critical',
            recommendation='Schedule must contain activities.'
        ))

        no_type = [a for a in self.activities if not a.get('task_type', '')]
        checks.append(self.make_check(
            'IND-102', 'Untyped Activities',
            'All activities need type classification',
            len(no_type), total, 0, 'Industry', 'high', 'Completeness',
            'Assign Task / Milestone / LOE / etc.',
            no_type
        ))

        no_wbs = [a for a in self.activities if not a.get('wbs_id', '')]
        checks.append(self.make_check(
            'IND-103', 'Missing WBS Assignment',
            'Activities need WBS assignment',
            len(no_wbs), total, 0, 'Industry', 'high', 'Completeness',
            'Assign activities to WBS nodes.',
            no_wbs
        ))

        no_cal = [a for a in self.activities if not a.get('clndr_id', '')]
        checks.append(self.make_check(
            'IND-104', 'Missing Calendar Assignment',
            'All activities need a calendar',
            len(no_cal), total, 0, 'Industry', 'high', 'Completeness',
            'Assign calendars to avoid default/silent calendar issues.',
            no_cal
        ))

        checks.append(self.make_metric(
            'IND-105', 'Milestone Presence',
            f'{len(self.milestones)} milestones',
            len(self.milestones), 'Industry', 'Completeness',
            threshold_min=3, severity='medium',
            recommendation='Projects should have key milestones for tracking.'
        ))

        return {'name': 'Schedule Completeness', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 2. LOGIC QUALITY
    # ═══════════════════════════════════════════════════════
    def _logic_quality(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1
        dens_denom = len(self.real_activities) or 1

        density = len(self.relationships) / dens_denom
        checks.append(self.make_metric(
            'IND-201', 'Logic Density',
            f'{density:.2f} rel / real activity',
            density, 'Industry', 'Logic',
            threshold_min=1.5, threshold_max=4.0, severity='medium',
            recommendation='Industry norm: roughly 1.5-4.0 relationships per activity.'
        ))

        fs = sum(1 for r in active_rels if r.get('pred_type') == 'PR_FS')
        fs_pct = fs / rel_total * 100
        checks.append(self.make_metric(
            'IND-202', 'FS Percentage (Active Logic)',
            f'{fs_pct:.1f}%',
            fs_pct, 'Industry', 'Logic',
            threshold_min=80, severity='medium',
            recommendation='Industry norm: 80%+ FS relationships.'
        ))

        # Dangling = open start OR open end (incomplete, non-milestone)
        open_start = self.open_start_activities()
        open_end = self.open_end_activities()
        dangling_ids = {str(a.get('task_id')) for a in open_start} | {
            str(a.get('task_id')) for a in open_end
        }
        dangling = [a for a in self.incomplete if str(a.get('task_id')) in dangling_ids]

        checks.append(self.make_check(
            'IND-203', 'Dangling Activities',
            'Incomplete non-milestone activities missing pred and/or succ',
            len(dangling), total_inc, 2, 'Industry', 'high', 'Logic',
            'Close the network: every work activity needs proper logic.',
            dangling
        ))

        has_cycle = self._has_circular_logic()
        checks.append(self.make_boolean(
            'IND-204', 'Circular Logic Free',
            'No circular dependencies detected in the network',
            not has_cycle, 'Industry', 'Logic',
            severity='critical',
            recommendation='Break cycle(s) — schedule will not calculate correctly.'
        ))

        open_s = open_start
        open_e = open_end
        checks.append(self.make_check(
            'IND-205', 'Open Start Activities',
            'Incomplete non-milestones without predecessors',
            len(open_s), total_inc, 1, 'Industry', 'high', 'Logic',
            'Only start milestones should lack predecessors.',
            open_s
        ))
        checks.append(self.make_check(
            'IND-206', 'Open End Activities',
            'Incomplete non-milestones without successors',
            len(open_e), total_inc, 1, 'Industry', 'high', 'Logic',
            'Only finish milestones should lack successors.',
            open_e
        ))

        leads = [r for r in active_rels if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'IND-207', 'Negative Lags (Leads)',
            'Leads distort CPM',
            len(leads), rel_total, 0, 'Industry', 'high', 'Logic',
            'Remove negative lags.',
            leads
        ))

        fs_lag = self.fs_with_lag()
        checks.append(self.make_check(
            'IND-208', 'FS + Lag Relationships',
            'Prefer explicit wait activities over FS lag',
            len(fs_lag), rel_total, 5, 'Industry', 'medium', 'Logic',
            'Replace lag with visible schedule activities where practical.',
            fs_lag
        ))

        return {'name': 'Logic Quality', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 3. RESOURCE REALISM
    # ═══════════════════════════════════════════════════════
    def _resource_realism(self):
        checks = []

        checks.append(self.make_metric(
            'IND-301', 'Resource Assignments',
            f'{len(self.resources)}',
            len(self.resources), 'Industry', 'Resources',
            severity='low', info_only=True
        ))

        if not self.resources:
            checks.append(self.make_metric(
                'IND-300', 'Schedule Resource Loaded',
                'No TASKRSRC assignments found',
                None, 'Industry', 'Resources', info_only=True,
                recommendation='Resource loading is preferred for cost/crew realism; N/A if pure logic IMS.'
            ))
            return {'name': 'Resource Realism', 'checks': checks}

        tasks_with_res = set(str(r.get('task_id')) for r in self.resources)
        work_acts = [
            a for a in self.incomplete
            if not self.is_milestone(a) and a.get('task_type') != 'TT_LOE'
        ]
        no_res = [a for a in work_acts if str(a.get('task_id', '')) not in tasks_with_res]
        no_res_pct = len(no_res) / max(len(work_acts), 1) * 100

        checks.append(self.make_metric(
            'IND-302', 'Unresourced Work',
            f'{no_res_pct:.1f}%',
            no_res_pct, 'Industry', 'Resources',
            threshold_max=15, severity='medium',
            recommendation='Industry norm: <15% unresourced work when loading is required.'
        ))
        # Also attach list via a companion check for exports
        checks.append(self.make_check(
            'IND-302b', 'Unresourced Work Activities (List)',
            'Work activities without resource assignments',
            len(no_res), max(len(work_acts), 1), 15, 'Industry', 'medium', 'Resources',
            'Assign resources where required by contract/controls process.',
            no_res
        ))

        cost_loaded = sum(1 for r in self.resources if self.to_float(r.get('target_cost', '0')) > 0)
        cost_pct = cost_loaded / max(len(self.resources), 1) * 100
        checks.append(self.make_metric(
            'IND-303', 'Cost-Loaded Assignments',
            f'{cost_pct:.1f}%',
            cost_pct, 'Industry', 'Resources',
            threshold_min=85, severity='medium',
            recommendation='Cost loading enables budget and EVM analysis.'
        ))

        return {'name': 'Resource Realism', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 4. PROGRESS TRANSPARENCY
    # ═══════════════════════════════════════════════════════
    def _progress_transparency(self):
        checks = []
        total = len(self.activities) or 1

        prog_issues = [
            a for a in self.activities
            if self.to_float(a.get('phys_complete_pct', '0')) > 0
            and not a.get('act_start_date', '')
        ]
        checks.append(self.make_check(
            'IND-401', 'Inconsistent Progress',
            'Progress without actual start',
            len(prog_issues), total, 0, 'Industry', 'critical', 'Progress',
            'Enter actual start when progress is claimed.',
            prog_issues
        ))

        if self.data_date:
            age = (datetime.now() - self.data_date).days
            checks.append(self.make_metric(
                'IND-402', 'Data Date Age',
                f'{age} days',
                age, 'Industry', 'Progress',
                threshold_max=30, severity='medium',
                info_only=(age > 365),
                recommendation='Industry norm: update monthly for live control.'
            ))

        comp_missing = [
            a for a in self.completed
            if not a.get('act_start_date', '') or not a.get('act_end_date', '')
        ]
        checks.append(self.make_check(
            'IND-403', 'Completed with Missing Actuals',
            'Complete activities need both actual start and finish',
            len(comp_missing), max(len(self.completed), 1), 0, 'Industry', 'high', 'Progress',
            'Backfill actual start/finish on completed work.',
            comp_missing
        ))

        finish_no_100 = [
            a for a in self.activities
            if a.get('act_end_date', '')
            and self.to_float(a.get('phys_complete_pct', '0')) < 100
        ]
        checks.append(self.make_check(
            'IND-404', 'Actual Finish Without 100%',
            'Finished activities should be 100% complete',
            len(finish_no_100), total, 0, 'Industry', 'high', 'Progress',
            'Set physical % to 100 when actual finish is recorded.',
            finish_no_100
        ))

        return {'name': 'Progress Transparency', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 5. OPTIMIZATION
    # ═══════════════════════════════════════════════════════
    def _schedule_optimization(self):
        checks = []
        total_inc = len(self.incomplete) or 1

        constrained = [a for a in self.incomplete if self.has_hard_constraint(a)]
        checks.append(self.make_check(
            'IND-501', 'Hard-Constrained Activities',
            'Hard constraints override CPM optimization',
            len(constrained), total_inc, 5, 'Industry', 'medium', 'Optimization',
            'Minimize MSO/MEO/Mandatory constraints for better CPM analysis.',
            constrained
        ))

        # True duplicates: same pred, succ, AND type (ladder SS+FF is OK)
        rel_tuples = [
            (str(r.get('pred_task_id', '')), str(r.get('task_id', '')), r.get('pred_type', ''))
            for r in self.relationships
        ]
        dup_rels = len(rel_tuples) - len(set(rel_tuples))
        checks.append(self.make_metric(
            'IND-502', 'Duplicate Relationships',
            f'{dup_rels} exact duplicate ties (same pred/succ/type)',
            dup_rels, 'Industry', 'Optimization',
            threshold_max=0, severity='low',
            recommendation='Remove duplicate identical relationships. SS+FF ladder pairs are not duplicates.'
        ))

        floats = [a.get('total_float_days', 0) for a in self.incomplete]
        if floats:
            avg = statistics.mean(floats)
            checks.append(self.make_metric(
                'IND-503', 'Average Float',
                f'{avg:.1f} days',
                avg, 'Industry', 'Optimization',
                threshold_min=5, threshold_max=60, severity='low', info_only=True,
                recommendation='Balance schedule pressure vs contingency.'
            ))

        alap = [
            a for a in self.incomplete
            if a.get('cstr_type') == 'CS_ALAP' or a.get('cstr_type2') == 'CS_ALAP'
        ]
        checks.append(self.make_check(
            'IND-504', 'ALAP Constraints',
            'ALAP consumes float and can hide risk',
            len(alap), total_inc, 2, 'Industry', 'medium', 'Optimization',
            'Minimize ALAP usage.',
            alap
        ))

        crit_inc = [a for a in self.incomplete if a.get('is_critical')]
        cp_pct = len(crit_inc) / total_inc * 100
        checks.append(self.make_metric(
            'IND-505', 'Critical Path % (Incomplete)',
            f'{cp_pct:.1f}%',
            cp_pct, 'Industry', 'Optimization',
            threshold_min=5, threshold_max=30, severity='medium',
            recommendation='Very high critical density often indicates over-constrained or poorly linked networks.'
        ))

        return {'name': 'Optimization Opportunities', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 6. MAINTAINABILITY
    # ═══════════════════════════════════════════════════════
    def _maintainability(self):
        checks = []
        total = len(self.activities) or 1

        no_name = [a for a in self.activities if not str(a.get('task_name', '')).strip()]
        checks.append(self.make_check(
            'IND-601', 'Missing Names',
            'All activities need clear names',
            len(no_name), total, 0, 'Industry', 'critical', 'Maintainability',
            'Name every activity clearly.',
            no_name
        ))

        id_lengths = [len(a.get('task_code', '')) for a in self.activities if a.get('task_code')]
        if id_lengths:
            unique = len(set(id_lengths))
            checks.append(self.make_metric(
                'IND-602', 'ID Format Consistency',
                f'{unique} different lengths',
                unique, 'Industry', 'Maintainability',
                threshold_max=3, severity='low',
                recommendation='Use consistent activity ID format.'
            ))

        max_depth = self._wbs_max_depth()
        checks.append(self.make_metric(
            'IND-603', 'WBS Depth',
            f'{max_depth} levels (parent hierarchy)',
            max_depth, 'Industry', 'Maintainability',
            threshold_max=8, severity='low',
            recommendation='WBS deeper than 8 levels is often overly complex.'
        ))

        name_counts = Counter(
            str(a.get('task_name', '')).strip()
            for a in self.activities if str(a.get('task_name', '')).strip()
        )
        dup_names = {n for n, c in name_counts.items() if c > 1}
        dup_acts = [a for a in self.activities if str(a.get('task_name', '')).strip() in dup_names]
        checks.append(self.make_check(
            'IND-604', 'Duplicate Activity Names',
            'Names should be unique where practical',
            len(dup_acts), total, 5, 'Industry', 'low', 'Maintainability',
            'Add distinguishing context to duplicate names.',
            dup_acts
        ))

        code_counts = Counter(
            a.get('task_code', '') for a in self.activities if a.get('task_code')
        )
        dup_codes = {c for c, n in code_counts.items() if n > 1}
        dup_code_acts = [a for a in self.activities if a.get('task_code') in dup_codes]
        checks.append(self.make_check(
            'IND-605', 'Duplicate Activity IDs',
            'Activity IDs should be unique',
            len(dup_code_acts), total, 0, 'Industry', 'critical', 'Maintainability',
            'Fix duplicate IDs (or separate multi-project exports).',
            dup_code_acts
        ))

        return {'name': 'Maintainability', 'checks': checks}
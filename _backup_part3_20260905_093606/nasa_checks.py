"""
NASA NPR 7120.5 SCHEDULE MANAGEMENT
====================================
"""

from health_standards.base_checker import BaseChecker
from collections import Counter, defaultdict
from datetime import datetime
import statistics


class NASAChecks(BaseChecker):
    """NASA schedule management check suite."""

    def run_checks(self):
        return {
            'name': 'NASA NPR 7120.5 & Handbook',
            'description': 'NASA program and project management schedule requirements',
            'categories': [
                self._schedule_structure(),
                self._logic_integrity(),
                self._duration_analysis(),
                self._milestone_management(),
                self._critical_path_analysis(),
                self._risk_maturity(),
            ]
        }

    def _wbs_maps(self):
        by_id = {str(w.get('wbs_id', '')): w for w in self.wbs_nodes if w.get('wbs_id')}

        def parent_of(w):
            for k in ('parent_wbs_id', 'parent_id', 'parent_wbs', 'wbs_parent_id'):
                v = w.get(k, '')
                if v not in (None, '', '0', 0):
                    return str(v)
            return ''

        children = defaultdict(list)
        for wid, w in by_id.items():
            p = parent_of(w)
            if p:
                children[p].append(wid)

        acts_by_wbs = defaultdict(list)
        for a in self.activities:
            wid = str(a.get('wbs_id', '') or '')
            if wid:
                acts_by_wbs[wid].append(a)

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

        leaf_ids = [wid for wid in by_id if not children.get(wid)]
        leaves_with_acts = [wid for wid in leaf_ids if acts_by_wbs.get(wid)]
        max_depth = max((depth(wid) for wid in by_id), default=0)

        return {
            'by_id': by_id,
            'children': children,
            'acts_by_wbs': acts_by_wbs,
            'leaf_ids': leaf_ids,
            'leaves_with_acts': leaves_with_acts,
            'max_depth': max_depth,
        }

    def _schedule_structure(self):
        checks = []
        total = len(self.activities) or 1
        wbs = self._wbs_maps()

        checks.append(self.make_metric(
            'NASA-101', 'IMS Activity Count',
            f'{len(self.activities)} activities',
            len(self.activities), 'NASA', 'Structure',
            threshold_min=100, severity='low', info_only=True,
            recommendation='IMS should contain sufficient detail for management.'
        ))

        leaf_total = len(wbs['leaf_ids']) or 1
        leaf_covered = len(wbs['leaves_with_acts'])
        coverage = leaf_covered / leaf_total * 100
        checks.append(self.make_metric(
            'NASA-102', 'Leaf WBS Coverage',
            f'{coverage:.1f}% of leaf WBS nodes have activities ({leaf_covered}/{leaf_total})',
            coverage, 'NASA', 'Structure',
            threshold_min=80, severity='medium',
            recommendation='Ensure leaf WBS elements map to planned work (parent headers may be empty).'
        ))

        no_name = [a for a in self.activities if not str(a.get('task_name', '')).strip()]
        checks.append(self.make_check(
            'NASA-103', 'Missing Activity Names',
            'All activities must have descriptive names',
            len(no_name), total, 0, 'NASA', 'critical', 'Structure',
            'Add descriptive names to all activities.',
            no_name
        ))

        short_names = [
            a for a in self.activities
            if 0 < len(str(a.get('task_name', '')).strip()) < 10
        ]
        checks.append(self.make_check(
            'NASA-104', 'Very Short Activity Names (<10 chars)',
            'NASA recommends descriptive verb-based names',
            len(short_names), total, 3, 'NASA', 'medium', 'Structure',
            'Use verb-based descriptive names (e.g., "Design Panel", "Test Interface").',
            short_names
        ))

        name_counts = Counter(
            str(a.get('task_name', '')).strip()
            for a in self.activities if str(a.get('task_name', '')).strip()
        )
        dup_names = {n for n, c in name_counts.items() if c > 1}
        dup_acts = [a for a in self.activities if str(a.get('task_name', '')).strip() in dup_names]
        checks.append(self.make_check(
            'NASA-105', 'Duplicate Activity Names',
            'Activity names should be unique for clarity',
            len(dup_acts), total, 5, 'NASA', 'medium', 'Structure',
            'Add distinguishing context to duplicate names.',
            dup_acts
        ))

        id_lengths = [len(a.get('task_code', '')) for a in self.activities if a.get('task_code')]
        unique_lengths = len(set(id_lengths)) if id_lengths else 0
        checks.append(self.make_metric(
            'NASA-106', 'Activity ID Format Consistency',
            f'{unique_lengths} different ID lengths',
            unique_lengths, 'NASA', 'Structure',
            threshold_max=3, severity='low',
            recommendation='Use consistent ID formatting across all activities.'
        ))

        checks.append(self.make_metric(
            'NASA-107', 'Maximum WBS Depth',
            f'{wbs["max_depth"]} levels (parent hierarchy)',
            wbs['max_depth'], 'NASA', 'Structure',
            threshold_min=2, threshold_max=8, severity='low', info_only=True
        ))

        return {'name': 'Schedule Structure', 'checks': checks}

    def _logic_integrity(self):
        checks = []
        total = len(self.incomplete) or 1
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1
        dens_denom = len(self.real_activities) or 1

        density = len(self.relationships) / dens_denom
        checks.append(self.make_metric(
            'NASA-201', 'Logic Density',
            f'{density:.2f} relationships per real activity',
            density, 'NASA', 'Logic',
            threshold_min=1.5, threshold_max=3.5, severity='medium',
            recommendation='NASA guideline: roughly 1.5-3.5 relationships per activity.'
        ))

        open_start = self.open_start_activities()
        open_end = self.open_end_activities()

        checks.append(self.make_check(
            'NASA-202', 'Open Start Activities',
            'Incomplete non-milestone activities without predecessors',
            len(open_start), total, 1, 'NASA', 'high', 'Logic',
            'Add predecessors to eliminate dangling activities.',
            open_start
        ))

        checks.append(self.make_check(
            'NASA-203', 'Open End Activities',
            'Incomplete non-milestone activities without successors',
            len(open_end), total, 1, 'NASA', 'high', 'Logic',
            'Add successors to eliminate dangling activities.',
            open_end
        ))

        fs_rels = [r for r in active_rels if r.get('pred_type') == 'PR_FS']
        fs_pct = len(fs_rels) / rel_total * 100
        checks.append(self.make_metric(
            'NASA-204', 'Finish-to-Start Percentage',
            f'{fs_pct:.1f}% are FS (active logic)',
            fs_pct, 'NASA', 'Logic',
            threshold_min=85, severity='medium',
            recommendation='NASA prefers 85%+ FS relationships.'
        ))

        cross_wbs = 0
        for r in active_rels:
            pred = self.engine.activity_by_id.get(str(r.get('pred_task_id', '')), {})
            succ = self.engine.activity_by_id.get(str(r.get('task_id', '')), {})
            if pred.get('wbs_id') and succ.get('wbs_id') and pred.get('wbs_id') != succ.get('wbs_id'):
                cross_wbs += 1
        cross_pct = cross_wbs / rel_total * 100
        checks.append(self.make_metric(
            'NASA-205', 'Cross-WBS Relationships',
            f'{cross_pct:.1f}% of active ties cross WBS boundaries',
            cross_pct, 'NASA', 'Logic',
            severity='low', info_only=True,
            recommendation='Cross-WBS logic is normal but should be reviewed for interfaces.'
        ))

        checks.append(self.make_metric(
            'NASA-206', 'Total Relationships',
            f'{len(self.relationships)} logic ties',
            len(self.relationships), 'NASA', 'Logic',
            severity='low', info_only=True
        ))

        too_many_preds = [
            a for a in self.incomplete
            if len(self.engine.predecessors.get(str(a.get('task_id', '')), [])) > 10
        ]
        checks.append(self.make_check(
            'NASA-207', 'Activities with >10 Predecessors',
            'Complex fan-in may need decomposition',
            len(too_many_preds), total, 3, 'NASA', 'low', 'Logic',
            'Consider summary milestones to reduce complexity.',
            too_many_preds
        ))

        too_many_succs = [
            a for a in self.incomplete
            if len(self.engine.successors.get(str(a.get('task_id', '')), [])) > 10
        ]
        checks.append(self.make_check(
            'NASA-208', 'Activities with >10 Successors',
            'High fan-out = risk concentration',
            len(too_many_succs), total, 3, 'NASA', 'low', 'Logic',
            'Review activities driving many successors.',
            too_many_succs
        ))

        fs_lag = self.fs_with_lag()
        checks.append(self.make_check(
            'NASA-FS-LAG', 'FS + Lag Relationships',
            'NASA guidance discourages FS with lag',
            len(fs_lag), rel_total, 3, 'NASA', 'medium', 'Logic',
            'Replace lag with a schedule activity for transparency.',
            fs_lag
        ))

        leads = [r for r in active_rels if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'NASA-209', 'Negative Lags (Leads)',
            'Leads distort network logic',
            len(leads), rel_total, 0, 'NASA', 'high', 'Logic',
            'Remove negative lags.',
            leads
        ))

        return {'name': 'Logic & Network Integrity', 'checks': checks}

    def _duration_analysis(self):
        checks = []
        total = len(self.incomplete) or 1

        durations = [
            a.get('original_duration_days', 0) for a in self.real_activities
            if a.get('original_duration_days', 0) > 0
        ]

        if durations:
            mean_dur = statistics.mean(durations)
            median_dur = statistics.median(durations)
            checks.append(self.make_metric(
                'NASA-301', 'Average Duration',
                f'{mean_dur:.1f} days',
                mean_dur, 'NASA', 'Duration',
                threshold_min=1, threshold_max=30, severity='low', info_only=True,
                recommendation='NASA typical: 5-20 days average.'
            ))
            checks.append(self.make_metric(
                'NASA-302', 'Median Duration',
                f'{median_dur:.1f} days',
                median_dur, 'NASA', 'Duration',
                threshold_min=1, threshold_max=25, severity='low', info_only=True
            ))
            if len(durations) > 1:
                checks.append(self.make_metric(
                    'NASA-303', 'Duration Std Deviation',
                    f'{statistics.stdev(durations):.1f} days',
                    statistics.stdev(durations), 'NASA', 'Duration',
                    severity='low', info_only=True
                ))

        very_short = [
            a for a in self.incomplete
            if 0 < a.get('original_duration_days', 0) < 2 and not self.is_milestone(a)
        ]
        checks.append(self.make_check(
            'NASA-304', 'Very Short Activities (<2 days)',
            'May need consolidation',
            len(very_short), total, 5, 'NASA', 'low', 'Duration',
            'Consider consolidating micro-activities.',
            very_short
        ))

        excessive = [
            a for a in self.incomplete
            if a.get('original_duration_days', 0) > 88
            and not self.is_milestone(a)
            and a.get('task_type') != 'TT_LOE'
        ]
        checks.append(self.make_check(
            'NASA-305', 'Excessive Duration (>88 days)',
            'NASA handbook-aligned max ~88-day detailed activities',
            len(excessive), total, 2, 'NASA', 'medium', 'Duration',
            'Break down activities over 88 days.',
            excessive
        ))

        return {'name': 'Duration Analysis', 'checks': checks}

    def _milestone_management(self):
        checks = []
        total = len(self.activities) or 1
        mile_total = max(len(self.milestones), 1)

        mile_pct = len(self.milestones) / total * 100 if total else 0
        checks.append(self.make_metric(
            'NASA-401', 'Milestone Percentage',
            f'{mile_pct:.1f}% are milestones',
            mile_pct, 'NASA', 'Milestones',
            threshold_min=3, threshold_max=15, severity='medium',
            recommendation='NASA guideline: roughly 3-15% milestones.'
        ))

        mile_with_dur = [
            a for a in self.milestones
            if a.get('original_duration_days', 0) > 0
        ]
        checks.append(self.make_check(
            'NASA-402', 'Milestones with Duration',
            'Milestones must have zero duration',
            len(mile_with_dur), mile_total, 0, 'NASA', 'critical', 'Milestones',
            'Set milestone durations to zero.',
            mile_with_dur
        ))

        finish_miles = [
            a for a in self.milestones
            if a.get('task_type') == 'TT_FinMile'
            or (
                a.get('task_type') == 'TT_Mile'
                and str(a.get('task_id', '')) not in self.engine.successors
                and a.get('status_code') != 'TK_Complete'
            )
        ]
        mile_no_pred = [
            a for a in finish_miles
            if str(a.get('task_id', '')) not in self.engine.predecessors
        ]
        checks.append(self.make_check(
            'NASA-403', 'Finish Milestones Without Predecessors',
            'Finish milestones must have predecessors',
            len(mile_no_pred), max(len(finish_miles), 1), 0, 'NASA', 'high', 'Milestones',
            'Add predecessors to finish milestones.',
            mile_no_pred
        ))

        checks.append(self.make_metric(
            'NASA-404', 'Total Milestones',
            f'{len(self.milestones)} milestones',
            len(self.milestones), 'NASA', 'Milestones',
            threshold_min=5, severity='medium',
            recommendation='NASA projects typically need multiple key milestones.'
        ))

        return {'name': 'Milestone Management', 'checks': checks}

    def _critical_path_analysis(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        crit_inc = [a for a in self.incomplete if a.get('is_critical')]
        cp_count = len(crit_inc)
        cp_pct = cp_count / total_inc * 100

        checks.append(self.make_metric(
            'NASA-501', 'Critical Path % (Incomplete)',
            f'{cp_count} activities ({cp_pct:.1f}% of incomplete)',
            cp_pct, 'NASA', 'Critical Path',
            threshold_min=5, threshold_max=25, severity='medium',
            recommendation='NASA guideline: CP roughly 5-25% of remaining activities.'
        ))

        checks.append(self.make_boolean(
            'NASA-502', 'Critical Path Exists',
            'Schedule must have a critical path on remaining work',
            cp_count > 0, 'NASA', 'Critical Path',
            severity='critical',
            recommendation='Must have valid CPM critical path.'
        ))

        continuity = self._cp_continuity()
        checks.append(self.make_metric(
            'NASA-502b', 'Critical Path Continuity',
            'Fraction of critical acts linked to other critical acts',
            continuity, 'NASA', 'Critical Path',
            threshold_min=0.85, severity='high',
            recommendation='Critical path should form a continuous chain to project finish.'
        ))

        near = [a for a in self.incomplete if 0 < a.get('total_float_days', 0) <= 5]
        near_pct = len(near) / total_inc * 100
        checks.append(self.make_metric(
            'NASA-503', 'Near-Critical (<5 days float)',
            f'{near_pct:.1f}% near-critical',
            near_pct, 'NASA', 'Critical Path',
            threshold_max=15, severity='medium',
            recommendation='High near-critical percentage = high schedule risk.'
        ))

        floats = [a.get('total_float_days', 0) for a in self.incomplete]
        if floats:
            checks.append(self.make_metric(
                'NASA-504', 'Float Range (max)',
                f'{min(floats):.0f} to {max(floats):.0f} days',
                max(floats), 'NASA', 'Critical Path',
                threshold_max=200, severity='low', info_only=True
            ))

        return {'name': 'Critical Path Analysis', 'checks': checks}

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

    def _risk_maturity(self):
        checks = []
        total = len(self.activities) or 1

        if self.data_date:
            age = (datetime.now() - self.data_date).days
            checks.append(self.make_metric(
                'NASA-601', 'Data Date Age',
                f'{age} days old',
                age, 'NASA', 'Maturity',
                threshold_max=30, severity='medium',
                info_only=(age > 365),
                recommendation='Data date should be updated regularly (≤30 days) for live projects.'
            ))

        complete_pct = len(self.completed) / total * 100 if total else 0
        checks.append(self.make_metric(
            'NASA-602', 'Overall Completion (activity count)',
            f'{complete_pct:.1f}% complete',
            complete_pct, 'NASA', 'Maturity',
            severity='low', info_only=True
        ))

        checks.append(self.make_metric(
            'NASA-603', 'Active Activities',
            f'{len(self.in_progress)} in progress',
            len(self.in_progress), 'NASA', 'Maturity',
            severity='low', info_only=True
        ))

        ns_pct = len(self.not_started) / total * 100 if total else 0
        checks.append(self.make_metric(
            'NASA-604', 'Not Started Percentage',
            f'{ns_pct:.1f}%',
            ns_pct, 'NASA', 'Maturity',
            severity='low', info_only=True
        ))

        pool = self.real_activities
        pool_n = len(pool) or 1
        with_bl = sum(1 for a in pool if a.get('target_start_date', ''))
        bl_pct = with_bl / pool_n * 100
        checks.append(self.make_metric(
            'NASA-605', 'Target/Planned Date Coverage',
            f'{bl_pct:.1f}% have target start (baseline proxy)',
            bl_pct, 'NASA', 'Maturity',
            threshold_min=100, severity='high',
            recommendation='All discrete activities should have planned/target dates; true PMB may be a separate baseline.'
        ))

        hard = [a for a in self.incomplete if self.has_hard_constraint(a)]
        checks.append(self.make_check(
            'NASA-606', 'Hard Constraints',
            'Hard constraints override CPM',
            len(hard), len(self.incomplete) or 1, 5, 'NASA', 'high', 'Maturity',
            'Minimize MSO/MEO/Mandatory constraints.',
            hard
        ))

        return {'name': 'Schedule Maturity & Risk', 'checks': checks}

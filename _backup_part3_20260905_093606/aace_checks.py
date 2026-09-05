"""
AACE INTERNATIONAL SCHEDULE PRACTICES
======================================
"""

from health_standards.base_checker import BaseChecker
from collections import Counter, defaultdict
import statistics


class AACEChecks(BaseChecker):
    """AACE International check suite."""

    def run_checks(self):
        return {
            'name': 'AACE International RPs',
            'description': 'AACE International Recommended Practices for scheduling',
            'categories': [
                self._activity_definition(),
                self._duration_estimation(),
                self._logic_relationships(),
                self._resource_loading(),
                self._forensic_readiness(),
                self._schedule_level_detail(),
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

        max_depth = max((depth(wid) for wid in by_id), default=0)
        return max_depth

    def _activity_definition(self):
        checks = []
        total = len(self.activities) or 1
        
        checks.append(self.make_metric(
            'AACE-101', 'Discrete Activity Count',
            f'{len(self.real_activities)} discrete activities',
            len(self.real_activities), 'AACE', 'Activity Definition',
            threshold_min=10, severity='low', info_only=True
        ))
        
        loe = sum(1 for a in self.activities if a.get('task_type') == 'TT_LOE')
        loe_pct = loe / total * 100
        checks.append(self.make_metric(
            'AACE-102', 'LOE Percentage',
            f'{loe_pct:.1f}% LOE',
            loe_pct, 'AACE', 'Activity Definition',
            threshold_max=10, severity='medium',
            recommendation='AACE recommends LOE < 10% of activities.'
        ))
        
        generic_names = {'TASK', 'WORK', 'ACTIVITY', 'ITEM', 'TEST', 'DO', 'COMPLETE', 'NEW TASK'}
        generic = [
            a for a in self.activities 
            if str(a.get('task_name', '')).strip().upper() in generic_names
        ]
        checks.append(self.make_check(
            'AACE-103', 'Generic Activity Names',
            'Names should be specific and meaningful',
            len(generic), total, 1, 'AACE', 'low', 'Activity Definition',
            'Use descriptive, action-oriented names.',
            generic
        ))
        
        start_mile = sum(1 for a in self.activities if a.get('task_type') == 'TT_Mile')
        finish_mile = sum(1 for a in self.activities if a.get('task_type') == 'TT_FinMile')
        checks.append(self.make_metric(
            'AACE-104', 'Start vs Finish Milestones',
            f'{start_mile} start, {finish_mile} finish',
            start_mile + finish_mile, 'AACE', 'Activity Definition',
            severity='low', info_only=True
        ))
        
        return {'name': 'Activity Definition (RP 32R-04)', 'checks': checks}

    def _duration_estimation(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        
        durations = [
            a.get('original_duration_days', 0) for a in self.real_activities 
            if a.get('original_duration_days', 0) > 0
        ]
        
        if durations:
            avg = statistics.mean(durations)
            median = statistics.median(durations)
            
            checks.append(self.make_metric(
                'AACE-201', 'Average Duration',
                f'{avg:.1f} days',
                avg, 'AACE', 'Duration Estimation',
                threshold_min=1, threshold_max=20, severity='low', info_only=True,
                recommendation='AACE typical: 5-15 days average.'
            ))
            
            checks.append(self.make_metric(
                'AACE-202', 'Median Duration',
                f'{median:.1f} days',
                median, 'AACE', 'Duration Estimation',
                threshold_min=1, threshold_max=20, severity='low', info_only=True
            ))
        
        if durations:
            v_short = sum(1 for d in durations if d < 1)
            short = sum(1 for d in durations if 1 <= d < 5)
            med = sum(1 for d in durations if 5 <= d < 20)
            long_d = sum(1 for d in durations if 20 <= d < 44)
            v_long = sum(1 for d in durations if d >= 44)
            
            checks.append(self.make_metric(
                'AACE-203', 'Duration Distribution',
                f'{v_short} <1d | {short} 1-5d | {med} 5-20d | {long_d} 20-44d | {v_long} ≥44d',
                len(durations), 'AACE', 'Duration Estimation',
                severity='low', info_only=True
            ))
        
        long_acts = [
            a for a in self.incomplete 
            if a.get('original_duration_days', 0) > 44
            and not self.is_milestone(a) and a.get('task_type') != 'TT_LOE'
        ]
        checks.append(self.make_check(
            'AACE-204', 'Activities Over AACE Max (44 days)',
            'Break down activities per AACE guidance',
            len(long_acts), total_inc, 5, 'AACE', 'medium', 'Duration Estimation',
            'Decompose activities exceeding 44-day threshold.',
            long_acts
        ))
        
        round_5 = sum(1 for d in durations if d > 0 and d % 5 == 0)
        round_pct = round_5 / len(durations) * 100 if durations else 0
        checks.append(self.make_metric(
            'AACE-205', 'Round Durations (multiples of 5)',
            f'{round_pct:.1f}%',
            round_pct, 'AACE', 'Duration Estimation',
            severity='low', info_only=True,
            recommendation='High round percentage may indicate rough estimation.'
        ))
        
        return {'name': 'Duration Estimation (RP 32R-04)', 'checks': checks}

    def _logic_relationships(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1
        
        type_counts = Counter(r.get('pred_type', '') for r in active_rels)
        fs = type_counts.get('PR_FS', 0)
        fs_pct = fs / rel_total * 100
        
        checks.append(self.make_metric(
            'AACE-301', 'FS Percentage',
            f'{fs_pct:.1f}% (active logic)',
            fs_pct, 'AACE', 'Logic',
            threshold_min=80, severity='medium',
            recommendation='AACE recommends 80%+ FS relationships.'
        ))
        
        ss_pairs = set((str(r.get('pred_task_id')), str(r.get('task_id'))) 
                      for r in active_rels if r.get('pred_type') == 'PR_SS')
        ff_pairs = set((str(r.get('pred_task_id')), str(r.get('task_id'))) 
                      for r in active_rels if r.get('pred_type') == 'PR_FF')
        ladder = ss_pairs & ff_pairs
        
        checks.append(self.make_metric(
            'AACE-302', 'Ladder Logic Pairs (SS+FF)',
            f'{len(ladder)} active pairs',
            len(ladder), 'AACE', 'Logic',
            severity='low', info_only=True,
            recommendation='Ladder logic is acceptable for overlapping activities.'
        ))
        
        lags = [r.get('lag_days', 0) for r in active_rels if r.get('lag_days', 0) != 0]
        if lags:
            avg_lag = statistics.mean([abs(l) for l in lags])
            checks.append(self.make_metric(
                'AACE-303', 'Average Lag Magnitude',
                f'{avg_lag:.1f} days',
                avg_lag, 'AACE', 'Logic',
                threshold_max=10, severity='medium',
                recommendation='High avg lag indicates over-reliance on lags.'
            ))
        
        sf_rels = [r for r in active_rels if r.get('pred_type') == 'PR_SF']
        checks.append(self.make_check(
            'AACE-304', 'SF Relationships',
            'Start-to-Finish rarely correct',
            len(sf_rels), rel_total, 0, 'AACE', 'high', 'Logic',
            'Verify each SF relationship - usually a mistake.',
            sf_rels
        ))
        
        open_start = self.open_start_activities()
        open_end = self.open_end_activities()
        
        checks.append(self.make_check(
            'AACE-OPEN-01', 'Open Start Activities',
            'Incomplete non-milestone activities without predecessors',
            len(open_start), total_inc, 1, 'AACE', 'high', 'Logic',
            'AACE requires proper logic ties. Only start milestones should have no predecessors.',
            open_start
        ))
        
        checks.append(self.make_check(
            'AACE-OPEN-02', 'Open End Activities',
            'Incomplete non-milestone activities without successors',
            len(open_end), total_inc, 1, 'AACE', 'high', 'Logic',
            'AACE requires closed network. Only finish milestones should have no successors.',
            open_end
        ))
        
        fs_lag = self.fs_with_lag()
        checks.append(self.make_check(
            'AACE-FS-LAG', 'FS + Lag Relationships',
            'AACE discourages FS relationships with lag',
            len(fs_lag), rel_total, 3, 'AACE', 'medium', 'Logic',
            'Replace lag with a schedule activity for transparency (per AACE RP 38R-06).',
            fs_lag
        ))
        
        return {'name': 'Logic Relationships', 'checks': checks}

    def _resource_loading(self):
        checks = []
        
        if not self.resources:
            checks.append(self.make_metric(
                'AACE-400', 'Resource Loading Present',
                'No resource assignments in XER',
                None, 'AACE', 'Resources', info_only=True,
                recommendation='Resource loading enables forensic delay and cost analysis.'
            ))
            return {'name': 'Resource Loading', 'checks': checks}
            
        tasks_with_res = set(str(r.get('task_id')) for r in self.resources)
        work_acts = [
            a for a in self.incomplete 
            if not self.is_milestone(a) and a.get('task_type') != 'TT_LOE'
        ]
        
        no_res = [a for a in work_acts if str(a.get('task_id', '')) not in tasks_with_res]
        no_res_pct = len(no_res) / max(len(work_acts), 1) * 100
        
        checks.append(self.make_metric(
            'AACE-401', 'Unresourced Work %',
            f'{no_res_pct:.1f}%',
            no_res_pct, 'AACE', 'Resources',
            threshold_max=10, severity='medium',
            recommendation='AACE recommends <10% unresourced work.'
        ))
        
        with_cost = sum(1 for r in self.resources if self.to_float(r.get('target_cost', '0')) > 0)
        cost_pct = with_cost / max(len(self.resources), 1) * 100
        checks.append(self.make_metric(
            'AACE-402', 'Costed Resources',
            f'{cost_pct:.1f}%',
            cost_pct, 'AACE', 'Resources',
            threshold_min=90, severity='medium',
            recommendation='Cost loading enables forensic analysis.'
        ))
        
        return {'name': 'Resource Loading', 'checks': checks}

    def _forensic_readiness(self):
        checks = []
        total = len(self.activities) or 1
        
        with_bl = sum(1 for a in self.real_activities if a.get('target_start_date', ''))
        bl_pct = with_bl / max(len(self.real_activities), 1) * 100
        checks.append(self.make_metric(
            'AACE-501', 'Target Date Coverage (Baseline Proxy)',
            f'{bl_pct:.1f}% have target start',
            bl_pct, 'AACE', 'Forensic Readiness',
            threshold_min=100, severity='high',
            recommendation='Complete baseline is critical for forensic delay analysis.'
        ))
        
        with_actuals = sum(
            1 for a in self.activities 
            if a.get('act_start_date', '') or a.get('act_end_date', '')
        )
        actual_pct = with_actuals / total * 100
        checks.append(self.make_metric(
            'AACE-502', 'Activities with Actual Dates',
            f'{actual_pct:.1f}%',
            actual_pct, 'AACE', 'Forensic Readiness',
            severity='low', info_only=True
        ))
        
        checks.append(self.make_boolean(
            'AACE-503', 'Data Date Set',
            'Required for time-slice analysis',
            self.data_date is not None, 'AACE', 'Forensic Readiness',
            severity='high',
            recommendation='Data date required for forensic time-slice analysis.'
        ))
        
        checks.append(self.make_metric(
            'AACE-504', 'Calendar Definitions',
            f'{len(self.calendars)} calendars',
            len(self.calendars), 'AACE', 'Forensic Readiness',
            threshold_min=1, severity='medium',
            recommendation='Calendars needed for accurate CPM analysis.'
        ))
        
        return {'name': 'Forensic Readiness (RP 29R-03)', 'checks': checks}

    def _schedule_level_detail(self):
        checks = []
        
        act_count = len(self.real_activities)
        if act_count < 100:
            level = 'Level 1 (Summary)'
        elif act_count < 500:
            level = 'Level 2 (Summary)'
        elif act_count < 2000:
            level = 'Level 3 (Working)'
        elif act_count < 5000:
            level = 'Level 4 (Detail)'
        else:
            level = 'Level 5 (Highly Detailed)'
        
        checks.append(self.make_metric(
            'AACE-601', 'AACE Schedule Level',
            level,
            act_count, 'AACE', 'Level of Detail',
            severity='low', info_only=True
        ))
        
        max_depth = self._wbs_maps()
        checks.append(self.make_metric(
            'AACE-602', 'WBS Depth',
            f'{max_depth} levels',
            max_depth, 'AACE', 'Level of Detail',
            threshold_min=2, threshold_max=8, severity='medium',
            recommendation='AACE recommends 2-8 WBS levels.'
        ))
        
        wbs_counts = Counter(
            str(a.get('wbs_id', '')) for a in self.activities if a.get('wbs_id')
        )
        if wbs_counts:
            values = list(wbs_counts.values())
            if len(values) > 1:
                mean_val = statistics.mean(values)
                if mean_val > 0:
                    cv = statistics.stdev(values) / mean_val
                    checks.append(self.make_metric(
                        'AACE-603', 'WBS Coefficient of Variation',
                        f'{cv:.2f}',
                        cv, 'AACE', 'Level of Detail',
                        threshold_max=2.0, severity='low',
                        recommendation='High variation (>2.0) indicates inconsistent schedule detail across WBS branches.'
                    ))
        
        return {'name': 'Level of Detail (RP 37R-06)', 'checks': checks}

"""
AACE INTERNATIONAL SCHEDULE PRACTICES
======================================
Enhanced checks based on:
- AACE RP 29R-03 (Forensic Schedule Analysis)
- AACE RP 32R-04 (Determining Activity Durations)
- AACE RP 37R-06 (Schedule Level of Detail)
- AACE RP 38R-06 (Documenting the Schedule Basis)
- Plus: Open Ends and FS+Lag detection
"""

from health_standards.base_checker import BaseChecker
from collections import Counter
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

    def _activity_definition(self):
        """AACE RP 32R-04 activity definition."""
        checks = []
        total = len(self.activities) or 1
        
        # AACE-101: Activity Discreteness
        checks.append(self.make_metric(
            'AACE-101', 'Discrete Activity Count',
            f'{len(self.real_activities)} discrete activities',
            len(self.real_activities), 'AACE', 'Activity Definition',
            threshold_min=10, severity='low',
            info_only=True
        ))
        
        # AACE-102: LOE Percentage
        loe = sum(1 for a in self.activities if a.get('task_type') == 'TT_LOE')
        loe_pct = loe / total * 100
        checks.append(self.make_metric(
            'AACE-102', 'LOE Percentage',
            f'{loe_pct:.1f}% LOE',
            loe_pct, 'AACE', 'Activity Definition',
            threshold_max=10, severity='medium',
            recommendation='AACE recommends LOE < 10% of activities.'
        ))
        
        # AACE-103: Meaningful Activity Names
        generic_names = ['Task', 'Work', 'Activity', 'Item', 'Test', 'Do', 'Complete']
        generic = [a for a in self.activities 
                  if a.get('task_name', '').strip() in generic_names]
        checks.append(self.make_check(
            'AACE-103', 'Generic Activity Names',
            'Names should be specific and meaningful',
            len(generic), total, 1, 'AACE', 'low', 'Activity Definition',
            'Use descriptive, action-oriented names.',
            generic
        ))
        
        # AACE-104: Milestone Types
        start_mile = sum(1 for a in self.activities if a.get('task_type') == 'TT_Mile')
        finish_mile = sum(1 for a in self.activities if a.get('task_type') == 'TT_FinMile')
        checks.append(self.make_metric(
            'AACE-104', 'Start vs Finish Milestones',
            f'{start_mile} start, {finish_mile} finish',
            start_mile + finish_mile, 'AACE', 'Activity Definition',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        return {'name': 'Activity Definition (RP 32R-04)', 'checks': checks}

    def _duration_estimation(self):
        """AACE RP 32R-04 duration estimation."""
        checks = []
        total = len(self.incomplete) or 1
        
        durations = [a.get('original_duration_days', 0) for a in self.real_activities 
                    if a.get('original_duration_days', 0) > 0]
        
        # AACE-201: Duration Statistics
        if durations:
            avg = statistics.mean(durations)
            median = statistics.median(durations)
            
            checks.append(self.make_metric(
                'AACE-201', 'Average Duration',
                f'{avg:.1f} days',
                avg, 'AACE', 'Duration Estimation',
                threshold_min=1, threshold_max=20, severity='low',
                info_only=True,
                recommendation='AACE typical: 5-15 days average.'
            ))
            
            checks.append(self.make_metric(
                'AACE-202', 'Median Duration',
                f'{median:.1f} days',
                median, 'AACE', 'Duration Estimation',
                threshold_min=1, threshold_max=20, severity='low',
                info_only=True
            ))
        
        # AACE-203: Duration Buckets
        very_short = sum(1 for d in durations if d < 1)
        short = sum(1 for d in durations if 1 <= d < 5)
        medium = sum(1 for d in durations if 5 <= d < 20)
        long = sum(1 for d in durations if 20 <= d < 44)
        very_long = sum(1 for d in durations if d >= 44)
        
        checks.append(self.make_metric(
            'AACE-203', 'Duration Distribution',
            f'{very_short} < 1d | {short} 1-5d | {medium} 5-20d | {long} 20-44d | {very_long} >44d',
            len(durations), 'AACE', 'Duration Estimation',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        # AACE-204: AACE Recommended Max (44 days per RP 37R-06 for detailed activities)
        long_acts = [a for a in self.incomplete 
                    if a.get('original_duration_days', 0) > 44
                    and a.get('task_type') not in ['TT_Mile', 'TT_FinMile', 'TT_LOE']]
        checks.append(self.make_check(
            'AACE-204', 'Activities Over AACE Max (44 days)',
            'Break down activities per AACE guidance',
            len(long_acts), total, 5, 'AACE', 'medium', 'Duration Estimation',
            'Decompose activities exceeding 44-day threshold.',
            long_acts
        ))
        
        # AACE-205: Duration Rounding
        round_5 = sum(1 for d in durations if d > 0 and d % 5 == 0)
        round_pct = round_5 / len(durations) * 100 if durations else 0
        checks.append(self.make_metric(
            'AACE-205', 'Round Durations (multiples of 5)',
            f'{round_pct:.1f}%',
            round_pct, 'AACE', 'Duration Estimation',
            threshold_max=None, severity='low',
            info_only=True,
            recommendation='High round percentage may indicate rough estimation.'
        ))
        
        return {'name': 'Duration Estimation (RP 32R-04)', 'checks': checks}

    def _logic_relationships(self):
        """Logic quality per AACE + Open Ends + FS+Lag."""
        checks = []
        total = len(self.real_activities) or 1
        rel_total = len(self.relationships) or 1
        
        # AACE-301: Relationship Type Distribution
        type_counts = Counter(r.get('pred_type', '') for r in self.relationships)
        
        fs = type_counts.get('PR_FS', 0)
        ss = type_counts.get('PR_SS', 0)
        ff = type_counts.get('PR_FF', 0)
        sf = type_counts.get('PR_SF', 0)
        
        fs_pct = fs / rel_total * 100
        checks.append(self.make_metric(
            'AACE-301', 'FS Percentage',
            f'{fs_pct:.1f}%',
            fs_pct, 'AACE', 'Logic',
            threshold_min=80, severity='medium',
            recommendation='AACE recommends 80%+ FS relationships.'
        ))
        
        # AACE-302: SS with matching FF (Ladder Logic)
        ss_pairs = set((r.get('pred_task_id'), r.get('task_id')) 
                      for r in self.relationships if r.get('pred_type') == 'PR_SS')
        ff_pairs = set((r.get('pred_task_id'), r.get('task_id')) 
                      for r in self.relationships if r.get('pred_type') == 'PR_FF')
        ladder = ss_pairs & ff_pairs
        
        checks.append(self.make_metric(
            'AACE-302', 'Ladder Logic Pairs (SS+FF)',
            f'{len(ladder)} pairs',
            len(ladder), 'AACE', 'Logic',
            threshold_min=0, severity='low',
            info_only=True,
            recommendation='Ladder logic is acceptable for overlapping activities.'
        ))
        
        # AACE-303: Lag Analysis
        lags = [r.get('lag_days', 0) for r in self.relationships if r.get('lag_days', 0) != 0]
        if lags:
            avg_lag = statistics.mean([abs(l) for l in lags])
            checks.append(self.make_metric(
                'AACE-303', 'Average Lag Magnitude',
                f'{avg_lag:.1f} days',
                avg_lag, 'AACE', 'Logic',
                threshold_max=10, severity='medium',
                recommendation='High avg lag indicates over-reliance on lags.'
            ))
        
        # AACE-304: SF Relationships (Almost Never Correct)
        sf_rels = [r for r in self.relationships if r.get('pred_type') == 'PR_SF']
        checks.append(self.make_check(
            'AACE-304', 'SF Relationships',
            'Start-to-Finish rarely correct',
            len(sf_rels), rel_total, 0, 'AACE', 'high', 'Logic',
            'Verify each SF relationship - usually a mistake.',
            sf_rels
        ))
        
        # ─── NEW: AACE-OPEN-01: Open Start Activities ───
        open_start = [a for a in self.real_activities
                      if a.get('task_id', '') not in self.engine.predecessors
                      and a.get('task_type') not in ['TT_Mile']]
        checks.append(self.make_check(
            'AACE-OPEN-01', 'Open Start Activities',
            'Non-start-milestone activities without predecessors',
            len(open_start), total, 1, 'AACE', 'high', 'Logic',
            'AACE requires proper logic ties. Only start milestones should have no predecessors.',
            open_start
        ))
        
        # ─── NEW: AACE-OPEN-02: Open End Activities ───
        open_end = [a for a in self.real_activities
                    if a.get('task_id', '') not in self.engine.successors
                    and a.get('task_type') not in ['TT_FinMile']]
        checks.append(self.make_check(
            'AACE-OPEN-02', 'Open End Activities',
            'Non-finish-milestone activities without successors',
            len(open_end), total, 1, 'AACE', 'high', 'Logic',
            'AACE requires closed network. Only finish milestones should have no successors.',
            open_end
        ))
        
        # ─── NEW: AACE-FS-LAG: FS Relationships with Lag ───
        fs_lag = [r for r in self.relationships
                  if r.get('pred_type') == 'PR_FS' and r.get('lag_days', 0) > 0]
        
        seen = set()
        affected = []
        for r in fs_lag:
            sid = r.get('task_id')
            if sid and sid not in seen:
                seen.add(sid)
                a = self.engine.activity_by_id.get(sid)
                if a:
                    affected.append(a)
        
        checks.append(self.make_check(
            'AACE-FS-LAG', 'FS + Lag Relationships',
            'AACE discourages FS relationships with lag',
            len(fs_lag), rel_total, 3, 'AACE', 'medium', 'Logic',
            'Replace lag with a schedule activity for transparency (per AACE RP 38R-06).',
            affected
        ))
        
        return {'name': 'Logic Relationships', 'checks': checks}

    def _resource_loading(self):
        """Resource loading per AACE."""
        checks = []
        
        # AACE-401: Resource Loading Coverage
        tasks_with_res = set(r.get('task_id') for r in self.resources)
        work_acts = [a for a in self.incomplete 
                    if a.get('task_type') not in ['TT_Mile', 'TT_FinMile', 'TT_LOE']]
        
        no_res = [a for a in work_acts if a.get('task_id', '') not in tasks_with_res]
        no_res_pct = len(no_res) / max(len(work_acts), 1) * 100
        
        checks.append(self.make_metric(
            'AACE-401', 'Unresourced Work %',
            f'{no_res_pct:.1f}%',
            no_res_pct, 'AACE', 'Resources',
            threshold_max=10, severity='medium',
            recommendation='AACE recommends <10% unresourced work.'
        ))
        
        # AACE-402: Resource Cost Distribution
        with_cost = sum(1 for r in self.resources 
                       if self.to_float(r.get('target_cost', '0')) > 0)
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
        """AACE RP 29R-03 forensic readiness."""
        checks = []
        total = len(self.activities) or 1
        
        # AACE-501: Baseline for Forensics
        with_bl = sum(1 for a in self.activities if a.get('target_start_date', ''))
        bl_pct = with_bl / total * 100
        checks.append(self.make_metric(
            'AACE-501', 'Baseline for Forensics',
            f'{bl_pct:.1f}% have baseline',
            bl_pct, 'AACE', 'Forensic Readiness',
            threshold_min=100, severity='high',
            recommendation='Complete baseline is critical for forensic analysis.'
        ))
        
        # AACE-502: Actual Dates Documented
        with_actuals = sum(1 for a in self.activities 
                          if a.get('act_start_date', '') or a.get('act_end_date', ''))
        actual_pct = with_actuals / total * 100
        checks.append(self.make_metric(
            'AACE-502', 'Activities with Actual Dates',
            f'{actual_pct:.1f}%',
            actual_pct, 'AACE', 'Forensic Readiness',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        # AACE-503: Data Date Presence
        checks.append(self.make_boolean(
            'AACE-503', 'Data Date Set',
            'Required for time-slice analysis',
            self.data_date is not None, 'AACE', 'Forensic Readiness',
            severity='high',
            recommendation='Data date required for forensic time-slice analysis.'
        ))
        
        # AACE-504: Calendar Definitions
        checks.append(self.make_metric(
            'AACE-504', 'Calendar Definitions',
            f'{len(self.calendars)} calendars',
            len(self.calendars), 'AACE', 'Forensic Readiness',
            threshold_min=1, severity='medium',
            recommendation='Calendars needed for accurate CPM analysis.'
        ))
        
        return {'name': 'Forensic Readiness (RP 29R-03)', 'checks': checks}

    def _schedule_level_detail(self):
        """AACE RP 37R-06 level of detail."""
        checks = []
        
        # AACE-601: Level Determination
        act_count = len(self.activities)
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
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        # AACE-602: WBS Depth for Level
        max_depth = max((w.get('wbs_short_name', '').count('.') for w in self.wbs_nodes), default=0)
        checks.append(self.make_metric(
            'AACE-602', 'WBS Depth',
            f'{max_depth} levels',
            max_depth, 'AACE', 'Level of Detail',
            threshold_min=2, threshold_max=8, severity='medium',
            recommendation='AACE recommends 2-8 WBS levels.'
        ))
        
        # AACE-603: Consistency of Detail
        wbs_activity_counts = Counter(a.get('wbs_id', '') for a in self.activities)
        if wbs_activity_counts:
            values = list(wbs_activity_counts.values())
            if len(values) > 1:
                cv = statistics.stdev(values) / statistics.mean(values)
                checks.append(self.make_metric(
                    'AACE-603', 'WBS Coefficient of Variation',
                    f'{cv:.2f}',
                    cv, 'AACE', 'Level of Detail',
                    threshold_max=2.0, severity='low',
                    recommendation='High variation may indicate inconsistent detail.'
                ))
        
        return {'name': 'Level of Detail (RP 37R-06)', 'checks': checks}
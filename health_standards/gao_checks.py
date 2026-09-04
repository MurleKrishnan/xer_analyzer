"""
GAO SCHEDULE ASSESSMENT GUIDE
==============================
Based on:
- GAO-16-89G Schedule Assessment Guide
- GAO 10 Best Practices for Project Schedules
- Plus: Open Ends, FS+Lag, CP continuity, BP5 date integrity
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

    # ═══════════════════════════════════════════════════════
    # BP1: CAPTURING ALL WORK
    # ═══════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════
    # BP2: SEQUENCING
    # ═══════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════
    # BP3: RESOURCES
    # ═══════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════
    # BP4: DURATIONS
    # ═══════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════
    # BP5: SCHEDULE VERIFIED (integrity + light integration)
    # ═══════════════════════════════════════════════════════
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

        # Vertical integration heuristic: WBS summary EF before max child EF
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
        """
        Flag WBS nodes whose rolled child EF is later than any TT_WBS task
        sitting on that WBS (when present). Lightweight proxy for BP5 vertical integration.
        """
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

    # ═══════════════════════════════════════════════════════
    # BP6: CRITICAL PATH TRACED
    # ═══════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════
    # BP7: FLOAT
    # ═══════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════
    # BP8: BASELINE (target dates proxy)
    # ═══════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════
    # BP9: UPDATES MAINTAINED
    # ═══════════════════════════════════════════════════════
    def _bp9_updates_maintained(self):
        checks = []
        total = len(self.activities) or 1

        if self.data_date:
            # Prefer ERMHDR export date if engine stored it; else wall clock
            ref = datetime.now()
            age = (ref - self.data_date).days
            # Stale demo XERs: do not hard-fail ancient snapshots
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

    # ═══════════════════════════════════════════════════════
    # BP10: RISK INDICATORS (deterministic proxies)
    # ═══════════════════════════════════════════════════════
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

        # Risk concentration: remaining duration on near-critical
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
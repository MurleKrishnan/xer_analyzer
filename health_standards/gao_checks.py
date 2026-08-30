"""
GAO SCHEDULE ASSESSMENT GUIDE
==============================
Enhanced checks based on:
- GAO-16-89G Schedule Assessment Guide
- GAO 10 Best Practices for Project Schedules
- Plus: Open Ends and FS+Lag detection
"""

from health_standards.base_checker import BaseChecker
from collections import Counter
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
        """GAO BP1: All activities captured."""
        checks = []
        total = len(self.activities) or 1
        
        # GAO-101: Activity Existence
        checks.append(self.make_metric(
            'GAO-101', 'Total Activities in Schedule',
            f'{len(self.activities)} activities',
            len(self.activities), 'GAO', 'BP1: Capturing Work',
            threshold_min=1, severity='critical',
            recommendation='Schedule must contain activities.'
        ))
        
        # GAO-102: Activity Names
        no_name = [a for a in self.activities if not a.get('task_name', '').strip()]
        checks.append(self.make_check(
            'GAO-102', 'Missing Activity Names',
            'All activities must be named',
            len(no_name), total, 0, 'GAO', 'critical', 'BP1: Capturing Work',
            'Add names to all activities.',
            no_name
        ))
        
        # GAO-103: WBS Assignment
        no_wbs = [a for a in self.activities if not a.get('wbs_id', '')]
        checks.append(self.make_check(
            'GAO-103', 'Activities Without WBS',
            'All activities must be assigned to WBS',
            len(no_wbs), total, 0, 'GAO', 'high', 'BP1: Capturing Work',
            'Assign activities to appropriate WBS nodes.',
            no_wbs
        ))
        
        # GAO-104: Activity Type Assigned
        no_type = [a for a in self.activities if not a.get('task_type', '')]
        checks.append(self.make_check(
            'GAO-104', 'Missing Activity Types',
            'All activities need type designation',
            len(no_type), total, 0, 'GAO', 'high', 'BP1: Capturing Work',
            'Assign type: Task, Milestone, LOE, etc.'
        ))
        
        return {'name': 'BP1: Capturing All Work', 'checks': checks}

    def _bp2_sequencing_activities(self):
        """GAO BP2: Activities properly sequenced + Open Ends + FS+Lag."""
        checks = []
        total = len(self.real_activities) or 1
        rel_total = len(self.relationships) or 1
        
        # GAO-201: Relationships Exist
        checks.append(self.make_metric(
            'GAO-201', 'Total Relationships',
            f'{len(self.relationships)} logic ties',
            len(self.relationships), 'GAO', 'BP2: Sequencing',
            threshold_min=1, severity='critical',
            recommendation='Schedule must have relationships defined.'
        ))
        
        # ─── GAO-202: Open Start Activities (Enhanced) ───
        missing_pred = [a for a in self.real_activities 
                       if a.get('task_id', '') not in self.engine.predecessors
                       and a.get('task_type') not in ['TT_Mile']]
        checks.append(self.make_check(
            'GAO-202', 'Open Start Activities',
            'Activities without predecessors (except start milestones)',
            len(missing_pred), total, 1, 'GAO', 'high', 'BP2: Sequencing',
            'Add predecessor logic to eliminate dangling starts.',
            missing_pred
        ))
        
        # ─── GAO-203: Open End Activities (Enhanced) ───
        missing_succ = [a for a in self.real_activities 
                       if a.get('task_id', '') not in self.engine.successors
                       and a.get('task_type') not in ['TT_FinMile']]
        checks.append(self.make_check(
            'GAO-203', 'Open End Activities',
            'Activities without successors (except finish milestones)',
            len(missing_succ), total, 1, 'GAO', 'high', 'BP2: Sequencing',
            'Add successor logic to eliminate dangling ends.',
            missing_succ
        ))
        
        # GAO-204: FS Relationship Preference
        fs = [r for r in self.relationships if r.get('pred_type') == 'PR_FS']
        fs_pct = len(fs) / rel_total * 100
        checks.append(self.make_metric(
            'GAO-204', 'FS Relationships %',
            f'{fs_pct:.1f}% are FS',
            fs_pct, 'GAO', 'BP2: Sequencing',
            threshold_min=90, severity='medium',
            recommendation='GAO recommends 90%+ Finish-to-Start.'
        ))
        
        # GAO-205: SF Relationships (should be zero)
        sf = [r for r in self.relationships if r.get('pred_type') == 'PR_SF']
        checks.append(self.make_check(
            'GAO-205', 'Start-to-Finish Relationships',
            'SF relationships should be avoided',
            len(sf), rel_total, 0, 'GAO', 'high', 'BP2: Sequencing',
            'Convert SF to standard FS relationships.',
            sf
        ))
        
        # GAO-206: Negative Lags (Leads)
        leads = [r for r in self.relationships if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'GAO-206', 'Negative Lags (Leads)',
            'No relationships should have leads',
            len(leads), rel_total, 0, 'GAO', 'high', 'BP2: Sequencing',
            'Remove all negative lags.'
        ))
        
        # GAO-207: Excessive Lags
        big_lags = [r for r in self.relationships if r.get('lag_days', 0) > 20]
        checks.append(self.make_check(
            'GAO-207', 'Large Lags (>20 days)',
            'Large lags may hide work',
            len(big_lags), rel_total, 3, 'GAO', 'medium', 'BP2: Sequencing',
            'Consider replacing large lags with activities.'
        ))
        
        # GAO-208: Logic Density
        density = len(self.relationships) / len(self.activities) if self.activities else 0
        checks.append(self.make_metric(
            'GAO-208', 'Logic Density (Rel/Act)',
            f'{density:.2f}',
            density, 'GAO', 'BP2: Sequencing',
            threshold_min=1.5, threshold_max=4.0, severity='medium',
            recommendation='Density 1.5-4.0 indicates healthy network.'
        ))
        
        # ─── NEW: GAO-FS-LAG: FS + Lag Relationships ───
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
            'GAO-FS-LAG', 'FS + Lag Relationships',
            'Finish-to-Start relationships using lag (waiting periods)',
            len(fs_lag), rel_total, 3, 'GAO', 'medium', 'BP2: Sequencing',
            'Use activities instead of lags for waiting periods (transparency).',
            affected
        ))
        
        return {'name': 'BP2: Sequencing Activities', 'checks': checks}

    def _bp3_resources_established(self):
        """GAO BP3: Resources established."""
        checks = []
        total = len(self.incomplete) or 1
        
        tasks_with_res = set(r.get('task_id') for r in self.resources)
        work_acts = [a for a in self.incomplete 
                    if a.get('task_type') not in ['TT_Mile', 'TT_FinMile', 'TT_LOE']]
        
        # GAO-301: Resource Assignment
        no_res = [a for a in work_acts if a.get('task_id', '') not in tasks_with_res]
        checks.append(self.make_check(
            'GAO-301', 'Work Activities Without Resources',
            'GAO best practice: resource-loaded schedules',
            len(no_res), max(len(work_acts), 1), 10, 'GAO', 'medium', 'BP3: Resources',
            'Assign resources to work activities.',
            no_res
        ))
        
        # GAO-302: Cost Assignment
        with_cost = [r for r in self.resources 
                    if self.to_float(r.get('target_cost', '0')) > 0]
        cost_pct = len(with_cost) / max(len(self.resources), 1) * 100
        checks.append(self.make_metric(
            'GAO-302', 'Cost-Loaded Assignments',
            f'{cost_pct:.1f}% have costs',
            cost_pct, 'GAO', 'BP3: Resources',
            threshold_min=80, severity='medium',
            recommendation='Cost-loaded schedules enable EVM.'
        ))
        
        # GAO-303: Resource Types
        role_ids = set(r.get('role_id', '') for r in self.resources if r.get('role_id'))
        checks.append(self.make_metric(
            'GAO-303', 'Unique Resource Roles',
            f'{len(role_ids)} roles used',
            len(role_ids), 'GAO', 'BP3: Resources',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        return {'name': 'BP3: Resources Established', 'checks': checks}

    def _bp4_durations_established(self):
        """GAO BP4: Reasonable durations."""
        checks = []
        total = len(self.incomplete) or 1
        
        # GAO-401: Zero Duration
        zero_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) == 0
                   and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        checks.append(self.make_check(
            'GAO-401', 'Zero Duration Tasks',
            'Only milestones may have zero duration',
            len(zero_dur), total, 1, 'GAO', 'high', 'BP4: Durations',
            'Add duration or convert to milestone.',
            zero_dur
        ))
        
        # GAO-402: Very Long Duration
        long_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) > 44]
        checks.append(self.make_check(
            'GAO-402', 'Long Duration (>44 days)',
            'Break down long-duration activities',
            len(long_dur), total, 5, 'GAO', 'medium', 'BP4: Durations',
            'Decompose long activities for better tracking.',
            long_dur
        ))
        
        # GAO-403: Duration Statistics
        durs = [a.get('original_duration_days', 0) for a in self.real_activities 
               if a.get('original_duration_days', 0) > 0]
        if durs:
            avg = statistics.mean(durs)
            checks.append(self.make_metric(
                'GAO-403', 'Average Activity Duration',
                f'{avg:.1f} days',
                avg, 'GAO', 'BP4: Durations',
                threshold_min=1, threshold_max=30, severity='low',
                info_only=True
            ))
        
        # GAO-404: Duration Consistency
        if durs and len(durs) > 1:
            stdev = statistics.stdev(durs)
            checks.append(self.make_metric(
                'GAO-404', 'Duration Standard Deviation',
                f'{stdev:.1f} days',
                stdev, 'GAO', 'BP4: Durations',
                threshold_max=None, severity='low',
                info_only=True
            ))
        
        return {'name': 'BP4: Realistic Durations', 'checks': checks}

    def _bp5_schedule_verified(self):
        """GAO BP5: Schedule verified."""
        checks = []
        total = len(self.activities) or 1
        
        # GAO-501: Data Date Set
        checks.append(self.make_boolean(
            'GAO-501', 'Data Date Established',
            'Schedule must have data date',
            self.data_date is not None, 'GAO', 'BP5: Verification',
            severity='critical',
            recommendation='Set data date for progress tracking.'
        ))
        
        # GAO-502: Invalid Dates
        invalid = []
        for a in self.activities:
            if a.get('status_code') == 'TK_NotStart' and a.get('act_start_date', ''):
                invalid.append(a)
        
        checks.append(self.make_check(
            'GAO-502', 'Invalid Date Combinations',
            'Actual dates on unstarted tasks',
            len(invalid), total, 0, 'GAO', 'critical', 'BP5: Verification',
            'Fix invalid date combinations.',
            invalid
        ))
        
        # GAO-503: Finish Before Start
        rev_dates = []
        for a in self.activities:
            s = a.get('early_start_date_parsed')
            e = a.get('early_end_date_parsed')
            if s and e and e < s:
                rev_dates.append(a)
        
        checks.append(self.make_check(
            'GAO-503', 'Finish Before Start',
            'Finish dates must be after start',
            len(rev_dates), total, 0, 'GAO', 'critical', 'BP5: Verification',
            'Fix inverted dates.',
            rev_dates
        ))
        
        return {'name': 'BP5: Schedule Verified', 'checks': checks}

    def _bp6_critical_path_traced(self):
        """GAO BP6: Critical path traced."""
        checks = []
        
        cp_count = len(self.engine.critical_activities)
        total = len(self.real_activities) or 1
        cp_pct = cp_count / total * 100
        
        # GAO-601: CP Exists
        checks.append(self.make_boolean(
            'GAO-601', 'Critical Path Exists',
            'Schedule must have critical path',
            cp_count > 0, 'GAO', 'BP6: Critical Path',
            severity='critical',
            recommendation='Must have valid critical path.'
        ))
        
        # GAO-602: CP Percentage
        checks.append(self.make_metric(
            'GAO-602', 'Critical Path %',
            f'{cp_pct:.1f}%',
            cp_pct, 'GAO', 'BP6: Critical Path',
            threshold_min=5, threshold_max=25, severity='medium',
            recommendation='GAO guideline: 5-25% critical activities.'
        ))
        
        # GAO-603: Multiple Near-Critical Paths
        near = [a for a in self.incomplete 
               if 0 < a.get('total_float_days', 0) <= 5]
        checks.append(self.make_metric(
            'GAO-603', 'Near-Critical Activities',
            f'{len(near)} within 5 days of CP',
            len(near), 'GAO', 'BP6: Critical Path',
            threshold_max=None, severity='medium',
            info_only=True
        ))
        
        return {'name': 'BP6: Critical Path Traced', 'checks': checks}

    def _bp7_float_analyzed(self):
        """GAO BP7: Reasonable float."""
        checks = []
        total = len(self.incomplete) or 1
        
        # GAO-701: Negative Float
        neg = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'GAO-701', 'Negative Float',
            'Schedule cannot have negative float',
            len(neg), total, 0, 'GAO', 'critical', 'BP7: Float',
            'Address all negative float immediately.',
            neg
        ))
        
        # GAO-702: Excessive Float
        high = [a for a in self.incomplete if a.get('total_float_days', 0) > 44]
        checks.append(self.make_check(
            'GAO-702', 'High Float (>44 days)',
            'Excessive float indicates missing logic',
            len(high), total, 5, 'GAO', 'medium', 'BP7: Float',
            'Investigate high-float activities.',
            high
        ))
        
        # GAO-703: Extreme Float
        extreme = [a for a in self.incomplete if a.get('total_float_days', 0) > 100]
        checks.append(self.make_check(
            'GAO-703', 'Extreme Float (>100 days)',
            'Extreme float almost always = broken logic',
            len(extreme), total, 2, 'GAO', 'high', 'BP7: Float',
            'Fix logic causing extreme float.',
            extreme
        ))
        
        # GAO-704: Float Statistics
        floats = [a.get('total_float_days', 0) for a in self.incomplete]
        if floats:
            median = statistics.median(floats)
            checks.append(self.make_metric(
                'GAO-704', 'Median Float',
                f'{median:.1f} days',
                median, 'GAO', 'BP7: Float',
                threshold_max=None, severity='low',
                info_only=True
            ))
        
        return {'name': 'BP7: Float Analyzed', 'checks': checks}

    def _bp8_baseline_established(self):
        """GAO BP8: Baseline established."""
        checks = []
        total = len(self.activities) or 1
        
        # GAO-801: Baseline Set
        with_bl = sum(1 for a in self.activities if a.get('target_start_date', ''))
        bl_pct = with_bl / total * 100
        checks.append(self.make_metric(
            'GAO-801', 'Baseline Coverage',
            f'{bl_pct:.1f}% have baseline',
            bl_pct, 'GAO', 'BP8: Baseline',
            threshold_min=100, severity='high',
            recommendation='All activities must have baseline dates.'
        ))
        
        # GAO-802: Baseline Finish
        with_bl_end = sum(1 for a in self.activities if a.get('target_end_date', ''))
        end_pct = with_bl_end / total * 100
        checks.append(self.make_metric(
            'GAO-802', 'Baseline Finish Coverage',
            f'{end_pct:.1f}% have BL finish',
            end_pct, 'GAO', 'BP8: Baseline',
            threshold_min=100, severity='high',
            recommendation='All activities need baseline finish dates.'
        ))
        
        return {'name': 'BP8: Baseline Established', 'checks': checks}

    def _bp9_updates_maintained(self):
        """GAO BP9: Schedule maintained."""
        checks = []
        total = len(self.activities) or 1
        
        # GAO-901: Data Date Currency
        if self.data_date:
            from datetime import datetime
            age = (datetime.now() - self.data_date).days
            checks.append(self.make_metric(
                'GAO-901', 'Data Date Age',
                f'{age} days',
                age, 'GAO', 'BP9: Updates',
                threshold_max=30, severity='medium',
                recommendation='Update schedule monthly (data date <30 days).'
            ))
        
        # GAO-902: Progress Consistency
        prog_no_start = [a for a in self.activities
                        if self.to_float(a.get('phys_complete_pct', '0')) > 0
                        and not a.get('act_start_date', '')]
        checks.append(self.make_check(
            'GAO-902', 'Progress Without Actual Start',
            'Update actuals with progress',
            len(prog_no_start), total, 0, 'GAO', 'critical', 'BP9: Updates',
            'Add actual dates for progressed work.',
            prog_no_start
        ))
        
        # GAO-903: 100% Without Actual Finish
        comp_no_end = [a for a in self.activities
                      if self.to_float(a.get('phys_complete_pct', '0')) >= 100
                      and not a.get('act_end_date', '')]
        checks.append(self.make_check(
            'GAO-903', '100% Without Actual Finish',
            'Complete activities need finish dates',
            len(comp_no_end), total, 0, 'GAO', 'critical', 'BP9: Updates',
            'Add actual finish dates.',
            comp_no_end
        ))
        
        return {'name': 'BP9: Updates Maintained', 'checks': checks}

    def _bp10_risk_managed(self):
        """GAO BP10: Risk-adjusted analysis."""
        checks = []
        total = len(self.real_activities) or 1
        
        # GAO-1001: Hard Constraints (Risk Indicator)
        hard = ['CS_MANDSTART', 'CS_MANDFIN', 'CS_ALAP']
        constrained = [a for a in self.incomplete if a.get('cstr_type', '') in hard]
        checks.append(self.make_check(
            'GAO-1001', 'Hard Constraints (Risk)',
            'Hard constraints prevent risk analysis',
            len(constrained), len(self.incomplete) or 1, 2, 'GAO', 'high', 'BP10: Risk',
            'Remove hard constraints for proper CPM.',
            constrained
        ))
        
        # GAO-1002: Milestone Risk (Near-Critical Milestones)
        near_crit_mile = [a for a in self.milestones 
                         if 0 < a.get('total_float_days', 0) <= 10
                         and a.get('status_code') != 'TK_Complete']
        checks.append(self.make_metric(
            'GAO-1002', 'Near-Critical Milestones',
            f'{len(near_crit_mile)} at risk',
            len(near_crit_mile), 'GAO', 'BP10: Risk',
            threshold_max=None, severity='high',
            info_only=True,
            recommendation='Monitor near-critical milestones closely.'
        ))
        
        # GAO-1003: Slippage Indicator (Negative Float)
        neg = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'GAO-1003', 'Slipped Activities (Negative Float)',
            'Indicators of schedule slippage',
            len(neg), len(self.incomplete) or 1, 0, 'GAO', 'critical', 'BP10: Risk',
            'Recovery planning required for negative float.',
            neg
        ))
        
        return {'name': 'BP10: Risk Managed', 'checks': checks}
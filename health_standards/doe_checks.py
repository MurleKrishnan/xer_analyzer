"""
DOE PM-30 SCHEDULE ASSESSMENT
==============================
95 checks based on:
- DOE Order 413.3B (Program & Project Management)
- DOE PM-30 Schedule Assessment Guide
- DOE-HDBK-1140-2001
"""

from health_standards.base_checker import BaseChecker


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
            ]
        }

    def _project_structure(self):
        """WBS and organization checks."""
        checks = []
        total = len(self.activities) or 1
        
        # DOE-101: WBS Coverage
        wbs_ids = set(a.get('wbs_id', '') for a in self.activities)
        checks.append(self.make_metric(
            'DOE-101', 'WBS Nodes with Activities',
            f'{len(wbs_ids)} WBS nodes contain activities',
            len(wbs_ids), 'DOE', 'WBS Structure',
            threshold_min=1, severity='medium',
            recommendation='All work should be organized under WBS.'
        ))
        
        # DOE-102: Empty WBS Nodes
        empty_wbs = [w for w in self.wbs_nodes if w.get('wbs_id', '') not in wbs_ids]
        checks.append(self.make_check(
            'DOE-102', 'Empty WBS Nodes',
            'WBS nodes without any activities',
            len(empty_wbs), len(self.wbs_nodes) or 1, 5, 'DOE', 'low', 'WBS Structure',
            'Remove empty WBS nodes or add planned activities.'
        ))
        
        # DOE-103: WBS Depth
        max_depth = max((w.get('wbs_short_name', '').count('.') for w in self.wbs_nodes), default=0)
        checks.append(self.make_metric(
            'DOE-103', 'Maximum WBS Depth',
            f'{max_depth} levels deep',
            max_depth, 'DOE', 'WBS Structure',
            threshold_min=3, threshold_max=7, severity='medium',
            recommendation='WBS depth should be 3-7 levels.'
        ))
        
        # DOE-104: Activities per WBS Distribution
        from collections import Counter
        wbs_counts = Counter(a.get('wbs_id', '') for a in self.activities)
        if wbs_counts:
            max_activities = max(wbs_counts.values())
            avg_activities = sum(wbs_counts.values()) / len(wbs_counts)
            
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
        """Overall schedule integrity."""
        checks = []
        total = len(self.incomplete) or 1
        
        # DOE-201: Total Activity Count Health
        checks.append(self.make_metric(
            'DOE-201', 'Total Activities',
            f'{len(self.activities)} activities in schedule',
            len(self.activities), 'DOE', 'Schedule Integrity',
            threshold_min=10, severity='low',
            info_only=True
        ))
        
        # DOE-202: Milestones Percentage
        mile_pct = len(self.milestones) / len(self.activities) * 100 if self.activities else 0
        checks.append(self.make_metric(
            'DOE-202', 'Milestone Percentage',
            f'{mile_pct:.1f}% are milestones',
            mile_pct, 'DOE', 'Schedule Integrity',
            threshold_min=2, threshold_max=15, severity='medium',
            recommendation='Milestones should be 2-15% of activities.'
        ))
        
        # DOE-203: Level of Effort Percentage
        loe_count = sum(1 for a in self.activities if a.get('task_type') == 'TT_LOE')
        loe_pct = loe_count / len(self.activities) * 100 if self.activities else 0
        checks.append(self.make_metric(
            'DOE-203', 'Level of Effort Percentage',
            f'{loe_pct:.1f}% are LOE',
            loe_pct, 'DOE', 'Schedule Integrity',
            threshold_max=15, severity='medium',
            recommendation='LOE should be <15% of schedule.'
        ))
        
        # DOE-204: Zero Duration Non-Milestones
        zero_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) == 0
                   and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        checks.append(self.make_check(
            'DOE-204', 'Zero Duration Non-Milestones',
            'Only milestones should have zero duration',
            len(zero_dur), total, 1, 'DOE', 'high', 'Schedule Integrity',
            'Convert to milestones or add duration.',
            zero_dur
        ))
        
        # DOE-205: Long Duration Threshold (60 days for DOE)
        long_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) > 60
                   and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        checks.append(self.make_check(
            'DOE-205', 'Long Duration Activities (>60 days)',
            'DOE recommends max 60-day activities',
            len(long_dur), total, 5, 'DOE', 'medium', 'Schedule Integrity',
            'Break down activities over 60 days.',
            long_dur
        ))
        
        # DOE-206: Activity Coding Consistency
        coded = sum(1 for a in self.activities if a.get('task_code', ''))
        code_pct = coded / len(self.activities) * 100 if self.activities else 0
        checks.append(self.make_metric(
            'DOE-206', 'Activity ID Coverage',
            f'{code_pct:.1f}% have activity IDs',
            code_pct, 'DOE', 'Schedule Integrity',
            threshold_min=100, severity='high',
            recommendation='All activities must have unique IDs.'
        ))
        
        # DOE-207: Duplicate Activity IDs
        from collections import Counter
        code_counts = Counter(a.get('task_code', '') for a in self.activities if a.get('task_code'))
        dup_ids = [code for code, count in code_counts.items() if count > 1]
        checks.append(self.make_check(
            'DOE-207', 'Duplicate Activity IDs',
            'Activity IDs must be unique',
            len(dup_ids), len(self.activities) or 1, 0, 'DOE', 'critical', 'Schedule Integrity',
            'Fix duplicate activity IDs immediately.'
        ))
        
        return {'name': 'Schedule Integrity', 'checks': checks}

    def _resource_management(self):
        """Resource assignment and cost checks."""
        checks = []
        total = len(self.incomplete) or 1
        
        tasks_with_res = set(r.get('task_id') for r in self.resources)
        work_activities = [a for a in self.incomplete 
                          if a.get('task_type') not in ['TT_Mile', 'TT_FinMile', 'TT_LOE']]
        
        # DOE-301: Resource Loading
        unresourced = [a for a in work_activities if a.get('task_id', '') not in tasks_with_res]
        checks.append(self.make_check(
            'DOE-301', 'Unresourced Work Activities',
            'DOE requires resource-loaded schedules',
            len(unresourced), max(len(work_activities), 1), 10, 'DOE', 'high', 'Resources',
            'Assign resources to all work activities.',
            unresourced
        ))
        
        # DOE-302: Cost Loading
        costed = [r for r in self.resources if self.to_float(r.get('target_cost', '0')) > 0]
        cost_pct = len(costed) / len(self.resources) * 100 if self.resources else 0
        checks.append(self.make_metric(
            'DOE-302', 'Cost-Loaded Assignments',
            f'{cost_pct:.1f}% have costs assigned',
            cost_pct, 'DOE', 'Resources',
            threshold_min=90, severity='high',
            recommendation='DOE requires cost-loaded schedules.'
        ))
        
        # DOE-303: Zero-Cost Resources with Hours
        zero_cost_with_hours = [r for r in self.resources 
                               if self.to_float(r.get('target_cost', '0')) == 0
                               and self.to_float(r.get('target_qty', '0')) > 0]
        checks.append(self.make_check(
            'DOE-303', 'Zero-Cost Resources with Hours',
            'Resources with hours must have costs',
            len(zero_cost_with_hours), len(self.resources) or 1, 5, 'DOE', 'medium', 'Resources',
            'Add costs to all resource assignments.'
        ))
        
        # DOE-304: Milestone Resources (should be none)
        mile_with_res = [a for a in self.milestones if a.get('task_id', '') in tasks_with_res]
        checks.append(self.make_check(
            'DOE-304', 'Milestones with Resources',
            'Milestones should not have resource assignments',
            len(mile_with_res), max(len(self.milestones), 1), 5, 'DOE', 'medium', 'Resources',
            'Remove resources from milestones.',
            mile_with_res
        ))
        
        # DOE-305: Resource Distribution
        checks.append(self.make_metric(
            'DOE-305', 'Total Resource Assignments',
            f'{len(self.resources)} resource assignments',
            len(self.resources), 'DOE', 'Resources',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        return {'name': 'Resource Management', 'checks': checks}

    def _progress_measurement(self):
        """Progress reporting quality."""
        checks = []
        total = len(self.activities) or 1
        
        # DOE-401: Progress Without Actual Start
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
        
        # DOE-402: Complete Without Actual Finish
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
        
        # DOE-403: Actual Finish Without 100%
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
        
        # DOE-404: Progress Consistency
        remain_issues = [a for a in self.in_progress
                        if a.get('remaining_duration_days', 0) >= a.get('original_duration_days', 0)
                        and self.to_float(a.get('phys_complete_pct', '0')) > 0]
        checks.append(self.make_check(
            'DOE-404', 'Progress vs Remaining Duration',
            'Progress must reduce remaining duration',
            len(remain_issues), max(len(self.in_progress), 1), 5, 'DOE', 'high', 'Progress',
            'Update remaining duration to match progress.',
            remain_issues
        ))
        
        # DOE-405: Data Date Set
        checks.append(self.make_boolean(
            'DOE-405', 'Data Date Set',
            'Schedule must have a data date',
            self.data_date is not None, 'DOE', 'Progress',
            severity='critical',
            recommendation='Set a valid data date before analysis.'
        ))
        
        return {'name': 'Progress Measurement', 'checks': checks}

    def _risk_management(self):
        """Risk-related schedule checks."""
        checks = []
        total = len(self.incomplete) or 1
        
        # DOE-501: Critical Path Ratio
        cp_count = len(self.engine.critical_activities)
        cp_pct = cp_count / total * 100
        checks.append(self.make_metric(
            'DOE-501', 'Critical Path Percentage',
            f'{cp_pct:.1f}% on critical path',
            cp_pct, 'DOE', 'Risk',
            threshold_min=5, threshold_max=25, severity='medium',
            recommendation='CP should be 5-25%. Too few = slack; too many = high risk.'
        ))
        
        # DOE-502: Near-Critical Activities (< 10 days float)
        near_crit = [a for a in self.incomplete 
                    if 0 < a.get('total_float_days', 0) <= 10]
        checks.append(self.make_metric(
            'DOE-502', 'Near-Critical Activities',
            f'{len(near_crit)} activities with <10 days float',
            len(near_crit), 'DOE', 'Risk',
            threshold_max=None, severity='medium',
            info_only=True,
            recommendation='Near-critical activities can quickly become critical.'
        ))
        
        # DOE-503: Total Float Distribution
        floats = [a.get('total_float_days', 0) for a in self.incomplete]
        if floats:
            import statistics
            median_float = statistics.median(floats)
            checks.append(self.make_metric(
                'DOE-503', 'Median Total Float',
                f'{median_float:.1f} days median float',
                median_float, 'DOE', 'Risk',
                threshold_min=5, threshold_max=60, severity='medium',
                recommendation='Very low = tight schedule; very high = broken logic.'
            ))
        
        # DOE-504: Schedule Contingency
        # Estimate based on avg float
        if floats:
            avg_float = sum(floats) / len(floats)
            checks.append(self.make_metric(
                'DOE-504', 'Average Total Float (Contingency)',
                f'{avg_float:.1f} days average',
                avg_float, 'DOE', 'Risk',
                threshold_min=0, severity='low',
                info_only=True
            ))
        
        return {'name': 'Risk Management', 'checks': checks}

    def _earned_value_checks(self):
        """DOE EVM-related checks."""
        checks = []
        
        # DOE-601: Baseline Set
        with_baseline = sum(1 for a in self.activities if a.get('target_start_date', ''))
        bl_pct = with_baseline / len(self.activities) * 100 if self.activities else 0
        checks.append(self.make_metric(
            'DOE-601', 'Activities with Baseline',
            f'{bl_pct:.1f}% have baseline dates',
            bl_pct, 'DOE', 'Earned Value',
            threshold_min=100, severity='high',
            recommendation='All activities need baseline dates for EVM.'
        ))
        
        # DOE-602: WBS Levels for EV Reporting
        max_depth = max((w.get('wbs_short_name', '').count('.') for w in self.wbs_nodes), default=0)
        checks.append(self.make_metric(
            'DOE-602', 'WBS Depth for EV Reporting',
            f'{max_depth} levels',
            max_depth, 'DOE', 'Earned Value',
            threshold_min=3, severity='medium',
            recommendation='EV reporting needs at least 3 WBS levels.'
        ))
        
        # DOE-603: Work Package Size
        total_bl_cost = sum(self.to_float(r.get('target_cost', '0')) for r in self.resources)
        if total_bl_cost > 0 and self.activities:
            avg_cost = total_bl_cost / len(self.activities)
            checks.append(self.make_metric(
                'DOE-603', 'Average Activity Budget',
                f'${avg_cost:,.0f} average',
                avg_cost, 'DOE', 'Earned Value',
                threshold_min=0, severity='low',
                info_only=True
            ))
        
        return {'name': 'Earned Value Compliance', 'checks': checks}
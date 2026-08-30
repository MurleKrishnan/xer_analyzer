"""
DCMA 14-POINT ASSESSMENT (Enhanced)
====================================
Enhanced checks based on:
- DCMA 14-Point Schedule Assessment
- DCMA 14-Point Analysis Guide (2012 & updates)
- Plus: Open Ends, FS+Lag detection
"""

from health_standards.base_checker import BaseChecker


class DCMAChecks(BaseChecker):
    """DCMA 14-Point comprehensive check suite."""

    def run_checks(self):
        """Run all DCMA checks organized by category."""
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
        """DCMA-01 & DCMA-02 with sub-metrics + Open Ends."""
        checks = []
        total = len(self.incomplete) or 1
        
        # ─── DCMA-01: Missing Predecessors ───
        missing_preds = [a for a in self.incomplete 
                        if a.get('task_id', '') not in self.engine.predecessors]
        checks.append(self.make_check(
            'DCMA-01', 'Missing Predecessors',
            'Every activity (except start milestones) should have a predecessor',
            len(missing_preds), total, 5, 'DCMA', 'high', 'Logic',
            'Add logical predecessors to activities. Only project start milestones may have none.',
            missing_preds
        ))
        
        # DCMA-01a: Missing Preds on Critical Path
        critical_missing_preds = [a for a in missing_preds if a.get('is_critical')]
        checks.append(self.make_check(
            'DCMA-01a', 'Critical Path Missing Predecessors',
            'Critical activities without predecessors',
            len(critical_missing_preds), max(len(missing_preds), 1), 0, 'DCMA', 'critical', 'Logic',
            'Critical activities MUST have predecessors.',
            critical_missing_preds
        ))
        
        # DCMA-02: Missing Successors
        missing_succs = [a for a in self.incomplete 
                        if a.get('task_id', '') not in self.engine.successors]
        checks.append(self.make_check(
            'DCMA-02', 'Missing Successors',
            'Every activity (except finish milestones) should have a successor',
            len(missing_succs), total, 5, 'DCMA', 'high', 'Logic',
            'Add logical successors to activities. Only project finish milestones may have none.',
            missing_succs
        ))
        
        # DCMA-02a: Critical Path Missing Successors
        critical_missing_succs = [a for a in missing_succs if a.get('is_critical')]
        checks.append(self.make_check(
            'DCMA-02a', 'Critical Path Missing Successors',
            'Critical activities without successors',
            len(critical_missing_succs), max(len(missing_succs), 1), 0, 'DCMA', 'critical', 'Logic',
            'Critical activities MUST have successors.',
            critical_missing_succs
        ))
        
        # ─── NEW: DCMA-OPEN-01: Open Start Activities ───
        open_start = [a for a in self.incomplete
                      if a.get('task_id', '') not in self.engine.predecessors
                      and a.get('task_type') not in ['TT_Mile']]
        checks.append(self.make_check(
            'DCMA-OPEN-01', 'Open Start Activities',
            'Non-start-milestone activities without predecessors (dangling starts)',
            len(open_start), total, 0, 'DCMA', 'high', 'Logic',
            'Only start milestones should have no predecessors. Add predecessor logic to eliminate dangling starts.',
            open_start
        ))
        
        # ─── NEW: DCMA-OPEN-02: Open End Activities ───
        open_end = [a for a in self.incomplete
                    if a.get('task_id', '') not in self.engine.successors
                    and a.get('task_type') not in ['TT_FinMile']]
        checks.append(self.make_check(
            'DCMA-OPEN-02', 'Open End Activities',
            'Non-finish-milestone activities without successors (dangling ends)',
            len(open_end), total, 0, 'DCMA', 'high', 'Logic',
            'Only finish milestones should have no successors. Add successor logic to eliminate dangling ends.',
            open_end
        ))
        
        return {'name': 'Logic Checks', 'checks': checks}

    def _lag_lead_checks(self):
        """DCMA-03, DCMA-04, DCMA-05 with sub-metrics + FS+Lag."""
        checks = []
        rel_total = len(self.relationships) or 1
        
        # DCMA-03: Leads (Negative Lag)
        leads = [r for r in self.relationships if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'DCMA-03', 'Leads (Negative Lag)',
            'No relationships should have negative lag',
            len(leads), rel_total, 0, 'DCMA', 'high', 'Logic',
            'Remove all negative lags. Leads distort CPM calculations.',
            leads
        ))
        
        # DCMA-03a: Large Leads (>5 days)
        large_leads = [r for r in leads if r.get('lag_days', 0) < -5]
        checks.append(self.make_check(
            'DCMA-03a', 'Large Leads (>5 days)',
            'Leads greater than 5 days',
            len(large_leads), rel_total, 0, 'DCMA', 'high', 'Logic',
            'Large leads (>5 days) significantly distort schedule.',
            large_leads
        ))
        
        # DCMA-04: Lags
        lags = [r for r in self.relationships if r.get('lag_days', 0) > 0]
        checks.append(self.make_check(
            'DCMA-04', 'Excessive Lags',
            'Minimize use of positive lags',
            len(lags), rel_total, 5, 'DCMA', 'medium', 'Logic',
            'Replace lags with work activities or hammocks.',
            lags
        ))
        
        # DCMA-04a: Large Lags (>10 days)
        large_lags = [r for r in lags if r.get('lag_days', 0) > 10]
        checks.append(self.make_check(
            'DCMA-04a', 'Large Lags (>10 days)',
            'Lags greater than 10 days',
            len(large_lags), rel_total, 2, 'DCMA', 'high', 'Logic',
            'Large lags may hide activities or duration.',
            large_lags
        ))
        
        # DCMA-05: Relationship Types
        non_fs = [r for r in self.relationships if r.get('pred_type') != 'PR_FS']
        checks.append(self.make_check(
            'DCMA-05', 'Non-FS Relationships',
            'Minimize SS, FF, SF relationships',
            len(non_fs), rel_total, 10, 'DCMA', 'medium', 'Logic',
            'Use Finish-to-Start relationships whenever possible.',
            non_fs
        ))
        
        # DCMA-05a: SF Relationships (should be near zero)
        sf_rels = [r for r in self.relationships if r.get('pred_type') == 'PR_SF']
        checks.append(self.make_check(
            'DCMA-05a', 'Start-to-Finish Relationships',
            'SF relationships should be avoided',
            len(sf_rels), rel_total, 1, 'DCMA', 'high', 'Logic',
            'SF relationships are counterintuitive and often incorrect.',
            sf_rels
        ))
        
        # ─── NEW: DCMA-FS-LAG: FS Relationships with Positive Lag ───
        fs_lag_rels = [
            r for r in self.relationships
            if r.get('pred_type') == 'PR_FS' and r.get('lag_days', 0) > 0
        ]
        
        # Extract unique successor activities affected
        affected_ids = set()
        affected_acts = []
        for r in fs_lag_rels:
            succ_id = r.get('task_id')
            if succ_id and succ_id not in affected_ids:
                affected_ids.add(succ_id)
                succ = self.engine.activity_by_id.get(succ_id)
                if succ:
                    affected_acts.append(succ)
        
        checks.append(self.make_check(
            'DCMA-FS-LAG', 'FS Relationships with Lag',
            'Finish-to-Start relationships with positive lag (waiting periods)',
            len(fs_lag_rels), rel_total, 3, 'DCMA', 'medium', 'Logic',
            'Replace lags with real activities (e.g., "Cure Time", "Waiting Approval") for transparency.',
            affected_acts
        ))
        
        return {'name': 'Lag/Lead Analysis', 'checks': checks}

    def _constraint_checks(self):
        """DCMA-06 with detailed constraint breakdown."""
        checks = []
        total = len(self.incomplete) or 1
        
        # DCMA-06: All Hard Constraints
        hard_types = ['CS_ALAP', 'CS_MSO', 'CS_MFO', 'CS_MANDSTART', 'CS_MANDFIN']
        constrained = [a for a in self.incomplete 
                      if a.get('cstr_type', '') in hard_types 
                      or a.get('cstr_type2', '') in hard_types]
        checks.append(self.make_check(
            'DCMA-06', 'Hard Constraints',
            'Minimize hard constraints that override CPM',
            len(constrained), total, 5, 'DCMA', 'high', 'Constraints',
            'Replace hard constraints with logical relationships.',
            constrained
        ))
        
        # DCMA-06a: Mandatory Start
        mand_start = [a for a in self.incomplete if a.get('cstr_type') == 'CS_MANDSTART']
        checks.append(self.make_check(
            'DCMA-06a', 'Mandatory Start Constraints',
            'Mandatory start prevents proper CPM',
            len(mand_start), total, 1, 'DCMA', 'critical', 'Constraints',
            'Mandatory Start constraints prevent CPM. Use logic instead.',
            mand_start
        ))
        
        # DCMA-06b: Mandatory Finish
        mand_fin = [a for a in self.incomplete if a.get('cstr_type') == 'CS_MANDFIN']
        checks.append(self.make_check(
            'DCMA-06b', 'Mandatory Finish Constraints',
            'Mandatory finish prevents proper CPM',
            len(mand_fin), total, 1, 'DCMA', 'critical', 'Constraints',
            'Mandatory Finish constraints prevent CPM. Use logic instead.',
            mand_fin
        ))
        
        # DCMA-06c: Must Start On
        must_start = [a for a in self.incomplete if a.get('cstr_type') == 'CS_MSO']
        checks.append(self.make_check(
            'DCMA-06c', 'Must Start On Constraints',
            'Must Start On constraints',
            len(must_start), total, 2, 'DCMA', 'high', 'Constraints',
            'Prefer logical relationships over date constraints.',
            must_start
        ))
        
        # DCMA-06d: Must Finish On
        must_fin = [a for a in self.incomplete if a.get('cstr_type') == 'CS_MFO']
        checks.append(self.make_check(
            'DCMA-06d', 'Must Finish On Constraints',
            'Must Finish On constraints',
            len(must_fin), total, 2, 'DCMA', 'high', 'Constraints',
            'Prefer logical relationships over date constraints.',
            must_fin
        ))
        
        # DCMA-06e: ALAP
        alap = [a for a in self.incomplete if a.get('cstr_type') == 'CS_ALAP']
        checks.append(self.make_check(
            'DCMA-06e', 'As Late As Possible',
            'ALAP constraints eliminate float',
            len(alap), total, 1, 'DCMA', 'high', 'Constraints',
            'ALAP consumes all float, hiding schedule risk.',
            alap
        ))
        
        return {'name': 'Constraint Analysis', 'checks': checks}

    def _float_duration_checks(self):
        """DCMA-07, DCMA-08, DCMA-09 with sub-metrics."""
        checks = []
        total = len(self.incomplete) or 1
        
        # DCMA-07: High Float (>44 days)
        high_float = [a for a in self.incomplete 
                     if a.get('total_float_days', 0) > 44]
        checks.append(self.make_check(
            'DCMA-07', 'High Float (>44 days)',
            'Activities should not have excessive float',
            len(high_float), total, 5, 'DCMA', 'medium', 'Float',
            'High float often indicates missing successors.',
            high_float
        ))
        
        # DCMA-07a: Very High Float (>132 days = 6 months)
        very_high_float = [a for a in self.incomplete 
                          if a.get('total_float_days', 0) > 132]
        checks.append(self.make_check(
            'DCMA-07a', 'Very High Float (>132 days)',
            'Excessive float beyond 6 months',
            len(very_high_float), total, 2, 'DCMA', 'high', 'Float',
            'Very high float almost always indicates broken logic.',
            very_high_float
        ))
        
        # DCMA-08: Negative Float
        neg_float = [a for a in self.incomplete 
                    if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'DCMA-08', 'Negative Float',
            'No activities should have negative total float',
            len(neg_float), total, 0, 'DCMA', 'critical', 'Float',
            'Negative float means the schedule cannot meet constraints.',
            neg_float
        ))
        
        # DCMA-08a: Severe Negative Float (<-10 days)
        severe_neg = [a for a in self.incomplete 
                     if a.get('total_float_days', 0) < -10]
        checks.append(self.make_check(
            'DCMA-08a', 'Severe Negative Float (<-10 days)',
            'Critical schedule issues',
            len(severe_neg), total, 0, 'DCMA', 'critical', 'Float',
            'Immediate action required to recover schedule.',
            severe_neg
        ))
        
        # DCMA-09: High Duration (>44 days)
        high_dur = [a for a in self.incomplete 
                   if a.get('original_duration_days', 0) > 44 
                   and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        checks.append(self.make_check(
            'DCMA-09', 'High Duration Activities',
            'Activities should be broken down to <44 days',
            len(high_dur), total, 5, 'DCMA', 'medium', 'Duration',
            'Decompose long-duration activities for better visibility.',
            high_dur
        ))
        
        # DCMA-09a: Very High Duration (>88 days)
        very_high_dur = [a for a in self.incomplete 
                        if a.get('original_duration_days', 0) > 88
                        and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        checks.append(self.make_check(
            'DCMA-09a', 'Very High Duration (>88 days)',
            'Activities over 4 months',
            len(very_high_dur), total, 2, 'DCMA', 'high', 'Duration',
            'Activities >88 days almost always need decomposition.',
            very_high_dur
        ))
        
        return {'name': 'Float & Duration Analysis', 'checks': checks}

    def _date_progress_checks(self):
        """DCMA-10 and progress validation."""
        checks = []
        total = len(self.activities) or 1
        
        # DCMA-10: Invalid Dates
        invalid = []
        for a in self.activities:
            if a.get('status_code') == 'TK_NotStart' and a.get('act_start_date', ''):
                invalid.append(a)
        
        checks.append(self.make_check(
            'DCMA-10', 'Invalid Dates (Not Started with Actual)',
            'Unstarted activities should not have actual dates',
            len(invalid), total, 0, 'DCMA', 'critical', 'Dates',
            'Remove actual dates from unstarted activities.',
            invalid
        ))
        
        # DCMA-10a: Actual finish after data date
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
        
        return {'name': 'Date Validity', 'checks': checks}

    def _resource_metric_checks(self):
        """DCMA-11, DCMA-12, DCMA-13, DCMA-14."""
        checks = []
        total = len(self.incomplete) or 1
        
        # DCMA-11: Missing Resources
        tasks_with_res = set(r.get('task_id') for r in self.resources)
        missing_res = [a for a in self.incomplete 
                      if a.get('task_id', '') not in tasks_with_res
                      and a.get('task_type') not in ['TT_Mile', 'TT_FinMile', 'TT_LOE']]
        
        checks.append(self.make_check(
            'DCMA-11', 'Missing Resources',
            'Work activities should have resources',
            len(missing_res), total, 5, 'DCMA', 'medium', 'Resources',
            'Assign resources for cost/schedule integration.',
            missing_res
        ))
        
        # DCMA-12: CPLI
        cpli = self._calculate_cpli()
        checks.append(self.make_metric(
            'DCMA-12', 'CPLI (Critical Path Length Index)',
            'CPLI ≥ 0.95 indicates achievable schedule',
            cpli, 'DCMA', 'Metrics',
            threshold_min=0.95, severity='high',
            recommendation='CPLI < 0.95 means critical path exceeds remaining time.',
            unit=''
        ))
        
        # DCMA-13: BEI
        bei = self._calculate_bei()
        checks.append(self.make_metric(
            'DCMA-13', 'BEI (Baseline Execution Index)',
            'BEI ≥ 0.95 indicates on-track execution',
            bei, 'DCMA', 'Metrics',
            threshold_min=0.95, severity='high',
            recommendation='BEI < 0.95 means tasks completing later than baseline.',
            unit=''
        ))
        
        # DCMA-14: Critical Path Test
        cp_exists = len(self.engine.critical_activities) > 0
        checks.append(self.make_boolean(
            'DCMA-14', 'Critical Path Test',
            'Continuous critical path must exist',
            cp_exists, 'DCMA', 'Metrics',
            severity='critical',
            recommendation='Every project must have a valid critical path.'
        ))
        
        return {'name': 'Resources & Metrics', 'checks': checks}

    def _calculate_cpli(self):
        """Calculate Critical Path Length Index."""
        try:
            if not self.data_date or not self.projects:
                return 1.0
            proj = self.projects[0]
            baseline_finish = self.engine._parse_date(proj.get('plan_end_date', ''))
            if not baseline_finish:
                return 1.0
            
            end_dates = [a.get('early_end_date_parsed') for a in self.incomplete 
                        if a.get('early_end_date_parsed')]
            if not end_dates:
                return 1.0
            
            project_finish = max(end_dates)
            
            baseline_days = max(1, (baseline_finish - self.data_date).days)
            remaining_days = max(1, (project_finish - self.data_date).days)
            
            return round(baseline_days / remaining_days, 3)
        except:
            return 1.0

    def _calculate_bei(self):
        """Calculate Baseline Execution Index."""
        try:
            if not self.data_date:
                return 1.0
            
            should_be_complete = 0
            actually_complete = 0
            
            for a in self.real_activities:
                bl_end = a.get('target_end_date_parsed')
                if bl_end and bl_end <= self.data_date:
                    should_be_complete += 1
                    if a.get('status_code') == 'TK_Complete':
                        actually_complete += 1
            
            if should_be_complete == 0:
                return 1.0
            
            return round(actually_complete / should_be_complete, 3)
        except:
            return 1.0
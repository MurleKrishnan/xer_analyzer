"""
DCMA 14-POINT ASSESSMENT (Enhanced)
====================================
Based on:
- DCMA 14-Point Schedule Assessment
- DCMA 14-Point Analysis Guide (2012 & updates)
- Plus: Open Ends, FS+Lag, and refined CP continuity checks
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

    # ═══════════════════════════════════════════════════════
    # 1. LOGIC CHECKS (DCMA-01, DCMA-02, Open Ends)
    # ═══════════════════════════════════════════════════════
    def _logic_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        
        # Uses shared helpers from base_checker (milestone-aware, incomplete-only)
        open_start = self.open_start_activities()
        open_end = self.open_end_activities()
        
        # ─── DCMA-01: Missing Predecessors ───
        checks.append(self.make_check(
            'DCMA-01', 'Missing Predecessors',
            'Every activity (except start milestones) should have a predecessor',
            len(open_start), total, 5, 'DCMA', 'high', 'Logic',
            'Add logical predecessors to activities. Only project start milestones may have none.',
            open_start
        ))
        
        # DCMA-01a: Missing Preds on Critical Path
        crit_incomplete = [a for a in self.incomplete if a.get('is_critical')]
        crit_missing_pred = [a for a in open_start if a.get('is_critical')]
        checks.append(self.make_check(
            'DCMA-01a', 'Critical Path Missing Predecessors',
            'Critical activities without predecessors',
            len(crit_missing_pred), max(len(crit_incomplete), 1), 0, 'DCMA', 'critical', 'Logic',
            'Critical activities MUST have predecessors.',
            crit_missing_pred
        ))
        
        # DCMA-02: Missing Successors
        checks.append(self.make_check(
            'DCMA-02', 'Missing Successors',
            'Every activity (except finish milestones) should have a successor',
            len(open_end), total, 5, 'DCMA', 'high', 'Logic',
            'Add logical successors to activities. Only project finish milestones may have none.',
            open_end
        ))
        
        # DCMA-02a: Critical Path Missing Successors
        crit_missing_succ = [a for a in open_end if a.get('is_critical')]
        checks.append(self.make_check(
            'DCMA-02a', 'Critical Path Missing Successors',
            'Critical activities without successors',
            len(crit_missing_succ), max(len(crit_incomplete), 1), 0, 'DCMA', 'critical', 'Logic',
            'Critical activities MUST have successors.',
            crit_missing_succ
        ))
        
        # DCMA-OPEN-01: Open Start Activities (explicit extension)
        checks.append(self.make_check(
            'DCMA-OPEN-01', 'Open Start Activities',
            'Non-milestone activities without predecessors',
            len(open_start), total, 0, 'DCMA', 'high', 'Logic',
            'Only start milestones should have no predecessors.',
            open_start
        ))
        
        # DCMA-OPEN-02: Open End Activities
        checks.append(self.make_check(
            'DCMA-OPEN-02', 'Open End Activities',
            'Non-milestone activities without successors',
            len(open_end), total, 0, 'DCMA', 'high', 'Logic',
            'Only finish milestones should have no successors.',
            open_end
        ))
        
        return {'name': 'Logic Checks', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 2. LAG / LEAD CHECKS (DCMA-03, 04, 05, FS+Lag)
    # ═══════════════════════════════════════════════════════
    def _lag_lead_checks(self):
        checks = []
        
        # Only assess ACTIVE (non-completed successor) relationships
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1
        
        # DCMA-03: Leads (Negative Lag)
        leads = [r for r in active_rels if r.get('lag_days', 0) < 0]
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
        lags = [r for r in active_rels if r.get('lag_days', 0) > 0]
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
        
        # DCMA-05: Non-FS Relationship Types
        non_fs = [r for r in active_rels if r.get('pred_type') != 'PR_FS']
        checks.append(self.make_check(
            'DCMA-05', 'Non-FS Relationships',
            'Minimize SS, FF, SF relationships',
            len(non_fs), rel_total, 10, 'DCMA', 'medium', 'Logic',
            'Use Finish-to-Start relationships whenever possible.',
            non_fs
        ))
        
        # DCMA-05a: SF Relationships (should be near zero)
        sf_rels = [r for r in active_rels if r.get('pred_type') == 'PR_SF']
        checks.append(self.make_check(
            'DCMA-05a', 'Start-to-Finish Relationships',
            'SF relationships should be avoided',
            len(sf_rels), rel_total, 1, 'DCMA', 'high', 'Logic',
            'SF relationships are counterintuitive and often incorrect.',
            sf_rels
        ))
        
        # DCMA-FS-LAG: FS with positive lag (extension)
        fs_lag_rels = self.fs_with_lag()
        checks.append(self.make_check(
            'DCMA-FS-LAG', 'FS Relationships with Lag',
            'Finish-to-Start relationships with positive lag (waiting periods)',
            len(fs_lag_rels), rel_total, 3, 'DCMA', 'medium', 'Logic',
            'Replace lags with real activities (e.g., "Cure Time", "Waiting Approval") for transparency.',
            fs_lag_rels
        ))
        
        return {'name': 'Lag/Lead Analysis', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 3. CONSTRAINT CHECKS (DCMA-06)
    # ═══════════════════════════════════════════════════════
    def _constraint_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        
        # DCMA-06: Hard Constraints (excludes ALAP - tracked separately)
        constrained = [a for a in self.incomplete if self.has_hard_constraint(a)]
        checks.append(self.make_check(
            'DCMA-06', 'Hard Constraints',
            'Minimize hard constraints that override CPM',
            len(constrained), total, 5, 'DCMA', 'high', 'Constraints',
            'Replace hard constraints with logical relationships.',
            constrained
        ))
        
        # DCMA-06a: Mandatory Start
        mand_start = [a for a in self.incomplete 
                      if a.get('cstr_type') == 'CS_MANDSTART' or a.get('cstr_type2') == 'CS_MANDSTART']
        checks.append(self.make_check(
            'DCMA-06a', 'Mandatory Start Constraints',
            'Mandatory start prevents proper CPM',
            len(mand_start), total, 1, 'DCMA', 'critical', 'Constraints',
            'Mandatory Start constraints prevent CPM. Use logic instead.',
            mand_start
        ))
        
        # DCMA-06b: Mandatory Finish
        mand_fin = [a for a in self.incomplete 
                    if a.get('cstr_type') == 'CS_MANDFIN' or a.get('cstr_type2') == 'CS_MANDFIN']
        checks.append(self.make_check(
            'DCMA-06b', 'Mandatory Finish Constraints',
            'Mandatory finish prevents proper CPM',
            len(mand_fin), total, 1, 'DCMA', 'critical', 'Constraints',
            'Mandatory Finish constraints prevent CPM. Use logic instead.',
            mand_fin
        ))
        
        # DCMA-06c: Must Start On
        must_start = [a for a in self.incomplete 
                      if a.get('cstr_type') == 'CS_MSO' or a.get('cstr_type2') == 'CS_MSO']
        checks.append(self.make_check(
            'DCMA-06c', 'Must Start On Constraints',
            'Must Start On constraints',
            len(must_start), total, 2, 'DCMA', 'high', 'Constraints',
            'Prefer logical relationships over date constraints.',
            must_start
        ))
        
        # DCMA-06d: Must Finish On (corrected code: CS_MEO not CS_MFO)
        must_fin = [a for a in self.incomplete 
                    if a.get('cstr_type') == 'CS_MEO' or a.get('cstr_type2') == 'CS_MEO']
        checks.append(self.make_check(
            'DCMA-06d', 'Must Finish On Constraints',
            'Must Finish On constraints',
            len(must_fin), total, 2, 'DCMA', 'high', 'Constraints',
            'Prefer logical relationships over date constraints.',
            must_fin
        ))
        
        # DCMA-06e: ALAP (tracked separately from hard constraints)
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

    # ═══════════════════════════════════════════════════════
    # 4. FLOAT / DURATION CHECKS (DCMA-07, 08, 09)
    # ═══════════════════════════════════════════════════════
    def _float_duration_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        milestones = {'TT_Mile', 'TT_FinMile'}
        
        # DCMA-07: High Float (>44 days)
        high_float = [a for a in self.incomplete if a.get('total_float_days', 0) > 44]
        checks.append(self.make_check(
            'DCMA-07', 'High Float (>44 days)',
            'Activities should not have excessive float',
            len(high_float), total, 5, 'DCMA', 'medium', 'Float',
            'High float often indicates missing successors.',
            high_float
        ))
        
        # DCMA-07a: Very High Float (>132 days)
        very_high_float = [a for a in self.incomplete if a.get('total_float_days', 0) > 132]
        checks.append(self.make_check(
            'DCMA-07a', 'Very High Float (>132 days)',
            'Excessive float beyond 6 months',
            len(very_high_float), total, 2, 'DCMA', 'high', 'Float',
            'Very high float almost always indicates broken logic.',
            very_high_float
        ))
        
        # DCMA-08: Negative Float
        neg_float = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'DCMA-08', 'Negative Float',
            'No activities should have negative total float',
            len(neg_float), total, 0, 'DCMA', 'critical', 'Float',
            'Negative float means the schedule cannot meet constraints.',
            neg_float
        ))
        
        # DCMA-08a: Severe Negative Float (<-10 days)
        severe_neg = [a for a in self.incomplete if a.get('total_float_days', 0) < -10]
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
                   and a.get('task_type') not in milestones]
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
                        and a.get('task_type') not in milestones]
        checks.append(self.make_check(
            'DCMA-09a', 'Very High Duration (>88 days)',
            'Activities over 4 months',
            len(very_high_dur), total, 2, 'DCMA', 'high', 'Duration',
            'Activities >88 days almost always need decomposition.',
            very_high_dur
        ))
        
        return {'name': 'Float & Duration Analysis', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 5. DATE / PROGRESS VALIDITY (DCMA-10)
    # ═══════════════════════════════════════════════════════
    def _date_progress_checks(self):
        checks = []
        total = len(self.activities) or 1
        
        # DCMA-10: Invalid Dates (Not Started with Actual Start)
        invalid = [a for a in self.activities
                  if a.get('status_code') == 'TK_NotStart' and a.get('act_start_date', '')]
        checks.append(self.make_check(
            'DCMA-10', 'Invalid Dates (Not Started with Actual)',
            'Unstarted activities should not have actual dates',
            len(invalid), total, 0, 'DCMA', 'critical', 'Dates',
            'Remove actual dates from unstarted activities.',
            invalid
        ))
        
        # DCMA-10a: Actual Finish After Data Date
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
        
        # DCMA-10b: Actual Start After Data Date
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
        
        # DCMA-10c: Actual Finish Before Actual Start
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
        
        # DCMA-10d: Complete Without Actual Finish
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

    # ═══════════════════════════════════════════════════════
    # 6. RESOURCES & METRICS (DCMA-11, 12, 13, 14)
    # ═══════════════════════════════════════════════════════
    def _resource_metric_checks(self):
        checks = []
        total = len(self.incomplete) or 1
        milestones = {'TT_Mile', 'TT_FinMile', 'TT_LOE'}
        
        # DCMA-11: Missing Resources
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
        
        # DCMA-12: CPLI (Critical Path Length Index)
        cpli = self._calculate_cpli()
        checks.append(self.make_metric(
            'DCMA-12', 'CPLI (Critical Path Length Index)',
            'CPLI ≥ 0.95 indicates achievable schedule',
            cpli, 'DCMA', 'Metrics',
            threshold_min=0.95, severity='high',
            recommendation='CPLI < 0.95 means critical path exceeds remaining time to baseline finish.',
            unit=''
        ))
        
        # DCMA-13: BEI (Baseline Execution Index)
        bei = self._calculate_bei()
        checks.append(self.make_metric(
            'DCMA-13', 'BEI (Baseline Execution Index)',
            'BEI ≥ 0.95 indicates on-track execution',
            bei, 'DCMA', 'Metrics',
            threshold_min=0.95, severity='high',
            recommendation='BEI < 0.95 means tasks completing later than baseline.',
            unit=''
        ))
        
        # DCMA-14: Critical Path Test (Continuity)
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

    # ═══════════════════════════════════════════════════════
    # DCMA-12 CPLI CALCULATION
    # ═══════════════════════════════════════════════════════
    def _calculate_cpli(self):
        """
        CPLI = Time Available / Length of Critical Path
        Returns None (N/A) if data is insufficient.
        """
        try:
            if not self.data_date or not self.projects:
                return None
                
            proj = self.projects[0]
            baseline_finish = self.engine._parse_date(proj.get('plan_end_date', ''))
            if not baseline_finish:
                return None
            
            # Critical path finish = latest EF among critical incomplete activities
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

    # ═══════════════════════════════════════════════════════
    # DCMA-13 BEI CALCULATION
    # ═══════════════════════════════════════════════════════
    def _calculate_bei(self):
        """
        BEI = Actual Finishes To Date / Baseline Finishes Scheduled To Date
        Returns None (N/A) if data is insufficient.
        """
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

    # ═══════════════════════════════════════════════════════
    # DCMA-14 CRITICAL PATH CONTINUITY
    # ═══════════════════════════════════════════════════════
    def _calculate_cp_continuity(self):
        """
        Measures whether critical activities form a continuous path.
        Score = % of critical activities linked to another critical activity.
        A truly continuous CP scores near 1.0.
        """
        try:
            crit_ids = {str(a.get('task_id', '')) for a in self.incomplete if a.get('is_critical')}
            if not crit_ids:
                return None
            
            connected = 0
            for cid in crit_ids:
                # Check if any successor is also critical
                succs = self.engine.successors.get(cid, [])
                if any(str(s.get('task_id')) in crit_ids for s in succs):
                    connected += 1
                    continue
                # Or if any predecessor is critical (end-of-path activities)
                preds = self.engine.predecessors.get(cid, [])
                if any(str(p.get('task_id')) in crit_ids for p in preds):
                    connected += 1
            
            return round(connected / len(crit_ids), 3)
        except Exception:
            return None
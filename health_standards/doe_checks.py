"""
DOE PM-30 SCHEDULE ASSESSMENT
==============================
Based on:
- DOE Order 413.3B (Program & Project Management)
- DOE PM-30 Schedule Assessment Guide
- DOE-HDBK-1140-2001
- Plus: Open Ends and FS+Lag detection
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

    # ═══════════════════════════════════════════════════════
    # HELPER: WBS HIERARCHY
    # ═══════════════════════════════════════════════════════
    def _build_wbs_hierarchy(self):
        """Helper to compute WBS depth and subtree activity counts."""
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
        
        # Build children map to find truly empty subtrees
        children = defaultdict(list)
        for wid, w in by_id.items():
            p = parent_of(w)
            if p: children[p].append(wid)
            
        # Base activity counts per node
        acts_by_wbs = defaultdict(list)
        for a in self.activities:
            wid = str(a.get('wbs_id', ''))
            if wid: acts_by_wbs[wid].append(a)
            
        # Recursive subtree check
        def has_activities(wid, seen=None):
            seen = seen or set()
            if wid in seen: return False
            seen.add(wid)
            if acts_by_wbs[wid]: return True
            return any(has_activities(child, seen) for child in children.get(wid, []))
            
        empty_wbs = [w for wid, w in by_id.items() if not has_activities(wid)]
        
        return max_depth, empty_wbs, acts_by_wbs

    # ═══════════════════════════════════════════════════════
    # 1. PROJECT STRUCTURE
    # ═══════════════════════════════════════════════════════
    def _project_structure(self):
        checks = []
        total = len(self.activities) or 1
        
        max_depth, empty_wbs, acts_by_wbs = self._build_wbs_hierarchy()
        
        # DOE-101: WBS Coverage
        wbs_ids = set(a.get('wbs_id', '') for a in self.activities if a.get('wbs_id'))
        checks.append(self.make_metric(
            'DOE-101', 'WBS Nodes with Activities',
            f'{len(wbs_ids)} WBS nodes contain direct activities',
            len(wbs_ids), 'DOE', 'WBS Structure',
            threshold_min=1, severity='medium',
            recommendation='All work should be organized under WBS.'
        ))
        
        # DOE-102: Empty WBS Nodes (Subtree)
        checks.append(self.make_check(
            'DOE-102', 'Empty WBS Nodes (Subtree)',
            'WBS nodes with no activities in their entire branch',
            len(empty_wbs), len(self.wbs_nodes) or 1, 5, 'DOE', 'low', 'WBS Structure',
            'Remove empty WBS nodes or add planned activities.',
            empty_wbs
        ))
        
        # DOE-103: WBS Depth (Hierarchical)
        checks.append(self.make_metric(
            'DOE-103', 'Maximum WBS Depth',
            f'{max_depth} levels deep',
            max_depth, 'DOE', 'WBS Structure',
            threshold_min=3, threshold_max=7, severity='medium',
            recommendation='WBS depth should be 3-7 levels for healthy reporting.'
        ))
        
        # DOE-104 & 105: Activities per WBS
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

    # ═══════════════════════════════════════════════════════
    # 2. SCHEDULE INTEGRITY
    # ═══════════════════════════════════════════════════════
    def _schedule_integrity(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        
        # DOE-201: Total Activity Count
        checks.append(self.make_metric(
            'DOE-201', 'Total Activities',
            f'{len(self.activities)} activities in schedule',
            len(self.activities), 'DOE', 'Schedule Integrity',
            threshold_min=10, severity='low', info_only=True
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
        
        # DOE-203: LOE Percentage
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
                   and not self.is_milestone(a)]
        checks.append(self.make_check(
            'DOE-204', 'Zero Duration Non-Milestones',
            'Only milestones should have zero duration',
            len(zero_dur), total_inc, 1, 'DOE', 'high', 'Schedule Integrity',
            'Convert to milestones or add duration.',
            zero_dur
        ))
        
        # DOE-205: Long Duration Threshold (60 days for DOE)
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

    # ═══════════════════════════════════════════════════════
    # 3. RESOURCE MANAGEMENT
    # ═══════════════════════════════════════════════════════
    def _resource_management(self):
        checks = []
        
        # Guard: if no resources exist, gracefully skip cost checks
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
        
        # DOE-301: Resource Loading
        unresourced = [a for a in work_acts if a.get('task_id', '') not in tasks_with_res]
        checks.append(self.make_check(
            'DOE-301', 'Unresourced Work Activities',
            'DOE requires resource-loaded schedules',
            len(unresourced), work_total, 10, 'DOE', 'high', 'Resources',
            'Assign resources to all work activities.',
            unresourced
        ))
        
        # DOE-302: Cost Loading
        costed = [r for r in self.resources if self.to_float(r.get('target_cost', '0')) > 0]
        cost_pct = len(costed) / len(self.resources) * 100
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
        
        # Find unique activities for zero-cost resources
        zc_act_ids = {str(r.get('task_id')) for r in zero_cost_with_hours}
        zc_acts = [a for a in self.activities if str(a.get('task_id')) in zc_act_ids]
        
        checks.append(self.make_check(
            'DOE-303', 'Zero-Cost Resources with Hours',
            'Resources with hours must have costs',
            len(zero_cost_with_hours), len(self.resources) or 1, 5, 'DOE', 'medium', 'Resources',
            'Add rates/costs to all resource assignments.',
            zc_acts
        ))
        
        # DOE-304: Milestone Resources (should be none)
        mile_with_res = [a for a in self.milestones if str(a.get('task_id', '')) in tasks_with_res]
        checks.append(self.make_check(
            'DOE-304', 'Milestones with Resources',
            'Milestones should not have resource assignments',
            len(mile_with_res), max(len(self.milestones), 1), 5, 'DOE', 'medium', 'Resources',
            'Remove resources from milestones.',
            mile_with_res
        ))
        
        return {'name': 'Resource Management', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 4. PROGRESS MEASUREMENT
    # ═══════════════════════════════════════════════════════
    def _progress_measurement(self):
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
        
        # DOE-404: Progress Consistency (Softened logic to prevent scope-growth false positives)
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
        
        # DOE-405: Data Date Set
        checks.append(self.make_boolean(
            'DOE-405', 'Data Date Set',
            'Schedule must have a data date',
            self.data_date is not None, 'DOE', 'Progress',
            severity='critical',
            recommendation='Set a valid data date before analysis.'
        ))
        
        return {'name': 'Progress Measurement', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 5. RISK MANAGEMENT
    # ═══════════════════════════════════════════════════════
    def _risk_management(self):
        checks = []
        total_inc = len(self.incomplete) or 1
        
        # DOE-501: Critical Path Ratio (Incomplete only)
        crit_inc = [a for a in self.incomplete if a.get('is_critical')]
        cp_pct = len(crit_inc) / total_inc * 100
        checks.append(self.make_metric(
            'DOE-501', 'Critical Path Percentage',
            f'{cp_pct:.1f}% on critical path',
            cp_pct, 'DOE', 'Risk',
            threshold_min=5, threshold_max=25, severity='medium',
            recommendation='CP should be 5-25%. Too few = slack; too many = high risk.'
        ))
        
        # DOE-502: Near-Critical Activities (< 10 days float)
        near_crit = [a for a in self.incomplete if 0 < a.get('total_float_days', 0) <= 10]
        checks.append(self.make_metric(
            'DOE-502', 'Near-Critical Activities',
            f'{len(near_crit)} activities with <10 days float',
            len(near_crit), 'DOE', 'Risk',
            threshold_max=None, severity='medium', info_only=True,
            recommendation='Near-critical activities can quickly become critical.'
        ))
        
        # DOE-503: Total Float Distribution
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
        
        # DOE-504: Schedule Contingency
        if floats:
            avg_float = sum(floats) / len(floats)
            checks.append(self.make_metric(
                'DOE-504', 'Average Total Float (Contingency)',
                f'{avg_float:.1f} days average',
                avg_float, 'DOE', 'Risk',
                threshold_min=0, severity='low', info_only=True
            ))
        
        # DOE-505: Negative Float
        neg_float = [a for a in self.incomplete if a.get('total_float_days', 0) < 0]
        checks.append(self.make_check(
            'DOE-505', 'Negative Float Activities',
            'Activities behind schedule constraints',
            len(neg_float), total_inc, 0, 'DOE', 'critical', 'Risk',
            'Immediate recovery planning required for negative float.',
            neg_float
        ))
        
        return {'name': 'Risk Management', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 6. EARNED VALUE
    # ═══════════════════════════════════════════════════════
    def _earned_value_checks(self):
        checks = []
        
        # DOE-601: Target Dates (Baseline Proxy)
        with_target = sum(1 for a in self.real_activities if a.get('target_start_date', ''))
        target_pct = with_target / max(len(self.real_activities), 1) * 100
        checks.append(self.make_metric(
            'DOE-601', 'Activities with Target Dates',
            f'{target_pct:.1f}% have target (baseline) dates',
            target_pct, 'DOE', 'Earned Value',
            threshold_min=100, severity='high',
            recommendation='All activities need baseline/target dates for EVM.'
        ))
        
        # DOE-602: WBS Levels for EV Reporting
        max_depth, _, _ = self._build_wbs_hierarchy()
        checks.append(self.make_metric(
            'DOE-602', 'WBS Depth for EV Reporting',
            f'{max_depth} levels',
            max_depth, 'DOE', 'Earned Value',
            threshold_min=3, severity='medium',
            recommendation='EV reporting needs at least 3 WBS levels.'
        ))
        
        return {'name': 'Earned Value Compliance', 'checks': checks}

    # ═══════════════════════════════════════════════════════
    # 7. LOGIC NETWORK QUALITY
    # ═══════════════════════════════════════════════════════
    def _logic_network_quality(self):
        checks = []
        total = len(self.incomplete) or 1
        
        # Shared helpers from base_checker
        open_start = self.open_start_activities()
        open_end = self.open_end_activities()
        active_rels = self.active_relationships()
        rel_total = len(active_rels) or 1
        
        # DOE-701: Open Starts
        checks.append(self.make_check(
            'DOE-701', 'Open Start Activities',
            'Non-milestone activities without predecessors',
            len(open_start), total, 1, 'DOE', 'high', 'Logic Network',
            'DOE PM-30 requires closed-loop logic. Only start milestones should have no predecessors.',
            open_start
        ))
        
        # DOE-702: Open Ends
        checks.append(self.make_check(
            'DOE-702', 'Open End Activities',
            'Non-milestone activities without successors',
            len(open_end), total, 1, 'DOE', 'high', 'Logic Network',
            'DOE PM-30 requires closed-loop logic. Only finish milestones should have no successors.',
            open_end
        ))
        
        # DOE-703: Negative Lags
        neg_lags = [r for r in active_rels if r.get('lag_days', 0) < 0]
        checks.append(self.make_check(
            'DOE-703', 'Negative Lags (Leads)',
            'DOE does not permit negative lags',
            len(neg_lags), rel_total, 0, 'DOE', 'high', 'Logic Network',
            'Remove all negative lags per DOE guidelines.',
            neg_lags
        ))
        
        # DOE-704: Excessive Lags
        big_lags = [r for r in active_rels if r.get('lag_days', 0) > 15]
        checks.append(self.make_check(
            'DOE-704', 'Large Lags (>15 days)',
            'DOE recommends minimizing lags',
            len(big_lags), rel_total, 3, 'DOE', 'medium', 'Logic Network',
            'Convert large lags into schedule activities.',
            big_lags
        ))
        
        # DOE-705: Non-FS Relationships
        non_fs = [r for r in active_rels if r.get('pred_type') != 'PR_FS']
        checks.append(self.make_check(
            'DOE-705', 'Non-FS Relationships',
            'DOE prefers Finish-to-Start relationships',
            len(non_fs), rel_total, 10, 'DOE', 'medium', 'Logic Network',
            'Use FS relationships wherever possible.',
            non_fs
        ))
        
        # DOE-FS-LAG: FS with Lag
        fs_lag = self.fs_with_lag()
        checks.append(self.make_check(
            'DOE-FS-LAG', 'FS + Lag Relationships',
            'Finish-to-Start relationships with lag',
            len(fs_lag), rel_total, 3, 'DOE', 'medium', 'Logic Network',
            'DOE PM-30 discourages lags. Replace with real activities (e.g., "Cure Time").',
            fs_lag
        ))
        
        return {'name': 'Logic Network Quality', 'checks': checks}
"""
NASA NPR 7120.5 SCHEDULE MANAGEMENT
====================================
Enhanced checks based on:
- NASA NPR 7120.5F (NASA Space Flight PM Requirements)
- NASA Schedule Management Handbook (NASA/SP-2010-3403)
- NASA Cost Estimating Handbook
- Plus: Open Ends detection
"""

from health_standards.base_checker import BaseChecker
from collections import Counter
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

    def _schedule_structure(self):
        """NASA schedule structure requirements."""
        checks = []
        total = len(self.activities) or 1
        
        # NASA-101: Integrated Master Schedule (IMS) Size
        checks.append(self.make_metric(
            'NASA-101', 'IMS Activity Count',
            f'{len(self.activities)} activities',
            len(self.activities), 'NASA', 'Structure',
            threshold_min=100, severity='low',
            info_only=True,
            recommendation='IMS should contain sufficient detail for management.'
        ))
        
        # NASA-102: WBS Alignment
        wbs_ids = set(a.get('wbs_id', '') for a in self.activities)
        coverage = len(wbs_ids) / max(len(self.wbs_nodes), 1) * 100
        checks.append(self.make_metric(
            'NASA-102', 'WBS Coverage',
            f'{coverage:.1f}% of WBS nodes have activities',
            coverage, 'NASA', 'Structure',
            threshold_min=80, severity='medium',
            recommendation='Ensure comprehensive WBS-to-activity mapping.'
        ))
        
        # NASA-103: Activity Naming Standard
        no_name = [a for a in self.activities if not a.get('task_name', '').strip()]
        checks.append(self.make_check(
            'NASA-103', 'Missing Activity Names',
            'All activities must have descriptive names',
            len(no_name), total, 0, 'NASA', 'critical', 'Structure',
            'Add descriptive names to all activities.',
            no_name
        ))
        
        # NASA-104: Verb-First Naming (Best Practice Estimate)
        short_names = [a for a in self.activities 
                      if len(a.get('task_name', '').strip()) < 10]
        checks.append(self.make_check(
            'NASA-104', 'Very Short Activity Names (<10 chars)',
            'NASA recommends descriptive verb-based names',
            len(short_names), total, 3, 'NASA', 'medium', 'Structure',
            'Use verb-based descriptive names (e.g., "Design Panel", "Test Interface").',
            short_names
        ))
        
        # NASA-105: Duplicate Activity Names
        name_counts = Counter(a.get('task_name', '') for a in self.activities 
                             if a.get('task_name'))
        duplicates = sum(c for c in name_counts.values() if c > 1)
        checks.append(self.make_check(
            'NASA-105', 'Duplicate Activity Names',
            'Activity names should be unique for clarity',
            duplicates, total, 5, 'NASA', 'medium', 'Structure',
            'Add distinguishing context to duplicate names.'
        ))
        
        # NASA-106: Activity ID Consistency
        id_lengths = [len(a.get('task_code', '')) for a in self.activities 
                     if a.get('task_code')]
        unique_lengths = len(set(id_lengths)) if id_lengths else 0
        checks.append(self.make_metric(
            'NASA-106', 'Activity ID Format Consistency',
            f'{unique_lengths} different ID lengths',
            unique_lengths, 'NASA', 'Structure',
            threshold_max=3, severity='low',
            recommendation='Use consistent ID formatting across all activities.'
        ))
        
        return {'name': 'Schedule Structure', 'checks': checks}

    def _logic_integrity(self):
        """NASA logic and network integrity + Open Ends."""
        checks = []
        total = len(self.real_activities) or 1
        rel_total = len(self.relationships) or 1
        
        # NASA-201: Logic Density
        density = len(self.relationships) / len(self.activities) if self.activities else 0
        checks.append(self.make_metric(
            'NASA-201', 'Logic Density',
            f'{density:.2f} relationships per activity',
            density, 'NASA', 'Logic',
            threshold_min=1.5, threshold_max=3.5, severity='medium',
            recommendation='NASA guideline: 1.5-3.5 relationships per activity.'
        ))
        
        # ─── NASA-202: Open Start Activities (Enhanced) ───
        open_start = [a for a in self.real_activities 
                     if a.get('task_id', '') not in self.engine.predecessors
                     and a.get('task_type') not in ['TT_Mile']]
        checks.append(self.make_check(
            'NASA-202', 'Open Start Activities',
            'Only start milestones should have no predecessors',
            len(open_start), total, 1, 'NASA', 'high', 'Logic',
            'Add predecessors to eliminate dangling activities.',
            open_start
        ))
        
        # ─── NASA-203: Open End Activities (Enhanced) ───
        open_end = [a for a in self.real_activities 
                   if a.get('task_id', '') not in self.engine.successors
                   and a.get('task_type') not in ['TT_FinMile']]
        checks.append(self.make_check(
            'NASA-203', 'Open End Activities',
            'Only finish milestones should have no successors',
            len(open_end), total, 1, 'NASA', 'high', 'Logic',
            'Add successors to eliminate dangling activities.',
            open_end
        ))
        
        # NASA-204: Preferred Relationships (FS)
        fs_rels = [r for r in self.relationships if r.get('pred_type') == 'PR_FS']
        fs_pct = len(fs_rels) / rel_total * 100
        checks.append(self.make_metric(
            'NASA-204', 'Finish-to-Start Percentage',
            f'{fs_pct:.1f}% are FS relationships',
            fs_pct, 'NASA', 'Logic',
            threshold_min=85, severity='medium',
            recommendation='NASA prefers 85%+ FS relationships.'
        ))
        
        # NASA-205: Cross-WBS Relationships
        cross_wbs = 0
        for r in self.relationships:
            pred = self.engine.activity_by_id.get(r.get('pred_task_id'), {})
            succ = self.engine.activity_by_id.get(r.get('task_id'), {})
            if pred.get('wbs_id') != succ.get('wbs_id'):
                cross_wbs += 1
        
        cross_pct = cross_wbs / rel_total * 100
        checks.append(self.make_metric(
            'NASA-205', 'Cross-WBS Relationships',
            f'{cross_pct:.1f}% cross WBS boundaries',
            cross_pct, 'NASA', 'Logic',
            threshold_max=None, severity='low',
            info_only=True,
            recommendation='Cross-WBS logic is normal but should be reviewed.'
        ))
        
        # NASA-206: Total Relationships
        checks.append(self.make_metric(
            'NASA-206', 'Total Relationships',
            f'{len(self.relationships)} logic ties',
            len(self.relationships), 'NASA', 'Logic',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        # NASA-207: Excessive Predecessors (Complex Activities)
        too_many_preds = [a for a in self.real_activities 
                         if len(self.engine.predecessors.get(a.get('task_id', ''), [])) > 10]
        checks.append(self.make_check(
            'NASA-207', 'Activities with >10 Predecessors',
            'Complex activities may need decomposition',
            len(too_many_preds), total, 3, 'NASA', 'low', 'Logic',
            'Consider using summary milestones to reduce complexity.',
            too_many_preds
        ))
        
        # NASA-208: Excessive Successors
        too_many_succs = [a for a in self.real_activities 
                         if len(self.engine.successors.get(a.get('task_id', ''), [])) > 10]
        checks.append(self.make_check(
            'NASA-208', 'Activities with >10 Successors',
            'High-influence activities represent risk concentration',
            len(too_many_succs), total, 3, 'NASA', 'low', 'Logic',
            'Review activities driving many successors.',
            too_many_succs
        ))
        
        # ─── NEW: NASA-FS-LAG: FS Relationships with Lag ───
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
            'NASA-FS-LAG', 'FS + Lag Relationships',
            'NASA guidance discourages FS relationships with lag',
            len(fs_lag), rel_total, 3, 'NASA', 'medium', 'Logic',
            'Replace lag with a schedule activity for transparency.',
            affected
        ))
        
        return {'name': 'Logic & Network Integrity', 'checks': checks}

    def _duration_analysis(self):
        """Duration quality analysis."""
        checks = []
        total = len(self.incomplete) or 1
        
        durations = [a.get('original_duration_days', 0) for a in self.real_activities 
                    if a.get('original_duration_days', 0) > 0]
        
        # NASA-301: Duration Statistics
        if durations:
            mean_dur = statistics.mean(durations)
            median_dur = statistics.median(durations)
            
            checks.append(self.make_metric(
                'NASA-301', 'Average Duration',
                f'{mean_dur:.1f} days',
                mean_dur, 'NASA', 'Duration',
                threshold_min=1, threshold_max=30, severity='low',
                info_only=True,
                recommendation='NASA typical: 5-20 days average.'
            ))
            
            checks.append(self.make_metric(
                'NASA-302', 'Median Duration',
                f'{median_dur:.1f} days',
                median_dur, 'NASA', 'Duration',
                threshold_min=1, threshold_max=25, severity='low',
                info_only=True
            ))
            
            if len(durations) > 1:
                stdev_dur = statistics.stdev(durations)
                checks.append(self.make_metric(
                    'NASA-303', 'Duration Std Deviation',
                    f'{stdev_dur:.1f} days',
                    stdev_dur, 'NASA', 'Duration',
                    threshold_max=None, severity='low',
                    info_only=True
                ))
        
        # NASA-304: Very Short Activities
        very_short = [a for a in self.incomplete 
                     if 0 < a.get('original_duration_days', 0) < 2
                     and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        checks.append(self.make_check(
            'NASA-304', 'Very Short Activities (<2 days)',
            'May need consolidation',
            len(very_short), total, 5, 'NASA', 'low', 'Duration',
            'Consider consolidating micro-activities.',
            very_short
        ))
        
        # NASA-305: Excessive Duration (NASA >88 days)
        excessive = [a for a in self.incomplete 
                    if a.get('original_duration_days', 0) > 88
                    and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']]
        checks.append(self.make_check(
            'NASA-305', 'Excessive Duration (>88 days)',
            'NASA recommends max 88-day activities',
            len(excessive), total, 2, 'NASA', 'medium', 'Duration',
            'Break down activities over 88 days.',
            excessive
        ))
        
        return {'name': 'Duration Analysis', 'checks': checks}

    def _milestone_management(self):
        """Milestone quality checks."""
        checks = []
        total = len(self.activities) or 1
        
        # NASA-401: Milestone Count
        mile_pct = len(self.milestones) / total * 100
        checks.append(self.make_metric(
            'NASA-401', 'Milestone Percentage',
            f'{mile_pct:.1f}% are milestones',
            mile_pct, 'NASA', 'Milestones',
            threshold_min=3, threshold_max=15, severity='medium',
            recommendation='NASA guideline: 3-15% milestones.'
        ))
        
        # NASA-402: Milestones with Duration (should be zero)
        mile_with_dur = [a for a in self.milestones 
                        if a.get('original_duration_days', 0) > 0]
        checks.append(self.make_check(
            'NASA-402', 'Milestones with Duration',
            'Milestones must have zero duration',
            len(mile_with_dur), max(len(self.milestones), 1), 0, 'NASA', 'critical', 'Milestones',
            'Set milestone durations to zero.',
            mile_with_dur
        ))
        
        # NASA-403: Milestone Predecessors
        mile_no_pred = [a for a in self.milestones 
                       if a.get('task_type') == 'TT_FinMile'
                       and a.get('task_id', '') not in self.engine.predecessors]
        checks.append(self.make_check(
            'NASA-403', 'Finish Milestones Without Predecessors',
            'Finish milestones must have predecessors',
            len(mile_no_pred), max(len(self.milestones), 1), 0, 'NASA', 'high', 'Milestones',
            'Add predecessors to finish milestones.',
            mile_no_pred
        ))
        
        # NASA-404: Key Milestone Coverage
        checks.append(self.make_metric(
            'NASA-404', 'Total Milestones',
            f'{len(self.milestones)} milestones',
            len(self.milestones), 'NASA', 'Milestones',
            threshold_min=5, severity='medium',
            recommendation='NASA projects typically need multiple key milestones.'
        ))
        
        return {'name': 'Milestone Management', 'checks': checks}

    def _critical_path_analysis(self):
        """Critical path analysis."""
        checks = []
        total = len(self.real_activities) or 1
        
        cp_count = len(self.engine.critical_activities)
        cp_pct = cp_count / total * 100
        
        # NASA-501: Critical Path Length
        checks.append(self.make_metric(
            'NASA-501', 'Critical Path Activities',
            f'{cp_count} activities ({cp_pct:.1f}%)',
            cp_pct, 'NASA', 'Critical Path',
            threshold_min=5, threshold_max=25, severity='medium',
            recommendation='NASA guideline: CP should be 5-25% of activities.'
        ))
        
        # NASA-502: Critical Path Continuity
        cp_valid = cp_count > 0
        checks.append(self.make_boolean(
            'NASA-502', 'Critical Path Exists',
            'Schedule must have a critical path',
            cp_valid, 'NASA', 'Critical Path',
            severity='critical',
            recommendation='Must have valid CPM critical path.'
        ))
        
        # NASA-503: Near-Critical (<5 days float)
        near = [a for a in self.incomplete 
               if 0 < a.get('total_float_days', 0) <= 5]
        near_pct = len(near) / total * 100
        checks.append(self.make_metric(
            'NASA-503', 'Near-Critical (<5 days float)',
            f'{near_pct:.1f}% near-critical',
            near_pct, 'NASA', 'Critical Path',
            threshold_max=15, severity='medium',
            recommendation='High near-critical percentage = high schedule risk.'
        ))
        
        # NASA-504: Total Float Range
        floats = [a.get('total_float_days', 0) for a in self.incomplete]
        if floats:
            max_float = max(floats)
            min_float = min(floats)
            checks.append(self.make_metric(
                'NASA-504', 'Float Range',
                f'{min_float:.0f} to {max_float:.0f} days',
                max_float, 'NASA', 'Critical Path',
                threshold_max=200, severity='low',
                info_only=True
            ))
        
        return {'name': 'Critical Path Analysis', 'checks': checks}

    def _risk_maturity(self):
        """Schedule maturity and risk."""
        checks = []
        total = len(self.activities) or 1
        
        # NASA-601: Data Date Currency
        if self.data_date:
            from datetime import datetime
            days_old = (datetime.now() - self.data_date).days
            checks.append(self.make_metric(
                'NASA-601', 'Data Date Age',
                f'{days_old} days old',
                days_old, 'NASA', 'Maturity',
                threshold_max=30, severity='medium',
                recommendation='Data date should be updated regularly (≤30 days).'
            ))
        
        # NASA-602: Percent Complete Distribution
        complete_pct = len(self.completed) / total * 100
        checks.append(self.make_metric(
            'NASA-602', 'Overall Completion',
            f'{complete_pct:.1f}% complete',
            complete_pct, 'NASA', 'Maturity',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        # NASA-603: In-Progress Activities
        checks.append(self.make_metric(
            'NASA-603', 'Active Activities',
            f'{len(self.in_progress)} in progress',
            len(self.in_progress), 'NASA', 'Maturity',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        # NASA-604: Not Started Ratio
        ns_pct = len(self.not_started) / total * 100
        checks.append(self.make_metric(
            'NASA-604', 'Not Started Percentage',
            f'{ns_pct:.1f}%',
            ns_pct, 'NASA', 'Maturity',
            threshold_min=0, severity='low',
            info_only=True
        ))
        
        # NASA-605: Baseline Established
        with_bl = sum(1 for a in self.activities if a.get('target_start_date', ''))
        bl_pct = with_bl / total * 100
        checks.append(self.make_metric(
            'NASA-605', 'Baseline Coverage',
            f'{bl_pct:.1f}% have baseline',
            bl_pct, 'NASA', 'Maturity',
            threshold_min=100, severity='high',
            recommendation='All activities must have baseline dates.'
        ))
        
        return {'name': 'Schedule Maturity & Risk', 'checks': checks}
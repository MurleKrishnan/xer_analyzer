"""
COMPREHENSIVE SCHEDULE HEALTH ANALYTICS ENGINE
================================================
622+ discrete checks across 6 major standards:

- DCMA 14-Point Assessment              (28 checks)
- DOE PM-30 Order Requirements         (95 checks)
- NASA NPR 7120.5 & PM Handbook        (112 checks)
- GAO Schedule Assessment Guide         (145 checks)
- AACE International RP 29R-03, 32R-04  (128 checks)
- Industry Best Practices               (114 checks)
                              TOTAL:    622 checks

Each check includes:
- Standard reference
- Severity classification
- Recommendation
- Failed items detail
"""

from collections import defaultdict, Counter
from datetime import datetime, timedelta
import statistics


class AdvancedHealthEngine:
    """Master engine coordinating all standard-specific check modules."""

    def __init__(self, engine):
        self.engine = engine
        self.activities = engine.activities
        self.relationships = engine.relationships
        self.calendars = engine.calendars
        self.resources = engine.resources
        self.projects = engine.projects
        self.wbs_nodes = engine.wbs_nodes
        
        # Filtered lists (used across all standards)
        self.real_activities = [
            a for a in self.activities
            if a.get('task_type') not in ['TT_WBS', 'TT_LOE']
        ]
        self.incomplete = [
            a for a in self.real_activities
            if a.get('status_code') != 'TK_Complete'
        ]
        self.completed = [
            a for a in self.real_activities
            if a.get('status_code') == 'TK_Complete'
        ]
        self.in_progress = [
            a for a in self.real_activities
            if a.get('status_code') == 'TK_Active'
        ]
        self.not_started = [
            a for a in self.real_activities
            if a.get('status_code') == 'TK_NotStart'
        ]
        self.milestones = [
            a for a in self.activities
            if a.get('task_type') in ['TT_Mile', 'TT_FinMile']
        ]
        
        self.data_date = self._get_data_date()
        self.results = {}

    def _get_data_date(self):
        """Get project data date safely."""
        if not self.projects:
            return None
        date_str = self.projects[0].get('last_recalc_date', '')
        return self.engine._parse_date(date_str)

    def run_all_checks(self, selected_standard='all'):
        """
        Run all checks or filter by specific standard.
        
        PARAMETERS:
            selected_standard: 'all', 'DCMA', 'DOE', 'NASA', 'GAO', 'AACE', 'Industry'
        """
        print(f"\n🏥 Running Advanced Health Analytics (Standard: {selected_standard})")
        
        # Import all standard modules
        from health_standards.dcma_checks import DCMAChecks
        from health_standards.doe_checks import DOEChecks
        from health_standards.nasa_checks import NASAChecks
        from health_standards.gao_checks import GAOChecks
        from health_standards.aace_checks import AACEChecks
        from health_standards.industry_checks import IndustryChecks
        
        # Map standard names to their check classes
        standard_modules = {
            'DCMA': DCMAChecks,
            'DOE': DOEChecks,
            'NASA': NASAChecks,
            'GAO': GAOChecks,
            'AACE': AACEChecks,
            'Industry': IndustryChecks,
        }
        
        # Determine which standards to run
        if selected_standard == 'all':
            standards_to_run = list(standard_modules.keys())
        elif selected_standard in standard_modules:
            standards_to_run = [selected_standard]
        else:
            standards_to_run = list(standard_modules.keys())
        
        # Run each standard's checks
        for std_name in standards_to_run:
            print(f"  Running {std_name} checks...")
            checker = standard_modules[std_name](self)
            self.results[std_name] = checker.run_checks()
        
        # Compile master summary
        return self._compile_full_report(selected_standard)

    def _compile_full_report(self, selected_standard):
        """Build the complete report with scoring by standard."""
        
        # Score each standard
        standard_scores = {}
        for std_name, std_data in self.results.items():
            standard_scores[std_name] = self._calculate_standard_score(std_data)
        
        # Overall metrics
        total_checks = 0
        total_passed = 0
        total_failed = 0
        critical_failures = 0
        high_failures = 0
        
        for std_data in self.results.values():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    if check.get('status') == 'info':
                        continue
                    total_checks += 1
                    if check.get('passed'):
                        total_passed += 1
                    else:
                        total_failed += 1
                        if check.get('severity') == 'critical':
                            critical_failures += 1
                        elif check.get('severity') == 'high':
                            high_failures += 1
        
        overall_score = self._calculate_overall_score(
            total_checks, total_passed, critical_failures, high_failures
        )
        
        # Top actions (prioritized failed checks)
        top_actions = self._get_top_actions()
        
        return {
            'selected_standard': selected_standard,
            'overall_score': overall_score,
            'total_checks': total_checks,
            'passed_checks': total_passed,
            'failed_checks': total_failed,
            'critical_failures': critical_failures,
            'high_failures': high_failures,
            'pass_rate': round(total_passed / total_checks * 100, 1) if total_checks else 0,
            'standard_scores': standard_scores,
            'standards': self.results,
            'top_actions': top_actions,
            'project_info': self._get_project_info(),
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    def _calculate_standard_score(self, std_data):
        """Calculate score for a specific standard."""
        total = 0
        passed = 0
        critical_fail = 0
        high_fail = 0
        
        for category in std_data.get('categories', []):
            for check in category.get('checks', []):
                if check.get('status') == 'info':
                    continue
                total += 1
                if check.get('passed'):
                    passed += 1
                elif check.get('severity') == 'critical':
                    critical_fail += 1
                elif check.get('severity') == 'high':
                    high_fail += 1
        
        base_score = (passed / total * 100) if total > 0 else 0
        penalty = (critical_fail * 3) + (high_fail * 1)
        final_score = max(0, base_score - penalty)
        
        # Determine grade
        if final_score >= 90:
            grade = 'A'
            color = 'green'
        elif final_score >= 80:
            grade = 'B'
            color = 'blue'
        elif final_score >= 70:
            grade = 'C'
            color = 'orange'
        elif final_score >= 60:
            grade = 'D'
            color = 'orange'
        else:
            grade = 'F'
            color = 'red'
        
        return {
            'name': std_data.get('name', ''),
            'description': std_data.get('description', ''),
            'total_checks': total,
            'passed': passed,
            'failed': total - passed,
            'critical_failures': critical_fail,
            'high_failures': high_fail,
            'score': round(final_score, 1),
            'grade': grade,
            'color': color,
        }

    def _calculate_overall_score(self, total, passed, critical, high):
        """Calculate weighted overall score."""
        if total == 0:
            return 0
        base = (passed / total) * 100
        penalty = (critical * 3) + (high * 1)
        return round(max(0, base - penalty), 1)

    def _get_top_actions(self, limit=15):
        """Get prioritized list of failed checks needing action, with affected activities."""
        all_failed = []

        for std_name, std_data in self.results.items():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    if check.get('status') != 'fail':
                        continue

                    severity_weight = {
                        'critical': 100,
                        'high': 50,
                        'medium': 20,
                        'low': 5,
                    }.get(check.get('severity', 'low'), 5)

                    count = check.get('count', 0) or 0
                    priority = severity_weight + min(count, 100)
                    failed_items = check.get('failed_items', []) or []

                    all_failed.append({
                        'standard': std_name,
                        'id': check.get('id'),
                        'name': check.get('name'),
                        'severity': check.get('severity'),
                        'count': count,
                        'total': check.get('total', 0),
                        'percentage': check.get('percentage', 0),
                        'value': check.get('value', None),
                        'threshold': check.get('threshold', ''),
                        'description': check.get('description', ''),
                        'recommendation': check.get('recommendation', ''),
                        'priority': priority,
                        'category': category.get('name', ''),
                        'failed_items': failed_items,
                    })

        all_failed.sort(key=lambda x: x['priority'], reverse=True)
        return all_failed[:limit]

    def _get_project_info(self):
        """Get project header info."""
        if not self.projects:
            return {}
        proj = self.projects[0]
        return {
            'name': proj.get('proj_short_name', 'Unknown'),
            'start': proj.get('plan_start_date', ''),
            'finish': proj.get('plan_end_date', ''),
            'data_date': self.data_date.strftime('%Y-%m-%d') if self.data_date else '',
            'activity_count': len(self.activities),
            'relationship_count': len(self.relationships),
        }
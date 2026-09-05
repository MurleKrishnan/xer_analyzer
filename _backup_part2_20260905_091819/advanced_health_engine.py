"""
COMPREHENSIVE SCHEDULE HEALTH ANALYTICS ENGINE
================================================
622+ discrete checks across 6 major standards:

- DCMA 14-Point Assessment              (28 checks)
- DOE PM-30 Order Requirements          (95 checks)
- NASA NPR 7120.5 & PM Handbook         (112 checks)
- GAO Schedule Assessment Guide         (145 checks)
- AACE International RP 29R-03, 32R-04  (128 checks)
- Industry Best Practices               (114 checks)

Orchestrates execution, caching, and score compilation.
"""

from collections import defaultdict, Counter
from datetime import datetime
import logging

# Move imports to top level to avoid overhead on every API call
from health_standards.dcma_checks import DCMAChecks
from health_standards.doe_checks import DOEChecks
from health_standards.nasa_checks import NASAChecks
from health_standards.gao_checks import GAOChecks
from health_standards.aace_checks import AACEChecks
from health_standards.industry_checks import IndustryChecks

logger = logging.getLogger(__name__)


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
        
        # ─── SHARED FILTERED LISTS ───
        # WBS summaries excluded from all logic
        self.real_including_loe = [
            a for a in self.activities if a.get('task_type') != 'TT_WBS'
        ]
        # Standard filter: excludes both WBS and LOE
        self.real_activities = [
            a for a in self.real_including_loe if a.get('task_type') != 'TT_LOE'
        ]
        
        self.incomplete = [
            a for a in self.real_activities if a.get('status_code') != 'TK_Complete'
        ]
        self.completed = [
            a for a in self.real_activities if a.get('status_code') == 'TK_Complete'
        ]
        self.in_progress = [
            a for a in self.real_activities if a.get('status_code') == 'TK_Active'
        ]
        self.not_started = [
            a for a in self.real_activities if a.get('status_code') == 'TK_NotStart'
        ]
        self.milestones = [
            a for a in self.activities if a.get('task_type') in ['TT_Mile', 'TT_FinMile']
        ]
        
        self.data_date = self._get_data_date()
        self.results = {}

    def _get_data_date(self):
        """Get project data date safely."""
        if not self.projects:
            return None
        date_str = self.projects[0].get('last_recalc_date', '')
        return self.engine._parse_date(date_str)

    def run_all_checks(self, selected_standard='all', force=False):
        """
        Run all checks or filter by specific standard, using cache when available.
        """
        # ─── CACHE CHECK ───
        # Cache is stored on the underlying ScheduleEngine so it persists across API requests
        if not hasattr(self.engine, 'health_cache'):
            self.engine.health_cache = {}
            
        cache_key = selected_standard
        if not force and cache_key in self.engine.health_cache:
            logger.info(f"⚡ Returning cached health data for: {selected_standard}")
            return self.engine.health_cache[cache_key]

        logger.info(f"🏥 Running Advanced Health Analytics (Standard: {selected_standard})")
        
        standard_modules = {
            'DCMA': DCMAChecks,
            'DOE': DOEChecks,
            'NASA': NASAChecks,
            'GAO': GAOChecks,
            'AACE': AACEChecks,
            'Industry': IndustryChecks,
        }
        
        if selected_standard == 'all':
            standards_to_run = list(standard_modules.keys())
        elif selected_standard in standard_modules:
            standards_to_run = [selected_standard]
        else:
            standards_to_run = list(standard_modules.keys())
        
        for std_name in standards_to_run:
            logger.info(f"  Running {std_name} checks...")
            checker = standard_modules[std_name](self)
            self.results[std_name] = checker.run_checks()
        
        report = self._compile_full_report(selected_standard)
        
        # Save to cache
        self.engine.health_cache[cache_key] = report
        return report

    def _compile_full_report(self, selected_standard):
        """Build the complete report, enforce schema, and calculate scores."""
        
        # 1. Enforce Status/Passed Contract to prevent UI drift
        for std_data in self.results.values():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    # Ensure passed boolean perfectly matches status string
                    if check.get('status') == 'fail':
                        check['passed'] = False
                    elif check.get('status') == 'pass':
                        check['passed'] = True

        # 2. Score each standard
        standard_scores = {}
        for std_name, std_data in self.results.items():
            standard_scores[std_name] = self._calculate_standard_score(std_data)
        
        # 3. Overall metrics (Weighted approach)
        total_checks = 0
        total_passed = 0
        total_failed = 0
        critical_failures = 0
        high_failures = 0
        
        weights = {'critical': 5, 'high': 3, 'medium': 2, 'low': 1, 'info': 0}
        earned_points = 0
        possible_points = 0
        
        for std_data in self.results.values():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    if check.get('status') in ['info', 'na']:
                        continue
                        
                    total_checks += 1
                    weight = weights.get(check.get('severity', 'low'), 1)
                    possible_points += weight
                    
                    if check.get('passed'):
                        total_passed += 1
                        earned_points += weight
                    else:
                        total_failed += 1
                        if check.get('severity') == 'critical':
                            critical_failures += 1
                        elif check.get('severity') == 'high':
                            high_failures += 1
        
        overall_score = (earned_points / possible_points * 100) if possible_points > 0 else 100.0
        overall_score = round(overall_score, 1)
        
        # 4. Top actions (Prioritized failed checks - get all for PDF/Excel)
        all_actions = self._get_top_actions(limit=None)
        
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
            'top_actions': all_actions,  # UI slices to 15, Exports use all
            'project_info': self._get_project_info(),
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    def _calculate_standard_score(self, std_data):
        """Calculate weighted score and letter grade for a specific standard."""
        total = 0
        passed = 0
        critical_fail = 0
        high_fail = 0
        
        weights = {'critical': 5, 'high': 3, 'medium': 2, 'low': 1, 'info': 0}
        earned = 0
        possible = 0
        
        for category in std_data.get('categories', []):
            for check in category.get('checks', []):
                if check.get('status') in ['info', 'na']:
                    continue
                    
                total += 1
                w = weights.get(check.get('severity', 'low'), 1)
                possible += w
                
                if check.get('passed'):
                    passed += 1
                    earned += w
                else:
                    if check.get('severity') == 'critical':
                        critical_fail += 1
                    elif check.get('severity') == 'high':
                        high_fail += 1
        
        score = (earned / possible * 100) if possible > 0 else 100.0
        score = round(score, 1)
        
        # Determine grade
        if score >= 90:
            grade, color = 'A', 'green'
        elif score >= 80:
            grade, color = 'B', 'blue'
        elif score >= 70:
            grade, color = 'C', 'orange'
        elif score >= 60:
            grade, color = 'D', 'orange'
        else:
            grade, color = 'F', 'red'
        
        return {
            'name': std_data.get('name', ''),
            'description': std_data.get('description', ''),
            'total_checks': total,
            'passed': passed,
            'failed': total - passed,
            'critical_failures': critical_fail,
            'high_failures': high_fail,
            'score': score,
            'grade': grade,
            'color': color,
        }

    def _get_top_actions(self, limit=None):
        """Get prioritized list of failed checks needing action."""
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
                    # Higher severity rules, then highest impact count
                    priority = severity_weight + min(count, 100)

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
                        'failed_items': check.get('failed_items', []),
                    })

        all_failed.sort(key=lambda x: x['priority'], reverse=True)
        
        if limit is not None:
            return all_failed[:limit]
        return all_failed

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
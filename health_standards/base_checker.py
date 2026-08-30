"""
BASE CHECKER
============
Provides common check-building methods used by all standard modules.
"""

from collections import Counter, defaultdict
import statistics


class BaseChecker:
    """Base class with shared utility methods for all standard checkers."""

    def __init__(self, health_engine):
        """
        PARAMETERS:
            health_engine: The parent AdvancedHealthEngine instance
        """
        self.engine = health_engine.engine
        self.parent = health_engine
        
        # Convenient shortcuts
        self.activities = health_engine.activities
        self.real_activities = health_engine.real_activities
        self.incomplete = health_engine.incomplete
        self.completed = health_engine.completed
        self.in_progress = health_engine.in_progress
        self.not_started = health_engine.not_started
        self.milestones = health_engine.milestones
        self.relationships = health_engine.relationships
        self.resources = health_engine.resources
        self.calendars = health_engine.calendars
        self.projects = health_engine.projects
        self.wbs_nodes = health_engine.wbs_nodes
        self.data_date = health_engine.data_date

    # ═══════════════════════════════════════════
    # CHECK BUILDERS
    # ═══════════════════════════════════════════

    def make_check(self, id, name, desc, count, total, threshold_pct,
                   standard, severity, category='General',
                   recommendation='', failed_items=None):
        """Standard percentage-based check."""
        pct = (count / total * 100) if total > 0 else 0
        passed = pct <= threshold_pct
        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'count': count,
            'total': total,
            'percentage': round(pct, 2),
            'threshold': f'≤ {threshold_pct}%',
            'passed': passed,
            'status': 'pass' if passed else 'fail',
            'standard': standard,
            'severity': severity,
            'recommendation': recommendation,
            'failed_items': self.format_items(failed_items or []),
        }

    def make_metric(self, id, name, desc, value, standard, category='General',
                    threshold_min=None, threshold_max=None,
                    severity='medium', recommendation='', info_only=False,
                    unit=''):
        """Numeric metric-based check."""
        if info_only:
            passed = True
            threshold_text = 'Informational'
        elif threshold_min is not None and threshold_max is not None:
            passed = threshold_min <= value <= threshold_max
            threshold_text = f'{threshold_min} ≤ x ≤ {threshold_max}'
        elif threshold_max is not None:
            passed = value <= threshold_max
            threshold_text = f'≤ {threshold_max}'
        elif threshold_min is not None:
            passed = value >= threshold_min
            threshold_text = f'≥ {threshold_min}'
        else:
            passed = True
            threshold_text = 'N/A'
        
        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'value': round(value, 2) if isinstance(value, (int, float)) else value,
            'unit': unit,
            'threshold': threshold_text,
            'passed': passed,
            'status': 'info' if info_only else ('pass' if passed else 'fail'),
            'standard': standard,
            'severity': 'info' if info_only else severity,
            'recommendation': recommendation,
        }

    def make_boolean(self, id, name, desc, passed, standard, category='General',
                     severity='medium', recommendation=''):
        """Boolean pass/fail check."""
        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'passed': passed,
            'status': 'pass' if passed else 'fail',
            'standard': standard,
            'severity': severity,
            'recommendation': recommendation,
        }

    def format_items(self, items, limit=None):
        """
        Format failed items safely for display.
        Default: include ALL items (no truncation).
        Pass limit=N to cap the number.
        """
        if not items:
            return []

        selected = items if limit is None else items[:limit]

        formatted = []
        for i in selected:
            if isinstance(i, dict):
                formatted.append({
                    'code': i.get('task_code') or i.get('pred_code') or i.get('wbs_short_name') or '',
                    'name': i.get('task_name') or i.get('pred_name') or i.get('wbs_name') or '',
                    'wbs': (i.get('wbs_name') or '')[:60],
                    'value': i.get('total_float_days', ''),
                })
            elif isinstance(i, (tuple, list)):
                if len(i) >= 2:
                    pred = self.engine.activity_by_id.get(str(i[0]), {})
                    succ = self.engine.activity_by_id.get(str(i[1]), {})
                    formatted.append({
                        'code': f"{pred.get('task_code', i[0])} → {succ.get('task_code', i[1])}",
                        'name': f"{pred.get('task_name', '')} → {succ.get('task_name', '')}",
                        'wbs': '',
                    })
            else:
                formatted.append({'code': str(i), 'name': '', 'wbs': ''})

        return formatted
    def to_float(self, value):
        """Safe float conversion."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def count_by_type(self, task_type):
        """Count activities of a given type."""
        return sum(1 for a in self.activities if a.get('task_type') == task_type)
"""
BASE CHECKER
============
Provides common check-building methods and shared schedule logic 
used by all standard health modules (DCMA, DOE, GAO, etc.).
"""

from collections import Counter, defaultdict
import statistics
from typing import List, Dict, Any, Optional


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

    def make_check(self, id: str, name: str, desc: str, count: int, total: int, 
                   threshold_pct: float, standard: str, severity: str, 
                   category: str = 'General', recommendation: str = '', 
                   failed_items: Optional[List] = None, 
                   lower_bound: bool = False) -> Dict:
        """
        Standard percentage-based check.
        
        If lower_bound=True, passes if pct >= threshold (e.g., FS > 90%).
        Otherwise, passes if pct <= threshold (e.g., Hard Constraints < 5%).
        """
        pct = (count / total * 100) if total > 0 else 0
        
        if lower_bound:
            passed = pct >= threshold_pct
            thresh_str = f'≥ {threshold_pct}%'
        else:
            passed = pct <= threshold_pct
            thresh_str = f'≤ {threshold_pct}%'

        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'count': count,
            'total': total,
            'percentage': round(pct, 2),
            'threshold': thresh_str,
            'passed': passed,
            'status': 'pass' if passed else 'fail',
            'standard': standard,
            'severity': severity,
            'recommendation': recommendation,
            'failed_items': self.format_items(failed_items or []),
        }

    def make_metric(self, id: str, name: str, desc: str, value: Any, 
                    standard: str, category: str = 'General',
                    threshold_min: Optional[float] = None, 
                    threshold_max: Optional[float] = None,
                    severity: str = 'medium', recommendation: str = '', 
                    info_only: bool = False, unit: str = '') -> Dict:
        """Numeric metric-based check. Safely handles None values."""
        
        # ─── SAFE NULL HANDLING ───
        if value is None or str(value).upper() in ['N/A', 'NONE', 'NAN']:
            return {
                'id': id, 'name': name, 'description': desc, 'category': category,
                'value': 'N/A', 'unit': unit, 'threshold': 'N/A',
                'passed': True,  # Don't penalize score if data is missing
                'status': 'na', 'standard': standard, 'severity': 'info',
                'recommendation': recommendation or 'Insufficient data to compute metric.',
            }

        val = self.to_float(value)

        if info_only:
            passed = True
            threshold_text = 'Informational'
        elif threshold_min is not None and threshold_max is not None:
            passed = threshold_min <= val <= threshold_max
            threshold_text = f'{threshold_min} ≤ x ≤ {threshold_max}'
        elif threshold_max is not None:
            passed = val <= threshold_max
            threshold_text = f'≤ {threshold_max}'
        elif threshold_min is not None:
            passed = val >= threshold_min
            threshold_text = f'≥ {threshold_min}'
        else:
            passed = True
            threshold_text = 'N/A'
        
        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'value': round(val, 2) if isinstance(value, (int, float)) else value,
            'unit': unit,
            'threshold': threshold_text,
            'passed': passed,
            'status': 'info' if info_only else ('pass' if passed else 'fail'),
            'standard': standard,
            'severity': 'info' if info_only else severity,
            'recommendation': recommendation,
        }

    def make_boolean(self, id: str, name: str, desc: str, passed: bool, 
                     standard: str, category: str = 'General',
                     severity: str = 'medium', recommendation: str = '') -> Dict:
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

    # ═══════════════════════════════════════════
    # FORMATTING HELPERS
    # ═══════════════════════════════════════════

    def format_items(self, items: List, limit: Optional[int] = None) -> List[Dict]:
        """
        Format failed items safely for display in UI and PDF/Excel exports.
        Handles both Activity dicts and Relationship dicts.
        """
        if not items:
            return []

        selected = items if limit is None else items[:limit]
        formatted = []
        
        for i in selected:
            if isinstance(i, dict):
                # ─── RELATIONSHIP DICT DETECTION ───
                if 'pred_code' in i or 'succ_code' in i or 'pred_task_id' in i:
                    p_code = i.get('pred_code') or i.get('pred_task_id', '')
                    s_code = i.get('succ_code') or i.get('task_id', '')
                    p_name = i.get('pred_name', '')
                    s_name = i.get('succ_name', '')
                    rel_type = i.get('type_text') or i.get('pred_type', '')
                    lag = i.get('lag_days', 0)
                    lag_str = f" +{lag}d" if lag > 0 else (f" {lag}d" if lag < 0 else "")
                    
                    formatted.append({
                        'code': f"{p_code} → {s_code}",
                        'name': f"{p_name} → {s_name} ({rel_type}{lag_str})",
                        'wbs': '',
                        'value': f"Lag: {lag}d",
                    })
                # ─── ACTIVITY DICT DETECTION ───
                else:
                    formatted.append({
                        'code': i.get('task_code') or i.get('wbs_short_name') or '',
                        'name': i.get('task_name') or i.get('wbs_name') or '',
                        'wbs': (i.get('wbs_name') or '')[:60],
                        'value': i.get('total_float_days', ''),
                    })
            # ─── TUPLE/LIST DETECTION (Manual Relationship Pairs) ───
            elif isinstance(i, (tuple, list)) and len(i) >= 2:
                pred = self.engine.activity_by_id.get(str(i[0]), {})
                succ = self.engine.activity_by_id.get(str(i[1]), {})
                p_code = pred.get('task_code', str(i[0]))
                s_code = succ.get('task_code', str(i[1]))
                formatted.append({
                    'code': f"{p_code} → {s_code}",
                    'name': f"{pred.get('task_name', '')} → {succ.get('task_name', '')}",
                    'wbs': ''
                })
            else:
                formatted.append({'code': str(i), 'name': '', 'wbs': ''})

        return formatted

    def to_float(self, value: Any) -> float:
        """Safe float conversion."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def count_by_type(self, task_type: str) -> int:
        """Count activities of a given type."""
        return sum(1 for a in self.activities if a.get('task_type') == task_type)

    # ═══════════════════════════════════════════
    # SHARED LOGIC HELPERS (Used across standards)
    # ═══════════════════════════════════════════

    def open_start_activities(self) -> List[Dict]:
        """
        Return incomplete activities lacking predecessors.
        Excludes ALL milestones (TT_Mile and TT_FinMile) as they can legitimately
        serve as project boundaries.
        """
        milestones = {'TT_Mile', 'TT_FinMile'}
        return [
            a for a in self.incomplete
            if a.get('task_id', '') not in self.engine.predecessors
            and a.get('task_type') not in milestones
        ]

    def open_end_activities(self) -> List[Dict]:
        """
        Return incomplete activities lacking successors.
        Excludes ALL milestones (TT_Mile and TT_FinMile).
        """
        milestones = {'TT_Mile', 'TT_FinMile'}
        return [
            a for a in self.incomplete
            if a.get('task_id', '') not in self.engine.successors
            and a.get('task_type') not in milestones
        ]

    def active_relationships(self) -> List[Dict]:
        """
        Return relationships where the successor is not completed.
        This prevents historical (completed) logic from penalizing current metrics.
        """
        return [
            r for r in self.relationships
            if self.engine.activity_by_id.get(r.get('task_id', ''), {}).get('status_code') != 'TK_Complete'
        ]

    def has_hard_constraint(self, act: Dict, include_alap: bool = False) -> bool:
        """
        Check if activity has a hard constraint.
        CS_MFO was corrected to CS_MEO (Must Finish On).
        """
        codes = {'CS_MSO', 'CS_MEO', 'CS_MANDSTART', 'CS_MANDFIN'}
        if include_alap:
            codes.add('CS_ALAP')
        return act.get('cstr_type') in codes or act.get('cstr_type2') in codes

    def fs_with_lag(self) -> List[Dict]:
        """Return active Finish-to-Start relationships with positive lag."""
        return [
            r for r in self.active_relationships()
            if r.get('pred_type') == 'PR_FS' and r.get('lag_days', 0) > 0
        ]
        
    def is_milestone(self, act: Dict) -> bool:
        """Check if activity is any type of milestone."""
        return act.get('task_type') in ['TT_Mile', 'TT_FinMile']
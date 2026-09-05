"""
MULTI-PERIOD TREND ANALYSIS ENGINE
===================================
Processes a series of XER files (Jan, Feb, Mar, Apr, May updates) and extracts
time-series metrics to detect schedule drift, chronic critical activities,
and improvement/decline trends.

Metrics tracked over time:
- Projected finish date
- Overall health score
- Critical activity count (both TF ≤ 0 and Longest Path)
- Total activity count
- Slipped/added/deleted counts vs baseline
- EVM SPI/CPI/EAC drift
- DCMA compliance percentage
- Chronic critical activities (critical in 3+ updates)
"""

from parser import XERParser
from data_engine import ScheduleEngine
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class TrendAnalysisEngine:
    """Processes multiple XER files and extracts time-series trends."""

    def __init__(self):
        self.periods = []  # List of {name, engine, health, evm, data_date}
        self.trend_results = {}

    def add_period(self, file_path_or_stream, period_label=None):
        """
        Add one XER file as a schedule update.
        period_label: Optional friendly name (e.g., "Jan 2024", "Update 03")
        """
        logger.info(f"📊 Loading trend period: {period_label}")
        
        parser = XERParser()
        tables = parser.parse(file_path_or_stream)
        if tables is None:
            raise Exception(f"Failed to parse XER for period: {period_label}")
        
        engine = ScheduleEngine()
        engine.load_data(tables)
        engine.analyze()
        
        # Extract auto-generated data date
        data_date = None
        if engine.projects:
            dd_str = engine.projects[0].get('last_recalc_date', '')
            data_date = engine._parse_date(dd_str)
        
        period_info = {
            'label': period_label or (data_date.strftime('%Y-%m-%d') if data_date else f'Period {len(self.periods) + 1}'),
            'engine': engine,
            'data_date': data_date,
        }
        
        self.periods.append(period_info)
        logger.info(f"  ✅ Added period '{period_info['label']}' ({len(engine.activities)} activities)")
        return period_info['label']

    def analyze(self):
        """
        Run full trend analysis across all uploaded periods.
        Returns dict with all trend series and chronic activity detection.
        """
        if len(self.periods) < 2:
            return {'error': 'At least 2 schedule periods required for trend analysis.'}
        
        logger.info(f"📈 Analyzing trends across {len(self.periods)} periods...")
        
        # Sort periods chronologically by data date
        self.periods.sort(key=lambda p: p['data_date'] or datetime.min)
        
        # Extract per-period metrics
        period_metrics = []
        for p in self.periods:
            period_metrics.append(self._extract_period_metrics(p))
        
        # Compute chronic critical activities
        chronic_critical = self._detect_chronic_critical()
        
        # Compute slippage vs first period (baseline)
        slippage_trend = self._calculate_slippage_trend(period_metrics)
        
        # Compute activity count trend
        activity_trend = self._calculate_activity_trend(period_metrics)
        
        # Health score trend
        health_trend = self._calculate_health_trend(period_metrics)
        
        # EVM trend
        evm_trend = self._calculate_evm_trend(period_metrics)
        
        # Critical path trend
        critical_trend = self._calculate_critical_trend(period_metrics)
        
        self.trend_results = {
            'period_count': len(self.periods),
            'periods': [p['label'] for p in self.periods],
            'period_data_dates': [p['data_date'].strftime('%Y-%m-%d') if p['data_date'] else '' for p in self.periods],
            'period_metrics': period_metrics,
            'slippage_trend': slippage_trend,
            'activity_trend': activity_trend,
            'health_trend': health_trend,
            'evm_trend': evm_trend,
            'critical_trend': critical_trend,
            'chronic_critical': chronic_critical,
            'analyzed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        logger.info(f"  ✅ Trend analysis complete ({len(chronic_critical)} chronic critical activities)")
        return self.trend_results

    def _extract_period_metrics(self, period_info):
        """Extract summary metrics for a single period."""
        engine = period_info['engine']
        
        # Basic activity stats
        real_activities = [a for a in engine.activities if a.get('task_type') not in ('TT_WBS', 'TT_LOE')]
        incomplete = [a for a in real_activities if a.get('status_code') != 'TK_Complete']
        completed = [a for a in real_activities if a.get('status_code') == 'TK_Complete']
        
        # Project finish date (latest early_end among incomplete)
        project_finish = None
        end_dates = [a.get('early_end_date_parsed') for a in incomplete if a.get('early_end_date_parsed')]
        if end_dates:
            project_finish = max(end_dates)
        elif engine.projects:
            project_finish = engine._parse_date(engine.projects[0].get('plan_end_date', ''))
        
        # Critical (TF ≤ 0) count
        crit_count = sum(1 for a in incomplete if a.get('is_critical'))
        
        # Longest Path count (if calculated)
        lp_count = 0
        try:
            from longest_path_engine import LongestPathEngine
            lp = LongestPathEngine(engine)
            lp.calculate()
            lp_count = len(lp.longest_path_ids)
        except Exception:
            pass
        
        # Health score
        health_score = None
        health_pass_rate = None
        try:
            from advanced_health_engine import AdvancedHealthEngine
            he = AdvancedHealthEngine(engine)
            hr = he.run_all_checks('all')
            health_score = hr.get('overall_score')
            health_pass_rate = hr.get('pass_rate')
        except Exception as e:
            logger.warning(f"Health calc failed for {period_info['label']}: {e}")
        
        # EVM
        spi = cpi = eac = bac = None
        try:
            from evm_engine import EVMEngine
            evm = EVMEngine(engine)
            ev_results = evm.calculate()
            metrics = ev_results.get('metrics', {})
            spi = metrics.get('spi')
            cpi = metrics.get('cpi')
            eac = metrics.get('eac')
            bac = metrics.get('bac')
        except Exception as e:
            logger.warning(f"EVM calc failed for {period_info['label']}: {e}")
        
        # Negative float count
        neg_float_count = sum(1 for a in incomplete if a.get('total_float_days', 0) < 0)
        
        return {
            'label': period_info['label'],
            'data_date': period_info['data_date'].strftime('%Y-%m-%d') if period_info['data_date'] else '',
            'total_activities': len(engine.activities),
            'incomplete_count': len(incomplete),
            'completed_count': len(completed),
            'critical_count': crit_count,
            'longest_path_count': lp_count,
            'negative_float_count': neg_float_count,
            'project_finish': project_finish.strftime('%Y-%m-%d') if project_finish else None,
            'health_score': health_score,
            'health_pass_rate': health_pass_rate,
            'spi': spi,
            'cpi': cpi,
            'eac': eac,
            'bac': bac,
            'relationship_count': len(engine.relationships),
        }

    def _detect_chronic_critical(self):
        """
        Find activities that appeared as critical in 3+ periods.
        These are the true bottleneck activities.
        """
        activity_critical_map = defaultdict(list)  # {task_code: [period_labels_where_critical]}
        activity_details = {}  # {task_code: {name, wbs}}
        
        for period in self.periods:
            engine = period['engine']
            for act in engine.activities:
                if act.get('is_critical') and act.get('status_code') != 'TK_Complete':
                    code = act.get('task_code', '')
                    if not code:
                        continue
                    activity_critical_map[code].append(period['label'])
                    if code not in activity_details:
                        activity_details[code] = {
                            'name': act.get('task_name', ''),
                            'wbs': act.get('wbs_name', ''),
                        }
        
        chronic = []
        threshold = 3 if len(self.periods) >= 4 else 2
        
        for code, periods_list in activity_critical_map.items():
            if len(periods_list) >= threshold:
                chronic.append({
                    'code': code,
                    'name': activity_details[code]['name'],
                    'wbs': activity_details[code]['wbs'],
                    'critical_in_periods': periods_list,
                    'critical_count': len(periods_list),
                    'chronic_percentage': round(len(periods_list) / len(self.periods) * 100, 1),
                })
        
        chronic.sort(key=lambda x: x['critical_count'], reverse=True)
        return chronic

    def _calculate_slippage_trend(self, period_metrics):
        """Calculate cumulative slippage from first period."""
        if not period_metrics or not period_metrics[0].get('project_finish'):
            return {'labels': [], 'slippage_days': []}
        
        try:
            baseline_finish = datetime.strptime(period_metrics[0]['project_finish'], '%Y-%m-%d')
        except (ValueError, TypeError):
            return {'labels': [], 'slippage_days': []}
        
        labels = []
        slippage = []
        finishes = []
        for pm in period_metrics:
            labels.append(pm['label'])
            if pm.get('project_finish'):
                try:
                    curr_finish = datetime.strptime(pm['project_finish'], '%Y-%m-%d')
                    slippage.append((curr_finish - baseline_finish).days)
                    finishes.append(pm['project_finish'])
                except (ValueError, TypeError):
                    slippage.append(None)
                    finishes.append(None)
            else:
                slippage.append(None)
                finishes.append(None)
        
        return {
            'labels': labels,
            'slippage_days': slippage,
            'project_finishes': finishes,
            'baseline_finish': period_metrics[0]['project_finish'],
        }

    def _calculate_activity_trend(self, period_metrics):
        """Track total, incomplete, and completed activity counts."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'total': [pm['total_activities'] for pm in period_metrics],
            'incomplete': [pm['incomplete_count'] for pm in period_metrics],
            'completed': [pm['completed_count'] for pm in period_metrics],
        }

    def _calculate_health_trend(self, period_metrics):
        """Track health score over time."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'scores': [pm.get('health_score') for pm in period_metrics],
            'pass_rates': [pm.get('health_pass_rate') for pm in period_metrics],
        }

    def _calculate_evm_trend(self, period_metrics):
        """Track EVM SPI/CPI over time."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'spi': [pm.get('spi') for pm in period_metrics],
            'cpi': [pm.get('cpi') for pm in period_metrics],
            'eac': [pm.get('eac') for pm in period_metrics],
            'bac': [pm.get('bac') for pm in period_metrics],
        }

    def _calculate_critical_trend(self, period_metrics):
        """Track critical path metrics over time."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'critical_count': [pm['critical_count'] for pm in period_metrics],
            'longest_path_count': [pm['longest_path_count'] for pm in period_metrics],
            'negative_float_count': [pm['negative_float_count'] for pm in period_metrics],
        }

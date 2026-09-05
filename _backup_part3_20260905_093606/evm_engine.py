"""
EVM (EARNED VALUE MANAGEMENT) & S-CURVE ENGINE
================================================
Calculates project performance metrics and generates S-curve data.
"""

from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class EVMEngine:
    FALLBACK_COST_PER_DAY = 1000.0

    def __init__(self, engine):
        self.engine = engine
        self.evm_data = {}
        self.scurve_data = {}

        self.resource_costs = defaultdict(lambda: {'budget': 0.0, 'actual': 0.0})
        for r in getattr(engine, 'resources', []) or []:
            tid = str(r.get('task_id', '') or '')
            if not tid:
                continue
            self.resource_costs[tid]['budget'] += self._to_float(r.get('target_cost', '0'))
            self.resource_costs[tid]['actual'] += (
                self._to_float(r.get('act_reg_cost', '0'))
                + self._to_float(r.get('act_ot_cost', '0'))
                + self._to_float(r.get('act_cost', '0'))
            )

        total_budget = sum(c['budget'] for c in self.resource_costs.values())
        total_actual = sum(c['actual'] for c in self.resource_costs.values())
        self.has_real_costs = total_budget > 0 or total_actual > 0

    def calculate(self):
        logger.info("📊 Calculating EVM metrics...")
        self._calculate_evm_metrics()
        self._generate_scurve_data()
        logger.info("  ✅ EVM calculations complete (cost_loaded=%s)", self.has_real_costs)
        return {
            'metrics': self.evm_data,
            'scurve': self.scurve_data,
        }

    def _activity_budget_and_actual(self, act):
        tid = str(act.get('task_id', '') or '')
        duration = float(act.get('original_duration_days', 0) or 0)
        rc = self.resource_costs.get(tid, {'budget': 0.0, 'actual': 0.0})

        if self.has_real_costs:
            budget = float(rc['budget'] or 0.0)
            actual = float(rc['actual'] or 0.0)
            return budget, actual, False

        if duration <= 0:
            return 0.0, None, True
        budget = duration * self.FALLBACK_COST_PER_DAY
        return budget, None, True

    def _calculate_evm_metrics(self):
        activities = self.engine.activities
        data_date = self._get_data_date()

        total_bac = 0.0
        total_pv = 0.0
        total_ev = 0.0
        total_ac = 0.0
        ac_known = False

        for act in activities:
            if act.get('task_type') in ('TT_WBS', 'TT_LOE'):
                continue

            budget, actual, _ = self._activity_budget_and_actual(act)
            if budget <= 0 and (actual is None or actual <= 0):
                continue

            total_bac += budget

            progress = self._to_float(act.get('phys_complete_pct', '0')) / 100.0
            progress = max(0.0, min(1.0, progress))
            activity_ev = budget * progress
            total_ev += activity_ev

            if actual is not None and self.has_real_costs:
                total_ac += actual
                if actual > 0:
                    ac_known = True
            else:
                total_ac += activity_ev

            start_date = (
                act.get('target_start_date_parsed')
                or act.get('early_start_date_parsed')
            )
            end_date = (
                act.get('target_end_date_parsed')
                or act.get('early_end_date_parsed')
            )

            if start_date and end_date and data_date and budget > 0:
                if data_date < start_date:
                    planned_progress = 0.0
                elif data_date >= end_date:
                    planned_progress = 1.0
                else:
                    total_days = (end_date - start_date).days
                    days_done = (data_date - start_date).days
                    planned_progress = (days_done / total_days) if total_days > 0 else 0.0
                    planned_progress = max(0.0, min(1.0, planned_progress))
                total_pv += budget * planned_progress

        sv = total_ev - total_pv
        cv = total_ev - total_ac

        spi = (total_ev / total_pv) if total_pv > 0 else 0.0
        cpi = (total_ev / total_ac) if total_ac > 0 else 0.0
        eac = (total_bac / cpi) if cpi > 0 else total_bac

        etc = max(0.0, eac - total_ac)
        vac = total_bac - eac
        pct_complete = (total_ev / total_bac * 100.0) if total_bac > 0 else 0.0
        pct_spent = (total_ac / total_bac * 100.0) if total_bac > 0 else 0.0

        schedule_status = self._interpret_spi(spi if total_pv > 0 else 0.0)
        if not self.has_real_costs:
            cost_status = {
                'status': 'unknown',
                'text': 'N/A — schedule not cost-loaded',
            }
            cpi_out = cpi
        else:
            cost_status = self._interpret_cpi(cpi if total_ac > 0 else 0.0)
            cpi_out = cpi

        self.evm_data = {
            'bac': round(total_bac, 2),
            'pv': round(total_pv, 2),
            'ev': round(total_ev, 2),
            'ac': round(total_ac, 2),
            'sv': round(sv, 2),
            'cv': round(cv, 2),
            'spi': round(spi, 3),
            'cpi': round(cpi_out, 3),
            'eac': round(eac, 2),
            'etc': round(etc, 2),
            'vac': round(vac, 2),
            'pct_complete': round(pct_complete, 1),
            'pct_spent': round(pct_spent, 1),
            'is_cost_loaded': bool(self.has_real_costs),
            'ac_from_actuals': bool(self.has_real_costs and ac_known),
            'estimate_method': 'resource_cost' if self.has_real_costs else 'duration_proxy',
            'schedule_status': schedule_status,
            'cost_status': cost_status,
            'data_date': data_date.strftime('%Y-%m-%d') if data_date else 'Unknown',
        }

    def _generate_scurve_data(self):
        activities = [
            a for a in self.engine.activities
            if a.get('task_type') not in ('TT_WBS', 'TT_LOE')
        ]

        all_dates = []
        for act in activities:
            start = act.get('target_start_date_parsed') or act.get('early_start_date_parsed')
            end = act.get('target_end_date_parsed') or act.get('early_end_date_parsed')
            if start:
                all_dates.append(start)
            if end:
                all_dates.append(end)

        if not all_dates:
            self.scurve_data = {'error': 'No valid dates found'}
            return

        proj_start = min(all_dates)
        proj_end = max(all_dates)
        data_date = self._get_data_date()

        buckets = []
        current = proj_start
        max_buckets = 520
        while current <= proj_end and len(buckets) < max_buckets:
            buckets.append(current)
            current += timedelta(days=7)
        if not buckets or buckets[-1] < proj_end:
            buckets.append(proj_end)

        pv_curve = []
        ev_curve = []
        ac_curve = []
        labels = []

        for bucket_date in buckets:
            planned_value = 0.0
            earned_value = 0.0
            actual_cost = 0.0

            for act in activities:
                budget, actual, _ = self._activity_budget_and_actual(act)
                if budget <= 0:
                    continue

                start = act.get('target_start_date_parsed') or act.get('early_start_date_parsed')
                end = act.get('target_end_date_parsed') or act.get('early_end_date_parsed')
                if not start or not end:
                    continue

                if bucket_date >= end:
                    planned_value += budget
                elif bucket_date > start:
                    total_days = (end - start).days
                    days_done = (bucket_date - start).days
                    if total_days > 0:
                        planned_value += budget * min(1.0, max(0.0, days_done / total_days))

            if data_date and bucket_date <= data_date:
                for act in activities:
                    budget, actual, _ = self._activity_budget_and_actual(act)
                    if budget <= 0:
                        continue
                    start = act.get('target_start_date_parsed') or act.get('early_start_date_parsed')
                    end = act.get('target_end_date_parsed') or act.get('early_end_date_parsed')
                    if not start or not end:
                        continue

                    progress = max(0.0, min(1.0, self._to_float(act.get('phys_complete_pct', '0')) / 100.0))

                    if bucket_date < start:
                        portion = 0.0
                    elif bucket_date >= end:
                        portion = 1.0
                    else:
                        td = (end - start).days
                        portion = ((bucket_date - start).days / td) if td > 0 else 0.0
                        portion = max(0.0, min(1.0, portion))

                    if progress >= 1.0:
                        earned_value += budget * portion
                    else:
                        earned_value += budget * progress * portion

                    if self.has_real_costs and actual is not None:
                        actual_cost += float(actual) * portion
                    else:
                        actual_cost += budget * progress * portion

            labels.append(bucket_date.strftime('%Y-%m-%d'))
            pv_curve.append(round(planned_value, 2))

            if data_date and bucket_date <= data_date:
                ev_curve.append(round(earned_value, 2))
                ac_curve.append(round(actual_cost, 2))
            else:
                ev_curve.append(None)
                ac_curve.append(None)

        self.scurve_data = {
            'labels': labels,
            'planned_value': pv_curve,
            'earned_value': ev_curve,
            'actual_cost': ac_curve,
            'data_date': data_date.strftime('%Y-%m-%d') if data_date else None,
            'bac': self.evm_data.get('bac', 0),
            'is_cost_loaded': bool(self.has_real_costs),
        }

    def _get_data_date(self):
        if not getattr(self.engine, 'projects', None):
            return datetime.now()
        proj = self.engine.projects[0]
        date_str = proj.get('last_recalc_date', '')
        parsed = self.engine._parse_date(date_str)
        return parsed if parsed else datetime.now()

    def _interpret_spi(self, spi):
        if spi == 0:
            return {'status': 'unknown', 'text': 'Insufficient data'}
        if spi >= 1.0:
            return {'status': 'good', 'text': 'Ahead of schedule ✅'}
        if spi >= 0.95:
            return {'status': 'warning', 'text': 'Slightly behind ⚠️'}
        return {'status': 'bad', 'text': 'Behind schedule ❌'}

    def _interpret_cpi(self, cpi):
        if cpi == 0:
            return {'status': 'unknown', 'text': 'Insufficient data'}
        if cpi >= 1.0:
            return {'status': 'good', 'text': 'Under budget ✅'}
        if cpi >= 0.95:
            return {'status': 'warning', 'text': 'Slightly over budget ⚠️'}
        return {'status': 'bad', 'text': 'Over budget ❌'}

    def _to_float(self, value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

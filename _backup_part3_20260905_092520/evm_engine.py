"""
EVM (EARNED VALUE MANAGEMENT) & S-CURVE ENGINE
================================================
Calculates project performance metrics and generates S-curve data.

Uses real TASKRSRC costs when present.
Falls back to duration-based BAC proxy only when schedule is not cost-loaded,
and flags is_cost_loaded=False so the UI can show a disclaimer.

Never fabricates AC = EV * 1.05.
"""

from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class EVMEngine:
    """
    KEY METRICS:
    - BAC, PV, EV, AC, SV, CV, SPI, CPI, EAC, ETC, VAC
    """

    # Fallback only when NO resource costs exist anywhere in the file
    FALLBACK_COST_PER_DAY = 1000.0

    def __init__(self, engine):
        """
        PARAMETERS:
            engine: ScheduleEngine with loaded data
        """
        self.engine = engine
        self.evm_data = {}
        self.scurve_data = {}

        # Pre-index resource costs by task_id
        self.resource_costs = defaultdict(lambda: {'budget': 0.0, 'actual': 0.0})
        for r in getattr(engine, 'resources', []) or []:
            tid = str(r.get('task_id', '') or '')
            if not tid:
                continue
            self.resource_costs[tid]['budget'] += self._to_float(r.get('target_cost', '0'))
            self.resource_costs[tid]['actual'] += (
                self._to_float(r.get('act_reg_cost', '0'))
                + self._to_float(r.get('act_ot_cost', '0'))
                + self._to_float(r.get('act_cost', '0'))  # some exports
            )

        total_budget = sum(c['budget'] for c in self.resource_costs.values())
        total_actual = sum(c['actual'] for c in self.resource_costs.values())
        self.has_real_costs = total_budget > 0 or total_actual > 0

    def calculate(self):
        """Run all EVM calculations."""
        logger.info("📊 Calculating EVM metrics...")
        self._calculate_evm_metrics()
        self._generate_scurve_data()
        logger.info("  ✅ EVM calculations complete (cost_loaded=%s)", self.has_real_costs)
        return {
            'metrics': self.evm_data,
            'scurve': self.scurve_data,
        }

    # ═══════════════════════════════════════════════════════
    # CORE EVM
    # ═══════════════════════════════════════════════════════

    def _activity_budget_and_actual(self, act):
        """
        Returns (budget, actual_cost, used_fallback).
        actual may be None if unknown (not the same as 0).
        """
        tid = str(act.get('task_id', '') or '')
        duration = float(act.get('original_duration_days', 0) or 0)
        rc = self.resource_costs.get(tid, {'budget': 0.0, 'actual': 0.0})

        if self.has_real_costs:
            budget = float(rc['budget'] or 0.0)
            actual = float(rc['actual'] or 0.0)
            # If cost-loaded project but this task has no assignment, budget stays 0
            return budget, actual, False

        # Not cost-loaded: duration proxy for BAC/PV/EV only
        if duration <= 0:
            return 0.0, None, True
        budget = duration * self.FALLBACK_COST_PER_DAY
        # Without actual costs, do not invent AC — treat AC as EV for display
        # but mark is_cost_loaded False (CPI is not meaningful)
        return budget, None, True

    def _calculate_evm_metrics(self):
        activities = self.engine.activities
        data_date = self._get_data_date()

        total_bac = 0.0
        total_pv = 0.0
        total_ev = 0.0
        total_ac = 0.0
        ac_known = False  # True if any real actual cost was found

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
                # Uncosted: use EV as AC placeholder for curve shape only
                total_ac += activity_ev

            # Planned Value from target/early dates vs data date
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

        # Derived metrics
        sv = total_ev - total_pv
        cv = total_ev - total_ac

        if total_pv > 0:
            spi = total_ev / total_pv
        else:
            spi = 0.0

        # CPI only meaningful if we have real cost loading with actuals,
        # or if we intentionally use EV≈AC fallback (then CPI ~ 1)
        if total_ac > 0:
            cpi = total_ev / total_ac
        else:
            cpi = 0.0

        if cpi > 0:
            eac = total_bac / cpi
        else:
            eac = total_bac

        etc = max(0.0, eac - total_ac)
        vac = total_bac - eac
        pct_complete = (total_ev / total_bac * 100.0) if total_bac > 0 else 0.0
        pct_spent = (total_ac / total_bac * 100.0) if total_bac > 0 else 0.0

        # Status bands
        schedule_status = self._interpret_spi(spi if total_pv > 0 else 0.0)
        if not self.has_real_costs:
            cost_status = {
                'status': 'unknown',
                'text': 'N/A — schedule not cost-loaded',
            }
            # Present CPI as 0 display N/A path in UI via flag
            cpi_out = cpi  # will be ~1.0 if AC=EV placeholder
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

    # ═══════════════════════════════════════════════════════
    # S-CURVE
    # ═══════════════════════════════════════════════════════

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

        # Weekly buckets (cap length for very long projects)
        buckets = []
        current = proj_start
        max_buckets = 520  # ~10 years weekly
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

                # PV cumulative to bucket
                if bucket_date >= end:
                    planned_value += budget
                elif bucket_date > start:
                    total_days = (end - start).days
                    days_done = (bucket_date - start).days
                    if total_days > 0:
                        planned_value += budget * min(1.0, max(0.0, days_done / total_days))

                # EV/AC only through data date
                if data_date and bucket_date <= data_date:
                    progress = self._to_float(act.get('phys_complete_pct', '0')) / 100.0
                    progress = max(0.0, min(1.0, progress))

                    # Time-phase EV for curve smoothness before full progress
                    if bucket_date >= end:
                        earned_value += budget * progress
                    elif bucket_date > start:
                        total_days = (end - start).days
                        days_done = (bucket_date - start).days
                        if total_days > 0:
                            time_progress = min(1.0, max(0.0, days_done / total_days))
                            earned_value += budget * min(progress, time_progress if progress >= 1.0 else progress)
                            # Prefer physical % as cap: use progress * budget * time portion only if in progress
                            # Simpler stable approach: EV_t = budget * progress * (time_progress if not complete else 1)
                            # Use physical progress scaled by time for incomplete:
                    else:
                        pass

                    # Cleaner EV: full physical EV once started portion elapsed
                    # Recalculate simply:
                    pass

            # Second pass cleaner EV/AC for this bucket (clarity over micro-optimization)
            earned_value = 0.0
            actual_cost = 0.0
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

                    # Cumulative EV approximation: budget * progress * portion of activity window
                    # At/after data date snapshot, progress is as-of now — for historical buckets
                    # scale progress by portion only when still in window
                    if progress >= 1.0:
                        earned_value += budget * portion
                    else:
                        earned_value += budget * progress * portion

                    if self.has_real_costs and actual is not None:
                        # Spread actuals linearly over activity window (approximation)
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

    # ═══════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════

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
"""
EVM (EARNED VALUE MANAGEMENT) & S-CURVE ENGINE
================================================
Calculates project performance metrics and 
generates S-curve data for visualization.
"""

from datetime import datetime, timedelta
from collections import defaultdict


class EVMEngine:
    """
    Calculates Earned Value Management metrics.
    
    KEY METRICS:
    - BAC: Budget at Completion (total budget)
    - PV: Planned Value (BCWS - Budgeted Cost of Work Scheduled)
    - EV: Earned Value (BCWP - Budgeted Cost of Work Performed)
    - AC: Actual Cost (ACWP - Actual Cost of Work Performed)
    - SV: Schedule Variance (EV - PV)
    - CV: Cost Variance (EV - AC)
    - SPI: Schedule Performance Index (EV / PV)
    - CPI: Cost Performance Index (EV / AC)
    - EAC: Estimate at Completion (BAC / CPI)
    - ETC: Estimate to Complete (EAC - AC)
    - VAC: Variance at Completion (BAC - EAC)
    """

    def __init__(self, engine):
        """
        PARAMETERS:
            engine: A ScheduleEngine object with loaded data
        """
        self.engine = engine
        self.evm_data = {}
        self.scurve_data = {}

    def calculate(self):
        """Run all EVM calculations."""
        print("\n📊 Calculating EVM metrics...")
        
        self._calculate_evm_metrics()
        self._generate_scurve_data()
        
        print("  ✅ EVM calculations complete")
        return {
            'metrics': self.evm_data,
            'scurve': self.scurve_data
        }

    def _calculate_evm_metrics(self):
        """Calculate all EVM metrics."""
        activities = self.engine.activities
        
        # Assume each activity has a "budget" based on duration
        # In real projects, this would come from resource costs
        # For simplicity: 1 day = 1000 units of budget
        
        total_bac = 0  # Budget at Completion
        total_pv = 0   # Planned Value (what should be done by now)
        total_ev = 0   # Earned Value (what has actually been done)
        total_ac = 0   # Actual Cost
        
        # Get project data date
        data_date = self._get_data_date()
        
        for act in activities:
            # Skip summary activities
            if act.get('task_type') in ['TT_WBS', 'TT_LOE']:
                continue
            
            duration = act.get('original_duration_days', 0)
            if duration == 0:
                continue
            
            # Calculate budget for this activity
            # Simplified: budget = duration × standard rate
            activity_budget = duration * 1000  # $1000 per day
            
            total_bac += activity_budget
            
            # Get progress
            progress = self._to_float(act.get('phys_complete_pct', '0')) / 100.0
            
            # Earned Value = Budget × Progress
            activity_ev = activity_budget * progress
            total_ev += activity_ev
            
            # Actual Cost (simplified: assume actuals match earned for now)
            # In real projects, would come from TASKRSRC and TASKFIN tables
            activity_ac = activity_ev * 1.05  # Assume 5% cost overrun
            total_ac += activity_ac
            
            # Planned Value: How much should be done by data date
            start_date = self._get_date(act, 'target_start_date') or \
                        self._get_date(act, 'early_start_date')
            end_date = self._get_date(act, 'target_end_date') or \
                      self._get_date(act, 'early_end_date')
            
            if start_date and end_date and data_date:
                if data_date < start_date:
                    planned_progress = 0
                elif data_date >= end_date:
                    planned_progress = 1.0
                else:
                    total_days = (end_date - start_date).days
                    days_done = (data_date - start_date).days
                    planned_progress = days_done / total_days if total_days > 0 else 0
                
                activity_pv = activity_budget * planned_progress
                total_pv += activity_pv
        
        # Calculate derived metrics
        sv = total_ev - total_pv  # Schedule Variance
        cv = total_ev - total_ac  # Cost Variance
        spi = total_ev / total_pv if total_pv > 0 else 0
        cpi = total_ev / total_ac if total_ac > 0 else 0
        eac = total_bac / cpi if cpi > 0 else total_bac
        etc = eac - total_ac
        vac = total_bac - eac
        pct_complete = (total_ev / total_bac * 100) if total_bac > 0 else 0
        pct_spent = (total_ac / total_bac * 100) if total_bac > 0 else 0
        
        self.evm_data = {
            'bac': round(total_bac, 2),
            'pv': round(total_pv, 2),
            'ev': round(total_ev, 2),
            'ac': round(total_ac, 2),
            'sv': round(sv, 2),
            'cv': round(cv, 2),
            'spi': round(spi, 3),
            'cpi': round(cpi, 3),
            'eac': round(eac, 2),
            'etc': round(etc, 2),
            'vac': round(vac, 2),
            'pct_complete': round(pct_complete, 1),
            'pct_spent': round(pct_spent, 1),
            'schedule_status': self._interpret_spi(spi),
            'cost_status': self._interpret_cpi(cpi),
            'data_date': data_date.strftime('%Y-%m-%d') if data_date else 'Unknown',
        }

    def _generate_scurve_data(self):
        """
        Generate S-curve data points over time.
        
        Creates cumulative curves for:
        - Planned (PV)
        - Earned (EV)
        - Actual (AC)
        """
        activities = [
            a for a in self.engine.activities
            if a.get('task_type') not in ['TT_WBS', 'TT_LOE']
        ]
        
        # Find project date range
        all_dates = []
        for act in activities:
            start = self._get_date(act, 'target_start_date') or \
                   self._get_date(act, 'early_start_date')
            end = self._get_date(act, 'target_end_date') or \
                 self._get_date(act, 'early_end_date')
            
            if start:
                all_dates.append(start)
            if end:
                all_dates.append(end)
        
        if not all_dates:
            self.scurve_data = {'error': 'No valid dates found'}
            return
        
        proj_start = min(all_dates)
        proj_end = max(all_dates)
        
        # Create weekly buckets
        current_date = proj_start
        buckets = []
        
        while current_date <= proj_end:
            buckets.append(current_date)
            current_date += timedelta(days=7)
        
        # Calculate cumulative values for each bucket
        pv_curve = []
        ev_curve = []
        ac_curve = []
        labels = []
        
        data_date = self._get_data_date()
        
        for bucket_date in buckets:
            planned_value = 0
            earned_value = 0
            actual_cost = 0
            
            for act in activities:
                duration = act.get('original_duration_days', 0)
                if duration == 0:
                    continue
                
                budget = duration * 1000
                
                start = self._get_date(act, 'target_start_date') or \
                       self._get_date(act, 'early_start_date')
                end = self._get_date(act, 'target_end_date') or \
                     self._get_date(act, 'early_end_date')
                
                if not start or not end:
                    continue
                
                # Planned Value at this date
                if bucket_date >= end:
                    planned_value += budget
                elif bucket_date > start:
                    total_days = (end - start).days
                    days_done = (bucket_date - start).days
                    if total_days > 0:
                        planned_value += budget * (days_done / total_days)
                
                # Earned Value (only up to data date)
                if data_date and bucket_date <= data_date:
                    progress = self._to_float(act.get('phys_complete_pct', '0')) / 100.0
                    
                    # Interpolate progress based on time
                    if bucket_date >= end:
                        earned_value += budget * progress
                    elif bucket_date > start:
                        total_days = (end - start).days
                        days_done = (bucket_date - start).days
                        if total_days > 0:
                            time_progress = min(1.0, days_done / total_days)
                            earned_value += budget * min(progress, time_progress)
                    
                    actual_cost = earned_value * 1.05
            
            labels.append(bucket_date.strftime('%Y-%m-%d'))
            pv_curve.append(round(planned_value, 2))
            ev_curve.append(round(earned_value if data_date and bucket_date <= data_date else None, 2) if earned_value else None)
            ac_curve.append(round(actual_cost if data_date and bucket_date <= data_date else None, 2) if actual_cost else None)
        
        self.scurve_data = {
            'labels': labels,
            'planned_value': pv_curve,
            'earned_value': ev_curve,
            'actual_cost': ac_curve,
            'data_date': data_date.strftime('%Y-%m-%d') if data_date else None,
            'bac': self.evm_data.get('bac', 0)
        }

    def _get_data_date(self):
        """Get project data date."""
        if not self.engine.projects:
            return datetime.now()
        
        proj = self.engine.projects[0]
        date_str = proj.get('last_recalc_date', '')
        
        parsed = self.engine._parse_date(date_str)
        if parsed:
            return parsed
        
        # Fallback: use current date
        return datetime.now()

    def _get_date(self, act, field):
        """Get parsed date from activity."""
        return act.get(f'{field}_parsed', None)

    def _interpret_spi(self, spi):
        """Interpret SPI value."""
        if spi == 0:
            return {'status': 'unknown', 'text': 'Insufficient data'}
        elif spi >= 1.0:
            return {'status': 'good', 'text': 'Ahead of schedule ✅'}
        elif spi >= 0.95:
            return {'status': 'warning', 'text': 'Slightly behind ⚠️'}
        else:
            return {'status': 'bad', 'text': 'Behind schedule ❌'}

    def _interpret_cpi(self, cpi):
        """Interpret CPI value."""
        if cpi == 0:
            return {'status': 'unknown', 'text': 'Insufficient data'}
        elif cpi >= 1.0:
            return {'status': 'good', 'text': 'Under budget ✅'}
        elif cpi >= 0.95:
            return {'status': 'warning', 'text': 'Slightly over budget ⚠️'}
        else:
            return {'status': 'bad', 'text': 'Over budget ❌'}

    def _to_float(self, value):
        """Safely convert to float."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
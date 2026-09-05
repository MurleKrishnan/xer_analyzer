"""
RESOURCE ANALYTICS ENGINE
==========================
Extracts detailed resource loading data from XER files:
- Monthly man-hours histograms (stacked by resource type)
- Monthly cost burn rates (with cumulative curves)
- Top resources by units and cost
- Planned vs Actual comparisons
"""

from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ResourceEngine:
    """Extracts resource loading histograms and cost curves from the ScheduleEngine."""

    def __init__(self, engine):
        self.engine = engine
        self.resource_data = {}
        
        # Build resource name lookup
        self.resource_names = {}
        self.resource_types = {}
        for r in engine.raw_tables.get('RSRC', {}).get('rows', []):
            rid = str(r.get('rsrc_id', ''))
            if rid:
                name = r.get('rsrc_name', '') or r.get('rsrc_short_name', '') or 'Unnamed'
                self.resource_names[rid] = name
                # Classify by resource type
                rtype = r.get('rsrc_type', '')
                type_label = {
                    'RT_Labor': 'Labor',
                    'RT_Equip': 'Equipment',
                    'RT_Mat': 'Material',
                    'RT_Nonlabor': 'Non-Labor',
                }.get(rtype, 'Other')
                self.resource_types[rid] = type_label

    def calculate(self):
        """Run all resource extractions."""
        logger.info("👷 Calculating resource analytics...")
        try:
            self._extract_monthly_units()
            self._extract_monthly_costs()
            self._extract_top_resources()
            logger.info("  ✅ Resource analytics complete")
        except Exception as e:
            logger.exception("Resource extraction error: %s", e)
            self.resource_data = {'error': str(e)}
        return self.resource_data

    def _extract_monthly_units(self):
        """
        Spread activity resource hours across their duration into monthly buckets.
        Groups by resource type (Labor / Equipment / Material / etc).
        """
        activities = {str(a.get('task_id', '')): a for a in self.engine.activities}
        
        # {(year, month): {resource_type: units}}
        monthly_units_by_type = defaultdict(lambda: defaultdict(float))
        
        # Overall cumulative
        monthly_totals = defaultdict(float)
        
        for res in self.engine.resources:
            task_id = str(res.get('task_id', ''))
            rsrc_id = str(res.get('rsrc_id', ''))
            
            act = activities.get(task_id)
            if not act:
                continue
            
            total_units = self._to_float(res.get('target_qty', '0'))
            if total_units <= 0:
                continue
            
            rtype = self.resource_types.get(rsrc_id, 'Other')
            
            # Get activity time window
            start = act.get('target_start_date_parsed') or act.get('early_start_date_parsed')
            end = act.get('target_end_date_parsed') or act.get('early_end_date_parsed')
            if not start or not end or end <= start:
                continue
            
            # Spread units evenly by day across activity duration
            total_days = max(1, (end - start).days)
            units_per_day = total_units / total_days
            
            # Walk through each day and bucket into month
            current = start
            while current <= end:
                key = (current.year, current.month)
                monthly_units_by_type[key][rtype] += units_per_day
                monthly_totals[key] += units_per_day
                current += timedelta(days=1)
        
        # Convert to sorted month timeline
        if not monthly_totals:
            self.resource_data['monthly_units'] = {'labels': [], 'datasets': [], 'total_curve': []}
            return
        
        sorted_months = sorted(monthly_totals.keys())
        labels = [f"{y}-{m:02d}" for y, m in sorted_months]
        
        # Collect all resource types present
        all_types = set()
        for month_data in monthly_units_by_type.values():
            all_types.update(month_data.keys())
        
        type_colors = {
            'Labor': '#3b82f6',
            'Equipment': '#f59e0b',
            'Material': '#10b981',
            'Non-Labor': '#8b5cf6',
            'Other': '#64748b',
        }
        
        datasets = []
        for rtype in sorted(all_types):
            data_points = []
            for month_key in sorted_months:
                data_points.append(round(monthly_units_by_type[month_key].get(rtype, 0), 1))
            datasets.append({
                'label': rtype,
                'data': data_points,
                'backgroundColor': type_colors.get(rtype, '#64748b'),
                'stack': 'units',
            })
        
        # Cumulative line
        cumulative = []
        running = 0.0
        for month_key in sorted_months:
            running += monthly_totals[month_key]
            cumulative.append(round(running, 1))
        
        self.resource_data['monthly_units'] = {
            'labels': labels,
            'datasets': datasets,
            'cumulative_curve': cumulative,
            'peak_month': labels[monthly_totals.values().__iter__().__next__() and 
                                 max(range(len(sorted_months)), key=lambda i: monthly_totals[sorted_months[i]])] if sorted_months else '',
            'peak_units': round(max(monthly_totals.values()), 1) if monthly_totals else 0,
            'total_units': round(sum(monthly_totals.values()), 1),
        }

    def _extract_monthly_costs(self):
        """
        Spread activity resource costs across their duration into monthly buckets.
        Also separates planned (target_cost) vs actual (act_reg_cost + act_ot_cost).
        """
        activities = {str(a.get('task_id', '')): a for a in self.engine.activities}
        
        monthly_planned_cost = defaultdict(float)
        monthly_actual_cost = defaultdict(float)
        
        for res in self.engine.resources:
            task_id = str(res.get('task_id', ''))
            act = activities.get(task_id)
            if not act:
                continue
            
            planned_cost = self._to_float(res.get('target_cost', '0'))
            actual_cost = (
                self._to_float(res.get('act_reg_cost', '0'))
                + self._to_float(res.get('act_ot_cost', '0'))
                + self._to_float(res.get('act_cost', '0'))
            )
            
            if planned_cost <= 0 and actual_cost <= 0:
                continue
            
            start = act.get('target_start_date_parsed') or act.get('early_start_date_parsed')
            end = act.get('target_end_date_parsed') or act.get('early_end_date_parsed')
            if not start or not end or end <= start:
                continue
            
            total_days = max(1, (end - start).days)
            planned_per_day = planned_cost / total_days
            actual_per_day = actual_cost / total_days if actual_cost > 0 else 0
            
            current = start
            while current <= end:
                key = (current.year, current.month)
                monthly_planned_cost[key] += planned_per_day
                monthly_actual_cost[key] += actual_per_day
                current += timedelta(days=1)
        
        if not monthly_planned_cost and not monthly_actual_cost:
            self.resource_data['monthly_cost'] = {'labels': [], 'planned': [], 'actual': [], 'cumulative_planned': [], 'cumulative_actual': []}
            return
        
        all_months = sorted(set(list(monthly_planned_cost.keys()) + list(monthly_actual_cost.keys())))
        labels = [f"{y}-{m:02d}" for y, m in all_months]
        
        planned = [round(monthly_planned_cost.get(m, 0), 2) for m in all_months]
        actual = [round(monthly_actual_cost.get(m, 0), 2) for m in all_months]
        
        cumulative_planned = []
        cumulative_actual = []
        running_p = 0.0
        running_a = 0.0
        for i, _ in enumerate(all_months):
            running_p += planned[i]
            running_a += actual[i]
            cumulative_planned.append(round(running_p, 2))
            cumulative_actual.append(round(running_a, 2))
        
        # Total actuals count only up to data date
        has_actuals = any(a > 0 for a in actual)
        
        self.resource_data['monthly_cost'] = {
            'labels': labels,
            'planned': planned,
            'actual': actual if has_actuals else [],
            'cumulative_planned': cumulative_planned,
            'cumulative_actual': cumulative_actual if has_actuals else [],
            'total_planned': round(sum(planned), 2),
            'total_actual': round(sum(actual), 2) if has_actuals else 0,
            'peak_month_planned': labels[planned.index(max(planned))] if planned else '',
            'peak_planned_cost': round(max(planned), 2) if planned else 0,
        }

    def _extract_top_resources(self):
        """Top 20 resources by total man-hours and cost."""
        # {rsrc_id: {'units': X, 'cost': Y, 'name': N, 'type': T}}
        resource_totals = defaultdict(lambda: {'units': 0.0, 'cost': 0.0})
        
        for res in self.engine.resources:
            rid = str(res.get('rsrc_id', ''))
            if not rid:
                continue
            resource_totals[rid]['units'] += self._to_float(res.get('target_qty', '0'))
            resource_totals[rid]['cost'] += self._to_float(res.get('target_cost', '0'))
        
        # Convert to list with names
        resource_list = []
        for rid, totals in resource_totals.items():
            if totals['units'] > 0 or totals['cost'] > 0:
                resource_list.append({
                    'id': rid,
                    'name': self.resource_names.get(rid, f'Resource {rid}'),
                    'type': self.resource_types.get(rid, 'Other'),
                    'units': round(totals['units'], 1),
                    'cost': round(totals['cost'], 2),
                })
        
        # Sort by units (descending), take top 20
        top_by_units = sorted(resource_list, key=lambda x: x['units'], reverse=True)[:20]
        top_by_cost = sorted(resource_list, key=lambda x: x['cost'], reverse=True)[:20]
        
        self.resource_data['top_resources'] = {
            'by_units': top_by_units,
            'by_cost': top_by_cost,
            'total_count': len(resource_list),
        }

    def _to_float(self, value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

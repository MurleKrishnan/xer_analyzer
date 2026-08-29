"""
REPORT GENERATOR
================
Creates Excel reports from the Schedule Engine results.
"""

import os
from datetime import datetime


class ReportGenerator:
    """
    Generates Excel reports from schedule analysis results.
    
    HOW TO USE:
        reporter = ReportGenerator(engine)
        reporter.generate_full_report("output/my_report.xlsx")
    """

    def __init__(self, engine):
        """
        PARAMETERS:
            engine: A ScheduleEngine object (after analysis is complete)
        """
        self.engine = engine

    def generate_full_report(self, output_path):
        """
        Create a comprehensive Excel report with multiple tabs.
        
        PARAMETERS:
            output_path: Where to save the file 
                         Example: "output/schedule_report.xlsx"
        """
        try:
            import pandas as pd
        except ImportError:
            print("❌ pandas is required. Run: pip install pandas")
            return

        print(f"\n📝 Generating report: {output_path}")

        # Make sure the output folder exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Create Excel writer (like opening a new Excel workbook)
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:

            # ─── TAB 1: Summary Dashboard ───
            self._write_summary_tab(writer)

            # ─── TAB 2: DCMA Results ───
            self._write_dcma_tab(writer)

            # ─── TAB 3: All Activities ───
            self._write_activities_tab(writer)

            # ─── TAB 4: Critical Path ───
            self._write_critical_path_tab(writer)

            # ─── TAB 5: Relationships ───
            self._write_relationships_tab(writer)

            # ─── TAB 6: Issues List ───
            self._write_issues_tab(writer)

        print(f"  ✅ Report saved: {output_path}")

    def _write_summary_tab(self, writer):
        """Write the summary dashboard tab."""
        import pandas as pd
        
        stats = self.engine.schedule_stats
        
        summary_data = [
            ['Schedule Summary Report', ''],
            ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['', ''],
            ['ACTIVITY COUNTS', ''],
            ['Total Activities', stats.get('total_activities', 0)],
            ['  Not Started', stats.get('not_started', 0)],
            ['  In Progress', stats.get('in_progress', 0)],
            ['  Completed', stats.get('completed', 0)],
            ['', ''],
            ['ACTIVITY TYPES', ''],
            ['  Tasks', stats.get('tasks', 0)],
            ['  Milestones', stats.get('milestones', 0)],
            ['  Level of Effort', stats.get('loe', 0)],
            ['  WBS Summary', stats.get('wbs_summary', 0)],
            ['', ''],
            ['CRITICAL PATH', ''],
            ['  Critical Activities', stats.get('critical_count', 0)],
            ['  Negative Float', stats.get('negative_float', 0)],
            ['  High Float (>44d)', stats.get('high_float_gt_44d', 0)],
            ['', ''],
            ['RELATIONSHIPS', ''],
            ['  Total Relationships', stats.get('total_relationships', 0)],
            ['  Calendars', stats.get('total_calendars', 0)],
        ]
        
        df = pd.DataFrame(summary_data, columns=['Metric', 'Value'])
        df.to_excel(writer, sheet_name='Summary', index=False)
        print("  📊 Summary tab created")

    def _write_dcma_tab(self, writer):
        """Write the DCMA 14-Point results tab."""
        import pandas as pd
        
        rows = []
        for check_name, result in self.engine.dcma_results.items():
            row = {
                'Check': check_name.replace('_', ' '),
                'Count': result.get('count', result.get('value', 'N/A')),
                'Total': result.get('total', ''),
                'Percentage': f"{result.get('pct', '')}%" if 'pct' in result else str(result.get('value', '')),
                'Threshold': result.get('threshold', ''),
                'Result': 'PASS' if result.get('pass') else ('FAIL' if result.get('pass') is False else 'N/A')
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name='DCMA 14-Point', index=False)
        print("  🏥 DCMA tab created")

    def _write_activities_tab(self, writer):
        """Write all activities tab."""
        import pandas as pd
        
        df = self.engine.get_activities_dataframe()
        if df is not None:
            df.to_excel(writer, sheet_name='Activities', index=False)
            print(f"  📌 Activities tab created ({len(df)} rows)")

    def _write_critical_path_tab(self, writer):
        """Write critical path activities tab."""
        import pandas as pd
        
        columns = ['task_code', 'task_name', 'wbs_name', 
                   'original_duration_days', 'total_float_days',
                   'early_start_date', 'early_end_date',
                   'status_text']
        
        rows = []
        for act in self.engine.critical_activities:
            row = {col: act.get(col, '') for col in columns}
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name='Critical Path', index=False)
        print(f"  🔴 Critical Path tab created ({len(df)} rows)")

    def _write_relationships_tab(self, writer):
        """Write relationships tab."""
        import pandas as pd
        
        columns = ['pred_code', 'pred_name', 'succ_code', 'succ_name',
                   'type_text', 'lag_days']
        
        rows = []
        for rel in self.engine.relationships:
            row = {col: rel.get(col, '') for col in columns}
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name='Relationships', index=False)
        print(f"  🔗 Relationships tab created ({len(df)} rows)")

    def _write_issues_tab(self, writer):
        """Write a combined issues list from all DCMA checks."""
        import pandas as pd
        
        issues = []
        
        for check_name, result in self.engine.dcma_results.items():
            if not result.get('pass', True) and result.get('pass') is not None:
                # This check failed - list the offending items
                items = result.get('activities', result.get('items', []))
                for item in items[:100]:  # Limit to first 100 per check
                    issues.append({
                        'Issue Type': check_name.replace('_', ' '),
                        'Activity ID': item.get('task_code', item.get('pred_code', '')),
                        'Activity Name': item.get('task_name', item.get('pred_name', '')),
                        'WBS': item.get('wbs_name', ''),
                        'Status': item.get('status_text', ''),
                        'Total Float': item.get('total_float_days', ''),
                        'Duration': item.get('original_duration_days', ''),
                    })
        
        df = pd.DataFrame(issues)
        df.to_excel(writer, sheet_name='Issues', index=False)
        print(f"  ⚠️ Issues tab created ({len(df)} issues)")
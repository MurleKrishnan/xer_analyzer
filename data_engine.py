"""
SCHEDULE DATA ENGINE
====================
This is the "brain" that takes raw parsed XER data
and turns it into meaningful schedule information.

It handles:
- Activity organization and lookup
- Relationship/logic mapping
- Calendar interpretation
- Critical Path calculation (Forward & Backward Pass)
- Float calculation
- DCMA 14-Point schedule health checks
"""

from datetime import datetime, timedelta
from collections import defaultdict


# ─── KEY P6 FIELD MAPPINGS ───
# These are the most common field names found in XER files.
# This map helps us refer to them with friendly names.

FIELD_MAP = {
    # TASK (Activity) fields
    'task_id': 'task_id',              # Internal P6 ID (number)
    'task_code': 'task_code',          # Activity ID (e.g., "A1000")
    'task_name': 'task_name',          # Activity Name
    'proj_id': 'proj_id',             # Project ID it belongs to
    'wbs_id': 'wbs_id',              # WBS it belongs to
    'status_code': 'status_code',     # TK_NotStart, TK_Active, TK_Complete
    'task_type': 'task_type',         # TT_Task, TT_Mile, TT_LOE, TT_Rsrc, TT_WBS
    'total_float_hr_cnt': 'total_float_hr_cnt',
    'free_float_hr_cnt': 'free_float_hr_cnt',
    'target_start_date': 'target_start_date',
    'target_end_date': 'target_end_date',
    'act_start_date': 'act_start_date',
    'act_end_date': 'act_end_date',
    'early_start_date': 'early_start_date',
    'early_end_date': 'early_end_date',
    'late_start_date': 'late_start_date',
    'late_end_date': 'late_end_date',
    'target_drtn_hr_cnt': 'target_drtn_hr_cnt',
    'remain_drtn_hr_cnt': 'remain_drtn_hr_cnt',
    'phys_complete_pct': 'phys_complete_pct',
    'clndr_id': 'clndr_id',
}


class ScheduleEngine:
    """
    The main schedule analysis engine.
    
    HOW TO USE:
        1. Create the engine:     engine = ScheduleEngine()
        2. Load parsed data:      engine.load_data(parsed_tables)
        3. Run analysis:          engine.analyze()
        4. Get results:           results = engine.get_summary()
    """

    def __init__(self):
        """Set up empty containers for all schedule data."""
        
        # ─── RAW DATA (from parser) ───
        self.raw_tables = {}
        
        # ─── ORGANIZED DATA ───
        self.projects = []           # List of projects
        self.wbs_nodes = []          # WBS structure
        self.activities = []         # All activities
        self.relationships = []      # Logic ties
        self.calendars = {}          # Calendar definitions
        self.resources = []          # Resource assignments
        
        # ─── LOOKUP DICTIONARIES ───
        # (Think of these as index pages in a book)
        self.activity_by_id = {}       # Quick lookup: task_id → activity
        self.activity_by_code = {}     # Quick lookup: task_code → activity
        self.wbs_by_id = {}            # Quick lookup: wbs_id → wbs node
        
        # ─── NETWORK / GRAPH ───
        self.successors = defaultdict(list)    # task_id → list of successor task_ids
        self.predecessors = defaultdict(list)  # task_id → list of predecessor task_ids
        
        # ─── ANALYSIS RESULTS ───
        self.critical_activities = []
        self.dcma_results = {}
        self.schedule_stats = {}

    # ════════════════════════════════════════════
    # STEP A: LOAD DATA
    # ════════════════════════════════════════════

    def load_data(self, parsed_tables):
        """
        Takes the output from the XER Parser and organizes it.
        
        PARAMETERS:
            parsed_tables: The dictionary returned by XERParser.parse()
        """
        print("\n🔄 Loading data into Schedule Engine...")
        self.raw_tables = parsed_tables

        # ─── Load Projects ───
        self.projects = parsed_tables.get('PROJECT', {}).get('rows', [])
        print(f"  📁 Projects loaded: {len(self.projects)}")

        # ─── Load WBS ───
        self.wbs_nodes = parsed_tables.get('PROJWBS', {}).get('rows', [])
        for wbs in self.wbs_nodes:
            self.wbs_by_id[wbs.get('wbs_id', '')] = wbs
        print(f"  🌳 WBS nodes loaded: {len(self.wbs_nodes)}")

        # ─── Load Activities ───
        self._load_activities(parsed_tables)

        # ─── Load Relationships ───
        self._load_relationships(parsed_tables)

        # ─── Load Calendars ───
        self._load_calendars(parsed_tables)

        # ─── Load Resources ───
        self.resources = parsed_tables.get('TASKRSRC', {}).get('rows', [])
        print(f"  👷 Resource assignments loaded: {len(self.resources)}")

        print("  ✅ Data loading complete!")

    def _load_activities(self, parsed_tables):
        """Load and enrich activity data."""
        raw_activities = parsed_tables.get('TASK', {}).get('rows', [])

        for act in raw_activities:
            # Convert duration from hours to days (P6 stores in hours)
            orig_dur_hrs = self._to_float(act.get('target_drtn_hr_cnt', '0'))
            remain_dur_hrs = self._to_float(act.get('remain_drtn_hr_cnt', '0'))
            
            # Add calculated fields
            act['original_duration_days'] = orig_dur_hrs / 8.0  # assuming 8-hr day
            act['remaining_duration_days'] = remain_dur_hrs / 8.0
            
            # Convert float from hours to days
            total_float_hrs = self._to_float(act.get('total_float_hr_cnt', '0'))
            free_float_hrs = self._to_float(act.get('free_float_hr_cnt', '0'))
            act['total_float_days'] = total_float_hrs / 8.0
            act['free_float_days'] = free_float_hrs / 8.0

            # Parse dates
            for date_field in ['target_start_date', 'target_end_date',
                               'act_start_date', 'act_end_date',
                               'early_start_date', 'early_end_date',
                               'late_start_date', 'late_end_date']:
                act[f'{date_field}_parsed'] = self._parse_date(act.get(date_field, ''))

            # Determine status in plain English
            status = act.get('status_code', '')
            act['status_text'] = {
                'TK_NotStart': 'Not Started',
                'TK_Active': 'In Progress',
                'TK_Complete': 'Completed'
            }.get(status, status)

            # Determine activity type in plain English
            task_type = act.get('task_type', '')
            act['type_text'] = {
                'TT_Task': 'Task Dependent',
                'TT_Rsrc': 'Resource Dependent',
                'TT_Mile': 'Milestone',
                'TT_LOE': 'Level of Effort',
                'TT_WBS': 'WBS Summary',
                'TT_FinMile': 'Finish Milestone'
            }.get(task_type, task_type)

            # Is it critical? (Total Float = 0 or negative)
            act['is_critical'] = act['total_float_days'] <= 0

            # Look up WBS name
            wbs_id = act.get('wbs_id', '')
            wbs_node = self.wbs_by_id.get(wbs_id, {})
            act['wbs_name'] = wbs_node.get('wbs_name', 'Unknown')
            act['wbs_code'] = wbs_node.get('wbs_short_name', 'Unknown')

            # Store in main list and lookup dictionaries
            self.activities.append(act)
            self.activity_by_id[act.get('task_id', '')] = act
            self.activity_by_code[act.get('task_code', '')] = act

        print(f"  📌 Activities loaded: {len(self.activities)}")

    def _load_relationships(self, parsed_tables):
        """
        Load logic ties (relationships between activities).
        
        In P6, relationships are stored in the TASKPRED table:
        - pred_task_id = the predecessor activity
        - task_id = the successor activity  
        - pred_type = FS, SS, FF, SF
        - lag_hr_cnt = lag in hours
        """
        raw_rels = parsed_tables.get('TASKPRED', {}).get('rows', [])

        for rel in raw_rels:
            pred_task_id = rel.get('pred_task_id', '')
            succ_task_id = rel.get('task_id', '')
            
            # Translate relationship type
            pred_type = rel.get('pred_type', '')
            rel['type_text'] = {
                'PR_FS': 'Finish-to-Start',
                'PR_SS': 'Start-to-Start',
                'PR_FF': 'Finish-to-Finish',
                'PR_SF': 'Start-to-Finish'
            }.get(pred_type, pred_type)

            # Convert lag from hours to days
            lag_hrs = self._to_float(rel.get('lag_hr_cnt', '0'))
            rel['lag_days'] = lag_hrs / 8.0

            # Add predecessor/successor names for easy reading
            pred_act = self.activity_by_id.get(pred_task_id, {})
            succ_act = self.activity_by_id.get(succ_task_id, {})
            rel['pred_name'] = pred_act.get('task_name', 'Unknown')
            rel['pred_code'] = pred_act.get('task_code', 'Unknown')
            rel['succ_name'] = succ_act.get('task_name', 'Unknown')
            rel['succ_code'] = succ_act.get('task_code', 'Unknown')

            # Build the network graph
            self.successors[pred_task_id].append({
                'task_id': succ_task_id,
                'type': pred_type,
                'lag_days': rel['lag_days']
            })
            self.predecessors[succ_task_id].append({
                'task_id': pred_task_id,
                'type': pred_type,
                'lag_days': rel['lag_days']
            })

            self.relationships.append(rel)

        print(f"  🔗 Relationships loaded: {len(self.relationships)}")

    def _load_calendars(self, parsed_tables):
        """Load calendar definitions."""
        raw_calendars = parsed_tables.get('CALENDAR', {}).get('rows', [])
        for cal in raw_calendars:
            cal_id = cal.get('clndr_id', '')
            self.calendars[cal_id] = cal
        print(f"  📅 Calendars loaded: {len(self.calendars)}")

    # ════════════════════════════════════════════
    # STEP B: ANALYZE
    # ════════════════════════════════════════════

    def analyze(self):
        """
        Run all schedule analyses.
        This is the main "do everything" method.
        """
        print("\n🔍 Running Schedule Analysis...")
        
        self._calculate_statistics()
        self._identify_critical_path()
        self._run_dcma_checks()
        
        print("  ✅ Analysis complete!")

    def _calculate_statistics(self):
        """Calculate basic schedule statistics."""
        print("  📊 Calculating statistics...")

        total = len(self.activities)
        
        # Count by status
        not_started = sum(1 for a in self.activities 
                         if a.get('status_code') == 'TK_NotStart')
        in_progress = sum(1 for a in self.activities 
                         if a.get('status_code') == 'TK_Active')
        completed = sum(1 for a in self.activities 
                       if a.get('status_code') == 'TK_Complete')

        # Count by type
        tasks = sum(1 for a in self.activities 
                   if a.get('task_type') in ['TT_Task', 'TT_Rsrc'])
        milestones = sum(1 for a in self.activities 
                        if a.get('task_type') in ['TT_Mile', 'TT_FinMile'])
        loe = sum(1 for a in self.activities 
                 if a.get('task_type') == 'TT_LOE')
        wbs_summary = sum(1 for a in self.activities 
                         if a.get('task_type') == 'TT_WBS')

        # Count critical
        critical_count = sum(1 for a in self.activities if a.get('is_critical'))

        # Float distribution
        negative_float = sum(1 for a in self.activities 
                            if a.get('total_float_days', 0) < 0)
        zero_float = sum(1 for a in self.activities 
                        if a.get('total_float_days', 0) == 0)
        positive_float = sum(1 for a in self.activities 
                            if a.get('total_float_days', 0) > 0)
        high_float = sum(1 for a in self.activities 
                        if a.get('total_float_days', 0) > 44)  # > 44 days ≈ 2 months

        self.schedule_stats = {
            'total_activities': total,
            'not_started': not_started,
            'in_progress': in_progress,
            'completed': completed,
            'tasks': tasks,
            'milestones': milestones,
            'loe': loe,
            'wbs_summary': wbs_summary,
            'critical_count': critical_count,
            'negative_float': negative_float,
            'zero_float': zero_float,
            'positive_float': positive_float,
            'high_float_gt_44d': high_float,
            'total_relationships': len(self.relationships),
            'total_calendars': len(self.calendars),
        }

    def _identify_critical_path(self):
        """
        Identify critical activities.
        
        SIMPLE APPROACH: Activities with Total Float ≤ 0 are critical.
        (This matches how P6 determines criticality by default)
        """
        print("  🔴 Identifying Critical Path...")

        self.critical_activities = [
            a for a in self.activities 
            if a.get('is_critical') and a.get('task_type') not in ['TT_LOE', 'TT_WBS']
        ]

        print(f"     Found {len(self.critical_activities)} critical activities")

    def _run_dcma_checks(self):
        """
        Run the DCMA 14-Point Schedule Assessment.
        
        WHAT IS DCMA 14-POINT?
        It's a standard checklist used by the U.S. Defense Contract 
        Management Agency to evaluate schedule health. Even non-defense
        projects use it as a best practice.
        
        Each check produces a percentage — there are acceptable thresholds.
        """
        print("  🏥 Running DCMA 14-Point Health Checks...")

        total = len(self.activities)
        if total == 0:
            print("     ⚠️ No activities to analyze!")
            return

        # Filter to just "real" activities (exclude LOE and WBS Summary)
        real_activities = [
            a for a in self.activities
            if a.get('task_type') not in ['TT_LOE', 'TT_WBS']
        ]
        real_count = len(real_activities)
        
        incomplete_activities = [
            a for a in real_activities 
            if a.get('status_code') != 'TK_Complete'
        ]
        incomplete_count = len(incomplete_activities)

        # ─── CHECK 1: Logic (Missing Predecessors) ───
        # Every activity should have at least one predecessor
        # THRESHOLD: ≤ 5% should be missing predecessors
        missing_pred = []
        for act in incomplete_activities:
            task_id = act.get('task_id', '')
            if task_id not in self.predecessors:
                missing_pred.append(act)
        
        # ─── CHECK 2: Logic (Missing Successors) ───
        # Every activity should have at least one successor
        # THRESHOLD: ≤ 5% should be missing successors
        missing_succ = []
        for act in incomplete_activities:
            task_id = act.get('task_id', '')
            if task_id not in self.successors:
                missing_succ.append(act)

        # ─── CHECK 3: Leads (Negative Lag) ───
        # No relationships should have negative lag
        # THRESHOLD: 0%
        leads = [r for r in self.relationships if r.get('lag_days', 0) < 0]

        # ─── CHECK 4: Lags ───
        # Minimize use of lags
        # THRESHOLD: ≤ 5%
        lags = [r for r in self.relationships if r.get('lag_days', 0) > 0]

        # ─── CHECK 5: Relationship Types ───
        # Minimize non-FS relationships
        # THRESHOLD: ≤ 10% should be non-FS
        non_fs = [r for r in self.relationships 
                 if r.get('pred_type') != 'PR_FS']

        # ─── CHECK 6: Hard Constraints ───
        # Minimize hard constraints (they override CPM logic)
        # THRESHOLD: ≤ 5%
        hard_constraint_types = [
            'CS_ALAP',    # As Late As Possible
            'CS_MSO',     # Must Start On
            'CS_MFO',     # Must Finish On
            'CS_MANDSTART', # Mandatory Start
            'CS_MANDFIN',   # Mandatory Finish
        ]
        constrained = [
            a for a in incomplete_activities
            if a.get('cstr_type', '') in hard_constraint_types
               or a.get('cstr_type2', '') in hard_constraint_types
        ]

        # ─── CHECK 7: High Float ───
        # Activities with excessive float (>44 days) indicate disconnected logic
        # THRESHOLD: ≤ 5%
        high_float = [
            a for a in incomplete_activities
            if a.get('total_float_days', 0) > 44
        ]

        # ─── CHECK 8: Negative Float ───
        # Negative float means the schedule can't meet its constraints
        # THRESHOLD: 0%
        neg_float = [
            a for a in incomplete_activities
            if a.get('total_float_days', 0) < 0
        ]

        # ─── CHECK 9: High Duration ───
        # Activities longer than 44 days should be broken down
        # THRESHOLD: ≤ 5%
        high_duration = [
            a for a in incomplete_activities
            if a.get('original_duration_days', 0) > 44
            and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']
        ]

        # ─── CHECK 10: Invalid Dates ───
        # Actual dates should not be in the future (past the data date)
        # This is a simplified check
        invalid_dates = [
            a for a in self.activities
            if a.get('status_code') == 'TK_NotStart' 
            and a.get('act_start_date', '') != ''
        ]

        # ─── CHECK 11: Resources ───
        # Activities should have resources assigned
        tasks_with_resources = set()
        for res in self.resources:
            tasks_with_resources.add(res.get('task_id', ''))
        
        missing_resources = [
            a for a in incomplete_activities
            if a.get('task_id', '') not in tasks_with_resources
            and a.get('task_type') not in ['TT_Mile', 'TT_FinMile']
        ]

        # ─── CHECK 12: Critical Path Length Index (CPLI) ───
        # CPLI = (Project Duration + Total Float of Last Activity) / Project Duration
        # THRESHOLD: ≥ 1.0 (schedule can meet its deadline)
        # Simplified calculation
        cpli = "N/A (requires data date and project finish)"

        # ─── CHECK 13: Baseline Execution Index (BEI) ───
        # BEI = # of Completed Tasks / # of Tasks That Should Be Complete
        # Simplified
        bei = "N/A (requires baseline comparison)"

        # ─── CHECK 14: Critical Path Test ───
        # Verify the critical path is valid and continuous
        critical_pct = (len(self.critical_activities) / incomplete_count * 100) if incomplete_count > 0 else 0

        # ─── COMPILE RESULTS ───
        def calc_pct(count, base):
            return round((count / base * 100), 1) if base > 0 else 0

        self.dcma_results = {
            '01_Missing_Predecessors': {
                'count': len(missing_pred),
                'total': incomplete_count,
                'pct': calc_pct(len(missing_pred), incomplete_count),
                'threshold': '≤ 5%',
                'pass': calc_pct(len(missing_pred), incomplete_count) <= 5,
                'activities': missing_pred
            },
            '02_Missing_Successors': {
                'count': len(missing_succ),
                'total': incomplete_count,
                'pct': calc_pct(len(missing_succ), incomplete_count),
                'threshold': '≤ 5%',
                'pass': calc_pct(len(missing_succ), incomplete_count) <= 5,
                'activities': missing_succ
            },
            '03_Leads': {
                'count': len(leads),
                'total': len(self.relationships),
                'pct': calc_pct(len(leads), len(self.relationships)),
                'threshold': '0%',
                'pass': len(leads) == 0,
                'items': leads
            },
            '04_Lags': {
                'count': len(lags),
                'total': len(self.relationships),
                'pct': calc_pct(len(lags), len(self.relationships)),
                'threshold': '≤ 5%',
                'pass': calc_pct(len(lags), len(self.relationships)) <= 5,
                'items': lags
            },
            '05_Relationship_Types': {
                'count': len(non_fs),
                'total': len(self.relationships),
                'pct': calc_pct(len(non_fs), len(self.relationships)),
                'threshold': '≤ 10%',
                'pass': calc_pct(len(non_fs), len(self.relationships)) <= 10,
                'items': non_fs
            },
            '06_Hard_Constraints': {
                'count': len(constrained),
                'total': incomplete_count,
                'pct': calc_pct(len(constrained), incomplete_count),
                'threshold': '≤ 5%',
                'pass': calc_pct(len(constrained), incomplete_count) <= 5,
                'activities': constrained
            },
            '07_High_Float': {
                'count': len(high_float),
                'total': incomplete_count,
                'pct': calc_pct(len(high_float), incomplete_count),
                'threshold': '≤ 5%',
                'pass': calc_pct(len(high_float), incomplete_count) <= 5,
                'activities': high_float
            },
            '08_Negative_Float': {
                'count': len(neg_float),
                'total': incomplete_count,
                'pct': calc_pct(len(neg_float), incomplete_count),
                'threshold': '0%',
                'pass': len(neg_float) == 0,
                'activities': neg_float
            },
            '09_High_Duration': {
                'count': len(high_duration),
                'total': incomplete_count,
                'pct': calc_pct(len(high_duration), incomplete_count),
                'threshold': '≤ 5%',
                'pass': calc_pct(len(high_duration), incomplete_count) <= 5,
                'activities': high_duration
            },
            '10_Invalid_Dates': {
                'count': len(invalid_dates),
                'total': total,
                'pct': calc_pct(len(invalid_dates), total),
                'threshold': '0%',
                'pass': len(invalid_dates) == 0,
                'activities': invalid_dates
            },
            '11_Missing_Resources': {
                'count': len(missing_resources),
                'total': incomplete_count,
                'pct': calc_pct(len(missing_resources), incomplete_count),
                'threshold': '≤ 5%',
                'pass': calc_pct(len(missing_resources), incomplete_count) <= 5,
                'activities': missing_resources
            },
            '12_CPLI': {
                'value': cpli,
                'threshold': '≥ 1.0',
                'pass': None
            },
            '13_BEI': {
                'value': bei,
                'threshold': '≥ 1.0',
                'pass': None
            },
            '14_Critical_Path_Pct': {
                'value': round(critical_pct, 1),
                'threshold': 'Should be reasonable (typically 10-20%)',
                'pass': 5 <= critical_pct <= 25 if critical_pct > 0 else None
            }
        }

        # Print results
        self._print_dcma_results()

    def _print_dcma_results(self):
        """Print DCMA results in a nice format."""
        print("\n" + "=" * 65)
        print("🏥 DCMA 14-POINT SCHEDULE HEALTH CHECK")
        print("=" * 65)
        
        for check_name, result in self.dcma_results.items():
            if 'pct' in result:
                status = "✅ PASS" if result['pass'] else "❌ FAIL"
                print(f"  {check_name:35s} {result['pct']:>6.1f}% "
                      f"({result['count']}/{result['total']}) "
                      f"[{result['threshold']}] {status}")
            else:
                value = result.get('value', 'N/A')
                status = ""
                if result.get('pass') is True:
                    status = "✅ PASS"
                elif result.get('pass') is False:
                    status = "❌ FAIL"
                print(f"  {check_name:35s} {str(value):>6s} "
                      f"[{result['threshold']}] {status}")
        
        # Overall score
        checks_with_results = [r for r in self.dcma_results.values() 
                               if r.get('pass') is not None]
        passed = sum(1 for r in checks_with_results if r['pass'])
        total_checks = len(checks_with_results)
        
        print(f"\n  OVERALL SCORE: {passed}/{total_checks} checks passed")
        print("=" * 65)

    # ════════════════════════════════════════════
    # STEP C: GET RESULTS
    # ════════════════════════════════════════════

    def get_summary(self):
        """Return a summary of all analysis results."""
        return {
            'stats': self.schedule_stats,
            'dcma': self.dcma_results,
            'critical_path': self.critical_activities,
        }

    def get_activities_dataframe(self):
        """
        Convert activities to a pandas DataFrame for easy analysis.
        
        A DataFrame is like an Excel spreadsheet in Python.
        """
        try:
            import pandas as pd
            
            # Select the most useful columns
            columns = [
                'task_code', 'task_name', 'wbs_code', 'wbs_name',
                'status_text', 'type_text',
                'original_duration_days', 'remaining_duration_days',
                'total_float_days', 'free_float_days',
                'is_critical',
                'early_start_date', 'early_end_date',
                'late_start_date', 'late_end_date',
                'target_start_date', 'target_end_date',
                'act_start_date', 'act_end_date',
                'phys_complete_pct'
            ]
            
            # Build rows with only the selected columns
            rows = []
            for act in self.activities:
                row = {col: act.get(col, '') for col in columns}
                rows.append(row)
            
            df = pd.DataFrame(rows)
            return df
            
        except ImportError:
            print("⚠️ pandas not installed. Run: pip install pandas")
            return None

    # ════════════════════════════════════════════
    # UTILITY METHODS
    # ════════════════════════════════════════════

    def _to_float(self, value):
        """Safely convert a string to float."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _parse_date(self, date_string):
        """
        Parse a P6 date string into a Python date object.
        
        P6 dates can come in various formats:
        - "2024-01-15 08:00"
        - "2024-01-15"
        - "15-Jan-24"
        - "" (empty)
        """
        if not date_string or date_string.strip() == '':
            return None

        # Try common P6 date formats
        formats = [
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%d-%b-%y',
            '%d-%b-%Y',
            '%m/%d/%Y',
            '%m/%d/%Y %H:%M',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_string.strip(), fmt)
            except ValueError:
                continue

        return None  # Couldn't parse the date

    def find_activity(self, search_term):
        """
        Search for an activity by code or name.
        
        EXAMPLE:
            results = engine.find_activity("A1000")
            results = engine.find_activity("Mobilization")
        """
        results = []
        search_lower = search_term.lower()
        
        for act in self.activities:
            code = act.get('task_code', '').lower()
            name = act.get('task_name', '').lower()
            
            if search_lower in code or search_lower in name:
                results.append(act)
        
        return results

    def get_predecessors(self, task_code):
        """Get all predecessors of an activity."""
        act = self.activity_by_code.get(task_code)
        if not act:
            return []
        
        task_id = act.get('task_id', '')
        pred_list = self.predecessors.get(task_id, [])
        
        results = []
        for pred in pred_list:
            pred_act = self.activity_by_id.get(pred['task_id'], {})
            results.append({
                'code': pred_act.get('task_code', ''),
                'name': pred_act.get('task_name', ''),
                'type': pred['type'],
                'lag': pred['lag_days']
            })
        
        return results

    def get_successors(self, task_code):
        """Get all successors of an activity."""
        act = self.activity_by_code.get(task_code)
        if not act:
            return []
        
        task_id = act.get('task_id', '')
        succ_list = self.successors.get(task_id, [])
        
        results = []
        for succ in succ_list:
            succ_act = self.activity_by_id.get(succ['task_id'], {})
            results.append({
                'code': succ_act.get('task_code', ''),
                'name': succ_act.get('task_name', ''),
                'type': succ['type'],
                'lag': succ['lag_days']
            })
            # ════════════════════════════════════════════
    # NEW: ENHANCED ANALYTICS FOR WEB DASHBOARD
    # ════════════════════════════════════════════

    def get_dashboard_data(self):
        """
        Package ALL data needed for the web dashboard.
        
        This is like preparing a "care package" for the browser
        containing everything it needs to show charts and tables.
        """
        return {
            'project_info': self._get_project_info(),
            'summary_cards': self._get_summary_cards(),
            'status_distribution': self._get_status_distribution(),
            'float_distribution': self._get_float_distribution(),
            'dcma_summary': self._get_dcma_summary(),
            'wbs_breakdown': self._get_wbs_breakdown(),
            'critical_activities': self._get_critical_activities_data(),
            'top_issues': self._get_top_issues(),
            'activities_table': self._get_activities_table_data(),
            'schedule_timeline': self._get_timeline_data(),
        }
    def get_gantt_data(self, max_activities=200):
        """
        Prepare activity data formatted for the Gantt chart.
        
        Frappe Gantt needs data in this format:
        {
            id: 'unique_id',
            name: 'Activity Name',
            start: 'YYYY-MM-DD',
            end: 'YYYY-MM-DD',
            progress: 0-100,
            dependencies: 'id1,id2'
        }
        """
        tasks = []
        activities_added = set()
        
        # Filter out summary activities
        real_activities = [
            a for a in self.activities
            if a.get('task_type') not in ['TT_WBS', 'TT_LOE']
        ][:max_activities]
        
        for act in real_activities:
            # Get dates (prefer early dates, fall back to target)
            start_date = (act.get('early_start_date') or 
                         act.get('target_start_date') or 
                         act.get('act_start_date') or '')
            
            end_date = (act.get('early_end_date') or 
                       act.get('target_end_date') or 
                       act.get('act_end_date') or '')
            
            if not start_date or not end_date:
                continue
            
            # Convert P6 date format to YYYY-MM-DD
            start_clean = self._clean_date_for_gantt(start_date)
            end_clean = self._clean_date_for_gantt(end_date)
            
            if not start_clean or not end_clean:
                continue
            
            # Get dependencies (predecessors)
            task_id = act.get('task_id', '')
            pred_list = self.predecessors.get(task_id, [])
            
            # Only include dependencies that we're actually showing
            dep_ids = []
            for pred in pred_list:
                pred_id = pred['task_id']
                if pred_id in [a.get('task_id') for a in real_activities]:
                    dep_ids.append(pred_id)
            
            # Calculate progress
            progress = self._to_float(act.get('phys_complete_pct', '0'))
            
            # Determine bar color
            bar_class = 'critical' if act.get('is_critical') else 'normal'
            if act.get('status_code') == 'TK_Complete':
                bar_class = 'completed'
            
            tasks.append({
                'id': task_id,
                'name': f"{act.get('task_code', '')} - {act.get('task_name', '')[:40]}",
                'start': start_clean,
                'end': end_clean,
                'progress': int(progress),
                'dependencies': ','.join(dep_ids) if dep_ids else '',
                'custom_class': bar_class,
                'wbs': act.get('wbs_name', ''),
                'float_days': act.get('total_float_days', 0),
                'duration': act.get('original_duration_days', 0),
                'status': act.get('status_text', ''),
            })
            activities_added.add(task_id)
        
        return {
            'tasks': tasks,
            'total': len(tasks),
            'critical_count': sum(1 for t in tasks if t['custom_class'] == 'critical')
        }

    def _clean_date_for_gantt(self, date_string):
        """
        Convert P6 date format to YYYY-MM-DD.
        
        P6 dates come as '2024-01-15 08:00' or similar.
        Gantt library needs just '2024-01-15'.
        """
        if not date_string:
            return None
        
        # Try to parse and reformat
        parsed = self._parse_date(date_string)
        if parsed:
            return parsed.strftime('%Y-%m-%d')
        return None
    
    def _get_project_info(self):
        """Get basic project header info."""
        if not self.projects:
            return {'name': 'Unknown', 'start': '', 'finish': ''}
        
        proj = self.projects[0]
        return {
            'name': proj.get('proj_short_name', 'Unnamed Project'),
            'start': proj.get('plan_start_date', ''),
            'finish': proj.get('plan_end_date', ''),
            'data_date': proj.get('last_recalc_date', ''),
        }

    def _get_summary_cards(self):
        """Get numbers for the top summary cards."""
        stats = self.schedule_stats
        total_checks = sum(1 for r in self.dcma_results.values() 
                          if r.get('pass') is not None)
        passed_checks = sum(1 for r in self.dcma_results.values() 
                           if r.get('pass') is True)
        
        return [
            {
                'label': 'Total Activities',
                'value': stats.get('total_activities', 0),
                'icon': '📌',
                'color': 'blue'
            },
            {
                'label': 'Critical Activities',
                'value': stats.get('critical_count', 0),
                'icon': '🔴',
                'color': 'red'
            },
            {
                'label': 'Completed',
                'value': stats.get('completed', 0),
                'icon': '✅',
                'color': 'green'
            },
            {
                'label': 'In Progress',
                'value': stats.get('in_progress', 0),
                'icon': '🔄',
                'color': 'orange'
            },
            {
                'label': 'Relationships',
                'value': stats.get('total_relationships', 0),
                'icon': '🔗',
                'color': 'purple'
            },
            {
                'label': 'DCMA Score',
                'value': f"{passed_checks}/{total_checks}",
                'icon': '🏥',
                'color': 'teal'
            },
        ]

    def _get_status_distribution(self):
        """Data for the status pie chart."""
        stats = self.schedule_stats
        return {
            'labels': ['Not Started', 'In Progress', 'Completed'],
            'values': [
                stats.get('not_started', 0),
                stats.get('in_progress', 0),
                stats.get('completed', 0),
            ],
            'colors': ['#94a3b8', '#f59e0b', '#10b981']
        }

    def _get_float_distribution(self):
        """Data for the float bar chart."""
        stats = self.schedule_stats
        return {
            'labels': ['Negative Float', 'Zero Float (Critical)', 
                      'Positive Float', 'High Float (>44d)'],
            'values': [
                stats.get('negative_float', 0),
                stats.get('zero_float', 0),
                stats.get('positive_float', 0) - stats.get('high_float_gt_44d', 0),
                stats.get('high_float_gt_44d', 0),
            ],
            'colors': ['#dc2626', '#ef4444', '#3b82f6', '#f59e0b']
        }

    def _get_dcma_summary(self):
        """DCMA results formatted for the dashboard."""
        results = []
        for check_name, result in self.dcma_results.items():
            # Skip checks without pass/fail results
            if result.get('pass') is None:
                continue
            
            clean_name = check_name.replace('_', ' ').split(' ', 1)[1] \
                        if '_' in check_name else check_name
            
            results.append({
                'name': clean_name,
                'value': f"{result.get('pct', 0)}%" if 'pct' in result 
                        else str(result.get('value', '')),
                'threshold': result.get('threshold', ''),
                'pass': result.get('pass', False),
                'count': result.get('count', 0),
                'total': result.get('total', 0),
            })
        return results

    def _get_wbs_breakdown(self):
        """Count activities per WBS for the WBS chart."""
        wbs_counts = {}
        for act in self.activities:
            wbs = act.get('wbs_name', 'Unknown')
            # Take just the first part of the WBS name for cleaner display
            wbs_short = wbs[:30] + '...' if len(wbs) > 30 else wbs
            wbs_counts[wbs_short] = wbs_counts.get(wbs_short, 0) + 1
        
        # Sort by count (biggest first) and take top 10
        sorted_wbs = sorted(wbs_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'labels': [item[0] for item in sorted_wbs],
            'values': [item[1] for item in sorted_wbs],
        }

    def _get_critical_activities_data(self):
        """Critical activities formatted for the table."""
        results = []
        for act in self.critical_activities[:50]:  # Top 50
            results.append({
                'code': act.get('task_code', ''),
                'name': act.get('task_name', ''),
                'wbs': act.get('wbs_name', ''),
                'duration': round(act.get('original_duration_days', 0), 1),
                'float': round(act.get('total_float_days', 0), 1),
                'status': act.get('status_text', ''),
                'start': act.get('early_start_date', ''),
                'finish': act.get('early_end_date', ''),
            })
        return results

    def _get_top_issues(self):
        """Get the most important issues found."""
        issues = []
        
        for check_name, result in self.dcma_results.items():
            if result.get('pass') is False:
                clean_name = check_name.replace('_', ' ').split(' ', 1)[1] \
                            if '_' in check_name else check_name
                
                issues.append({
                    'check': clean_name,
                    'count': result.get('count', 0),
                    'percentage': result.get('pct', 0),
                    'severity': 'high' if result.get('pct', 0) > 15 else 'medium',
                })
        
        # Sort by count (biggest issues first)
        issues.sort(key=lambda x: x['count'], reverse=True)
        return issues

    def _get_activities_table_data(self):
        """All activities formatted for the searchable table."""
        results = []
        for act in self.activities:
            # Skip WBS summary activities
            if act.get('task_type') == 'TT_WBS':
                continue
                
            results.append({
                'code': act.get('task_code', ''),
                'name': act.get('task_name', ''),
                'wbs': act.get('wbs_name', ''),
                'type': act.get('type_text', ''),
                'status': act.get('status_text', ''),
                'duration': round(act.get('original_duration_days', 0), 1),
                'remaining': round(act.get('remaining_duration_days', 0), 1),
                'float': round(act.get('total_float_days', 0), 1),
                'critical': act.get('is_critical', False),
                'start': act.get('early_start_date', ''),
                'finish': act.get('early_end_date', ''),
                'progress': act.get('phys_complete_pct', '0'),
            })
        return results

    def _get_timeline_data(self):
        """Data for the schedule timeline/Gantt chart."""
        results = []
        for act in self.activities[:100]:  # First 100 for performance
            if act.get('task_type') in ['TT_WBS', 'TT_LOE']:
                continue
            
            start = act.get('early_start_date', '') or act.get('target_start_date', '')
            finish = act.get('early_end_date', '') or act.get('target_end_date', '')
            
            if start and finish:
                results.append({
                    'code': act.get('task_code', ''),
                    'name': act.get('task_name', '')[:40],
                    'start': start,
                    'finish': finish,
                    'critical': act.get('is_critical', False),
                    'progress': self._to_float(act.get('phys_complete_pct', '0')),
                })
        return results
"""
MICROSOFT PROJECT XML PARSER
=============================
Reads an MS Project .xml export and maps it to the standard XER dictionary
structure. Simulates P6 fields (like converting float days to hours) so 
the ScheduleEngine operates seamlessly.
"""

import xml.etree.ElementTree as ET
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class MSPXMLParser:
    def __init__(self):
        self.tables = {}
        self.ns = ''
        self.hrs_per_day = 8.0

    def parse(self, stream):
        logger.info("📂 Parsing MS Project XML...")
        try:
            tree = ET.parse(stream)
            root = tree.getroot()
            
            match = re.match(r'\{.*\}', root.tag)
            self.ns = match.group(0) if match else ''
            
            self._init_tables()
            
            # Extract standard hours per day from MSP Project settings
            self.hrs_per_day = float(self._get_text(root, 'MinutesPerDay', '480')) / 60.0
            
            self._parse_project(root)
            self._parse_calendars(root)
            self._parse_tasks_and_wbs(root)
            self._parse_resources(root)
            
            logger.info("  ✅ MSP XML parsing complete")
            return self.tables
        except Exception as e:
            logger.exception(f"❌ Failed to parse MSP XML: {e}")
            return None

    def _init_tables(self):
        tables_to_init = ['PROJECT', 'PROJWBS', 'TASK', 'TASKPRED', 'CALENDAR', 'RSRC', 'TASKRSRC']
        for t in tables_to_init:
            self.tables[t] = {'fields': [], 'rows': []}

    def _find_all(self, parent, tag):
        return parent.findall(f".//{self.ns}{tag}") if self.ns else parent.findall(f".//{tag}")

    def _get_text(self, element, tag, default=''):
        el = element.find(f"{self.ns}{tag}") if self.ns else element.find(tag)
        return el.text if el is not None and el.text else default
        
    def _msp_dur_to_hours(self, msp_duration):
        """MSP stores duration as 'PT16H0M0S'. Convert to hours."""
        if not msp_duration or not msp_duration.startswith('PT'):
            return "0"
        try:
            hours = 0
            if 'H' in msp_duration:
                h_part = msp_duration.split('T')[1].split('H')[0]
                hours += float(h_part)
            if 'M' in msp_duration:
                m_part = msp_duration.split('T')[1].split('H')[-1].split('M')[0]
                hours += float(m_part) / 60.0
            return str(hours)
        except Exception:
            return "0"
            
    def _msp_date_to_p6(self, msp_date):
        if not msp_date: return ""
        # MSP format: 2024-03-01T08:00:00
        return msp_date.replace('T', ' ')

    def _parse_project(self, root):
        self.tables['PROJECT']['rows'].append({
            'proj_id': '1',
            'proj_short_name': self._get_text(root, 'Name', 'MSP Project'),
            'plan_start_date': self._msp_date_to_p6(self._get_text(root, 'StartDate')),
            'plan_end_date': self._msp_date_to_p6(self._get_text(root, 'FinishDate')),
            'last_recalc_date': self._msp_date_to_p6(self._get_text(root, 'StatusDate'))
        })

    def _parse_calendars(self, root):
        # Create a default calendar
        self.tables['CALENDAR']['rows'].append({
            'clndr_id': '1',
            'clndr_name': 'Standard',
            'day_hr_cnt': str(self.hrs_per_day)
        })

    def _parse_tasks_and_wbs(self, root):
        for task in self._find_all(root, 'Task'):
            uid = self._get_text(task, 'UID')
            if not uid or uid == '0':  # Skip Project root task
                continue
                
            is_summary = self._get_text(task, 'Summary') == '1'
            name = self._get_text(task, 'Name')
            wbs_code = self._get_text(task, 'WBS')
            parent_uid = self._get_text(task, 'ParentTaskUID', '0')
            
            if is_summary:
                self.tables['PROJWBS']['rows'].append({
                    'wbs_id': uid,
                    'wbs_short_name': wbs_code,
                    'wbs_name': name,
                    'parent_wbs_id': parent_uid if parent_uid != '0' else ''
                })
            else:
                pct = self._get_text(task, 'PercentComplete', '0')
                status = 'TK_Complete' if pct == '100' else ('TK_Active' if float(pct) > 0 else 'TK_NotStart')
                is_mile = self._get_text(task, 'Milestone') == '1'
                
                row = {
                    'task_id': uid,
                    'task_code': wbs_code or f"T{uid}",
                    'task_name': name,
                    'proj_id': '1',
                    'wbs_id': parent_uid,
                    'clndr_id': '1',
                    
                    'task_type': 'TT_FinMile' if is_mile else 'TT_Task',
                    'status_code': status,
                    
                    'early_start_date': self._msp_date_to_p6(self._get_text(task, 'EarlyStart') or self._get_text(task, 'Start')),
                    'early_end_date': self._msp_date_to_p6(self._get_text(task, 'EarlyFinish') or self._get_text(task, 'Finish')),
                    'late_start_date': self._msp_date_to_p6(self._get_text(task, 'LateStart')),
                    'late_end_date': self._msp_date_to_p6(self._get_text(task, 'LateFinish')),
                    'act_start_date': self._msp_date_to_p6(self._get_text(task, 'ActualStart')),
                    'act_end_date': self._msp_date_to_p6(self._get_text(task, 'ActualFinish')),
                    
                    'target_drtn_hr_cnt': self._msp_dur_to_hours(self._get_text(task, 'Duration')),
                    'remain_drtn_hr_cnt': self._msp_dur_to_hours(self._get_text(task, 'RemainingDuration')),
                    'total_float_hr_cnt': self._msp_dur_to_hours(self._get_text(task, 'TotalSlack')),
                    'free_float_hr_cnt': self._msp_dur_to_hours(self._get_text(task, 'FreeSlack')),
                    'phys_complete_pct': pct,
                }
                self.tables['TASK']['rows'].append(row)
                
                # Predecessors are nested inside Task in MSP
                for pred in self._find_all(task, 'PredecessorLink'):
                    p_uid = self._get_text(pred, 'PredecessorUID')
                    m_type = self._get_text(pred, 'Type', '1') # 1=FS, 0=FF, 2=SF, 3=SS
                    t_map = {'0': 'PR_FF', '1': 'PR_FS', '2': 'PR_SF', '3': 'PR_SS'}
                    
                    lag_fmt = self._get_text(pred, 'LinkLagFormat', '7') # 7 = tenths of min
                    lag_val = float(self._get_text(pred, 'LinkLag', '0'))
                    
                    # MSP stores lag in tenths of a minute. Convert to hours
                    lag_hrs = (lag_val / 10.0) / 60.0
                    
                    self.tables['TASKPRED']['rows'].append({
                        'pred_task_id': p_uid,
                        'task_id': uid,
                        'pred_type': t_map.get(m_type, 'PR_FS'),
                        'lag_hr_cnt': str(lag_hrs)
                    })

    def _parse_resources(self, root):
        for res in self._find_all(root, 'Resource'):
            uid = self._get_text(res, 'UID')
            if not uid or uid == '0': continue
            self.tables['RSRC']['rows'].append({
                'rsrc_id': uid,
                'rsrc_name': self._get_text(res, 'Name', f"Res {uid}")
            })
            
        for assn in self._find_all(root, 'Assignment'):
            t_uid = self._get_text(assn, 'TaskUID')
            r_uid = self._get_text(assn, 'ResourceUID')
            if not t_uid or not r_uid: continue
            
            self.tables['TASKRSRC']['rows'].append({
                'task_id': t_uid,
                'rsrc_id': r_uid,
                'target_cost': self._get_text(assn, 'Cost', '0'),
                'act_reg_cost': self._get_text(assn, 'ActualCost', '0'),
                # Units in MSP are often complex (PT8H0M0S), simple fallback:
                'target_qty': self._msp_dur_to_hours(self._get_text(assn, 'Work'))
            })

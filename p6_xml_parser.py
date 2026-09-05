"""
PRIMAVERA P6 XML PARSER
=======================
Reads a Primavera P6 .xml export and maps it to the standard XER dictionary
structure so existing engines can process it seamlessly.
"""

import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

class P6XMLParser:
    def __init__(self):
        self.tables = {}
        self.ns = ''

    def parse(self, stream):
        logger.info("📂 Parsing P6 XML...")
        try:
            tree = ET.parse(stream)
            root = tree.getroot()
            
            # Extract namespace (P6 XMLs use xmlns)
            match = re.match(r'\{.*\}', root.tag)
            self.ns = match.group(0) if match else ''
            
            self._init_tables()
            self._parse_projects(root)
            self._parse_wbs(root)
            self._parse_activities(root)
            self._parse_relationships(root)
            self._parse_calendars(root)
            self._parse_resources(root)
            
            logger.info("  ✅ P6 XML parsing complete")
            return self.tables
        except Exception as e:
            logger.exception(f"❌ Failed to parse P6 XML: {e}")
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

    def _parse_projects(self, root):
        for proj in self._find_all(root, 'Project'):
            self.tables['PROJECT']['rows'].append({
                'proj_id': self._get_text(proj, 'ObjectId'),
                'proj_short_name': self._get_text(proj, 'Id'),
                'plan_start_date': self._get_text(proj, 'PlannedStartDate'),
                'plan_end_date': self._get_text(proj, 'MustFinishByDate'),
                'last_recalc_date': self._get_text(proj, 'DataDate')
            })

    def _parse_wbs(self, root):
        for wbs in self._find_all(root, 'WBS'):
            self.tables['PROJWBS']['rows'].append({
                'wbs_id': self._get_text(wbs, 'ObjectId'),
                'wbs_short_name': self._get_text(wbs, 'Code'),
                'wbs_name': self._get_text(wbs, 'Name'),
                'parent_wbs_id': self._get_text(wbs, 'ParentObjectId')
            })

    def _parse_activities(self, root):
        for act in self._find_all(root, 'Activity'):
            
            # Map activity types
            xml_type = self._get_text(act, 'Type', 'Task Dependent')
            type_map = {
                'Task Dependent': 'TT_Task',
                'Resource Dependent': 'TT_Rsrc',
                'Start Milestone': 'TT_Mile',
                'Finish Milestone': 'TT_FinMile',
                'Level of Effort': 'TT_LOE',
                'WBS Summary': 'TT_WBS'
            }
            
            # Map status
            xml_status = self._get_text(act, 'Status', 'Not Started')
            status_map = {
                'Not Started': 'TK_NotStart',
                'In Progress': 'TK_Active',
                'Completed': 'TK_Complete'
            }
            
            row = {
                'task_id': self._get_text(act, 'ObjectId'),
                'task_code': self._get_text(act, 'Id'),
                'task_name': self._get_text(act, 'Name'),
                'proj_id': self._get_text(act, 'ProjectObjectId'),
                'wbs_id': self._get_text(act, 'WBSObjectId'),
                'clndr_id': self._get_text(act, 'CalendarObjectId'),
                
                'task_type': type_map.get(xml_type, 'TT_Task'),
                'status_code': status_map.get(xml_status, 'TK_NotStart'),
                
                # Dates
                'early_start_date': self._get_text(act, 'EarlyStartDate'),
                'early_end_date': self._get_text(act, 'EarlyFinishDate'),
                'late_start_date': self._get_text(act, 'LateStartDate'),
                'late_end_date': self._get_text(act, 'LateFinishDate'),
                'target_start_date': self._get_text(act, 'PlannedStartDate'),
                'target_end_date': self._get_text(act, 'PlannedFinishDate'),
                'act_start_date': self._get_text(act, 'ActualStartDate'),
                'act_end_date': self._get_text(act, 'ActualFinishDate'),
                
                # Durations and Float (XML uses hours)
                'target_drtn_hr_cnt': self._get_text(act, 'PlannedDuration'),
                'remain_drtn_hr_cnt': self._get_text(act, 'RemainingDuration'),
                'total_float_hr_cnt': self._get_text(act, 'TotalFloat'),
                'free_float_hr_cnt': self._get_text(act, 'FreeFloat'),
                'phys_complete_pct': self._get_text(act, 'PhysicalPercentComplete'),
                
                # Constraints
                'cstr_type': self._map_constraint(self._get_text(act, 'PrimaryConstraintType')),
                'cstr_date': self._get_text(act, 'PrimaryConstraintDate'),
                'cstr_type2': self._map_constraint(self._get_text(act, 'SecondaryConstraintType')),
                'cstr_date2': self._get_text(act, 'SecondaryConstraintDate'),
            }
            self.tables['TASK']['rows'].append(row)

    def _map_constraint(self, xml_cstr):
        cmap = {
            'Start On': 'CS_MSO', 'Start On or After': 'CS_MSOA', 'Start On or Before': 'CS_MSOB',
            'Finish On': 'CS_MEO', 'Finish On or After': 'CS_MEOA', 'Finish On or Before': 'CS_MEOB',
            'Mandatory Start': 'CS_MANDSTART', 'Mandatory Finish': 'CS_MANDFIN', 'As Late As Possible': 'CS_ALAP'
        }
        return cmap.get(xml_cstr, '')

    def _parse_relationships(self, root):
        for rel in self._find_all(root, 'Relationship'):
            xml_type = self._get_text(rel, 'Type', 'Finish to Start')
            type_map = {
                'Finish to Start': 'PR_FS', 'Start to Start': 'PR_SS',
                'Finish to Finish': 'PR_FF', 'Start to Finish': 'PR_SF'
            }
            self.tables['TASKPRED']['rows'].append({
                'pred_task_id': self._get_text(rel, 'PredecessorActivityObjectId'),
                'task_id': self._get_text(rel, 'SuccessorActivityObjectId'),
                'pred_type': type_map.get(xml_type, 'PR_FS'),
                'lag_hr_cnt': self._get_text(rel, 'Lag')
            })

    def _parse_calendars(self, root):
        for cal in self._find_all(root, 'Calendar'):
            self.tables['CALENDAR']['rows'].append({
                'clndr_id': self._get_text(cal, 'ObjectId'),
                'clndr_name': self._get_text(cal, 'Name'),
                'day_hr_cnt': self._get_text(cal, 'HoursPerDay', '8')
            })

    def _parse_resources(self, root):
        for rsrc in self._find_all(root, 'Resource'):
            self.tables['RSRC']['rows'].append({
                'rsrc_id': self._get_text(rsrc, 'ObjectId'),
                'rsrc_short_name': self._get_text(rsrc, 'Id'),
                'rsrc_name': self._get_text(rsrc, 'Name')
            })
            
        for assign in self._find_all(root, 'ResourceAssignment'):
            self.tables['TASKRSRC']['rows'].append({
                'task_id': self._get_text(assign, 'ActivityObjectId'),
                'rsrc_id': self._get_text(assign, 'ResourceObjectId'),
                'target_qty': self._get_text(assign, 'PlannedUnits'),
                'target_cost': self._get_text(assign, 'PlannedCost'),
                'act_reg_qty': self._get_text(assign, 'ActualUnits'),
                'act_reg_cost': self._get_text(assign, 'ActualCost')
            })

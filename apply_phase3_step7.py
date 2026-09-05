import os
import shutil
from datetime import datetime
import re

print("🚀 Applying Phase 3 - Step 7: Multi-Format Importers (P6 XML & MS Project)...")

# 1. Create Backup Folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = f"_backup_phase3_step7_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
print(f"📦 Created backup folder: {backup_dir}")

files_to_backup = [
    "app.py",
    "templates/index.html",
    "templates/comparison.html",
    "templates/trends.html",
    "static/dashboard.js",
    "static/comparison.js",
    "static/trends.js",
]

for file_path in files_to_backup:
    if os.path.exists(file_path):
        dest = os.path.join(backup_dir, os.path.basename(file_path.replace("/", os.sep)))
        shutil.copy2(file_path, dest)
        print(f"   Backed up {file_path}")


# ==============================================================================
# FILE 1: p6_xml_parser.py (NEW)
# ==============================================================================

P6_XML_PARSER_CODE = '''"""
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
'''

with open("p6_xml_parser.py", "w", encoding="utf-8") as f:
    f.write(P6_XML_PARSER_CODE)
print("  ✅ Created p6_xml_parser.py")


# ==============================================================================
# FILE 2: msp_xml_parser.py (NEW)
# ==============================================================================

MSP_XML_PARSER_CODE = '''"""
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
'''

with open("msp_xml_parser.py", "w", encoding="utf-8") as f:
    f.write(MSP_XML_PARSER_CODE)
print("  ✅ Created msp_xml_parser.py")


# ==============================================================================
# FILE 3: universal_parser.py (NEW - Factory Router)
# ==============================================================================

UNIVERSAL_PARSER_CODE = '''"""
UNIVERSAL SCHEDULE PARSER
=========================
Detects file type (.xer, P6 .xml, MSP .xml) and routes to the appropriate parser.
Returns standard XER dictionary structure regardless of input format.
"""

from parser import XERParser
from p6_xml_parser import P6XMLParser
from msp_xml_parser import MSPXMLParser
import logging

logger = logging.getLogger(__name__)

class UniversalParser:
    def parse(self, stream, filename):
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if ext == 'xer':
            logger.info("Routing to XER Parser")
            return XERParser().parse(stream)
            
        elif ext == 'xml':
            # Peak at first few lines to differentiate P6 XML vs MSP XML
            try:
                head = stream.read(1024)
                if isinstance(head, bytes):
                    head_str = head.decode('utf-8', errors='ignore')
                else:
                    head_str = head
                stream.seek(0)  # Reset stream position
                
                if 'schemas.microsoft.com/project' in head_str:
                    logger.info("Routing to MSP XML Parser")
                    return MSPXMLParser().parse(stream)
                else:
                    logger.info("Routing to P6 XML Parser")
                    return P6XMLParser().parse(stream)
            except Exception as e:
                logger.error(f"Failed to detect XML schema: {e}")
                return None
                
        else:
            logger.error(f"Unsupported file format: {ext}")
            return None
'''

with open("universal_parser.py", "w", encoding="utf-8") as f:
    f.write(UNIVERSAL_PARSER_CODE)
print("  ✅ Created universal_parser.py")


# ==============================================================================
# FILE 4: app.py Patch
# ==============================================================================

import re

try:
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()

    # 1. Update Allowed Extensions
    app_code = app_code.replace(
        "ALLOWED_EXTENSIONS = {'xer'}",
        "ALLOWED_EXTENSIONS = {'xer', 'xml'}"
    )

    # 2. Swap XERParser for UniversalParser
    app_code = app_code.replace(
        "from parser import XERParser",
        "from universal_parser import UniversalParser"
    )

    # 3. Update analyze_xer_file implementation
    old_analyze = """def analyze_xer_file(file_path_or_stream, original_filename, session_data):
    logger.info("🔍 Analyzing XER: %s", original_filename)
    parser = XERParser()
    tables = parser.parse(file_path_or_stream)"""
    
    new_analyze = """def analyze_xer_file(file_path_or_stream, original_filename, session_data):
    logger.info("🔍 Analyzing File: %s", original_filename)
    parser = UniversalParser()
    
    # Must pass stream and filename to UniversalParser
    with open(file_path_or_stream, 'rb') as f:
        tables = parser.parse(f, original_filename)"""
        
    app_code = app_code.replace(old_analyze, new_analyze)

    # 4. Update Error Messages
    app_code = app_code.replace(
        "'error': 'File must be a .xer file'",
        "'error': 'File must be a .xer or .xml file'"
    )

    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
    print("  ✅ Patched app.py to support UniversalParser and .xml files")

except Exception as e:
    print(f"  ⚠️ Could not auto-patch app.py: {e}")


# ==============================================================================
# FILE 5: UI Wording Patches (HTML & JS)
# ==============================================================================

def patch_ui_files(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Update HTML attributes and text
    content = content.replace('accept=".xer"', 'accept=".xer,.xml"')
    content = content.replace('Upload XER', 'Upload Schedule')
    content = content.replace('.xer file', '.xer or .xml file')
    content = content.replace('Upload Two XER Files', 'Upload Two Schedule Files')
    content = content.replace('XER file', 'Schedule file')
    
    # JS Specifics
    content = content.replace(".endsWith('.xer')", ".match(/\\.(xer|xml)$/i)")
    content = content.replace("upload a .xer", "upload a .xer or .xml")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

for ui_file in [
    "templates/index.html",
    "templates/comparison.html",
    "templates/trends.html",
    "static/dashboard.js",
    "static/comparison.js",
    "static/trends.js"
]:
    patch_ui_files(ui_file)
    print(f"  ✅ Patched UI wording in {ui_file}")

print("\n🎉 Phase 3 - Step 7 (Multi-Format Importers) Applied Successfully!")
print("✨ Restart Flask, and you can now upload Primavera XML and MS Project XML files!")
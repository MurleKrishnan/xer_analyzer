import os
import shutil
from datetime import datetime

print("🚀 Starting Patch Application via Python (Part 1/3)...")

# 1. Create Backup Folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = f"_backup_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
print(f"📦 Created backup folder: {backup_dir}")

# Backup files if they exist
files_to_backup = [
    "config.py",
    "parser.py",
    "health_standards/base_checker.py",
    "requirements.txt",
    "Procfile",
    "runtime.txt",
]

for file_path in files_to_backup:
    if os.path.exists(file_path):
        dest = os.path.join(
            backup_dir, os.path.basename(file_path.replace("/", os.sep))
        )
        shutil.copy2(file_path, dest)
        print(f"   Backed up {file_path}")

os.makedirs("health_standards", exist_ok=True)


# ------------------------------------------------------------------------------
# 1. config.py
# ------------------------------------------------------------------------------
CONFIG_CODE = '''"""
BRANDING & CONFIGURATION
========================
Customize the look and feel of your app here.
"""

import os
from datetime import datetime

COMPANY_NAME = "MK Constructions"
APP_TITLE = "P6 Schedule Analyzer"
APP_SUBTITLE = "Advanced Schedule Analytics & DCMA Health Check"

LOGO_PATH = "img/logo.png"
USE_LOGO_IMAGE = False

ACTIVE_THEME = 'blue'

THEMES = {
    'blue': {
        'primary': '#1e40af',
        'primary_dark': '#3730a3',
        'accent': '#3b82f6',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#dc2626',
        'bg': '#f1f5f9',
        'surface': '#ffffff',
        'text': '#1e293b',
        'muted': '#64748b',
        'border': '#e2e8f0',
    },
    'green': {
        'primary': '#065f46',
        'primary_dark': '#064e3b',
        'accent': '#10b981',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'danger': '#dc2626',
        'bg': '#f0fdf4',
        'surface': '#ffffff',
        'text': '#1e293b',
        'muted': '#64748b',
        'border': '#d1fae5',
    },
    'purple': {
        'primary': '#5b21b6',
        'primary_dark': '#4c1d95',
        'accent': '#8b5cf6',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#dc2626',
        'bg': '#faf5ff',
        'surface': '#ffffff',
        'text': '#1e293b',
        'muted': '#64748b',
        'border': '#e9d5ff',
    },
    'dark': {
        'primary': '#1f2937',
        'primary_dark': '#111827',
        'accent': '#6366f1',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#ef4444',
        'bg': '#0f172a',
        'surface': '#1e293b',
        'text': '#f1f5f9',
        'muted': '#94a3b8',
        'border': '#334155',
    },
    'orange': {
        'primary': '#c2410c',
        'primary_dark': '#9a3412',
        'accent': '#f97316',
        'success': '#10b981',
        'warning': '#eab308',
        'danger': '#dc2626',
        'bg': '#fff7ed',
        'surface': '#ffffff',
        'text': '#1e293b',
        'muted': '#64748b',
        'border': '#fed7aa',
    },
}

ENABLE_GANTT = True
ENABLE_COMPARISON = True
ENABLE_EVM = True
ENABLE_EXPORT = True
ENABLE_HEALTH = True

MAX_UPLOAD_SIZE_MB = 100
MAX_GANTT_ACTIVITIES = 2000
DEFAULT_PORT = int(os.environ.get('PORT', 5000))

SESSION_LIFETIME_HOURS = 24
HEALTH_CACHE_ENABLED = True

MAX_ITEMS_PER_CHECK_UI = 200
MAX_ITEMS_PER_CHECK_PDF = 50
MAX_TOP_ACTIONS_UI = 15
MAX_TOP_ACTIONS_PDF = 15

HEALTH_STANDARDS_DIR = "health_standards"
FILTER_PRESETS_DIR = "filter_presets"

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-CHANGE-ME-in-production')
DEBUG = os.environ.get('FLASK_DEBUG', '1') == '1'

FOOTER_TEXT = "Powered by P6 Schedule Analyzer"
FOOTER_YEAR = datetime.now().year

def get_theme():
    return THEMES.get(ACTIVE_THEME, THEMES['blue'])

def get_config():
    return {
        'company_name': COMPANY_NAME,
        'app_title': APP_TITLE,
        'app_subtitle': APP_SUBTITLE,
        'logo_path': LOGO_PATH,
        'use_logo_image': USE_LOGO_IMAGE,
        'theme': get_theme(),
        'features': {
            'gantt': ENABLE_GANTT,
            'comparison': ENABLE_COMPARISON,
            'evm': ENABLE_EVM,
            'export': ENABLE_EXPORT,
            'health': ENABLE_HEALTH,
        },
        'footer_text': FOOTER_TEXT,
        'footer_year': FOOTER_YEAR,
        'limits': {
            'max_upload_mb': MAX_UPLOAD_SIZE_MB,
            'max_gantt_activities': MAX_GANTT_ACTIVITIES,
            'max_items_ui': MAX_ITEMS_PER_CHECK_UI,
            'max_items_pdf': MAX_ITEMS_PER_CHECK_PDF,
        },
    }
'''

with open("config.py", "w", encoding="utf-8") as f:
    f.write(CONFIG_CODE)
print("  ✅ Updated config.py")


# ------------------------------------------------------------------------------
# 2. parser.py
# ------------------------------------------------------------------------------
PARSER_CODE = '''"""
XER PARSER
==========
Reads a .xer file and converts it into organized data tables.
Supports file paths, streams, multi-project XERs, and DataFrame exports.
"""

import io
import logging
from typing import Dict, List, Optional, Union, Any

logger = logging.getLogger(__name__)

class XERParser:
    def __init__(self):
        self.tables: Dict[str, Dict[str, Any]] = {}
        self.header: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def parse(self, source: Union[str, io.IOBase, Any]) -> Optional[Dict]:
        if hasattr(source, 'read'):
            logger.info("📂 Parsing XER from stream")
            return self._parse_stream(source)
        else:
            logger.info(f"📂 Parsing XER from file: {source}")
            return self._parse_file(str(source))

    def _parse_file(self, file_path: str) -> Optional[Dict]:
        try:
            with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                return self._process_lines(f)
        except FileNotFoundError:
            error_msg = f"❌ File not found: {file_path}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return None
        except Exception as e:
            error_msg = f"❌ Failed to read {file_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return None

    def _parse_stream(self, stream) -> Optional[Dict]:
        try:
            if hasattr(stream, 'mode') and 'b' in getattr(stream, 'mode', ''):
                data = stream.read()
                text = data.decode('utf-8-sig', errors='ignore') if isinstance(data, bytes) else data
                lines = text.splitlines()
            else:
                raw = stream.read()
                text = raw.decode('utf-8-sig', errors='ignore') if isinstance(raw, bytes) else raw
                lines = text.splitlines()
            return self._process_lines(lines)
        except Exception as e:
            error_msg = f"❌ Failed to parse stream: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return None

    def _process_lines(self, lines) -> Dict:
        current_table: Optional[str] = None
        current_fields: List[str] = []
        line_number = 0

        for line in lines:
            line_number += 1
            if isinstance(line, bytes):
                line = line.decode('utf-8-sig', errors='ignore')
            line = line.rstrip('\\n').rstrip('\\r')
            if not line.strip():
                continue

            try:
                if line.startswith('ERMHDR'):
                    self._parse_header(line)
                    continue

                if line.startswith('%T'):
                    parts = line.split('\\t')
                    if len(parts) >= 2:
                        current_table = parts[1].strip()
                        current_fields = []
                        if current_table not in self.tables:
                            self.tables[current_table] = {'fields': [], 'rows': []}
                    continue

                if line.startswith('%F'):
                    parts = line.split('\\t')
                    fields = [p.strip() for p in parts[1:]]
                    if current_table:
                        existing = self.tables[current_table]['fields']
                        if not existing:
                            self.tables[current_table]['fields'] = fields
                            current_fields = fields
                        elif existing != fields:
                            warning = f"⚠️ Field mismatch for '{current_table}' at line {line_number}"
                            self.warnings.append(warning)
                            current_fields = existing
                        else:
                            current_fields = existing
                    continue

                if line.startswith('%R'):
                    parts = line.split('\\t')
                    values = [p.strip() for p in parts[1:]]
                    if not current_table or not current_fields:
                        warning = f"⚠️ Orphan %R at line {line_number}"
                        self.warnings.append(warning)
                        continue

                    row = {}
                    for i, field in enumerate(current_fields):
                        row[field] = values[i] if i < len(values) else ''
                    self.tables[current_table]['rows'].append(row)
                    continue

                if line.startswith('%E'):
                    current_table = None
                    current_fields = []
                    continue

            except Exception as e:
                error_msg = f"❌ Error parsing line {line_number}: {e}"
                self.errors.append(error_msg)

        return self.tables

    def _parse_header(self, line: str) -> None:
        parts = line.split('\\t')
        self.header = {
            'format': parts[0] if len(parts) > 0 else '',
            'version': parts[1] if len(parts) > 1 else '',
            'export_date': parts[2] if len(parts) > 2 else '',
            'export_time': parts[3] if len(parts) > 3 else '',
            'project_name': parts[4] if len(parts) > 4 else '',
            'user': parts[5] if len(parts) > 5 else '',
            'raw': parts,
        }

    def get_table(self, table_name: str) -> List[Dict[str, str]]:
        return self.tables.get(table_name, {}).get('rows', [])

    def get_fields(self, table_name: str) -> List[str]:
        return self.tables.get(table_name, {}).get('fields', [])

    def get_table_names(self) -> List[str]:
        return list(self.tables.keys())

    def get_project_id(self) -> Optional[str]:
        projects = self.get_table('PROJECT')
        return projects[0].get('proj_id') if projects else None

    def get_activities(self, proj_id: Optional[str] = None) -> List[Dict]:
        tasks = self.get_table('TASK')
        if proj_id:
            return [t for t in tasks if t.get('proj_id') == proj_id]
        return tasks

    def table_as_dict(self, table_name: str, key_field: str) -> Dict[str, Dict]:
        return {
            row[key_field]: row
            for row in self.get_table(table_name)
            if key_field in row and row[key_field]
        }

    def to_dataframes(self) -> Dict[str, Any]:
        try:
            import pandas as pd
        except ImportError:
            return {}
        result = {}
        for name, data in self.tables.items():
            rows = data.get('rows', [])
            fields = data.get('fields', [])
            result[name] = pd.DataFrame(rows, columns=fields if fields else None)
        return result

    def has_errors(self) -> bool: return len(self.errors) > 0
    def has_warnings(self) -> bool: return len(self.warnings) > 0
    def get_errors(self) -> List[str]: return list(self.errors)
    def get_warnings(self) -> List[str]: return list(self.warnings)
'''

with open("parser.py", "w", encoding="utf-8") as f:
    f.write(PARSER_CODE)
print("  ✅ Updated parser.py")


# ------------------------------------------------------------------------------
# 3. health_standards/base_checker.py
# ------------------------------------------------------------------------------
BASE_CHECKER_CODE = '''"""
BASE CHECKER
============
Provides common check-building methods and shared schedule logic.
"""

from collections import Counter, defaultdict
import statistics
from typing import List, Dict, Any, Optional

class BaseChecker:
    def __init__(self, health_engine):
        self.engine = health_engine.engine
        self.parent = health_engine
        
        self.activities = health_engine.activities
        self.real_activities = health_engine.real_activities
        self.incomplete = health_engine.incomplete
        self.completed = health_engine.completed
        self.in_progress = health_engine.in_progress
        self.not_started = health_engine.not_started
        self.milestones = health_engine.milestones
        self.relationships = health_engine.relationships
        self.resources = health_engine.resources
        self.calendars = health_engine.calendars
        self.projects = health_engine.projects
        self.wbs_nodes = health_engine.wbs_nodes
        self.data_date = health_engine.data_date

    def make_check(self, id: str, name: str, desc: str, count: int, total: int, 
                   threshold_pct: float, standard: str, severity: str, 
                   category: str = 'General', recommendation: str = '', 
                   failed_items: Optional[List] = None, 
                   lower_bound: bool = False) -> Dict:
        pct = (count / total * 100) if total > 0 else 0
        passed = (pct >= threshold_pct) if lower_bound else (pct <= threshold_pct)
        thresh_str = f'≥ {threshold_pct}%' if lower_bound else f'≤ {threshold_pct}%'

        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'count': count,
            'total': total,
            'percentage': round(pct, 2),
            'threshold': thresh_str,
            'passed': passed,
            'status': 'pass' if passed else 'fail',
            'standard': standard,
            'severity': severity,
            'recommendation': recommendation,
            'failed_items': self.format_items(failed_items or []),
        }

    def make_metric(self, id: str, name: str, desc: str, value: Any, 
                    standard: str, category: str = 'General',
                    threshold_min: Optional[float] = None, 
                    threshold_max: Optional[float] = None,
                    severity: str = 'medium', recommendation: str = '', 
                    info_only: bool = False, unit: str = '') -> Dict:
        if value is None or str(value).upper() in ['N/A', 'NONE', 'NAN']:
            return {
                'id': id, 'name': name, 'description': desc, 'category': category,
                'value': 'N/A', 'unit': unit, 'threshold': 'N/A',
                'passed': True, 'status': 'na', 'standard': standard, 'severity': 'info',
                'recommendation': recommendation or 'Insufficient data to compute metric.',
            }

        val = self.to_float(value)

        if info_only:
            passed = True
            threshold_text = 'Informational'
        elif threshold_min is not None and threshold_max is not None:
            passed = threshold_min <= val <= threshold_max
            threshold_text = f'{threshold_min} ≤ x ≤ {threshold_max}'
        elif threshold_max is not None:
            passed = val <= threshold_max
            threshold_text = f'≤ {threshold_max}'
        elif threshold_min is not None:
            passed = val >= threshold_min
            threshold_text = f'≥ {threshold_min}'
        else:
            passed = True
            threshold_text = 'N/A'
        
        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'value': round(val, 2) if isinstance(value, (int, float)) else value,
            'unit': unit,
            'threshold': threshold_text,
            'passed': passed,
            'status': 'info' if info_only else ('pass' if passed else 'fail'),
            'standard': standard,
            'severity': 'info' if info_only else severity,
            'recommendation': recommendation,
        }

    def make_boolean(self, id: str, name: str, desc: str, passed: bool, 
                     standard: str, category: str = 'General',
                     severity: str = 'medium', recommendation: str = '') -> Dict:
        return {
            'id': id,
            'name': name,
            'description': desc,
            'category': category,
            'passed': passed,
            'status': 'pass' if passed else 'fail',
            'standard': standard,
            'severity': severity,
            'recommendation': recommendation,
        }

    def format_items(self, items: List, limit: Optional[int] = None) -> List[Dict]:
        if not items:
            return []

        selected = items if limit is None else items[:limit]
        formatted = []
        
        for i in selected:
            if isinstance(i, dict):
                if 'pred_code' in i or 'succ_code' in i or 'pred_task_id' in i:
                    p_code = i.get('pred_code') or i.get('pred_task_id', '')
                    s_code = i.get('succ_code') or i.get('task_id', '')
                    p_name = i.get('pred_name', '')
                    s_name = i.get('succ_name', '')
                    rel_type = i.get('type_text') or i.get('pred_type', '')
                    lag = i.get('lag_days', 0)
                    lag_str = f" +{lag}d" if lag > 0 else (f" {lag}d" if lag < 0 else "")
                    
                    formatted.append({
                        'code': f"{p_code} → {s_code}",
                        'name': f"{p_name} → {s_name} ({rel_type}{lag_str})",
                        'wbs': '',
                        'value': f"Lag: {lag}d",
                    })
                else:
                    formatted.append({
                        'code': i.get('task_code') or i.get('wbs_short_name') or '',
                        'name': i.get('task_name') or i.get('wbs_name') or '',
                        'wbs': (i.get('wbs_name') or '')[:60],
                        'value': i.get('total_float_days', ''),
                    })
            elif isinstance(i, (tuple, list)) and len(i) >= 2:
                pred = self.engine.activity_by_id.get(str(i[0]), {})
                succ = self.engine.activity_by_id.get(str(i[1]), {})
                p_code = pred.get('task_code', str(i[0]))
                s_code = succ.get('task_code', str(i[1]))
                formatted.append({
                    'code': f"{p_code} → {s_code}",
                    'name': f"{pred.get('task_name', '')} → {succ.get('task_name', '')}",
                    'wbs': ''
                })
            else:
                formatted.append({'code': str(i), 'name': '', 'wbs': ''})

        return formatted

    def to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def count_by_type(self, task_type: str) -> int:
        return sum(1 for a in self.activities if a.get('task_type') == task_type)

    def open_start_activities(self) -> List[Dict]:
        milestones = {'TT_Mile', 'TT_FinMile'}
        return [
            a for a in self.incomplete
            if a.get('task_id', '') not in self.engine.predecessors
            and a.get('task_type') not in milestones
        ]

    def open_end_activities(self) -> List[Dict]:
        milestones = {'TT_Mile', 'TT_FinMile'}
        return [
            a for a in self.incomplete
            if a.get('task_id', '') not in self.engine.successors
            and a.get('task_type') not in milestones
        ]

    def active_relationships(self) -> List[Dict]:
        return [
            r for r in self.relationships
            if self.engine.activity_by_id.get(r.get('task_id', ''), {}).get('status_code') != 'TK_Complete'
        ]

    def has_hard_constraint(self, act: Dict, include_alap: bool = False) -> bool:
        codes = {'CS_MSO', 'CS_MEO', 'CS_MANDSTART', 'CS_MANDFIN'}
        if include_alap:
            codes.add('CS_ALAP')
        return act.get('cstr_type') in codes or act.get('cstr_type2') in codes

    def fs_with_lag(self) -> List[Dict]:
        return [
            r for r in self.active_relationships()
            if r.get('pred_type') == 'PR_FS' and r.get('lag_days', 0) > 0
        ]
        
    def is_milestone(self, act: Dict) -> bool:
        return act.get('task_type') in ['TT_Mile', 'TT_FinMile']
'''

base_checker_path = os.path.join("health_standards", "base_checker.py")
with open(base_checker_path, "w", encoding="utf-8") as f:
    f.write(BASE_CHECKER_CODE)
print("  ✅ Updated health_standards/base_checker.py")


# ------------------------------------------------------------------------------
# 4. requirements.txt, Procfile, runtime.txt
# ------------------------------------------------------------------------------
REQS_CODE = """Flask>=3.0.0,<3.1.0
flask-cors>=4.0.0,<5.0.0
Werkzeug>=3.0.0,<3.1.0
openpyxl>=3.1.2,<3.2.0
pandas>=2.1.0,<2.3.0
gunicorn>=21.2.0,<22.0.0
reportlab>=4.0.0,<4.2.0
"""
with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write(REQS_CODE)
print("  ✅ Updated requirements.txt")

PROCFILE_CODE = (
    "web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4"
    " --timeout 120 --graceful-timeout 30 --keep-alive 5 --access-logfile -"
    " --error-logfile - --log-level info\n"
)
with open("Procfile", "w", encoding="utf-8") as f:
    f.write(PROCFILE_CODE)
print("  ✅ Updated Procfile")

RUNTIME_CODE = "python-3.11.11\n"
with open("runtime.txt", "w", encoding="utf-8") as f:
    f.write(RUNTIME_CODE)
print("  ✅ Updated runtime.txt")

print("\n🎉 Part 1 Patches Applied Successfully via Python!")
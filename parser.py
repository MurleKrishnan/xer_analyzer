"""
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
            line = line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue

            try:
                if line.startswith('ERMHDR'):
                    self._parse_header(line)
                    continue

                if line.startswith('%T'):
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        current_table = parts[1].strip()
                        current_fields = []
                        if current_table not in self.tables:
                            self.tables[current_table] = {'fields': [], 'rows': []}
                    continue

                if line.startswith('%F'):
                    parts = line.split('\t')
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
                    parts = line.split('\t')
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
        parts = line.split('\t')
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

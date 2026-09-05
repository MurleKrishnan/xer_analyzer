"""
XER PARSER
==========
Reads a .xer file and converts it into organized data tables 
(Python dictionaries and lists).

Supports:
- File paths (local files)
- File-like streams (Flask uploads, BytesIO, StringIO)
- Multi-project XER files
- Corrupted / partial XER recovery (with warnings)
- Direct conversion to pandas DataFrames

Grammar handled:
- ERMHDR      → header line
- %T <name>   → table start
- %F <fields> → column headers
- %R <values> → data row
- %E          → end marker
"""

import io
import logging
from typing import Dict, List, Optional, Union, Any


logger = logging.getLogger(__name__)


class XERParser:
    """
    Main XER parser class.
    
    USAGE (file path):
        parser = XERParser()
        tables = parser.parse("input/schedule.xer")
    
    USAGE (Flask upload stream):
        parser = XERParser()
        tables = parser.parse(request.files['file'])
    
    USAGE (BytesIO):
        parser = XERParser()
        tables = parser.parse(io.BytesIO(xer_bytes))
    
    RESULT STRUCTURE:
        {
            'PROJECT': {
                'fields': ['proj_id', 'proj_short_name', ...],
                'rows': [
                    {'proj_id': '1001', 'proj_short_name': 'MY_PROJECT', ...}
                ]
            },
            'TASK': {
                'fields': [...],
                'rows': [...]
            },
            ...
        }
    """

    def __init__(self):
        """Initialize empty storage."""
        self.tables: Dict[str, Dict[str, Any]] = {}
        self.header: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    # ═══════════════════════════════════════════════════════
    # MAIN PARSE ENTRY POINT
    # ═══════════════════════════════════════════════════════

    def parse(self, source: Union[str, io.IOBase, Any]) -> Optional[Dict]:
        """
        Parse an XER from a file path OR a file-like stream.
        
        PARAMETERS:
            source: Either
                - str: file path
                - file-like object with .read() (Flask FileStorage, BytesIO, StringIO)
        
        RETURNS:
            Dictionary of tables, or None on fatal error.
        """
        # Detect input type
        if hasattr(source, 'read'):
            # File-like stream (Flask upload, BytesIO, etc.)
            logger.info("📂 Parsing XER from stream")
            return self._parse_stream(source)
        else:
            # Path string
            logger.info(f"📂 Parsing XER from file: {source}")
            return self._parse_file(str(source))

    def _parse_file(self, file_path: str) -> Optional[Dict]:
        """Parse from a file path on disk."""
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
        """Parse from a file-like stream."""
        try:
            # Handle both bytes and text streams
            if hasattr(stream, 'mode') and 'b' in getattr(stream, 'mode', ''):
                # Binary — decode
                data = stream.read()
                if isinstance(data, bytes):
                    text = data.decode('utf-8-sig', errors='ignore')
                else:
                    text = data
                lines = text.splitlines()
            else:
                # Try reading as text first
                try:
                    raw = stream.read()
                    if isinstance(raw, bytes):
                        text = raw.decode('utf-8-sig', errors='ignore')
                    else:
                        text = raw
                    lines = text.splitlines()
                except Exception:
                    # Fallback: iterate directly
                    lines = list(stream)
            
            return self._process_lines(lines)
        except Exception as e:
            error_msg = f"❌ Failed to parse stream: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return None

    def _process_lines(self, lines) -> Dict:
        """
        Core line-by-line parser.
        Works with any iterable of lines (file handle, list, etc.).
        """
        current_table: Optional[str] = None
        current_fields: List[str] = []
        line_number = 0

        for line in lines:
            line_number += 1

            # Handle bytes just in case
            if isinstance(line, bytes):
                line = line.decode('utf-8-sig', errors='ignore')

            # Strip line endings
            line = line.rstrip('\n').rstrip('\r')

            if not line.strip():
                continue

            try:
                # ─── HEADER LINE ───
                if line.startswith('ERMHDR'):
                    self._parse_header(line)
                    continue

                # ─── TABLE NAME (%T) ───
                if line.startswith('%T'):
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        current_table = parts[1].strip()
                        current_fields = []

                        # Create table entry if not present
                        if current_table not in self.tables:
                            self.tables[current_table] = {
                                'fields': [],
                                'rows': []
                            }
                        logger.debug(f"  📋 Table: {current_table}")
                    continue

                # ─── FIELD NAMES (%F) ───
                if line.startswith('%F'):
                    parts = line.split('\t')
                    fields = [p.strip() for p in parts[1:]]

                    if current_table:
                        existing = self.tables[current_table]['fields']
                        if not existing:
                            self.tables[current_table]['fields'] = fields
                            current_fields = fields
                        elif existing != fields:
                            warning = (
                                f"⚠️ Field mismatch for table '{current_table}' "
                                f"at line {line_number} (multi-project XER?)"
                            )
                            self.warnings.append(warning)
                            logger.warning(warning)
                            # Use existing field list to keep rows consistent
                            current_fields = existing
                        else:
                            current_fields = existing
                    continue

                # ─── DATA ROW (%R) ───
                if line.startswith('%R'):
                    parts = line.split('\t')
                    values = [p.strip() for p in parts[1:]]

                    if not current_table or not current_fields:
                        warning = (
                            f"⚠️ Orphan %R at line {line_number} "
                            f"(no active table/fields)"
                        )
                        self.warnings.append(warning)
                        logger.warning(warning)
                        continue

                    # Warn if value count exceeds field count
                    if len(values) > len(current_fields):
                        warning = (
                            f"⚠️ Extra values in '{current_table}' at line {line_number}: "
                            f"{len(values)} values vs {len(current_fields)} fields"
                        )
                        self.warnings.append(warning)
                        logger.warning(warning)

                    # Build row dict (pad missing values with empty string)
                    row = {}
                    for i, field in enumerate(current_fields):
                        row[field] = values[i] if i < len(values) else ''

                    self.tables[current_table]['rows'].append(row)
                    continue

                # ─── END MARKER (%E) ───
                if line.startswith('%E'):
                    current_table = None
                    current_fields = []
                    continue

            except Exception as e:
                error_msg = f"❌ Error parsing line {line_number}: {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                # Continue rather than abort — try to recover

        self._log_summary()
        return self.tables

    # ═══════════════════════════════════════════════════════
    # HEADER PARSING
    # ═══════════════════════════════════════════════════════

    def _parse_header(self, line: str) -> None:
        """
        Parse ERMHDR line (varies slightly across P6 versions).
        
        Common format:
            ERMHDR  <version>  <export_date>  <export_time>  <user>  <db>  ...
        """
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
        logger.info(
            f"  📋 XER Version: {self.header.get('version', '?')} | "
            f"Export: {self.header.get('export_date', '?')}"
        )

    # ═══════════════════════════════════════════════════════
    # SUMMARY / DEBUG
    # ═══════════════════════════════════════════════════════

    def _log_summary(self) -> None:
        """Log a summary of what was parsed."""
        total_rows = sum(len(t['rows']) for t in self.tables.values())
        logger.info(
            f"✅ Parsed {len(self.tables)} tables, {total_rows:,} total rows"
            + (f" ({len(self.warnings)} warnings)" if self.warnings else "")
            + (f" ({len(self.errors)} errors)" if self.errors else "")
        )

    # ═══════════════════════════════════════════════════════
    # PUBLIC HELPERS — Access parsed data
    # ═══════════════════════════════════════════════════════

    def get_table(self, table_name: str) -> List[Dict[str, str]]:
        """
        Get all rows from a specific table.
        
        EXAMPLE:
            activities = parser.get_table('TASK')
        """
        if table_name in self.tables:
            return self.tables[table_name]['rows']
        logger.warning(f"Table '{table_name}' not found in XER file.")
        return []

    def get_fields(self, table_name: str) -> List[str]:
        """Get column names for a table."""
        if table_name in self.tables:
            return self.tables[table_name]['fields']
        return []

    def get_table_names(self) -> List[str]:
        """Get all table names in the file."""
        return list(self.tables.keys())

    def get_project_id(self) -> Optional[str]:
        """Get the first project's ID (convenience helper)."""
        projects = self.get_table('PROJECT')
        return projects[0].get('proj_id') if projects else None

    def get_activities(self, proj_id: Optional[str] = None) -> List[Dict]:
        """
        Get tasks, optionally filtered by project ID.
        Useful for multi-project XER files.
        """
        tasks = self.get_table('TASK')
        if proj_id:
            return [t for t in tasks if t.get('proj_id') == proj_id]
        return tasks

    def table_as_dict(self, table_name: str, key_field: str) -> Dict[str, Dict]:
        """
        Index a table by a primary key field for O(1) lookups.
        
        EXAMPLE:
            tasks_by_id = parser.table_as_dict('TASK', 'task_id')
            # Now: tasks_by_id['12345'] → {task dict}
        """
        return {
            row[key_field]: row
            for row in self.get_table(table_name)
            if key_field in row and row[key_field]
        }

    def to_dataframes(self) -> Dict[str, Any]:
        """
        Convert all tables to pandas DataFrames for analytics.
        
        RETURNS:
            {table_name: pandas.DataFrame}
        
        Returns empty dict if pandas is not installed.
        
        EXAMPLE:
            dfs = parser.to_dataframes()
            tasks_df = dfs.get('TASK')
            wbs_df = dfs.get('PROJWBS')
        """
        try:
            import pandas as pd
        except ImportError:
            logger.warning("pandas not installed — to_dataframes() returned empty dict")
            return {}

        result = {}
        for name, data in self.tables.items():
            rows = data.get('rows', [])
            fields = data.get('fields', [])
            if rows:
                result[name] = pd.DataFrame(rows, columns=fields if fields else None)
            else:
                result[name] = pd.DataFrame(columns=fields)
        return result

    # ═══════════════════════════════════════════════════════
    # ERROR / WARNING ACCESSORS
    # ═══════════════════════════════════════════════════════

    def has_errors(self) -> bool:
        """Check if fatal errors occurred during parsing."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings were raised."""
        return len(self.warnings) > 0

    def get_errors(self) -> List[str]:
        """Get list of error messages."""
        return list(self.errors)

    def get_warnings(self) -> List[str]:
        """Get list of warning messages."""
        return list(self.warnings)
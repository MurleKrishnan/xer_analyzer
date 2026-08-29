"""
XER PARSER
==========
This module reads a .xer file and converts it into 
organized data tables (Python dictionaries and lists).

Think of it like:
- Opening a book
- Reading each chapter (table)
- Writing notes about each chapter in organized notebooks
"""


class XERParser:
    """
    Main parser class.
    
    HOW IT WORKS:
    1. Opens the XER file
    2. Reads it line by line
    3. When it sees %T → starts a new table
    4. When it sees %F → reads the column headers
    5. When it sees %R → reads a row of data
    6. Stores everything in a neat dictionary
    """

    def __init__(self):
        """
        Initialize empty storage.
        
        self.tables will look like this after parsing:
        {
            'PROJECT': {
                'fields': ['proj_id', 'proj_short_name', ...],
                'rows': [
                    {'proj_id': '1001', 'proj_short_name': 'MY_PROJECT', ...}
                ]
            },
            'TASK': {
                'fields': ['task_id', 'proj_id', 'task_name', ...],
                'rows': [
                    {'task_id': '10001', 'task_name': 'Mobilization', ...},
                    {'task_id': '10002', 'task_name': 'Site Survey', ...}
                ]
            },
            ... more tables ...
        }
        """
        self.tables = {}
        self.header = {}
        self.errors = []

    def parse(self, file_path):
        """
        Main method - reads the entire XER file.
        
        PARAMETERS:
            file_path: Location of the .xer file
                       Example: "input/sample.xer"
        
        RETURNS:
            Dictionary of all tables found in the file
        """
        print(f"📂 Opening file: {file_path}")

        # Track what table we're currently reading
        current_table = None
        current_fields = []
        line_number = 0

        try:
            # Open the file and read it
            # encoding='utf-8-sig' handles special characters
            # errors='ignore' skips any weird characters
            with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as file:

                for line in file:
                    line_number += 1
                    
                    # Remove the newline character at the end
                    line = line.rstrip('\n').rstrip('\r')
                    
                    # Skip empty lines
                    if not line.strip():
                        continue

                    # ─── HEADER LINE ───
                    # First line of the file contains export info
                    if line.startswith('ERMHDR'):
                        self._parse_header(line)
                        continue

                    # ─── TABLE NAME (%T) ───
                    # Example: %T	TASK
                    # This tells us a new table is starting
                    if line.startswith('%T'):
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            current_table = parts[1].strip()
                            current_fields = []
                            
                            # Create a home for this table's data
                            if current_table not in self.tables:
                                self.tables[current_table] = {
                                    'fields': [],
                                    'rows': []
                                }
                            print(f"  📋 Found table: {current_table}")
                        continue

                    # ─── FIELD NAMES (%F) ───
                    # Example: %F	task_id	proj_id	task_name
                    # These are the column headers
                    if line.startswith('%F'):
                        parts = line.split('\t')
                        # Skip the '%F' part, keep the rest as field names
                        current_fields = [p.strip() for p in parts[1:]]
                        
                        if current_table:
                            self.tables[current_table]['fields'] = current_fields
                        continue

                    # ─── DATA ROW (%R) ───
                    # Example: %R	10001	1001	Mobilization
                    # This is actual data
                    if line.startswith('%R'):
                        parts = line.split('\t')
                        # Skip the '%R' part, keep the data values
                        values = [p.strip() for p in parts[1:]]

                        if current_table and current_fields:
                            # Combine field names with values into a dictionary
                            # Like matching column headers to row data
                            row = {}
                            for i, field in enumerate(current_fields):
                                if i < len(values):
                                    row[field] = values[i]
                                else:
                                    row[field] = ''  # Empty if no value provided
                            
                            self.tables[current_table]['rows'].append(row)
                        continue

                    # ─── END MARKER (%E) ───
                    if line.startswith('%E'):
                        continue

        except FileNotFoundError:
            error_msg = f"❌ File not found: {file_path}"
            print(error_msg)
            self.errors.append(error_msg)
            return None

        except Exception as e:
            error_msg = f"❌ Error on line {line_number}: {str(e)}"
            print(error_msg)
            self.errors.append(error_msg)
            return None

        # Print summary
        self._print_summary()
        return self.tables

    def _parse_header(self, line):
        """
        Reads the ERMHDR line (first line of file).
        
        Example line: ERMHDR	11.0	2024-01-15	Project1	admin
        """
        parts = line.split('\t')
        self.header = {
            'format': parts[0] if len(parts) > 0 else '',
            'version': parts[1] if len(parts) > 1 else '',
            'export_date': parts[2] if len(parts) > 2 else '',
            'project_name': parts[3] if len(parts) > 3 else '',
            'user': parts[4] if len(parts) > 4 else '',
        }
        print(f"  📋 File Version: {self.header.get('version', 'Unknown')}")
        print(f"  📅 Export Date: {self.header.get('export_date', 'Unknown')}")

    def _print_summary(self):
        """Prints a nice summary of what was found."""
        print("\n" + "=" * 50)
        print("📊 PARSING SUMMARY")
        print("=" * 50)
        
        total_rows = 0
        for table_name, table_data in self.tables.items():
            row_count = len(table_data['rows'])
            total_rows += row_count
            print(f"  {table_name:20s} → {row_count:>6,} rows")
        
        print(f"\n  {'TOTAL':20s} → {total_rows:>6,} rows")
        print(f"  Tables found: {len(self.tables)}")
        print("=" * 50)

    # ─── HELPER METHODS ───
    # These make it easy to get specific data

    def get_table(self, table_name):
        """
        Get all rows from a specific table.
        
        Example usage:
            activities = parser.get_table('TASK')
        
        Returns a list of dictionaries (one per row)
        """
        if table_name in self.tables:
            return self.tables[table_name]['rows']
        else:
            print(f"⚠️ Table '{table_name}' not found in XER file.")
            return []

    def get_fields(self, table_name):
        """Get the field/column names for a table."""
        if table_name in self.tables:
            return self.tables[table_name]['fields']
        return []

    def get_table_names(self):
        """Get a list of all tables found in the file."""
        return list(self.tables.keys())
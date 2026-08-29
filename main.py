"""
MAIN ENTRY POINT
=================
This is the file you run to execute everything.

HOW TO RUN:
    1. Put your .xer file in the 'input/' folder
    2. Open terminal
    3. Type: python main.py
    4. Check the 'output/' folder for your report
"""

from parser import XERParser
from data_engine import ScheduleEngine
from reports import ReportGenerator
import os


def main():
    """Main execution function."""

    print("╔══════════════════════════════════════════════╗")
    print("║    P6/XER PARSER + SCHEDULE DATA ENGINE     ║")
    print("║          Version 1.0                        ║")
    print("╚══════════════════════════════════════════════╝")

    # ─── CONFIGURATION ───
    # Change these to match your file names
    INPUT_FILE = "input/sample.xer"
    OUTPUT_FILE = "output/schedule_report.xlsx"

    # Create output folder if it doesn't exist
    os.makedirs("output", exist_ok=True)

    # ════════════════════════════════════════════
    # PHASE 1: PARSE THE XER FILE
    # ════════════════════════════════════════════
    print("\n" + "─" * 50)
    print("PHASE 1: PARSING XER FILE")
    print("─" * 50)

    parser = XERParser()
    tables = parser.parse(INPUT_FILE)

    if tables is None:
        print("❌ Failed to parse file. Exiting.")
        return

    # ════════════════════════════════════════════
    # PHASE 2: LOAD INTO DATA ENGINE
    # ════════════════════════════════════════════
    print("\n" + "─" * 50)
    print("PHASE 2: LOADING DATA ENGINE")
    print("─" * 50)

    engine = ScheduleEngine()
    engine.load_data(tables)

    # ════════════════════════════════════════════
    # PHASE 3: ANALYZE
    # ════════════════════════════════════════════
    print("\n" + "─" * 50)
    print("PHASE 3: ANALYZING SCHEDULE")
    print("─" * 50)

    engine.analyze()

    # ════════════════════════════════════════════
    # PHASE 4: GENERATE REPORTS
    # ════════════════════════════════════════════
    print("\n" + "─" * 50)
    print("PHASE 4: GENERATING REPORTS")
    print("─" * 50)

    reporter = ReportGenerator(engine)
    reporter.generate_full_report(OUTPUT_FILE)

    # ════════════════════════════════════════════
    # PHASE 5: INTERACTIVE EXPLORATION (OPTIONAL)
    # ════════════════════════════════════════════
    print("\n" + "─" * 50)
    print("PHASE 5: INTERACTIVE MODE")
    print("─" * 50)
    print("You can now explore the data interactively.")
    print("Type 'help' for commands, 'quit' to exit.\n")

    interactive_mode(engine)


def interactive_mode(engine):
    """
    Simple interactive command line to explore the schedule data.
    
    This is like having a conversation with your schedule!
    """
    while True:
        try:
            command = input("🔍 Enter command: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        if not command:
            continue

        if command.lower() == 'quit':
            print("Goodbye! 👋")
            break

        elif command.lower() == 'help':
            print("""
    Available Commands:
    ─────────────────────────────────────────────────
    search <term>      Search for activities by ID or name
    pred <activity_id> Show predecessors of an activity
    succ <activity_id> Show successors of an activity
    critical           List all critical activities
    stats              Show schedule statistics
    tables             Show all tables found in XER file
    count <table>      Count rows in a specific table
    quit               Exit the program
    ─────────────────────────────────────────────────
            """)

        elif command.lower().startswith('search '):
            term = command[7:]
            results = engine.find_activity(term)
            if results:
                print(f"\n  Found {len(results)} activities:")
                for act in results[:20]:
                    float_val = act.get('total_float_days', 0)
                    crit = "🔴" if act.get('is_critical') else "  "
                    print(f"    {crit} {act.get('task_code', ''):>10s} | "
                          f"{act.get('task_name', '')[:40]:40s} | "
                          f"Float: {float_val:>6.0f}d | "
                          f"{act.get('status_text', '')}")
            else:
                print(f"  No activities found matching '{term}'")

        elif command.lower().startswith('pred '):
            code = command[5:].strip()
            preds = engine.get_predecessors(code)
            if preds:
                print(f"\n  Predecessors of {code}:")
                for p in preds:
                    print(f"    ← {p['code']:>10s} | {p['name'][:40]:40s} | "
                          f"{p['type']} | Lag: {p['lag']}d")
            else:
                print(f"  No predecessors found for '{code}'")

        elif command.lower().startswith('succ '):
            code = command[5:].strip()
            succs = engine.get_successors(code)
            if succs:
                print(f"\n  Successors of {code}:")
                for s in succs:
                    print(f"    → {s['code']:>10s} | {s['name'][:40]:40s} | "
                          f"{s['type']} | Lag: {s['lag']}d")
            else:
                print(f"  No successors found for '{code}'")

        elif command.lower() == 'critical':
            print(f"\n  Critical Activities ({len(engine.critical_activities)}):")
            for act in engine.critical_activities[:30]:
                print(f"    🔴 {act.get('task_code', ''):>10s} | "
                      f"{act.get('task_name', '')[:40]:40s} | "
                      f"Float: {act.get('total_float_days', 0):>6.0f}d")

        elif command.lower() == 'stats':
            for key, value in engine.schedule_stats.items():
                print(f"    {key:30s}: {value}")

        elif command.lower() == 'tables':
            for table_name in engine.raw_tables:
                row_count = len(engine.raw_tables[table_name].get('rows', []))
                print(f"    {table_name:25s}: {row_count:>6,} rows")

        elif command.lower().startswith('count '):
            table = command[6:].strip().upper()
            if table in engine.raw_tables:
                count = len(engine.raw_tables[table].get('rows', []))
                print(f"    {table}: {count:,} rows")
            else:
                print(f"    Table '{table}' not found")

        else:
            print(f"    Unknown command: '{command}'. Type 'help' for options.")


# ─── RUN THE PROGRAM ───
if __name__ == '__main__':
    main()
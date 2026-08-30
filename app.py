"""
P6 SCHEDULE ANALYZER - MAIN WEB APPLICATION (app.py)
=====================================================
Integrates:
- Dashboard (XER parsing, DCMA basics, Excel export)
- Gantt Chart
- Schedule Comparison (Baseline vs Current)
- EVM & S-Curves
- Advanced Health Analytics (622+ checks across 6 standards)
- PDF Reports (Executive + Action List) with severity filter
- Excel Export (Top Actions with severity filter, one sheet per standard)
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime

# ─── CORE ENGINE IMPORTS ───
from parser import XERParser
from data_engine import ScheduleEngine
from reports import ReportGenerator

# ─── ADVANCED MODULE IMPORTS (Safe Imports) ───
try:
    from comparison_engine import ScheduleComparator
except ImportError:
    ScheduleComparator = None

try:
    from evm_engine import EVMEngine
except ImportError:
    EVMEngine = None

try:
    from advanced_health_engine import AdvancedHealthEngine
except ImportError:
    AdvancedHealthEngine = None

try:
    from pdf_report_generator import PDFReportGenerator
except ImportError:
    PDFReportGenerator = None

try:
    from config import get_config
except ImportError:
    def get_config():
        return {
            'company_name': 'My Company',
            'app_title': 'P6 Schedule Analyzer',
            'app_subtitle': 'DCMA 14-Point Check & Analytics',
            'use_logo_image': False,
            'features': {'gantt': True, 'comparison': True, 'evm': True, 'export': True}
        }


# ─── INITIALIZE FLASK ───
app = Flask(__name__)
CORS(app)

# ─── CONFIGURATION ───
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'xer'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ─── IN-MEMORY SESSION DATA ───
current_analysis = {
    'engine': None,
    'dashboard_data': None,
    'file_name': None,
    'analyzed_at': None,
}

current_comparison = {
    'comparator': None,
    'results': None,
    'baseline_file': None,
    'current_file': None,
}


# ─── HELPER FUNCTIONS ───
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def analyze_xer_file(file_path):
    print(f"\n🔍 Analyzing: {file_path}")
    parser = XERParser()
    tables = parser.parse(file_path)

    if tables is None:
        return {'error': 'Failed to parse XER file'}

    engine = ScheduleEngine()
    engine.load_data(tables)
    engine.analyze()

    dashboard_data = engine.get_dashboard_data()

    current_analysis['engine'] = engine
    current_analysis['dashboard_data'] = dashboard_data
    current_analysis['analyzed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return dashboard_data


@app.context_processor
def inject_config():
    return {'config': get_config()}


# ════════════════════════════════════════════
# ROUTE 1: MAIN DASHBOARD
# ════════════════════════════════════════════

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File must be a .xer file'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    current_analysis['file_name'] = filename

    try:
        dashboard_data = analyze_xer_file(file_path)
        if 'error' in dashboard_data:
            return jsonify(dashboard_data), 500

        return jsonify({
            'success': True,
            'file_name': filename,
            'analyzed_at': current_analysis['analyzed_at'],
            'data': dashboard_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard')
def get_dashboard():
    if current_analysis['dashboard_data'] is None:
        return jsonify({'has_data': False})

    return jsonify({
        'has_data': True,
        'file_name': current_analysis['file_name'],
        'analyzed_at': current_analysis['analyzed_at'],
        'data': current_analysis['dashboard_data']
    })


@app.route('/api/load-sample')
def load_sample():
    sample_path = os.path.join('input', 'sample.xer')
    if not os.path.exists(sample_path):
        return jsonify({'error': 'sample.xer not found in input/ folder'}), 404

    current_analysis['file_name'] = 'sample.xer'
    try:
        dashboard_data = analyze_xer_file(sample_path)
        return jsonify({
            'success': True,
            'file_name': 'sample.xer',
            'analyzed_at': current_analysis['analyzed_at'],
            'data': dashboard_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-excel')
def export_excel():
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No analysis available.'}), 400

    output_path = os.path.join(OUTPUT_FOLDER, 'schedule_report.xlsx')
    reporter = ReportGenerator(current_analysis['engine'])
    reporter.generate_full_report(output_path)

    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"schedule_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


# ════════════════════════════════════════════
# ROUTE 2: GANTT CHART
# ════════════════════════════════════════════

@app.route('/gantt')
def gantt_view():
    return render_template('gantt.html')


@app.route('/api/gantt-data')
def get_gantt_data():
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Please upload an XER file first.'}), 400

    max_acts = request.args.get('max', 200, type=int)
    gantt_data = current_analysis['engine'].get_gantt_data(max_activities=max_acts)

    return jsonify({
        'success': True,
        'file_name': current_analysis['file_name'],
        'data': gantt_data
    })


# ════════════════════════════════════════════
# ROUTE 3: COMPARISON (Baseline vs Current)
# ════════════════════════════════════════════

@app.route('/comparison')
def comparison_view():
    return render_template('comparison.html')


@app.route('/api/compare', methods=['POST'])
def compare_schedules():
    if ScheduleComparator is None:
        return jsonify({'error': 'comparison_engine.py is missing!'}), 500

    if 'baseline' not in request.files or 'current' not in request.files:
        return jsonify({'error': 'Both baseline and current files required'}), 400

    baseline_file = request.files['baseline']
    current_file = request.files['current']

    if not (allowed_file(baseline_file.filename) and allowed_file(current_file.filename)):
        return jsonify({'error': 'Both files must be .xer files'}), 400

    baseline_name = secure_filename(baseline_file.filename)
    current_name = secure_filename(current_file.filename)

    baseline_path = os.path.join(UPLOAD_FOLDER, f"baseline_{baseline_name}")
    current_path = os.path.join(UPLOAD_FOLDER, f"current_{current_name}")

    baseline_file.save(baseline_path)
    current_file.save(current_path)

    try:
        comparator = ScheduleComparator()
        comparator.load_baseline(baseline_path)
        comparator.load_current(current_path)
        results = comparator.compare()

        current_comparison['comparator'] = comparator
        current_comparison['results'] = results
        current_comparison['baseline_file'] = baseline_name
        current_comparison['current_file'] = current_name

        return jsonify({
            'success': True,
            'baseline_file': baseline_name,
            'current_file': current_name,
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/comparison-data')
def get_comparison_data():
    if current_comparison['results'] is None:
        return jsonify({'has_data': False})

    return jsonify({
        'has_data': True,
        'baseline_file': current_comparison['baseline_file'],
        'current_file': current_comparison['current_file'],
        'results': current_comparison['results']
    })


# ════════════════════════════════════════════
# ROUTE 4: EVM & S-CURVES
# ════════════════════════════════════════════

@app.route('/evm')
def evm_view():
    return render_template('evm.html')


@app.route('/api/evm-data')
def get_evm_data():
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Upload an XER file first.'}), 400

    if EVMEngine is None:
        return jsonify({'error': 'evm_engine.py is missing!'}), 500

    try:
        evm = EVMEngine(current_analysis['engine'])
        results = evm.calculate()
        return jsonify({
            'success': True,
            'file_name': current_analysis['file_name'],
            'data': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# ROUTE 5: HEALTH (Advanced Analytics)
# ════════════════════════════════════════════

@app.route('/health')
def health_view():
    """Show the advanced health page."""
    return render_template('health.html')


@app.route('/api/health-data')
def get_health_data():
    """Return advanced health analysis data with optional standard filter."""
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Upload a file first.'}), 400

    if AdvancedHealthEngine is None:
        return jsonify({'error': 'advanced_health_engine.py is missing!'}), 500

    selected_standard = request.args.get('standard', 'all')

    try:
        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        return jsonify({
            'success': True,
            'file_name': current_analysis['file_name'],
            'data': results
        })
    except Exception as e:
        print(f"❌ Health analysis error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# ROUTE 6: PDF REPORTS (with severity filter)
# ════════════════════════════════════════════

@app.route('/api/executive-pdf')
def download_executive_pdf():
    """Generate and download executive PDF report."""
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded'}), 400

    if PDFReportGenerator is None or AdvancedHealthEngine is None:
        return jsonify({'error': 'PDF or Health engine module missing!'}), 500

    selected_standard = request.args.get('standard', 'all')
    severity_filter = request.args.get('severity', 'all')

    try:
        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        generator = PDFReportGenerator(
            results,
            current_analysis['file_name'],
            severity_filter=severity_filter
        )
        pdf_buffer = generator.generate_executive_report()

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"executive_report_{selected_standard}_{severity_filter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"❌ PDF error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/actions-pdf')
def download_actions_pdf():
    """Generate and download action list PDF."""
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded'}), 400

    if PDFReportGenerator is None or AdvancedHealthEngine is None:
        return jsonify({'error': 'PDF or Health engine module missing!'}), 500

    selected_standard = request.args.get('standard', 'all')
    severity_filter = request.args.get('severity', 'all')

    try:
        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        generator = PDFReportGenerator(
            results,
            current_analysis['file_name'],
            severity_filter=severity_filter
        )
        pdf_buffer = generator.generate_actions_report()

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"action_list_{selected_standard}_{severity_filter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"❌ PDF error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# ROUTE 7: TOP ACTIONS EXCEL EXPORT
# One sheet per Standard + Severity Filter + Separators
# ════════════════════════════════════════════

@app.route('/api/actions-excel')
def download_actions_excel():
    """
    Export Top Actions + full affected activities to Excel.
    - One sheet per Standard (DCMA, DOE, NASA, GAO, AACE, Industry)
    - Filter by severity (all / critical / high / medium)
    - Empty rows between metrics for clear separation
    """
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Upload a file first.'}), 400

    if AdvancedHealthEngine is None:
        return jsonify({'error': 'advanced_health_engine.py is missing!'}), 500

    selected_standard = request.args.get('standard', 'all')
    severity_filter = request.args.get('severity', 'all').lower()

    # Severity filter definitions
    severity_levels = {
        'critical': ['critical'],
        'high': ['critical', 'high'],
        'medium': ['critical', 'high', 'medium'],
        'all': ['critical', 'high', 'medium', 'low', 'info']
    }
    allowed_severities = severity_levels.get(severity_filter, severity_levels['all'])

    try:
        import pandas as pd
        from io import BytesIO
        from openpyxl.styles import Font, PatternFill, Alignment

        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        top_actions = results.get('top_actions', []) or []
        standards_data = results.get('standards', {}) or {}

        # Apply severity filter to top actions
        filtered_top_actions = [
            a for a in top_actions
            if (a.get('severity') or 'low').lower() in allowed_severities
        ]

        # ─── Sheet 1: Report Info ───
        meta_rows = [
            ['Report Type', 'Schedule Health - Top Actions Export'],
            ['Selected Standard', selected_standard],
            ['Severity Filter', severity_filter.upper()],
            ['File Name', current_analysis.get('file_name', '')],
            ['Generated At', results.get('analysis_date', '')],
            ['', ''],
            ['Overall Score', results.get('overall_score', '')],
            ['Total Checks', results.get('total_checks', '')],
            ['Passed Checks', results.get('passed_checks', '')],
            ['Failed Checks', results.get('failed_checks', '')],
            ['Critical Failures', results.get('critical_failures', '')],
            ['High Failures', results.get('high_failures', '')],
            ['Pass Rate (%)', results.get('pass_rate', '')],
            ['', ''],
            ['Filtered Actions Count', len(filtered_top_actions)],
        ]

        # ─── Sheet 2: Top Actions Summary (filtered) ───
        top_summary_rows = []
        for idx, action in enumerate(filtered_top_actions, 1):
            top_summary_rows.append({
                'Rank': idx,
                'Standard': action.get('standard', ''),
                'Check ID': action.get('id', ''),
                'Check Name': action.get('name', ''),
                'Category': action.get('category', ''),
                'Severity': (action.get('severity') or '').upper(),
                'Affected Count': action.get('count', 0),
                'Total': action.get('total', 0),
                'Percentage': action.get('percentage', 0),
                'Threshold': action.get('threshold', ''),
                'Value': action.get('value', ''),
                'Recommendation': action.get('recommendation', ''),
                'Description': action.get('description', ''),
            })

        # ─── Build workbook ───
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:

            # Sheet: Report Info
            pd.DataFrame(meta_rows, columns=['Field', 'Value']).to_excel(
                writer, sheet_name='Report Info', index=False
            )

            # Sheet: Top Actions Summary
            if top_summary_rows:
                pd.DataFrame(top_summary_rows).to_excel(
                    writer, sheet_name='Top Actions Summary', index=False
                )
            else:
                pd.DataFrame([{
                    'Info': f'No actions matched severity filter: {severity_filter.upper()}'
                }]).to_excel(
                    writer, sheet_name='Top Actions Summary', index=False
                )

            # ─── One sheet per Standard (filtered by severity) ───
            for std_name, std_data in standards_data.items():
                sheet_name = (std_name or 'Standard')[:31]
                rows = []

                failed_in_std = []
                for category in std_data.get('categories', []):
                    for check in category.get('checks', []):
                        if check.get('status') != 'fail':
                            continue
                        # Apply severity filter
                        if (check.get('severity') or 'low').lower() not in allowed_severities:
                            continue
                        failed_in_std.append((category.get('name', ''), check))

                if not failed_in_std:
                    rows.append({
                        'Section': 'No Matching Failures',
                        'Field': '',
                        'Value': f'No {severity_filter.upper()} failures found for {std_name}',
                        'Activity ID': '',
                        'Activity Name': '',
                        'WBS': '',
                    })
                else:
                    for cat_name, check in failed_in_std:
                        # Metric header rows
                        rows.append({
                            'Section': 'METRIC',
                            'Field': 'Check ID',
                            'Value': check.get('id', ''),
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })
                        rows.append({
                            'Section': '',
                            'Field': 'Check Name',
                            'Value': check.get('name', ''),
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })
                        rows.append({
                            'Section': '',
                            'Field': 'Category',
                            'Value': cat_name,
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })
                        rows.append({
                            'Section': '',
                            'Field': 'Severity',
                            'Value': (check.get('severity') or '').upper(),
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })
                        rows.append({
                            'Section': '',
                            'Field': 'Description',
                            'Value': check.get('description', ''),
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })
                        rows.append({
                            'Section': '',
                            'Field': 'Threshold',
                            'Value': check.get('threshold', ''),
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })

                        if check.get('count') is not None:
                            rows.append({
                                'Section': '',
                                'Field': 'Affected',
                                'Value': f"{check.get('count', 0)} of {check.get('total', 0)} ({check.get('percentage', 0)}%)",
                                'Activity ID': '',
                                'Activity Name': '',
                                'WBS': '',
                            })
                        if check.get('value') is not None and check.get('value') != '':
                            rows.append({
                                'Section': '',
                                'Field': 'Value',
                                'Value': check.get('value', ''),
                                'Activity ID': '',
                                'Activity Name': '',
                                'WBS': '',
                            })

                        rows.append({
                            'Section': '',
                            'Field': 'Recommendation',
                            'Value': check.get('recommendation', ''),
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })

                        # Affected Activities Sub-Header
                        items = check.get('failed_items', []) or []
                        rows.append({
                            'Section': 'AFFECTED ACTIVITIES',
                            'Field': f'Total: {len(items)}',
                            'Value': '',
                            'Activity ID': 'Activity ID',
                            'Activity Name': 'Activity Name',
                            'WBS': 'WBS',
                        })

                        if items:
                            for item in items:
                                rows.append({
                                    'Section': '',
                                    'Field': '',
                                    'Value': '',
                                    'Activity ID': item.get('code', ''),
                                    'Activity Name': item.get('name', ''),
                                    'WBS': item.get('wbs', ''),
                                })
                        else:
                            rows.append({
                                'Section': '',
                                'Field': '',
                                'Value': '(No activity list available)',
                                'Activity ID': '',
                                'Activity Name': '',
                                'WBS': '',
                            })

                        # Empty separator rows between metrics
                        rows.append({'Section': '', 'Field': '', 'Value': '',
                                     'Activity ID': '', 'Activity Name': '', 'WBS': ''})
                        rows.append({'Section': '', 'Field': '', 'Value': '',
                                     'Activity ID': '', 'Activity Name': '', 'WBS': ''})

                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False)

            # ─── Post-process formatting ───
            workbook = writer.book

            header_font = Font(bold=True, color='FFFFFF', size=11)
            header_fill = PatternFill(start_color='1E40AF', end_color='1E40AF', fill_type='solid')
            metric_fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid')
            activity_hdr_fill = PatternFill(start_color='DBEAFE', end_color='DBEAFE', fill_type='solid')
            bold_font = Font(bold=True)
            wrap_align = Alignment(wrap_text=True, vertical='top')

            for sheet_name in workbook.sheetnames:
                ws = workbook[sheet_name]

                # Header row style
                for cell in ws[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='left', vertical='center')

                # Auto column widths
                for col in ws.columns:
                    max_len = 10
                    col_letter = col[0].column_letter
                    for cell in col:
                        try:
                            val = str(cell.value) if cell.value is not None else ''
                            if len(val) > max_len:
                                max_len = len(val)
                        except:
                            pass
                    ws.column_dimensions[col_letter].width = min(max_len + 2, 60)

                # Freeze header row
                ws.freeze_panes = 'A2'

                # Standard sheet highlighting
                if sheet_name not in ['Report Info', 'Top Actions Summary']:
                    for row in ws.iter_rows(min_row=2):
                        section_cell = row[0]
                        if section_cell.value == 'METRIC':
                            for c in row:
                                c.fill = metric_fill
                                c.font = bold_font
                        elif section_cell.value == 'AFFECTED ACTIVITIES':
                            for c in row:
                                c.fill = activity_hdr_fill
                                c.font = bold_font
                        for c in row:
                            c.alignment = wrap_align

        output.seek(0)

        filename = f"health_top_actions_{selected_standard}_{severity_filter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"❌ Actions Excel error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# LAUNCH SERVER
# ════════════════════════════════════════════

if __name__ == '__main__':
    import os as _os
    port = int(_os.environ.get('PORT', 5000))
    debug_mode = _os.environ.get('FLASK_ENV') != 'production'

    print("\n" + "=" * 60)
    print("🚀 P6 SCHEDULE ANALYZER - ALL FEATURES READY")
    print("=" * 60)
    print(f"📌 Running on port {port}")
    print(f"🔧 Debug mode: {debug_mode}")
    print("👉 Open in browser: http://localhost:5000\n")

    app.run(debug=debug_mode, host='0.0.0.0', port=port)
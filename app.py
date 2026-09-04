"""
P6 SCHEDULE ANALYZER - MAIN WEB APPLICATION (app.py)
=====================================================
Integrates:
- Dashboard (XER parsing, DCMA basics, Excel export)
- Gantt Chart (DHTMLX Gantt + WBS hierarchy)
- Schedule Comparison (Baseline vs Current)
- EVM & S-Curves (Earned Value Management)
- Advanced Health Analytics (622+ checks across 6 standards)
- PDF Reports (Executive + Action List with severity filter)
- Excel Export (Top Actions with severity filter, one sheet per standard)
"""

from flask import Flask, render_template, request, jsonify, send_file, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
import time
import logging
from datetime import datetime

# ─── CONFIG & BRANDING IMPORTS ───
try:
    from config import (
        get_config,
        MAX_UPLOAD_SIZE_MB,
        SECRET_KEY,
        SESSION_LIFETIME_HOURS,
    )
except ImportError:
    MAX_UPLOAD_SIZE_MB = 100
    SECRET_KEY = 'dev-only-CHANGE-ME'
    SESSION_LIFETIME_HOURS = 24
    def get_config():
        return {
            'company_name': 'MK Constructions',
            'app_title': 'P6 Schedule Analyzer',
            'app_subtitle': 'DCMA 14-Point Check & Analytics',
            'use_logo_image': False,
            'theme': {'primary': '#1e40af', 'accent': '#3b82f6'},
            'features': {'gantt': True, 'comparison': True, 'evm': True, 'export': True, 'health': True}
        }

# ─── CORE ENGINE IMPORTS ───
from parser import XERParser
from data_engine import ScheduleEngine
from reports import ReportGenerator

# ─── ADVANCED MODULE IMPORTS ───
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from comparison_engine import ScheduleComparator
    logger.info("✅ ScheduleComparator imported")
except Exception as e:
    ScheduleComparator = None
    logger.warning("❌ ScheduleComparator import failed: %s", e)

try:
    from evm_engine import EVMEngine
    logger.info("✅ EVMEngine imported")
except Exception as e:
    EVMEngine = None
    logger.warning("❌ EVMEngine import failed: %s", e)

try:
    from advanced_health_engine import AdvancedHealthEngine
    logger.info("✅ AdvancedHealthEngine imported")
except Exception as e:
    AdvancedHealthEngine = None
    logger.warning("❌ AdvancedHealthEngine import failed: %s", e)

try:
    from pdf_report_generator import PDFReportGenerator
    logger.info("✅ PDFReportGenerator imported")
except Exception as e:
    PDFReportGenerator = None
    logger.warning("❌ PDFReportGenerator import failed: %s", e)


# ─── INITIALIZE FLASK ───
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# ─── CONFIGURATION ───
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'xer'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Enforce upload limit

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ─── STORAGE CLEANUP UTILITY ───
def cleanup_old_files(folder, max_age_hours=SESSION_LIFETIME_HOURS):
    """Purge temporary files older than specified hours."""
    if not os.path.exists(folder):
        return
    cutoff = time.time() - (max_age_hours * 3600)
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        try:
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                logger.info("🧹 Cleaned up old file: %s", fname)
        except Exception as e:
            logger.warning("Could not delete %s: %s", fname, e)

# Run cleanup on application launch
cleanup_old_files(UPLOAD_FOLDER)
cleanup_old_files(OUTPUT_FOLDER)


# ─── SESSION-SCORED IN-MEMORY STORAGE ───
# Prevents multi-user data leakage when running on a shared server
SESSION_STORAGE = {}

def get_session_data():
    """Retrieve or initialize user session storage."""
    sid = session.get('sid')
    if not sid or sid not in SESSION_STORAGE:
        sid = uuid.uuid4().hex
        session['sid'] = sid
        SESSION_STORAGE[sid] = {
            'analysis': {'engine': None, 'dashboard_data': None, 'file_name': None, 'analyzed_at': None},
            'comparison': {'comparator': None, 'results': None, 'baseline_file': None, 'current_file': None},
            'health_cache': {},
        }
    return SESSION_STORAGE[sid]


# ─── HELPER FUNCTIONS ───
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def analyze_xer_file(file_path_or_stream, original_filename, session_data):
    logger.info("🔍 Analyzing XER: %s", original_filename)
    parser = XERParser()
    tables = parser.parse(file_path_or_stream)

    if tables is None or not tables:
        return {'error': 'Failed to parse XER file or file is empty.'}

    engine = ScheduleEngine()
    engine.load_data(tables)
    engine.analyze()

    dashboard_data = engine.get_dashboard_data()

    # Store in session
    analysis = session_data['analysis']
    analysis['engine'] = engine
    analysis['dashboard_data'] = dashboard_data
    analysis['file_name'] = original_filename
    analysis['analyzed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Invalidate health cache for new schedule
    session_data['health_cache'] = {}

    return dashboard_data


@app.context_processor
def inject_config():
    return {'config': get_config()}


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': f'File size exceeds maximum limit of {MAX_UPLOAD_SIZE_MB} MB.'}), 413


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

    original_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(file_path)

    sess_data = get_session_data()

    try:
        dashboard_data = analyze_xer_file(file_path, original_name, sess_data)
        if 'error' in dashboard_data:
            return jsonify(dashboard_data), 400

        analysis = sess_data['analysis']
        return jsonify({
            'success': True,
            'file_name': analysis['file_name'],
            'analyzed_at': analysis['analyzed_at'],
            'data': dashboard_data
        })
    except Exception as e:
        logger.exception("Upload analysis error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard')
def get_dashboard():
    sess_data = get_session_data()
    analysis = sess_data['analysis']

    if analysis['dashboard_data'] is None:
        return jsonify({'has_data': False})

    return jsonify({
        'has_data': True,
        'file_name': analysis['file_name'],
        'analyzed_at': analysis['analyzed_at'],
        'data': analysis['dashboard_data']
    })


@app.route('/api/load-sample')
def load_sample():
    sample_path = os.path.join('input', 'sample.xer')
    if not os.path.exists(sample_path):
        return jsonify({'error': 'sample.xer not found in input/ folder'}), 404

    sess_data = get_session_data()
    try:
        dashboard_data = analyze_xer_file(sample_path, 'sample.xer', sess_data)
        analysis = sess_data['analysis']
        return jsonify({
            'success': True,
            'file_name': 'sample.xer',
            'analyzed_at': analysis['analyzed_at'],
            'data': dashboard_data
        })
    except Exception as e:
        logger.exception("Sample load error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export-excel')
def export_excel():
    sess_data = get_session_data()
    engine = sess_data['analysis']['engine']

    if engine is None:
        return jsonify({'error': 'No schedule loaded. Please upload an XER file first.'}), 400

    out_name = f"schedule_report_{uuid.uuid4().hex[:8]}.xlsx"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], out_name)
    
    reporter = ReportGenerator(engine)
    res_path = reporter.generate_full_report(output_path)

    if not res_path or not os.path.exists(res_path):
        return jsonify({'error': 'Failed to generate Excel report.'}), 500

    return send_file(
        res_path,
        as_attachment=True,
        download_name=f"schedule_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ════════════════════════════════════════════
# ROUTE 2: GANTT CHART
# ════════════════════════════════════════════

@app.route('/gantt')
def gantt_view():
    return render_template('gantt.html')


@app.route('/api/gantt-data')
def get_gantt_data():
    sess_data = get_session_data()
    analysis = sess_data['analysis']

    if analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Please upload an XER file first.'}), 400

    max_acts = request.args.get('max', 2000, type=int)
    gantt_data = analysis['engine'].get_gantt_data(max_activities=max_acts)

    return jsonify({
        'success': True,
        'file_name': analysis['file_name'],
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

    baseline_path = os.path.join(app.config['UPLOAD_FOLDER'], f"bl_{uuid.uuid4().hex[:8]}_{baseline_name}")
    current_path = os.path.join(app.config['UPLOAD_FOLDER'], f"cur_{uuid.uuid4().hex[:8]}_{current_name}")

    baseline_file.save(baseline_path)
    current_file.save(current_path)

    sess_data = get_session_data()

    try:
        comparator = ScheduleComparator()
        comparator.load_baseline(baseline_path)
        comparator.load_current(current_path)
        results = comparator.compare()

        comp = sess_data['comparison']
        comp['comparator'] = comparator
        comp['results'] = results
        comp['baseline_file'] = baseline_name
        comp['current_file'] = current_name

        return jsonify({
            'success': True,
            'baseline_file': baseline_name,
            'current_file': current_name,
            'results': results
        })
    except Exception as e:
        logger.exception("Comparison error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/comparison-data')
def get_comparison_data():
    sess_data = get_session_data()
    comp = sess_data['comparison']

    if comp['results'] is None:
        return jsonify({'has_data': False})

    return jsonify({
        'has_data': True,
        'baseline_file': comp['baseline_file'],
        'current_file': comp['current_file'],
        'results': comp['results']
    })


# ════════════════════════════════════════════
# ROUTE 4: EVM & S-CURVES
# ════════════════════════════════════════════

@app.route('/evm')
def evm_view():
    return render_template('evm.html')


@app.route('/api/evm-data')
def get_evm_data():
    sess_data = get_session_data()
    analysis = sess_data['analysis']

    if analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Upload an XER file first.'}), 400

    if EVMEngine is None:
        return jsonify({'error': 'evm_engine.py is missing!'}), 500

    try:
        evm = EVMEngine(analysis['engine'])
        results = evm.calculate()
        return jsonify({
            'success': True,
            'file_name': analysis['file_name'],
            'data': results
        })
    except Exception as e:
        logger.exception("EVM calculation error")
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# ROUTE 5: HEALTH (Advanced Analytics)
# ════════════════════════════════════════════

@app.route('/health')
def health_view():
    return render_template('health.html')


@app.route('/api/health-data')
def get_health_data():
    sess_data = get_session_data()
    analysis = sess_data['analysis']

    if analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Upload a file first.'}), 400

    if AdvancedHealthEngine is None:
        return jsonify({'error': 'advanced_health_engine.py is missing!'}), 500

    selected_standard = request.args.get('standard', 'all')

    try:
        health = AdvancedHealthEngine(analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        return jsonify({
            'success': True,
            'file_name': analysis['file_name'],
            'data': results
        })
    except Exception as e:
        logger.exception("Health analysis error")
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# ROUTE 6: PDF REPORTS (with severity filter)
# ════════════════════════════════════════════

@app.route('/api/executive-pdf')
def download_executive_pdf():
    sess_data = get_session_data()
    analysis = sess_data['analysis']

    if analysis['engine'] is None:
        return jsonify({'error': 'No data loaded'}), 400

    if PDFReportGenerator is None or AdvancedHealthEngine is None:
        return jsonify({'error': 'PDF or Health engine module missing!'}), 500

    selected_standard = request.args.get('standard', 'all')
    severity_filter = request.args.get('severity', 'all')

    try:
        health = AdvancedHealthEngine(analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        generator = PDFReportGenerator(
            results,
            analysis['file_name'],
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
        logger.exception("PDF generation error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/actions-pdf')
def download_actions_pdf():
    sess_data = get_session_data()
    analysis = sess_data['analysis']

    if analysis['engine'] is None:
        return jsonify({'error': 'No data loaded'}), 400

    if PDFReportGenerator is None or AdvancedHealthEngine is None:
        return jsonify({'error': 'PDF or Health engine module missing!'}), 500

    selected_standard = request.args.get('standard', 'all')
    severity_filter = request.args.get('severity', 'all')

    try:
        health = AdvancedHealthEngine(analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        generator = PDFReportGenerator(
            results,
            analysis['file_name'],
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
        logger.exception("PDF actions error")
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# ROUTE 7: TOP ACTIONS EXCEL EXPORT
# ════════════════════════════════════════════

@app.route('/api/actions-excel')
def download_actions_excel():
    sess_data = get_session_data()
    analysis = sess_data['analysis']

    if analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Upload a file first.'}), 400

    if AdvancedHealthEngine is None:
        return jsonify({'error': 'advanced_health_engine.py is missing!'}), 500

    selected_standard = request.args.get('standard', 'all')
    severity_filter = request.args.get('severity', 'all').lower()

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

        health = AdvancedHealthEngine(analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        top_actions = results.get('top_actions', []) or []
        standards_data = results.get('standards', {}) or {}

        filtered_top_actions = [
            a for a in top_actions
            if (a.get('severity') or 'low').lower() in allowed_severities
        ]

        # Sheet 1: Report Info
        meta_rows = [
            ['Report Type', 'Schedule Health - Top Actions Export'],
            ['Selected Standard', selected_standard],
            ['Severity Filter', severity_filter.upper()],
            ['File Name', analysis.get('file_name', '')],
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

        # Sheet 2: Top Actions Summary
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

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(meta_rows, columns=['Field', 'Value']).to_excel(
                writer, sheet_name='Report Info', index=False
            )

            if top_summary_rows:
                pd.DataFrame(top_summary_rows).to_excel(
                    writer, sheet_name='Top Actions Summary', index=False
                )
            else:
                pd.DataFrame([{'Info': f'No actions matched severity filter: {severity_filter.upper()}'}]).to_excel(
                    writer, sheet_name='Top Actions Summary', index=False
                )

            for std_name, std_data in standards_data.items():
                sheet_name = (std_name or 'Standard')[:31]
                rows = []

                failed_in_std = []
                for category in std_data.get('categories', []):
                    for check in category.get('checks', []):
                        if check.get('status') != 'fail':
                            continue
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
                        rows.append({
                            'Section': 'METRIC',
                            'Field': 'Check ID',
                            'Value': check.get('id', ''),
                            'Activity ID': '', 'Activity Name': '', 'WBS': '',
                        })
                        rows.append({
                            'Section': '', 'Field': 'Check Name', 'Value': check.get('name', ''),
                            'Activity ID': '', 'Activity Name': '', 'WBS': '',
                        })
                        rows.append({
                            'Section': '', 'Field': 'Category', 'Value': cat_name,
                            'Activity ID': '', 'Activity Name': '', 'WBS': '',
                        })
                        rows.append({
                            'Section': '', 'Field': 'Severity', 'Value': (check.get('severity') or '').upper(),
                            'Activity ID': '', 'Activity Name': '', 'WBS': '',
                        })
                        rows.append({
                            'Section': '', 'Field': 'Description', 'Value': check.get('description', ''),
                            'Activity ID': '', 'Activity Name': '', 'WBS': '',
                        })
                        rows.append({
                            'Section': '', 'Field': 'Threshold', 'Value': check.get('threshold', ''),
                            'Activity ID': '', 'Activity Name': '', 'WBS': '',
                        })

                        if check.get('count') is not None:
                            rows.append({
                                'Section': '', 'Field': 'Affected',
                                'Value': f"{check.get('count', 0)} of {check.get('total', 0)} ({check.get('percentage', 0)}%)",
                                'Activity ID': '', 'Activity Name': '', 'WBS': '',
                            })
                        if check.get('value') is not None and check.get('value') != '':
                            rows.append({
                                'Section': '', 'Field': 'Value', 'Value': check.get('value', ''),
                                'Activity ID': '', 'Activity Name': '', 'WBS': '',
                            })

                        rows.append({
                            'Section': '', 'Field': 'Recommendation', 'Value': check.get('recommendation', ''),
                            'Activity ID': '', 'Activity Name': '', 'WBS': '',
                        })

                        items = check.get('failed_items', []) or []
                        rows.append({
                            'Section': 'AFFECTED ACTIVITIES', 'Field': f'Total: {len(items)}', 'Value': '',
                            'Activity ID': 'Activity ID', 'Activity Name': 'Activity Name', 'WBS': 'WBS',
                        })

                        if items:
                            for item in items:
                                rows.append({
                                    'Section': '', 'Field': '', 'Value': '',
                                    'Activity ID': item.get('code', ''),
                                    'Activity Name': item.get('name', ''),
                                    'WBS': item.get('wbs', ''),
                                })
                        else:
                            rows.append({
                                'Section': '', 'Field': '', 'Value': '(No activity list available)',
                                'Activity ID': '', 'Activity Name': '', 'WBS': '',
                            })

                        rows.append({'Section': '', 'Field': '', 'Value': '', 'Activity ID': '', 'Activity Name': '', 'WBS': ''})
                        rows.append({'Section': '', 'Field': '', 'Value': '', 'Activity ID': '', 'Activity Name': '', 'WBS': ''})

                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False)

            # Format Excel
            workbook = writer.book
            header_font = Font(bold=True, color='FFFFFF', size=11)
            header_fill = PatternFill(start_color='1E40AF', end_color='1E40AF', fill_type='solid')
            metric_fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid')
            activity_hdr_fill = PatternFill(start_color='DBEAFE', end_color='DBEAFE', fill_type='solid')
            bold_font = Font(bold=True)
            wrap_align = Alignment(wrap_text=True, vertical='top')

            for sheet_name in workbook.sheetnames:
                ws = workbook[sheet_name]
                for cell in ws[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='left', vertical='center')

                for col in ws.columns:
                    max_len = 10
                    col_letter = col[0].column_letter
                    for cell in col:
                        try:
                            val = str(cell.value) if cell.value is not None else ''
                            if len(val) > max_len:
                                max_len = len(val)
                        except Exception:
                            pass
                    ws.column_dimensions[col_letter].width = min(max_len + 2, 60)

                ws.freeze_panes = 'A2'

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
        logger.exception("Actions Excel error")
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# LAUNCH SERVER
# ════════════════════════════════════════════

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'

    logger.info("=" * 60)
    logger.info("🚀 P6 SCHEDULE ANALYZER - ALL FEATURES READY")
    logger.info("=" * 60)
    logger.info("📌 Running on port %s", port)
    logger.info("🔧 Debug mode: %s", debug_mode)
    logger.info("👉 Open in browser: http://localhost:%s\n", port)

    app.run(debug=debug_mode, host='0.0.0.0', port=port)
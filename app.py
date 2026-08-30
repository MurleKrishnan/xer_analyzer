"""
P6 SCHEDULE ANALYZER - MAIN WEB APPLICATION (app.py)
=====================================================
Integrates Dashboard, Gantt, Comparison, EVM, Health,
PDF reports, and Excel export.
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
# ROUTE 6: PDF REPORTS
# ════════════════════════════════════════════

@app.route('/api/executive-pdf')
def download_executive_pdf():
    """Generate and download executive PDF report."""
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded'}), 400

    if PDFReportGenerator is None or AdvancedHealthEngine is None:
        return jsonify({'error': 'PDF or Health engine module missing!'}), 500

    selected_standard = request.args.get('standard', 'all')

    try:
        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        generator = PDFReportGenerator(results, current_analysis['file_name'])
        pdf_buffer = generator.generate_executive_report()

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"executive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
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

    try:
        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        generator = PDFReportGenerator(results, current_analysis['file_name'])
        pdf_buffer = generator.generate_actions_report()

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"action_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"❌ PDF error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ════════════════════════════════════════════
# ROUTE 7: TOP ACTIONS EXCEL EXPORT (NEW)
# ════════════════════════════════════════════

@app.route('/api/actions-excel')
def download_actions_excel():
    """Export Top Actions + full affected activity lists to Excel."""
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded. Upload a file first.'}), 400

    if AdvancedHealthEngine is None:
        return jsonify({'error': 'advanced_health_engine.py is missing!'}), 500

    selected_standard = request.args.get('standard', 'all')

    try:
        import pandas as pd
        from io import BytesIO

        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)

        top_actions = results.get('top_actions', []) or []

        # ─── Sheet 1: Top Actions Summary ───
        summary_rows = []
        for idx, action in enumerate(top_actions, 1):
            summary_rows.append({
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

        # ─── Sheet 2: Full Affected Activities per Top Action ───
        detail_rows = []
        for idx, action in enumerate(top_actions, 1):
            items = action.get('failed_items', []) or []
            if not items:
                detail_rows.append({
                    'Rank': idx,
                    'Standard': action.get('standard', ''),
                    'Check ID': action.get('id', ''),
                    'Check Name': action.get('name', ''),
                    'Severity': (action.get('severity') or '').upper(),
                    'Activity ID': '',
                    'Activity Name': '',
                    'WBS': '',
                    'Extra Value': '',
                    'Recommendation': action.get('recommendation', ''),
                })
            else:
                for item in items:
                    detail_rows.append({
                        'Rank': idx,
                        'Standard': action.get('standard', ''),
                        'Check ID': action.get('id', ''),
                        'Check Name': action.get('name', ''),
                        'Severity': (action.get('severity') or '').upper(),
                        'Activity ID': item.get('code', ''),
                        'Activity Name': item.get('name', ''),
                        'WBS': item.get('wbs', ''),
                        'Extra Value': item.get('value', ''),
                        'Recommendation': action.get('recommendation', ''),
                    })

        # ─── Sheet 3: All Failed Checks + Activities ───
        all_failed_rows = []
        for std_name, std_data in (results.get('standards', {}) or {}).items():
            for category in std_data.get('categories', []):
                for check in category.get('checks', []):
                    if check.get('status') != 'fail':
                        continue

                    items = check.get('failed_items', []) or []
                    base = {
                        'Standard': std_name,
                        'Category': category.get('name', ''),
                        'Check ID': check.get('id', ''),
                        'Check Name': check.get('name', ''),
                        'Severity': (check.get('severity') or '').upper(),
                        'Count': check.get('count', 0),
                        'Total': check.get('total', 0),
                        'Percentage': check.get('percentage', 0),
                        'Threshold': check.get('threshold', ''),
                        'Value': check.get('value', ''),
                        'Recommendation': check.get('recommendation', ''),
                    }

                    if not items:
                        all_failed_rows.append({
                            **base,
                            'Activity ID': '',
                            'Activity Name': '',
                            'WBS': '',
                        })
                    else:
                        for item in items:
                            all_failed_rows.append({
                                **base,
                                'Activity ID': item.get('code', ''),
                                'Activity Name': item.get('name', ''),
                                'WBS': item.get('wbs', ''),
                            })

        # ─── Sheet 4: Report Info ───
        meta = [{
            'Selected Standard': selected_standard,
            'File Name': current_analysis.get('file_name', ''),
            'Overall Score': results.get('overall_score', ''),
            'Total Checks': results.get('total_checks', ''),
            'Failed Checks': results.get('failed_checks', ''),
            'Critical Failures': results.get('critical_failures', ''),
            'High Failures': results.get('high_failures', ''),
            'Pass Rate': results.get('pass_rate', ''),
            'Generated At': results.get('analysis_date', ''),
        }]

        # Build workbook
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(meta).to_excel(writer, sheet_name='Report Info', index=False)
            pd.DataFrame(summary_rows).to_excel(
                writer, sheet_name='Top Actions Summary', index=False
            )
            pd.DataFrame(detail_rows).to_excel(
                writer, sheet_name='Top Actions Activities', index=False
            )
            pd.DataFrame(all_failed_rows).to_excel(
                writer, sheet_name='All Failed Activities', index=False
            )

        output.seek(0)

        filename = f"health_top_actions_{selected_standard}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
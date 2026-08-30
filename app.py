"""
P6 SCHEDULE ANALYZER - MAIN WEB APPLICATION (app.py)
=====================================================
Integrates Dashboard, Gantt, Comparison, EVM, and Config.
"""
from pdf_report_generator import PDFReportGenerator
from flask import send_file
from advanced_health_engine import AdvancedHealthEngine
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
# LAUNCH SERVER
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
    
    # Get standard filter from query string
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
@app.route('/api/executive-pdf')
def download_executive_pdf():
    """Generate and download executive PDF report."""
    if current_analysis['engine'] is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    selected_standard = request.args.get('standard', 'all')
    
    try:
        # Run health analysis
        health = AdvancedHealthEngine(current_analysis['engine'])
        results = health.run_all_checks(selected_standard=selected_standard)
        
        # Generate PDF
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
    
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 P6 SCHEDULE ANALYZER - ALL FEATURES READY")
    print("=" * 60)
    print("👉 Open in browser: http://localhost:5000\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
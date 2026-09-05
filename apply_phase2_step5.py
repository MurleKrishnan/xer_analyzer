import os
import shutil
from datetime import datetime

print("🚀 Applying Phase 2 - Step 5: Multi-Period Trend Analysis...")

# 1. Create Backup Folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = f"_backup_phase2_step5_{timestamp}"
os.makedirs(backup_dir, exist_ok=True)
print(f"📦 Created backup folder: {backup_dir}")

files_to_backup = [
    "app.py",
    "templates/index.html",
    "templates/gantt.html",
    "templates/evm.html",
    "templates/comparison.html",
    "templates/health.html",
]

for file_path in files_to_backup:
    if os.path.exists(file_path):
        dest = os.path.join(backup_dir, os.path.basename(file_path.replace("/", os.sep)))
        shutil.copy2(file_path, dest)
        print(f"   Backed up {file_path}")


# ==============================================================================
# FILE 1: trend_engine.py (NEW - Multi-Period Trend Analytics Engine)
# ==============================================================================

TREND_ENGINE_CODE = '''"""
MULTI-PERIOD TREND ANALYSIS ENGINE
===================================
Processes a series of XER files (Jan, Feb, Mar, Apr, May updates) and extracts
time-series metrics to detect schedule drift, chronic critical activities,
and improvement/decline trends.

Metrics tracked over time:
- Projected finish date
- Overall health score
- Critical activity count (both TF ≤ 0 and Longest Path)
- Total activity count
- Slipped/added/deleted counts vs baseline
- EVM SPI/CPI/EAC drift
- DCMA compliance percentage
- Chronic critical activities (critical in 3+ updates)
"""

from parser import XERParser
from data_engine import ScheduleEngine
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class TrendAnalysisEngine:
    """Processes multiple XER files and extracts time-series trends."""

    def __init__(self):
        self.periods = []  # List of {name, engine, health, evm, data_date}
        self.trend_results = {}

    def add_period(self, file_path_or_stream, period_label=None):
        """
        Add one XER file as a schedule update.
        period_label: Optional friendly name (e.g., "Jan 2024", "Update 03")
        """
        logger.info(f"📊 Loading trend period: {period_label}")
        
        parser = XERParser()
        tables = parser.parse(file_path_or_stream)
        if tables is None:
            raise Exception(f"Failed to parse XER for period: {period_label}")
        
        engine = ScheduleEngine()
        engine.load_data(tables)
        engine.analyze()
        
        # Extract auto-generated data date
        data_date = None
        if engine.projects:
            dd_str = engine.projects[0].get('last_recalc_date', '')
            data_date = engine._parse_date(dd_str)
        
        period_info = {
            'label': period_label or (data_date.strftime('%Y-%m-%d') if data_date else f'Period {len(self.periods) + 1}'),
            'engine': engine,
            'data_date': data_date,
        }
        
        self.periods.append(period_info)
        logger.info(f"  ✅ Added period '{period_info['label']}' ({len(engine.activities)} activities)")
        return period_info['label']

    def analyze(self):
        """
        Run full trend analysis across all uploaded periods.
        Returns dict with all trend series and chronic activity detection.
        """
        if len(self.periods) < 2:
            return {'error': 'At least 2 schedule periods required for trend analysis.'}
        
        logger.info(f"📈 Analyzing trends across {len(self.periods)} periods...")
        
        # Sort periods chronologically by data date
        self.periods.sort(key=lambda p: p['data_date'] or datetime.min)
        
        # Extract per-period metrics
        period_metrics = []
        for p in self.periods:
            period_metrics.append(self._extract_period_metrics(p))
        
        # Compute chronic critical activities
        chronic_critical = self._detect_chronic_critical()
        
        # Compute slippage vs first period (baseline)
        slippage_trend = self._calculate_slippage_trend(period_metrics)
        
        # Compute activity count trend
        activity_trend = self._calculate_activity_trend(period_metrics)
        
        # Health score trend
        health_trend = self._calculate_health_trend(period_metrics)
        
        # EVM trend
        evm_trend = self._calculate_evm_trend(period_metrics)
        
        # Critical path trend
        critical_trend = self._calculate_critical_trend(period_metrics)
        
        self.trend_results = {
            'period_count': len(self.periods),
            'periods': [p['label'] for p in self.periods],
            'period_data_dates': [p['data_date'].strftime('%Y-%m-%d') if p['data_date'] else '' for p in self.periods],
            'period_metrics': period_metrics,
            'slippage_trend': slippage_trend,
            'activity_trend': activity_trend,
            'health_trend': health_trend,
            'evm_trend': evm_trend,
            'critical_trend': critical_trend,
            'chronic_critical': chronic_critical,
            'analyzed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        logger.info(f"  ✅ Trend analysis complete ({len(chronic_critical)} chronic critical activities)")
        return self.trend_results

    def _extract_period_metrics(self, period_info):
        """Extract summary metrics for a single period."""
        engine = period_info['engine']
        
        # Basic activity stats
        real_activities = [a for a in engine.activities if a.get('task_type') not in ('TT_WBS', 'TT_LOE')]
        incomplete = [a for a in real_activities if a.get('status_code') != 'TK_Complete']
        completed = [a for a in real_activities if a.get('status_code') == 'TK_Complete']
        
        # Project finish date (latest early_end among incomplete)
        project_finish = None
        end_dates = [a.get('early_end_date_parsed') for a in incomplete if a.get('early_end_date_parsed')]
        if end_dates:
            project_finish = max(end_dates)
        elif engine.projects:
            project_finish = engine._parse_date(engine.projects[0].get('plan_end_date', ''))
        
        # Critical (TF ≤ 0) count
        crit_count = sum(1 for a in incomplete if a.get('is_critical'))
        
        # Longest Path count (if calculated)
        lp_count = 0
        try:
            from longest_path_engine import LongestPathEngine
            lp = LongestPathEngine(engine)
            lp.calculate()
            lp_count = len(lp.longest_path_ids)
        except Exception:
            pass
        
        # Health score
        health_score = None
        health_pass_rate = None
        try:
            from advanced_health_engine import AdvancedHealthEngine
            he = AdvancedHealthEngine(engine)
            hr = he.run_all_checks('all')
            health_score = hr.get('overall_score')
            health_pass_rate = hr.get('pass_rate')
        except Exception as e:
            logger.warning(f"Health calc failed for {period_info['label']}: {e}")
        
        # EVM
        spi = cpi = eac = bac = None
        try:
            from evm_engine import EVMEngine
            evm = EVMEngine(engine)
            ev_results = evm.calculate()
            metrics = ev_results.get('metrics', {})
            spi = metrics.get('spi')
            cpi = metrics.get('cpi')
            eac = metrics.get('eac')
            bac = metrics.get('bac')
        except Exception as e:
            logger.warning(f"EVM calc failed for {period_info['label']}: {e}")
        
        # Negative float count
        neg_float_count = sum(1 for a in incomplete if a.get('total_float_days', 0) < 0)
        
        return {
            'label': period_info['label'],
            'data_date': period_info['data_date'].strftime('%Y-%m-%d') if period_info['data_date'] else '',
            'total_activities': len(engine.activities),
            'incomplete_count': len(incomplete),
            'completed_count': len(completed),
            'critical_count': crit_count,
            'longest_path_count': lp_count,
            'negative_float_count': neg_float_count,
            'project_finish': project_finish.strftime('%Y-%m-%d') if project_finish else None,
            'health_score': health_score,
            'health_pass_rate': health_pass_rate,
            'spi': spi,
            'cpi': cpi,
            'eac': eac,
            'bac': bac,
            'relationship_count': len(engine.relationships),
        }

    def _detect_chronic_critical(self):
        """
        Find activities that appeared as critical in 3+ periods.
        These are the true bottleneck activities.
        """
        activity_critical_map = defaultdict(list)  # {task_code: [period_labels_where_critical]}
        activity_details = {}  # {task_code: {name, wbs}}
        
        for period in self.periods:
            engine = period['engine']
            for act in engine.activities:
                if act.get('is_critical') and act.get('status_code') != 'TK_Complete':
                    code = act.get('task_code', '')
                    if not code:
                        continue
                    activity_critical_map[code].append(period['label'])
                    if code not in activity_details:
                        activity_details[code] = {
                            'name': act.get('task_name', ''),
                            'wbs': act.get('wbs_name', ''),
                        }
        
        chronic = []
        threshold = 3 if len(self.periods) >= 4 else 2
        
        for code, periods_list in activity_critical_map.items():
            if len(periods_list) >= threshold:
                chronic.append({
                    'code': code,
                    'name': activity_details[code]['name'],
                    'wbs': activity_details[code]['wbs'],
                    'critical_in_periods': periods_list,
                    'critical_count': len(periods_list),
                    'chronic_percentage': round(len(periods_list) / len(self.periods) * 100, 1),
                })
        
        chronic.sort(key=lambda x: x['critical_count'], reverse=True)
        return chronic

    def _calculate_slippage_trend(self, period_metrics):
        """Calculate cumulative slippage from first period."""
        if not period_metrics or not period_metrics[0].get('project_finish'):
            return {'labels': [], 'slippage_days': []}
        
        try:
            baseline_finish = datetime.strptime(period_metrics[0]['project_finish'], '%Y-%m-%d')
        except (ValueError, TypeError):
            return {'labels': [], 'slippage_days': []}
        
        labels = []
        slippage = []
        finishes = []
        for pm in period_metrics:
            labels.append(pm['label'])
            if pm.get('project_finish'):
                try:
                    curr_finish = datetime.strptime(pm['project_finish'], '%Y-%m-%d')
                    slippage.append((curr_finish - baseline_finish).days)
                    finishes.append(pm['project_finish'])
                except (ValueError, TypeError):
                    slippage.append(None)
                    finishes.append(None)
            else:
                slippage.append(None)
                finishes.append(None)
        
        return {
            'labels': labels,
            'slippage_days': slippage,
            'project_finishes': finishes,
            'baseline_finish': period_metrics[0]['project_finish'],
        }

    def _calculate_activity_trend(self, period_metrics):
        """Track total, incomplete, and completed activity counts."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'total': [pm['total_activities'] for pm in period_metrics],
            'incomplete': [pm['incomplete_count'] for pm in period_metrics],
            'completed': [pm['completed_count'] for pm in period_metrics],
        }

    def _calculate_health_trend(self, period_metrics):
        """Track health score over time."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'scores': [pm.get('health_score') for pm in period_metrics],
            'pass_rates': [pm.get('health_pass_rate') for pm in period_metrics],
        }

    def _calculate_evm_trend(self, period_metrics):
        """Track EVM SPI/CPI over time."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'spi': [pm.get('spi') for pm in period_metrics],
            'cpi': [pm.get('cpi') for pm in period_metrics],
            'eac': [pm.get('eac') for pm in period_metrics],
            'bac': [pm.get('bac') for pm in period_metrics],
        }

    def _calculate_critical_trend(self, period_metrics):
        """Track critical path metrics over time."""
        return {
            'labels': [pm['label'] for pm in period_metrics],
            'critical_count': [pm['critical_count'] for pm in period_metrics],
            'longest_path_count': [pm['longest_path_count'] for pm in period_metrics],
            'negative_float_count': [pm['negative_float_count'] for pm in period_metrics],
        }
'''

with open("trend_engine.py", "w", encoding="utf-8") as f:
    f.write(TREND_ENGINE_CODE)
print("  ✅ Created trend_engine.py")


# ==============================================================================
# FILE 2: app.py (Add /trends view + /api/trend-upload + /api/trend-data)
# ==============================================================================

# We patch existing app.py rather than rewriting - simpler and safer.
try:
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()
    
    # Add TrendAnalysisEngine import
    if "from trend_engine import TrendAnalysisEngine" not in app_code:
        app_code = app_code.replace(
            "try:\n    from longest_path_engine import LongestPathEngine",
            "try:\n    from trend_engine import TrendAnalysisEngine\n    logger.info(\"✅ TrendAnalysisEngine imported\")\nexcept Exception as e:\n    TrendAnalysisEngine = None\n    logger.warning(\"❌ TrendAnalysisEngine import failed: %s\", e)\n\ntry:\n    from longest_path_engine import LongestPathEngine"
        )
    
    # Add 'trends' storage to session
    if "'trends'" not in app_code:
        app_code = app_code.replace(
            "'longest_path_cache': None,",
            "'longest_path_cache': None,\n            'trends': {'engine': None, 'results': None, 'periods': []},"
        )
    
    # Add /trends view + /api/trend-* routes before if __name__ ==
    if "/api/trend-upload" not in app_code:
        trend_routes = '''

# ═══════════════════════════════════════════
# TREND ANALYSIS ROUTES (Phase 2, Step 5)
# ═══════════════════════════════════════════

@app.route('/trends')
def trends_view():
    return render_template('trends.html')


@app.route('/api/trend-upload', methods=['POST'])
def upload_trend_files():
    if TrendAnalysisEngine is None:
        return jsonify({'error': 'trend_engine.py is missing!'}), 500
    
    files = request.files.getlist('files')
    if not files or len(files) < 2:
        return jsonify({'error': 'At least 2 XER files required for trend analysis'}), 400
    
    for f in files:
        if not allowed_file(f.filename):
            return jsonify({'error': f'File {f.filename} is not a .xer file'}), 400
    
    sess_data = get_session_data()
    trend_engine = TrendAnalysisEngine()
    
    saved_files = []
    try:
        for idx, file in enumerate(files, 1):
            original_name = secure_filename(file.filename)
            unique_name = f"trend_{uuid.uuid4().hex[:8]}_{original_name}"
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(fpath)
            saved_files.append({'path': fpath, 'name': original_name})
            
            label = original_name.replace('.xer', '').replace('.XER', '')
            trend_engine.add_period(fpath, period_label=label)
        
        results = trend_engine.analyze()
        
        sess_data['trends']['engine'] = trend_engine
        sess_data['trends']['results'] = results
        sess_data['trends']['periods'] = [f['name'] for f in saved_files]
        
        return jsonify({
            'success': True,
            'period_count': len(saved_files),
            'periods': [f['name'] for f in saved_files],
            'data': results,
        })
    except Exception as e:
        logger.exception("Trend upload error")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trend-data')
def get_trend_data():
    sess_data = get_session_data()
    trends = sess_data.get('trends', {})
    if not trends.get('results'):
        return jsonify({'has_data': False})
    return jsonify({
        'has_data': True,
        'periods': trends['periods'],
        'data': trends['results'],
    })


@app.route('/api/trend-reset', methods=['POST'])
def reset_trend_analysis():
    sess_data = get_session_data()
    sess_data['trends'] = {'engine': None, 'results': None, 'periods': []}
    return jsonify({'success': True})

'''
        app_code = app_code.replace(
            "if __name__ == '__main__':",
            trend_routes + "\nif __name__ == '__main__':"
        )
    
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
    print("  ✅ Patched app.py (added Trend Analysis routes)")
except Exception as e:
    print(f"  ⚠️ Could not auto-patch app.py: {e}")


# ==============================================================================
# FILE 3: templates/trends.html (NEW - Multi-Period Trend Dashboard)
# ==============================================================================

TRENDS_HTML_CODE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trend Analysis | {{ config.app_title }}</title>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        :root {
            --color-primary: {{ config.theme.primary }};
            --color-primary-dark: {{ config.theme.primary_dark }};
            --color-accent: {{ config.theme.accent }};
            --color-success: {{ config.theme.success }};
            --color-warning: {{ config.theme.warning }};
            --color-danger: {{ config.theme.danger }};
            --color-bg: {{ config.theme.bg }};
            --color-surface: {{ config.theme.surface }};
            --color-text: {{ config.theme.text }};
            --color-muted: {{ config.theme.muted }};
            --color-border: {{ config.theme.border }};
        }
    </style>
    
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    
    <style>
        a.btn { text-decoration: none; }
        .app-header .btn-secondary[aria-current="page"] {
            background: rgba(255, 255, 255, 0.4); border-color: #fff; font-weight: 700;
        }

        .trend-upload-zone {
            background: var(--color-surface); border: 3px dashed var(--color-border);
            border-radius: 12px; padding: 3rem; text-align: center;
            cursor: pointer; transition: all 0.2s; margin: 2rem 0;
        }
        .trend-upload-zone:hover, .trend-upload-zone.dragover {
            border-color: var(--color-accent); background: rgba(59, 130, 246, 0.05);
        }
        .trend-upload-zone.has-files {
            border-color: var(--color-success); background: rgba(16, 185, 129, 0.05);
        }
        
        .selected-files-list {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 0.75rem; margin: 1.5rem 0; text-align: left;
        }
        .selected-file-chip {
            background: #fff; border: 1px solid var(--color-border);
            border-radius: 8px; padding: 0.75rem; font-size: 0.85rem;
            display: flex; justify-content: space-between; align-items: center;
        }
        .selected-file-chip .num {
            background: var(--color-accent); color: #fff;
            border-radius: 50%; width: 24px; height: 24px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.75rem; margin-right: 0.5rem;
        }
        .selected-file-chip .name {
            flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        
        .trend-summary-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem; margin: 2rem 0;
        }
        .trend-summary-card {
            background: var(--color-surface); border: 1px solid var(--color-border);
            border-radius: 10px; padding: 1.25rem; text-align: center;
            border-top: 4px solid var(--color-accent);
        }
        .trend-summary-card.slipped { border-top-color: var(--color-danger); }
        .trend-summary-card.improved { border-top-color: var(--color-success); }
        .trend-summary-card.warning { border-top-color: var(--color-warning); }
        .trend-summary-card .value {
            font-size: 1.75rem; font-weight: 700; color: var(--color-text);
        }
        .trend-summary-card .label {
            font-size: 0.8rem; color: var(--color-muted);
            text-transform: uppercase; letter-spacing: 0.02em; margin-top: 0.5rem;
        }
        
        .chart-panel {
            background: var(--color-surface); border: 1px solid var(--color-border);
            border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .chart-panel h3 {
            margin-bottom: 0.5rem; color: var(--color-primary); font-size: 1.15rem;
        }
        .chart-panel .subtitle {
            font-size: 0.85rem; color: var(--color-muted); margin-bottom: 1rem;
        }
        .chart-wrapper {
            position: relative; height: 320px;
        }
        .chart-grid-2 {
            display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;
        }
        @media (max-width: 900px) {
            .chart-grid-2 { grid-template-columns: 1fr; }
        }
        
        .chronic-table {
            width: 100%; border-collapse: collapse; font-size: 0.85rem;
            margin-top: 1rem;
        }
        .chronic-table th {
            background: var(--color-primary); color: #fff;
            padding: 0.65rem; text-align: left; font-weight: 600;
        }
        .chronic-table td {
            padding: 0.55rem 0.65rem; border-bottom: 1px solid var(--color-border);
        }
        .chronic-table tbody tr:hover { background: #f1f5f9; }
        .chronic-badge {
            display: inline-block; padding: 0.15rem 0.5rem;
            border-radius: 12px; font-size: 0.7rem; font-weight: 700;
            background: #fee2e2; color: #991b1b;
        }
        .chronic-badge.severe { background: #7f1d1d; color: #fff; }
    </style>
</head>
<body>
    <header class="app-header">
        <div class="header-content">
            <div class="logo-section">
                {% if config.use_logo_image %}
                    <img src="{{ url_for('static', filename=config.logo_path) }}" alt="Logo" style="height: 45px;">
                {% else %}
                    <span class="logo-icon">📈</span>
                {% endif %}
                <div>
                    <h1>{{ config.app_title }} — Trends</h1>
                    <p class="subtitle">Multi-Period Schedule Trend Analysis</p>
                </div>
            </div>
            <div class="header-actions">
                <a href="/" class="btn btn-secondary">📊 Dashboard</a>
                <a href="/gantt" class="btn btn-secondary">📅 Gantt</a>
                <a href="/comparison" class="btn btn-secondary">🔄 Compare</a>
                <a href="/trends" class="btn btn-secondary" aria-current="page">📈 Trends</a>
                <a href="/evm" class="btn btn-secondary">💰 EVM</a>
                <a href="/health" class="btn btn-secondary">🏥 Health</a>
            </div>
        </div>
    </header>

    <main class="app-main">
        <!-- UPLOAD SECTION -->
        <div id="uploadSection">
            <h2>📈 Multi-Period Trend Analysis</h2>
            <p style="color: var(--color-muted); margin-bottom: 1rem;">
                Upload <strong>2 or more</strong> XER schedule updates (e.g., monthly progress reports) to visualize 
                slippage, health, and EVM trends over time.
            </p>
            
            <div class="trend-upload-zone" id="trendDropZone">
                <div style="font-size: 3rem;">📁</div>
                <h3 style="margin: 1rem 0 0.5rem;">Drop XER files here or click to browse</h3>
                <p style="color: var(--color-muted); font-size: 0.9rem;">
                    Select multiple .xer files representing successive schedule updates
                </p>
                <input type="file" id="trendFileInput" accept=".xer" multiple style="display:none;">
            </div>
            
            <div id="selectedFilesList" class="selected-files-list" style="display:none;"></div>
            
            <div style="text-align: center; margin: 2rem 0;">
                <button id="analyzeTrendBtn" class="btn btn-primary" disabled 
                    style="padding: 0.85rem 3rem; font-size: 1.05rem;">
                    🔍 Analyze Trends
                </button>
                <button id="resetTrendBtn" class="btn btn-secondary" style="margin-left: 0.5rem;">
                    ♻️ Reset
                </button>
            </div>
        </div>

        <!-- LOADING -->
        <div id="loadingSection" class="loading-screen" style="display:none;">
            <div class="spinner"></div>
            <p style="margin-top: 1rem;">Analyzing multi-period trends...</p>
            <p style="color: var(--color-muted); font-size: 0.85rem; margin-top: 0.5rem;">
                This may take a moment as each XER file is fully processed.
            </p>
        </div>

        <!-- RESULTS SECTION -->
        <div id="resultsSection" style="display:none;">
            <div class="file-info-bar" style="margin-bottom: 1.5rem;">
                <span>📊 <strong id="periodCount">--</strong> periods analyzed</span>
                <span>🕐 <span id="analyzedAt">--</span></span>
                <button onclick="resetTrends()" class="btn btn-secondary" style="margin-left: auto;">
                    🔄 New Analysis
                </button>
            </div>

            <!-- Summary Cards -->
            <div class="trend-summary-grid" id="trendSummary"></div>

            <!-- Project Finish Trend -->
            <div class="chart-panel">
                <h3>📅 Project Finish Date Trend</h3>
                <div class="subtitle">How the projected completion date has shifted across periods.</div>
                <div class="chart-wrapper">
                    <canvas id="finishTrendChart"></canvas>
                </div>
            </div>

            <!-- Health & Critical Trends (Side by side) -->
            <div class="chart-grid-2">
                <div class="chart-panel">
                    <h3>🏥 Health Score Trend</h3>
                    <div class="subtitle">Schedule quality score across all standards (0-100).</div>
                    <div class="chart-wrapper">
                        <canvas id="healthTrendChart"></canvas>
                    </div>
                </div>
                
                <div class="chart-panel">
                    <h3>🔴 Critical Path Activity Trend</h3>
                    <div class="subtitle">Total Float ≤ 0 vs Longest Path activity counts.</div>
                    <div class="chart-wrapper">
                        <canvas id="criticalTrendChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- EVM & Activity Count -->
            <div class="chart-grid-2">
                <div class="chart-panel">
                    <h3>💰 EVM Performance Trend (SPI / CPI)</h3>
                    <div class="subtitle">Schedule and Cost Performance Indices over time.</div>
                    <div class="chart-wrapper">
                        <canvas id="evmTrendChart"></canvas>
                    </div>
                </div>
                
                <div class="chart-panel">
                    <h3>📊 Activity Count Trend</h3>
                    <div class="subtitle">Total, incomplete, and completed activity counts per period.</div>
                    <div class="chart-wrapper">
                        <canvas id="activityTrendChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Chronic Critical Activities -->
            <div class="chart-panel">
                <h3>⚠️ Chronic Critical Activities</h3>
                <div class="subtitle">
                    Activities that remained critical across multiple periods — these are the real project bottlenecks.
                </div>
                <div id="chronicCriticalContent"></div>
            </div>
        </div>
    </main>

    <footer class="app-footer">
        <p>&copy; {{ config.footer_year }} {{ config.company_name }} | {{ config.footer_text }}</p>
    </footer>

    <script src="{{ url_for('static', filename='trends.js') }}"></script>
</body>
</html>
'''

os.makedirs("templates", exist_ok=True)
with open("templates/trends.html", "w", encoding="utf-8") as f:
    f.write(TRENDS_HTML_CODE)
print("  ✅ Created templates/trends.html")


# ==============================================================================
# FILE 4: static/trends.js (NEW - Trend Chart Renderers)
# ==============================================================================

TRENDS_JS_CODE = '''/*
    MULTI-PERIOD TREND ANALYSIS PAGE LOGIC
    ========================================
*/

let selectedFiles = [];
let trendData = null;
let finishTrendChart = null;
let healthTrendChart = null;
let criticalTrendChart = null;
let evmTrendChart = null;
let activityTrendChart = null;

const MAX_UPLOAD_MB = 100;
const MAX_FILES = 12;

// ═══════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════

function esc(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtNum(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return '—';
    return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function fmtDelta(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return '—';
    if (n === 0) return '0d';
    return (n > 0 ? '+' : '') + n + 'd';
}

async function safeFetchJSON(url, options) {
    const res = await fetch(url, options || {});
    let data = {};
    try { data = await res.json(); }
    catch (e) {
        if (!res.ok) throw new Error('Request failed (' + res.status + ')');
        throw new Error('Invalid JSON response from server');
    }
    if (!res.ok || data.error) {
        throw new Error(data.error || ('Request failed (' + res.status + ')'));
    }
    return data;
}

// ═══════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {
    setupFileHandler();
    setupButtons();
    checkExistingTrend();
});

function setupFileHandler() {
    const dropZone = document.getElementById('trendDropZone');
    const input = document.getElementById('trendFileInput');
    if (!dropZone || !input) return;

    dropZone.addEventListener('click', function () { input.click(); });
    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', function () { dropZone.classList.remove('dragover'); });
    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFilesSelected(Array.from(e.dataTransfer.files));
        }
    });
    input.addEventListener('change', function (e) {
        if (e.target.files && e.target.files.length > 0) {
            handleFilesSelected(Array.from(e.target.files));
        }
    });
}

function setupButtons() {
    const analyzeBtn = document.getElementById('analyzeTrendBtn');
    if (analyzeBtn) analyzeBtn.addEventListener('click', runTrendAnalysis);
    
    const resetBtn = document.getElementById('resetTrendBtn');
    if (resetBtn) resetBtn.addEventListener('click', resetSelection);
}

function handleFilesSelected(files) {
    const validFiles = files.filter(function (f) {
        if (!f.name.toLowerCase().endsWith('.xer')) {
            alert('❌ Skipping ' + f.name + ' - not a .xer file');
            return false;
        }
        if (f.size > MAX_UPLOAD_MB * 1024 * 1024) {
            alert('❌ ' + f.name + ' exceeds ' + MAX_UPLOAD_MB + ' MB limit');
            return false;
        }
        return true;
    });
    
    // Merge with existing selection, avoid duplicates by name
    const existingNames = new Set(selectedFiles.map(function (f) { return f.name; }));
    validFiles.forEach(function (f) {
        if (!existingNames.has(f.name)) {
            selectedFiles.push(f);
        }
    });
    
    if (selectedFiles.length > MAX_FILES) {
        alert('⚠️ Maximum ' + MAX_FILES + ' files supported. Trimming to first ' + MAX_FILES + '.');
        selectedFiles = selectedFiles.slice(0, MAX_FILES);
    }
    
    updateSelectedFilesUI();
}

function updateSelectedFilesUI() {
    const list = document.getElementById('selectedFilesList');
    const dropZone = document.getElementById('trendDropZone');
    const analyzeBtn = document.getElementById('analyzeTrendBtn');
    
    if (!selectedFiles.length) {
        list.style.display = 'none';
        dropZone.classList.remove('has-files');
        analyzeBtn.disabled = true;
        return;
    }
    
    list.style.display = 'grid';
    dropZone.classList.add('has-files');
    analyzeBtn.disabled = selectedFiles.length < 2;
    
    list.innerHTML = selectedFiles.map(function (f, idx) {
        return (
            '<div class="selected-file-chip">' +
            '<span class="num">' + (idx + 1) + '</span>' +
            '<span class="name" title="' + esc(f.name) + '">' + esc(f.name) + '</span>' +
            '<button onclick="removeFile(' + idx + ')" ' +
            'style="background:none;border:none;color:#dc2626;cursor:pointer;font-size:1.1rem;padding:0 0.25rem;" ' +
            'title="Remove">✕</button>' +
            '</div>'
        );
    }).join('');
}

function removeFile(idx) {
    selectedFiles.splice(idx, 1);
    updateSelectedFilesUI();
}

function resetSelection() {
    selectedFiles = [];
    const input = document.getElementById('trendFileInput');
    if (input) input.value = '';
    updateSelectedFilesUI();
}

async function runTrendAnalysis() {
    if (selectedFiles.length < 2) {
        alert('❌ Please select at least 2 XER files.');
        return;
    }
    
    const uploadSec = document.getElementById('uploadSection');
    const loadingSec = document.getElementById('loadingSection');
    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'block';
    
    const formData = new FormData();
    selectedFiles.forEach(function (f) {
        formData.append('files', f);
    });
    
    try {
        const response = await safeFetchJSON('/api/trend-upload', {
            method: 'POST',
            body: formData,
        });
        trendData = response.data;
        renderTrendResults();
    } catch (err) {
        console.error('Trend analysis error:', err);
        alert('❌ ' + (err.message || 'Trend analysis failed'));
        if (loadingSec) loadingSec.style.display = 'none';
        if (uploadSec) uploadSec.style.display = 'block';
    }
}

async function checkExistingTrend() {
    try {
        const res = await fetch('/api/trend-data');
        const data = await res.json().catch(function () { return {}; });
        if (res.ok && data.has_data) {
            trendData = data.data;
            renderTrendResults();
        }
    } catch (e) { console.warn('No existing trend', e); }
}

function renderTrendResults() {
    const uploadSec = document.getElementById('uploadSection');
    const loadingSec = document.getElementById('loadingSection');
    const resultsSec = document.getElementById('resultsSection');
    
    if (uploadSec) uploadSec.style.display = 'none';
    if (loadingSec) loadingSec.style.display = 'none';
    if (resultsSec) resultsSec.style.display = 'block';
    
    if (!trendData) return;
    
    const periodCount = document.getElementById('periodCount');
    const analyzedAt = document.getElementById('analyzedAt');
    if (periodCount) periodCount.textContent = trendData.period_count || 0;
    if (analyzedAt) analyzedAt.textContent = trendData.analyzed_at || '';
    
    renderSummaryCards();
    renderFinishTrendChart();
    renderHealthTrendChart();
    renderCriticalTrendChart();
    renderEvmTrendChart();
    renderActivityTrendChart();
    renderChronicCritical();
}

function renderSummaryCards() {
    const container = document.getElementById('trendSummary');
    if (!container) return;
    
    const slippage = trendData.slippage_trend || {};
    const slipDays = slippage.slippage_days || [];
    const totalSlip = slipDays.length ? slipDays[slipDays.length - 1] : 0;
    
    const health = trendData.health_trend || {};
    const scores = (health.scores || []).filter(function (s) { return s != null; });
    const healthChange = scores.length >= 2 ? (scores[scores.length - 1] - scores[0]).toFixed(1) : 'N/A';
    
    const critical = trendData.critical_trend || {};
    const critCounts = critical.critical_count || [];
    const critChange = critCounts.length >= 2 ? (critCounts[critCounts.length - 1] - critCounts[0]) : 0;
    
    const evm = trendData.evm_trend || {};
    const spis = (evm.spi || []).filter(function (v) { return v != null && v !== 0; });
    const spiChange = spis.length >= 2 ? (spis[spis.length - 1] - spis[0]).toFixed(3) : 'N/A';
    
    const chronic = trendData.chronic_critical || [];
    
    const cards = [
        {
            value: fmtDelta(totalSlip),
            label: 'Total Slippage vs Period 1',
            cls: totalSlip > 0 ? 'slipped' : (totalSlip < 0 ? 'improved' : ''),
        },
        {
            value: healthChange !== 'N/A' ? (healthChange > 0 ? '+' : '') + healthChange : 'N/A',
            label: 'Health Score Change',
            cls: healthChange !== 'N/A' && parseFloat(healthChange) < 0 ? 'slipped' : (parseFloat(healthChange) > 0 ? 'improved' : ''),
        },
        {
            value: (critChange > 0 ? '+' : '') + critChange,
            label: 'Critical Activity Change',
            cls: critChange > 0 ? 'slipped' : (critChange < 0 ? 'improved' : ''),
        },
        {
            value: spiChange !== 'N/A' ? (spiChange > 0 ? '+' : '') + spiChange : 'N/A',
            label: 'SPI Change',
            cls: spiChange !== 'N/A' && parseFloat(spiChange) < 0 ? 'slipped' : (parseFloat(spiChange) > 0 ? 'improved' : ''),
        },
        {
            value: chronic.length,
            label: 'Chronic Critical Activities',
            cls: chronic.length > 10 ? 'slipped' : (chronic.length > 0 ? 'warning' : 'improved'),
        },
    ];
    
    container.innerHTML = cards.map(function (c) {
        return (
            '<div class="trend-summary-card ' + esc(c.cls) + '">' +
            '<div class="value">' + esc(c.value) + '</div>' +
            '<div class="label">' + esc(c.label) + '</div>' +
            '</div>'
        );
    }).join('');
}

function renderFinishTrendChart() {
    const canvas = document.getElementById('finishTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (finishTrendChart) { finishTrendChart.destroy(); finishTrendChart = null; }
    
    const slippage = trendData.slippage_trend || {};
    const labels = slippage.labels || [];
    const slipDays = slippage.slippage_days || [];
    const finishes = slippage.project_finishes || [];
    
    if (!labels.length) return;
    
    finishTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Slippage from Period 1 (days)',
                data: slipDays,
                borderColor: '#dc2626',
                backgroundColor: 'rgba(220, 38, 38, 0.15)',
                borderWidth: 3,
                fill: true,
                tension: 0.2,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBackgroundColor: '#dc2626',
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const idx = ctx.dataIndex;
                            const days = ctx.parsed.y;
                            const finish = finishes[idx] || '—';
                            return [
                                'Slippage: ' + fmtDelta(days),
                                'Project Finish: ' + finish
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: { callback: function (v) { return fmtDelta(v); } },
                    grid: { color: function (ctx) { return ctx.tick.value === 0 ? '#000' : '#e2e8f0'; } }
                }
            }
        }
    });
}

function renderHealthTrendChart() {
    const canvas = document.getElementById('healthTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (healthTrendChart) { healthTrendChart.destroy(); healthTrendChart = null; }
    
    const health = trendData.health_trend || {};
    
    healthTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: health.labels || [],
            datasets: [
                {
                    label: 'Health Score',
                    data: health.scores || [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.15)',
                    borderWidth: 3, fill: true, tension: 0.2,
                    pointRadius: 5, pointHoverRadius: 7,
                },
                {
                    label: 'Pass Rate (%)',
                    data: health.pass_rates || [],
                    borderColor: '#10b981',
                    borderDash: [5, 5], borderWidth: 2, fill: false, tension: 0.2,
                    pointRadius: 4,
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + '%'; } } } }
        }
    });
}

function renderCriticalTrendChart() {
    const canvas = document.getElementById('criticalTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (criticalTrendChart) { criticalTrendChart.destroy(); criticalTrendChart = null; }
    
    const critical = trendData.critical_trend || {};
    
    criticalTrendChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: critical.labels || [],
            datasets: [
                {
                    label: 'Critical (TF ≤ 0)',
                    data: critical.critical_count || [],
                    backgroundColor: '#dc2626',
                },
                {
                    label: 'Longest Path',
                    data: critical.longest_path_count || [],
                    backgroundColor: '#7c3aed',
                },
                {
                    label: 'Negative Float',
                    data: critical.negative_float_count || [],
                    backgroundColor: '#f59e0b',
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function renderEvmTrendChart() {
    const canvas = document.getElementById('evmTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (evmTrendChart) { evmTrendChart.destroy(); evmTrendChart = null; }
    
    const evm = trendData.evm_trend || {};
    
    evmTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: evm.labels || [],
            datasets: [
                {
                    label: 'SPI',
                    data: evm.spi || [],
                    borderColor: '#3b82f6',
                    borderWidth: 3, fill: false, tension: 0.2,
                    pointRadius: 5,
                },
                {
                    label: 'CPI',
                    data: evm.cpi || [],
                    borderColor: '#10b981',
                    borderWidth: 3, fill: false, tension: 0.2,
                    pointRadius: 5,
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                annotation: {
                    annotations: {
                        line1: { type: 'line', yMin: 1, yMax: 1, borderColor: '#000', borderWidth: 1, borderDash: [3, 3] }
                    }
                }
            },
            scales: {
                y: {
                    min: 0.7, max: 1.3,
                    ticks: { callback: function (v) { return v.toFixed(2); } }
                }
            }
        }
    });
}

function renderActivityTrendChart() {
    const canvas = document.getElementById('activityTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (activityTrendChart) { activityTrendChart.destroy(); activityTrendChart = null; }
    
    const activity = trendData.activity_trend || {};
    
    activityTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: activity.labels || [],
            datasets: [
                { label: 'Total Activities', data: activity.total || [], borderColor: '#3b82f6', borderWidth: 2, fill: false, tension: 0.2 },
                { label: 'Incomplete', data: activity.incomplete || [], borderColor: '#f59e0b', borderWidth: 2, fill: false, tension: 0.2 },
                { label: 'Completed', data: activity.completed || [], borderColor: '#10b981', borderWidth: 2, fill: false, tension: 0.2 }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function renderChronicCritical() {
    const container = document.getElementById('chronicCriticalContent');
    if (!container) return;
    
    const chronic = trendData.chronic_critical || [];
    
    if (!chronic.length) {
        container.innerHTML = '<p style="text-align:center;padding:2rem;color:#64748b;">✅ No chronic critical activities detected!</p>';
        return;
    }
    
    let html = '<table class="chronic-table"><thead><tr>' +
        '<th>Activity Code</th><th>Name</th><th>WBS</th>' +
        '<th>Critical in Periods</th><th style="text-align:right;">Frequency</th>' +
        '</tr></thead><tbody>';
    
    chronic.slice(0, 50).forEach(function (c) {
        const isSevere = c.chronic_percentage >= 75;
        const badgeClass = isSevere ? 'chronic-badge severe' : 'chronic-badge';
        
        html += '<tr>' +
            '<td><strong>' + esc(c.code) + '</strong></td>' +
            '<td>' + esc(c.name) + '</td>' +
            '<td style="font-size:0.8rem;color:#64748b;">' + esc(c.wbs) + '</td>' +
            '<td style="font-size:0.75rem;">' + esc(c.critical_in_periods.join(', ')) + '</td>' +
            '<td style="text-align:right;">' +
            '<span class="' + badgeClass + '">' +
            c.critical_count + ' / ' + trendData.period_count + ' (' + c.chronic_percentage + '%)' +
            '</span></td>' +
            '</tr>';
    });
    
    if (chronic.length > 50) {
        html += '<tr><td colspan="5" style="text-align:center;padding:1rem;color:#64748b;">' +
            '… and ' + (chronic.length - 50) + ' more chronic activities</td></tr>';
    }
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

async function resetTrends() {
    try {
        await fetch('/api/trend-reset', { method: 'POST' });
    } catch (e) {}
    
    trendData = null;
    selectedFiles = [];
    
    if (finishTrendChart) { finishTrendChart.destroy(); finishTrendChart = null; }
    if (healthTrendChart) { healthTrendChart.destroy(); healthTrendChart = null; }
    if (criticalTrendChart) { criticalTrendChart.destroy(); criticalTrendChart = null; }
    if (evmTrendChart) { evmTrendChart.destroy(); evmTrendChart = null; }
    if (activityTrendChart) { activityTrendChart.destroy(); activityTrendChart = null; }
    
    const uploadSec = document.getElementById('uploadSection');
    const resultsSec = document.getElementById('resultsSection');
    if (uploadSec) uploadSec.style.display = 'block';
    if (resultsSec) resultsSec.style.display = 'none';
    
    updateSelectedFilesUI();
}

window.removeFile = removeFile;
window.resetTrends = resetTrends;
'''

os.makedirs("static", exist_ok=True)
with open("static/trends.js", "w", encoding="utf-8") as f:
    f.write(TRENDS_JS_CODE)
print("  ✅ Created static/trends.js")


# ==============================================================================
# FILE 5-9: Add "📈 Trends" nav link to all templates
# ==============================================================================

def add_trends_nav_link(template_path):
    if not os.path.exists(template_path):
        return
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Only insert if not already present
        if '/trends' in content:
            return
        
        # Insert Trends link after Comparison link
        old = '<a href="/comparison" class="btn btn-secondary">🔄 Compare</a>'
        new = '<a href="/comparison" class="btn btn-secondary">🔄 Compare</a>\n                <a href="/trends" class="btn btn-secondary">📈 Trends</a>'
        content = content.replace(old, new, 1)
        
        # Also try alternative with aria-current
        if '/trends' not in content:
            old = '<a href="/comparison" class="btn btn-secondary" aria-current="page">🔄 Compare</a>'
            new = old + '\n                <a href="/trends" class="btn btn-secondary">📈 Trends</a>'
            content = content.replace(old, new, 1)
        
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ Added Trends nav link to {template_path}")
    except Exception as e:
        print(f"  ⚠️ Could not patch {template_path}: {e}")


for tpl in ["templates/index.html", "templates/gantt.html", "templates/evm.html", 
            "templates/comparison.html", "templates/health.html"]:
    add_trends_nav_link(tpl)


print("\n🎉 Phase 2 - Step 5 (Multi-Period Trend Analysis) Applied Successfully!")
print("✨ Restart Flask (python app.py), navigate to /trends,")
print("   upload 2 or more XER files, and see the multi-period trends!")
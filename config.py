"""
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

MAX_UPLOAD_SIZE_MB = 1000
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


# ═══════════════════════════════════════════════════════════
# PHASE 3 STEP 8: PERSISTENT BACKEND CONFIGURATION
# ═══════════════════════════════════════════════════════════
# All are optional — app auto-falls-back to local dev mode

# Database (optional — defaults to SQLite ./analyzer.db)
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Object Storage (optional — defaults to local ./uploads/)
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Task Queue (optional — defaults to in-process threads)
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', '')
WORKER_THREADS = int(os.environ.get('WORKER_THREADS', '2'))

# Project retention (days)
PROJECT_RETENTION_DAYS = int(os.environ.get('PROJECT_RETENTION_DAYS', '7'))

"""
BRANDING & CONFIGURATION
========================
Customize the look and feel of your app here.
"""

# ─── COMPANY BRANDING ───
COMPANY_NAME = "MK Constructions"
APP_TITLE = "P6 Schedule Analyzer"
APP_SUBTITLE = "Advanced Schedule Analytics & DCMA Health Check"

# Path to your logo (place logo.png in static/img/)
LOGO_PATH = "img/logo.png"
USE_LOGO_IMAGE = False  # Set to True if you have a logo image

# ─── COLOR THEMES ───
# Choose one: 'blue', 'green', 'purple', 'dark', 'orange'
ACTIVE_THEME = 'blue'

THEMES = {
    'blue': {
        'primary': '#1e40af',
        'primary_dark': '#3730a3',
        'accent': '#3b82f6',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#dc2626',
    },
    'green': {
        'primary': '#065f46',
        'primary_dark': '#064e3b',
        'accent': '#10b981',
        'success': '#22c55e',
        'warning': '#f59e0b',
        'danger': '#dc2626',
    },
    'purple': {
        'primary': '#5b21b6',
        'primary_dark': '#4c1d95',
        'accent': '#8b5cf6',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#dc2626',
    },
    'dark': {
        'primary': '#1f2937',
        'primary_dark': '#111827',
        'accent': '#6366f1',
        'success': '#10b981',
        'warning': '#f59e0b',
        'danger': '#ef4444',
    },
    'orange': {
        'primary': '#c2410c',
        'primary_dark': '#9a3412',
        'accent': '#f97316',
        'success': '#10b981',
        'warning': '#eab308',
        'danger': '#dc2626',
    }
}

# ─── FEATURE FLAGS ───
ENABLE_GANTT = True
ENABLE_COMPARISON = True
ENABLE_EVM = True
ENABLE_EXPORT = True

# ─── APP SETTINGS ───
MAX_UPLOAD_SIZE_MB = 100
MAX_GANTT_ACTIVITIES = 500
DEFAULT_PORT = 5000

# ─── FOOTER ───
FOOTER_TEXT = "Powered by P6 Schedule Analyzer"
FOOTER_YEAR = 2024


def get_theme():
    """Return the active theme colors."""
    return THEMES.get(ACTIVE_THEME, THEMES['blue'])


def get_config():
    """Return the full configuration."""
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
        },
        'footer_text': FOOTER_TEXT,
        'footer_year': FOOTER_YEAR,
    }
"""
AUTH DECORATORS
================
@login_required     : Requires authenticated user
@role_required('admin', 'owner') : Requires specific role(s)
@guest_or_user      : Allows both authenticated + legacy guest mode (backward compat)
"""

from functools import wraps
from flask import session, jsonify, redirect, url_for, request


def get_current_user():
    """Get the currently logged-in user dict, or None."""
    return session.get('user')


def get_current_org_id():
    """Get the current user's organization ID, or None."""
    user = get_current_user()
    return user.get('org_id') if user else None


def login_required(f):
    """Reject if no user in session."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required', 'redirect': '/login'}), 401
            return redirect(url_for('login_page', next=request.path))
        return f(*args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    """Require user to have one of the allowed roles."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('login_page'))
            
            if user.get('role') not in allowed_roles:
                if request.path.startswith('/api/'):
                    return jsonify({'error': f'Access denied. Required role: {allowed_roles}'}), 403
                return '<h1>403 Forbidden</h1><p>You do not have permission to access this page.</p>', 403
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


def guest_or_user(f):
    """Allow both authenticated users AND legacy guest sessions."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # No-op — just marks the route as intentionally allowing guest access
        return f(*args, **kwargs)
    return wrapper

/*
    Auth Widget - Auto-injects login/register or user menu
    into every page header.
*/

(function () {
    'use strict';
    
    let authState = null;
    
    async function initAuthWidget() {
        // Find header action area
        const header = document.querySelector('.header-actions');
        if (!header) return;
        
        // Create widget container
        const widget = document.createElement('div');
        widget.className = 'auth-widget';
        widget.id = 'authWidget';
        widget.innerHTML = '<div class="auth-loading">⏳ ...</div>';
        header.appendChild(widget);
        
        // Fetch current user
        try {
            const res = await fetch('/api/auth/me');
            const data = await res.json();
            authState = data;
            renderWidget(data);
        } catch (err) {
            console.warn('[Auth Widget] Could not fetch user:', err);
            renderGuestView();
        }
    }
    
    function renderWidget(data) {
        const widget = document.getElementById('authWidget');
        if (!widget) return;
        
        if (data && data.authenticated && data.user) {
            renderLoggedInView(data.user);
        } else {
            renderGuestView();
        }
    }
    
    function renderGuestView() {
        const widget = document.getElementById('authWidget');
        if (!widget) return;
        widget.innerHTML = `
            <div class="auth-guest-buttons">
                <a href="/login" class="auth-login-btn">Sign In</a>
                <a href="/register" class="auth-register-btn">Sign Up</a>
            </div>
        `;
    }
    
    function renderLoggedInView(user) {
        const widget = document.getElementById('authWidget');
        if (!widget) return;
        
        const initials = getInitials(user.full_name || user.email);
        const role = (user.role || 'viewer').toLowerCase();
        const isAdmin = role === 'owner' || role === 'admin';
        
        widget.innerHTML = `
            <button class="auth-user-btn" onclick="window.__toggleAuthDropdown(event)">
                <span class="auth-avatar">${escapeHtml(initials)}</span>
                <span class="auth-user-name">${escapeHtml(user.full_name || user.email)}</span>
                <span class="auth-dropdown-arrow">▼</span>
            </button>
            <div class="auth-dropdown" id="authDropdown">
                <div class="auth-dropdown-header">
                    <div class="auth-dropdown-name">${escapeHtml(user.full_name || 'User')}</div>
                    <div class="auth-dropdown-email">${escapeHtml(user.email)}</div>
                    <div class="auth-dropdown-org">
                        🏢 ${escapeHtml(user.org_name || 'Organization')}
                        <span class="auth-role-badge ${role}">${escapeHtml(role)}</span>
                    </div>
                </div>
                <div class="auth-dropdown-items">
                    <a href="/" class="auth-dropdown-item">
                        <span class="auth-dropdown-icon">📊</span>
                        <span>My Projects</span>
                    </a>
                    ${isAdmin ? `
                    <a href="/admin" class="auth-dropdown-item">
                        <span class="auth-dropdown-icon">⚙️</span>
                        <span>Admin Panel</span>
                    </a>
                    ` : ''}
                    <div class="auth-dropdown-divider"></div>
                    <a href="/logout" class="auth-dropdown-item danger">
                        <span class="auth-dropdown-icon">🚪</span>
                        <span>Sign Out</span>
                    </a>
                </div>
            </div>
        `;
    }
    
    window.__toggleAuthDropdown = function (e) {
        e.stopPropagation();
        const dd = document.getElementById('authDropdown');
        if (dd) dd.classList.toggle('show');
    };
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function (e) {
        const dd = document.getElementById('authDropdown');
        if (dd && dd.classList.contains('show') && !e.target.closest('.auth-widget')) {
            dd.classList.remove('show');
        }
    });
    
    // Close on ESC
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const dd = document.getElementById('authDropdown');
            if (dd) dd.classList.remove('show');
        }
    });
    
    function getInitials(name) {
        if (!name) return '?';
        const parts = String(name).trim().split(/\s+/);
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    
    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, m => (
            {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]
        ));
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAuthWidget);
    } else {
        initAuthWidget();
    }
    
    console.log('%c[Auth Widget] ✅ Ready', 'color: #10b981; font-weight: bold;');
})();

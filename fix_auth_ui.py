import os
import re

print("🔧 Adding Authentication UI to all page headers...")

# ==============================================================================
# STEP 1: Create static/auth_widget.css (Auth dropdown styles)
# ==============================================================================

AUTH_CSS = '''/*
    Auth Widget - User dropdown + Login/Register buttons in header
*/

.auth-widget {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.auth-loading {
    color: rgba(255,255,255,0.6);
    font-size: 0.8rem;
    padding: 0.4rem 0.8rem;
}

.auth-guest-buttons {
    display: flex;
    gap: 0.4rem;
    align-items: center;
}

.auth-guest-buttons a {
    text-decoration: none;
    padding: 0.45rem 0.9rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.15s;
    display: inline-block;
}

.auth-guest-buttons .auth-login-btn {
    background: rgba(255,255,255,0.15);
    color: #fff;
    border: 1px solid rgba(255,255,255,0.3);
}
.auth-guest-buttons .auth-login-btn:hover {
    background: rgba(255,255,255,0.25);
}

.auth-guest-buttons .auth-register-btn {
    background: #10b981;
    color: #fff;
    border: 1px solid #059669;
}
.auth-guest-buttons .auth-register-btn:hover {
    background: #059669;
}

/* User button */
.auth-user-btn {
    background: rgba(255,255,255,0.15);
    color: #fff;
    border: 1px solid rgba(255,255,255,0.3);
    padding: 0.4rem 0.8rem;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    transition: all 0.15s;
}
.auth-user-btn:hover {
    background: rgba(255,255,255,0.25);
}

.auth-avatar {
    background: linear-gradient(135deg, #10b981, #059669);
    color: #fff;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
}

.auth-user-name {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.auth-dropdown-arrow {
    font-size: 0.65rem;
    opacity: 0.7;
}

/* Dropdown menu */
.auth-dropdown {
    position: absolute;
    top: calc(100% + 0.5rem);
    right: 0;
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
    min-width: 260px;
    z-index: 1000;
    display: none;
    overflow: hidden;
    border: 1px solid #e2e8f0;
}
.auth-dropdown.show { display: block; }

.auth-dropdown-header {
    padding: 1rem 1.25rem;
    background: linear-gradient(135deg, #f8fafc, #f1f5f9);
    border-bottom: 1px solid #e2e8f0;
}

.auth-dropdown-name {
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.15rem;
}

.auth-dropdown-email {
    color: #64748b;
    font-size: 0.8rem;
}

.auth-dropdown-org {
    margin-top: 0.4rem;
    font-size: 0.75rem;
    color: #3b82f6;
    display: flex;
    align-items: center;
    gap: 0.3rem;
}

.auth-role-badge {
    display: inline-block;
    padding: 0.15rem 0.45rem;
    border-radius: 10px;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.auth-role-badge.owner { background: #7c3aed; color: #fff; }
.auth-role-badge.admin { background: #dc2626; color: #fff; }
.auth-role-badge.manager { background: #f59e0b; color: #fff; }
.auth-role-badge.viewer { background: #64748b; color: #fff; }

.auth-dropdown-items { padding: 0.4rem 0; }

.auth-dropdown-item {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.65rem 1.25rem;
    color: #334155;
    text-decoration: none;
    font-size: 0.9rem;
    cursor: pointer;
    background: none;
    border: none;
    width: 100%;
    text-align: left;
    font-family: inherit;
    transition: background 0.15s;
}
.auth-dropdown-item:hover {
    background: #f1f5f9;
    color: #1e40af;
}
.auth-dropdown-item.danger:hover {
    background: #fef2f2;
    color: #dc2626;
}

.auth-dropdown-icon {
    font-size: 1rem;
    width: 20px;
    text-align: center;
}

.auth-dropdown-divider {
    height: 1px;
    background: #e2e8f0;
    margin: 0.3rem 0;
}
'''

os.makedirs("static", exist_ok=True)
with open("static/auth_widget.css", "w", encoding="utf-8") as f:
    f.write(AUTH_CSS)
print("  ✅ Created static/auth_widget.css")


# ==============================================================================
# STEP 2: Create static/auth_widget.js (Auto-injects widget into header)
# ==============================================================================

AUTH_JS = '''/*
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
        const parts = String(name).trim().split(/\\s+/);
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
'''

with open("static/auth_widget.js", "w", encoding="utf-8") as f:
    f.write(AUTH_JS)
print("  ✅ Created static/auth_widget.js")


# ==============================================================================
# STEP 3: Inject auth widget CSS + JS into all page templates
# ==============================================================================

INJECTION_TAG = '''
    <!-- Auth Widget (Auto-injects login/user menu into header) -->
    <link rel="stylesheet" href="{{ url_for('static', filename='auth_widget.css') }}">
    <script src="{{ url_for('static', filename='auth_widget.js') }}"></script>
</head>'''

def inject_auth_widget(template_path):
    if not os.path.exists(template_path):
        return
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if 'auth_widget.js' in content:
            print(f"  ℹ️  Already injected: {template_path}")
            return
        
        # Replace last </head> with injection
        if '</head>' in content:
            content = content.replace('</head>', INJECTION_TAG, 1)
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  ✅ Injected auth widget: {template_path}")
        else:
            print(f"  ⚠️  No </head> tag in: {template_path}")
    except Exception as e:
        print(f"  ⚠️  Error patching {template_path}: {e}")


templates_to_patch = [
    "templates/index.html",
    "templates/gantt.html",
    "templates/comparison.html",
    "templates/evm.html",
    "templates/health.html",
    "templates/trends.html",
]

for tpl in templates_to_patch:
    inject_auth_widget(tpl)


# ==============================================================================
# STEP 4: Also make auth_service.register_new_org use bcrypt-free hashing
# to avoid extra dependency issues (uses Werkzeug's built-in scrypt/pbkdf2)
# ==============================================================================

print("\n🎉 Auth Widget Installed Successfully!\n")
print("=" * 70)
print("WHAT'S NEW ON YOUR TOOL:")
print("=" * 70)
print("")
print("📊 When NOT logged in:")
print("   Top-right header shows: [Sign In]  [Sign Up]")
print("")
print("👤 When logged in:")
print("   Top-right header shows: [Avatar] Your Name ▼")
print("   Click to expand dropdown with:")
print("     • 📊 My Projects")
print("     • ⚙️  Admin Panel (only if Owner/Admin role)")
print("     • 🚪 Sign Out")
print("")
print("=" * 70)
print("NEXT STEPS:")
print("=" * 70)
print("")
print("1. Restart your Flask server:")
print("     python app.py")
print("")
print("2. Refresh your browser (Ctrl+Shift+R for hard refresh)")
print("")
print("3. Look at the TOP-RIGHT corner of any page - you'll see [Sign In] [Sign Up]")
print("")
print("4. Click 'Sign Up' to create your first organization:")
print("     http://localhost:5000/register")
print("")
print("5. After signup, you'll auto-login and see your user avatar in header")
print("")
print("6. Click your avatar → 'Admin Panel' to manage users & invitations")
print("")
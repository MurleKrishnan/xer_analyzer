/*
    ACTIVITY INSPECTOR DRAWER (v2 - Enhanced)
    ==========================================
    Global slide-out drawer with:
    - Multi-strategy click detection (data-attr, class, text-based)
    - DataTables re-render support (via MutationObserver)
    - Console diagnostics for debugging
    - Recursive drill-down into pred/succ
*/

(function () {
    'use strict';

    console.log('%c[Activity Inspector] Initializing v2...', 'color: #3b82f6; font-weight: bold;');

    let drawer = null;
    let drawerBody = null;
    let drawerTitle = null;
    let overlay = null;
    let currentCode = null;
    let clickCount = 0;

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

    function fmtNum(v) {
        const n = Number(v);
        if (!Number.isFinite(n)) return '—';
        return n.toLocaleString('en-US', { maximumFractionDigits: 1 });
    }

    function fmtMoney(v) {
        const n = Number(v);
        if (!Number.isFinite(n) || n === 0) return '—';
        return '$' + Math.round(n).toLocaleString('en-US');
    }

    function fmtDate(v) {
        if (!v) return '—';
        return esc(v);
    }

    // ═══════════════════════════════════════════
    // BUILD DRAWER DOM
    // ═══════════════════════════════════════════

    function buildDrawer() {
        if (drawer) return;
        console.log('[Activity Inspector] Building drawer DOM...');

        overlay = document.createElement('div');
        overlay.className = 'ai-drawer-overlay';
        overlay.addEventListener('click', closeDrawer);
        document.body.appendChild(overlay);

        drawer = document.createElement('div');
        drawer.className = 'ai-drawer';
        drawer.setAttribute('role', 'dialog');
        drawer.setAttribute('aria-labelledby', 'ai-drawer-title');

        drawer.innerHTML =
            '<div class="ai-drawer-header">' +
            '<div style="flex:1;min-width:0;">' +
            '<div id="ai-drawer-title" class="ai-drawer-title">Activity Inspector</div>' +
            '<div id="ai-drawer-subtitle" class="ai-drawer-subtitle">Loading…</div>' +
            '</div>' +
            '<div class="ai-drawer-actions">' +
            '<button class="ai-drawer-btn" onclick="window.__aiCopyCode()" title="Copy Activity Code">📋</button>' +
            '<button class="ai-drawer-btn ai-drawer-close" onclick="window.__aiCloseDrawer()" title="Close (ESC)">✕</button>' +
            '</div>' +
            '</div>' +
            '<div id="ai-drawer-body" class="ai-drawer-body">' +
            '<div class="ai-loading">⏳ Loading activity details…</div>' +
            '</div>';

        document.body.appendChild(drawer);
        drawerBody = document.getElementById('ai-drawer-body');
        drawerTitle = document.getElementById('ai-drawer-title');
        console.log('[Activity Inspector] Drawer DOM ready.');
    }

    // ═══════════════════════════════════════════
    // OPEN / CLOSE
    // ═══════════════════════════════════════════

    async function openDrawer(activityCode) {
        if (!activityCode) {
            console.warn('[Activity Inspector] openDrawer called with empty code');
            return;
        }
        console.log('%c[Activity Inspector] Opening for code: ' + activityCode, 'color: #10b981; font-weight: bold;');

        buildDrawer();
        currentCode = activityCode;
        drawer.classList.add('ai-drawer-open');
        overlay.classList.add('ai-drawer-open');
        document.body.style.overflow = 'hidden';

        drawerTitle.textContent = 'Activity Inspector';
        document.getElementById('ai-drawer-subtitle').textContent = 'Loading ' + activityCode + '…';
        drawerBody.innerHTML = '<div class="ai-loading">⏳ Loading activity details…</div>';

        try {
            const url = '/api/activity-detail/' + encodeURIComponent(activityCode);
            console.log('[Activity Inspector] Fetching:', url);
            const res = await fetch(url);
            const payload = await res.json().catch(function () { return {}; });

            if (!res.ok || payload.error) {
                throw new Error(payload.error || 'Failed to load activity (' + res.status + ')');
            }

            renderDrawerContent(payload.data);
            console.log('[Activity Inspector] ✅ Loaded successfully');
        } catch (err) {
            console.error('[Activity Inspector] ❌ Error:', err);
            drawerBody.innerHTML =
                '<div class="ai-error">' +
                '<div style="font-size:2rem;">❌</div>' +
                '<p><strong>Failed to load activity ' + esc(activityCode) + '</strong></p>' +
                '<p style="color:#64748b;">' + esc(err.message || 'Unknown error') + '</p>' +
                '<p style="color:#64748b;font-size:0.8rem;margin-top:1rem;">Check the browser console for details.</p>' +
                '</div>';
        }
    }

    function closeDrawer() {
        if (!drawer) return;
        drawer.classList.remove('ai-drawer-open');
        overlay.classList.remove('ai-drawer-open');
        document.body.style.overflow = '';
        currentCode = null;
    }

    window.__aiCloseDrawer = closeDrawer;
    window.__aiOpenActivity = openDrawer;

    window.__aiCopyCode = function () {
        if (!currentCode) return;
        if (navigator.clipboard) {
            navigator.clipboard.writeText(currentCode).then(function () {
                showToast('📋 Copied: ' + currentCode);
            });
        }
    };

    function showToast(msg) {
        const toast = document.createElement('div');
        toast.className = 'ai-toast';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(function () { toast.classList.add('show'); }, 10);
        setTimeout(function () {
            toast.classList.remove('show');
            setTimeout(function () { toast.remove(); }, 300);
        }, 2000);
    }

    // ═══════════════════════════════════════════
    // RENDER CONTENT
    // ═══════════════════════════════════════════

    function renderDrawerContent(data) {
        if (!data) {
            drawerBody.innerHTML = '<div class="ai-error">No data returned</div>';
            return;
        }

        const id = data.identity || {};
        const dates = data.dates || {};
        const dur = data.duration || {};
        const flt = data.float || {};
        const preds = data.predecessors || [];
        const succs = data.successors || [];
        const resources = data.resources || [];
        const cstr = data.constraints || {};
        const violations = data.health_violations || [];

        drawerTitle.innerHTML = '<span class="ai-code-chip">' + esc(id.code) + '</span> <span style="font-weight:600;">' + esc(id.name) + '</span>';
        document.getElementById('ai-drawer-subtitle').innerHTML =
            esc(id.type) + ' &middot; ' + esc(id.status) +
            (id.wbs_name ? ' &middot; WBS: ' + esc(id.wbs_name) : '');

        let html = '';

        // Status badges
        html += '<div class="ai-badges">';
        if (flt.is_longest_path) html += '<span class="ai-badge lp">🎯 Longest Path</span>';
        if (flt.is_critical) html += '<span class="ai-badge critical">🔴 Critical</span>';
        if (flt.is_negative_float) html += '<span class="ai-badge danger">⚠️ Negative Float</span>';
        if (id.status === 'Completed') html += '<span class="ai-badge success">✅ Completed</span>';
        else if (id.status === 'In Progress') html += '<span class="ai-badge warning">🔄 In Progress</span>';
        else html += '<span class="ai-badge muted">📋 ' + esc(id.status) + '</span>';
        html += '</div>';

        if (violations.length) {
            html += '<div class="ai-section">' +
                '<div class="ai-section-title">⚠️ Health Violations (' + violations.length + ')</div>' +
                '<div class="ai-violations">';
            violations.forEach(function (v) {
                const sevClass = 'sev-' + esc((v.severity || 'low').toLowerCase());
                html += '<div class="ai-violation ' + sevClass + '">' +
                    '<span class="ai-violation-badge">' + esc(v.id) + '</span>' +
                    '<span class="ai-violation-name">' + esc(v.name) + '</span>' +
                    (v.value ? '<span class="ai-violation-value">' + esc(v.value) + '</span>' : '') +
                    '</div>';
            });
            html += '</div></div>';
        }

        html += '<div class="ai-section"><div class="ai-section-title">⏱ Duration & Float</div>' +
            '<div class="ai-kv-grid">' +
            kvRow('Original Duration', fmtNum(dur.original_days) + 'd') +
            kvRow('Remaining Duration', fmtNum(dur.remaining_days) + 'd') +
            kvRow('Actual Duration', fmtNum(dur.actual_days) + 'd') +
            kvRow('% Complete', fmtNum(id.phys_complete_pct) + '%') +
            kvRow('Total Float', fmtNum(flt.total_float_days) + 'd', flt.is_negative_float ? 'danger' : (flt.is_critical ? 'warning' : '')) +
            kvRow('Free Float', fmtNum(flt.free_float_days) + 'd') +
            '</div></div>';

        html += '<div class="ai-section"><div class="ai-section-title">📅 Dates</div>' +
            '<div class="ai-kv-grid">' +
            kvRow('Early Start', fmtDate(dates.early_start)) +
            kvRow('Early Finish', fmtDate(dates.early_finish)) +
            kvRow('Late Start', fmtDate(dates.late_start)) +
            kvRow('Late Finish', fmtDate(dates.late_finish)) +
            kvRow('Actual Start', fmtDate(dates.actual_start)) +
            kvRow('Actual Finish', fmtDate(dates.actual_finish)) +
            kvRow('Target Start', fmtDate(dates.target_start)) +
            kvRow('Target Finish', fmtDate(dates.target_finish)) +
            '</div></div>';

        if (cstr.primary_type || cstr.secondary_type) {
            html += '<div class="ai-section"><div class="ai-section-title">📌 Constraints</div>' +
                '<div class="ai-kv-grid">';
            if (cstr.primary_type) {
                html += kvRow('Primary', esc(cstr.primary_type) + (cstr.primary_date ? ' (' + esc(cstr.primary_date) + ')' : ''));
            }
            if (cstr.secondary_type) {
                html += kvRow('Secondary', esc(cstr.secondary_type) + (cstr.secondary_date ? ' (' + esc(cstr.secondary_date) + ')' : ''));
            }
            html += '</div></div>';
        }

        html += '<div class="ai-section">' +
            '<div class="ai-section-title">🔗 Predecessors (' + preds.length + ')</div>';
        if (!preds.length) {
            html += '<div class="ai-empty">No predecessors</div>';
        } else {
            html += '<div class="ai-rel-list">';
            preds.forEach(function (p) {
                html += '<div class="ai-rel-item' + (p.is_critical ? ' critical' : '') + '" data-activity-code="' + esc(p.code) + '">' +
                    '<span class="ai-rel-code">' + esc(p.code) + '</span>' +
                    '<span class="ai-rel-name">' + esc(p.name) + '</span>' +
                    '<span class="ai-rel-tag">' + esc(p.type) + (p.lag_days !== 0 ? ' ' + (p.lag_days > 0 ? '+' : '') + p.lag_days + 'd' : '') + '</span>' +
                    '</div>';
            });
            html += '</div>';
        }
        html += '</div>';

        html += '<div class="ai-section">' +
            '<div class="ai-section-title">➡️ Successors (' + succs.length + ')</div>';
        if (!succs.length) {
            html += '<div class="ai-empty">No successors</div>';
        } else {
            html += '<div class="ai-rel-list">';
            succs.forEach(function (s) {
                html += '<div class="ai-rel-item' + (s.is_critical ? ' critical' : '') + '" data-activity-code="' + esc(s.code) + '">' +
                    '<span class="ai-rel-code">' + esc(s.code) + '</span>' +
                    '<span class="ai-rel-name">' + esc(s.name) + '</span>' +
                    '<span class="ai-rel-tag">' + esc(s.type) + (s.lag_days !== 0 ? ' ' + (s.lag_days > 0 ? '+' : '') + s.lag_days + 'd' : '') + '</span>' +
                    '</div>';
            });
            html += '</div>';
        }
        html += '</div>';

        if (resources.length) {
            html += '<div class="ai-section">' +
                '<div class="ai-section-title">👷 Resources (' + resources.length + ')</div>' +
                '<div class="ai-resource-list">';
            resources.forEach(function (r) {
                html += '<div class="ai-resource-item">' +
                    '<div class="ai-resource-name">' + esc(r.name) + '</div>' +
                    '<div class="ai-resource-metrics">' +
                    '<span>📊 ' + fmtNum(r.planned_units) + ' hrs planned</span>' +
                    (r.actual_units > 0 ? '<span>✅ ' + fmtNum(r.actual_units) + ' hrs actual</span>' : '') +
                    (r.planned_cost > 0 ? '<span>💰 ' + fmtMoney(r.planned_cost) + ' planned</span>' : '') +
                    (r.actual_cost > 0 ? '<span>💵 ' + fmtMoney(r.actual_cost) + ' actual</span>' : '') +
                    '</div>' +
                    '</div>';
            });
            html += '</div></div>';
        }

        html += '<div class="ai-section"><div class="ai-section-title">🧭 Metadata</div>' +
            '<div class="ai-kv-grid">' +
            kvRow('Calendar', esc(id.calendar)) +
            kvRow('WBS Code', esc(id.wbs_code)) +
            kvRow('WBS Name', esc(id.wbs_name)) +
            kvRow('Activity Type', esc(id.type)) +
            '</div></div>';

        drawerBody.innerHTML = html;
    }

    function kvRow(label, value, cls) {
        return '<div class="ai-kv-row' + (cls ? ' ' + cls : '') + '">' +
            '<div class="ai-kv-label">' + label + '</div>' +
            '<div class="ai-kv-value">' + value + '</div>' +
            '</div>';
    }

    // ═══════════════════════════════════════════
    // MULTI-STRATEGY CLICK DETECTION
    // ═══════════════════════════════════════════

    function extractActivityCode(target) {
        // Strategy 1: Explicit data-activity-code attribute
        let el = target;
        while (el && el !== document.body) {
            if (el.dataset && el.dataset.activityCode) {
                return el.dataset.activityCode;
            }
            el = el.parentElement;
        }

        // Strategy 2: CSS class marker
        el = target;
        while (el && el !== document.body) {
            if (el.classList && el.classList.contains('activity-inspect-link')) {
                return el.textContent.trim();
            }
            el = el.parentElement;
        }

        // Strategy 3: First-column <strong> inside a data table row (DataTables-friendly)
        el = target;
        while (el && el !== document.body) {
            if (el.tagName === 'TD' && el.cellIndex === 0) {
                const strong = el.querySelector('strong');
                if (strong) {
                    const txt = strong.textContent.trim();
                    // Heuristic: only trigger if looks like an activity code (alphanumeric, 3-30 chars, no spaces)
                    if (txt && txt.length >= 2 && txt.length <= 40 && /^[A-Za-z0-9._-]+$/.test(txt)) {
                        return txt;
                    }
                }
            }
            if (el.tagName === 'TR') break;
            el = el.parentElement;
        }

        return null;
    }

    // Global click delegation
    document.addEventListener('click', function (e) {
        const code = extractActivityCode(e.target);
        if (code) {
            clickCount++;
            console.log('[Activity Inspector] Click #' + clickCount + ' detected code: "' + code + '"');
            e.preventDefault();
            e.stopPropagation();
            openDrawer(code);
        }
    }, true);  // Capture phase for early interception

    // ESC to close
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && drawer && drawer.classList.contains('ai-drawer-open')) {
            closeDrawer();
        }
    });

    // ═══════════════════════════════════════════
    // MUTATION OBSERVER for DataTables re-renders
    // ═══════════════════════════════════════════
    // Auto-inject data-activity-code onto <strong> tags in first columns
    // of any dynamically-rendered table rows

    function markActivityCells(root) {
        if (!root || !root.querySelectorAll) return;
        const rows = root.querySelectorAll('tr');
        let count = 0;
        rows.forEach(function (tr) {
            const firstCell = tr.querySelector('td:first-child');
            if (!firstCell) return;
            const strong = firstCell.querySelector('strong');
            if (!strong) return;
            if (strong.dataset.activityCode) return; // Already tagged
            const txt = strong.textContent.trim();
            if (txt && txt.length >= 2 && txt.length <= 40 && /^[A-Za-z0-9._-]+$/.test(txt)) {
                strong.dataset.activityCode = txt;
                strong.style.cursor = 'pointer';
                strong.title = 'Click to inspect activity ' + txt;
                count++;
            }
        });
        if (count > 0) {
            console.log('[Activity Inspector] Auto-tagged ' + count + ' activity codes');
        }
    }

    // Initial scan
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            markActivityCells(document.body);
            startObserver();
        });
    } else {
        markActivityCells(document.body);
        startObserver();
    }

    function startObserver() {
        const observer = new MutationObserver(function (mutations) {
            mutations.forEach(function (mut) {
                mut.addedNodes.forEach(function (node) {
                    if (node.nodeType === 1) {
                        markActivityCells(node);
                    }
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
        console.log('[Activity Inspector] Mutation observer started');
    }

    // Diagnostic helpers on window
    window.__aiDiagnostics = function () {
        console.group('%c[Activity Inspector] Diagnostics', 'color: #f59e0b; font-weight: bold;');
        console.log('Click count so far:', clickCount);
        console.log('Drawer built:', !!drawer);
        console.log('Drawer open:', drawer && drawer.classList.contains('ai-drawer-open'));

        const tagged = document.querySelectorAll('[data-activity-code]');
        console.log('Elements with data-activity-code:', tagged.length);
        if (tagged.length > 0) {
            console.log('Sample codes:', Array.from(tagged).slice(0, 5).map(function (el) { return el.dataset.activityCode; }));
        }

        const tables = document.querySelectorAll('table');
        console.log('Tables on page:', tables.length);

        const rows = document.querySelectorAll('tbody tr');
        console.log('Table rows on page:', rows.length);
        console.groupEnd();
        console.log('%cTo manually open a drawer: window.__aiOpenActivity("A1000")', 'color: #10b981;');
    };

    console.log('%c[Activity Inspector] ✅ Ready. Type window.__aiDiagnostics() in console for debug info.', 'color: #10b981; font-weight: bold;');
})();

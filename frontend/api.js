/**
 * CatalogIQ - Enterprise Product Intelligence API & Auth Client
 * Shared async fetch wrappers, session auth, alert management, and formatting utilities.
 */

// Automatically detect backend API host
const API_BASE = window.API_BASE_URL || (
  window.location.port === '8000' 
    ? window.location.origin 
    : 'http://localhost:8000'
);

const API = {
  /**
   * GET /api/dashboard - High-level metrics, health distribution, and top opportunities
   */
  async getDashboard() {
    const res = await fetch(`${API_BASE}/api/dashboard`);
    if (!res.ok) {
      throw new Error(`Dashboard fetch failed: HTTP ${res.status}`);
    }
    return await res.json();
  },

  /**
   * GET /api/searches - List search queries with optional filters
   */
  async getSearches(params = {}) {
    const query = new URLSearchParams();
    if (params.root_cause) query.set('root_cause', params.root_cause);
    if (params.min_opportunity_score != null) query.set('min_opportunity_score', params.min_opportunity_score);
    if (params.sort_by) query.set('sort_by', params.sort_by);
    if (params.order) query.set('order', params.order);

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/searches${qs}`);
    if (!res.ok) {
      throw new Error(`Searches fetch failed: HTTP ${res.status}`);
    }
    return await res.json();
  },

  /**
   * GET /api/searches/{query_id} - Deep dive diagnostics for a single search query
   */
  async getSearchDetail(queryId) {
    const res = await fetch(`${API_BASE}/api/searches/${encodeURIComponent(queryId)}`);
    if (!res.ok) {
      throw new Error(`Search detail fetch failed for '${queryId}': HTTP ${res.status}`);
    }
    return await res.json();
  },

  /**
   * GET /api/opportunities - Ranked opportunities list
   */
  async getOpportunities() {
    const res = await fetch(`${API_BASE}/api/opportunities`);
    if (!res.ok) {
      throw new Error(`Opportunities fetch failed: HTTP ${res.status}`);
    }
    return await res.json();
  },

  /**
   * GET /api/products - List products with optional search query and filters
   */
  async getProducts(params = {}) {
    const query = new URLSearchParams();
    if (params.q) query.set('q', params.q);
    if (params.category) query.set('category', params.category);
    if (params.gender) query.set('gender', params.gender);
    if (params.health_classification) query.set('health_classification', params.health_classification);
    if (params.page != null) query.set('page', params.page);
    if (params.page_size != null) query.set('page_size', params.page_size);

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await fetch(`${API_BASE}/api/products${qs}`);
    if (!res.ok) {
      throw new Error(`Products fetch failed: HTTP ${res.status}`);
    }
    return await res.json();
  },

  /**
   * GET /api/products/{product_id} - Single product health audit and breakdown
   */
  async getProduct(productId) {
    const res = await fetch(`${API_BASE}/api/products/${encodeURIComponent(productId)}`);
    if (!res.ok) {
      throw new Error(`Product fetch failed for '${productId}': HTTP ${res.status}`);
    }
    return await res.json();
  },

  /**
   * POST /api/explain - Plain-language executive explanation (LLM or fallback)
   */
  async explain(queryId, queryData = null) {
    const payload = {};
    if (queryId) payload.query_id = queryId;
    if (queryData) payload.query_data = queryData;

    const res = await fetch(`${API_BASE}/api/explain`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      throw new Error(`Explanation request failed: HTTP ${res.status}`);
    }
    return await res.json();
  }
};

// =========================================================================
// AUTHENTICATION & SESSION MANAGEMENT
// =========================================================================
// AUTHENTICATION & SESSION MANAGEMENT
// =========================================================================
const Auth = {
  SESSION_KEY: 'catalogiq_session',

  async login(email, password) {
    const normalizedEmail = (email || '').trim().toLowerCase();
    const cleanPassword = (password || '').trim();

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail, password: cleanPassword })
      });

      if (res.ok) {
        const data = await res.json();
        const user = {
          user_id: data.user.user_id,
          name: data.user.name,
          role: data.user.role || 'Catalog Specialist',
          organization: data.user.organization || 'CatalogIQ',
          email: data.user.email,
          is_admin: data.user.is_admin,
          loginTime: new Date().toISOString()
        };
        localStorage.setItem(this.SESSION_KEY, JSON.stringify(user));
        return { success: true, user };
      }

      const errData = await res.json().catch(() => ({}));
      return { success: false, error: errData.detail || 'Invalid email or password.' };
    } catch (networkErr) {
      // Fallback for offline/static demo environment
      if (normalizedEmail === 'admin@catalogiq.demo' && cleanPassword === 'catalogiq123') {
        const user = {
          user_id: 'admin-01',
          name: 'Adarsh',
          role: 'Catalog Manager',
          email: 'admin@catalogiq.demo',
          organization: 'CatalogIQ',
          is_admin: true,
          loginTime: new Date().toISOString()
        };
        localStorage.setItem(this.SESSION_KEY, JSON.stringify(user));
        return { success: true, user };
      }
      return { success: false, error: 'Invalid email or password.' };
    }
  },

  async requestAccess(payload) {
    const res = await fetch(`${API_BASE}/api/access-requests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to submit access request.');
    }
    return await res.json();
  },

  getUser() {
    try {
      const raw = localStorage.getItem(this.SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  },

  isAuthenticated() {
    return this.getUser() !== null;
  },

  logout() {
    localStorage.removeItem(this.SESSION_KEY);
    window.location.href = 'login.html';
  },

  requireAuth() {
    if (!this.isAuthenticated()) {
      const currentPath = window.location.pathname.split('/').pop() || 'dashboard.html';
      const search = window.location.search;
      const target = currentPath + search;
      if (currentPath !== 'login.html') {
        window.location.href = `login.html?redirect=${encodeURIComponent(target)}`;
      }
    }
  },

  renderUserBadge(containerId = 'user-account-badge') {
    const user = this.getUser() || { name: 'Adarsh', role: 'Catalog Manager' };
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
      <div class="flex items-center gap-3">
        <div class="hidden sm:flex flex-col text-right">
          <span class="text-xs font-bold text-slate-900 tracking-tight font-display">${user.name}</span>
          <span class="text-[10px] font-mono text-slate-500">${user.role}</span>
        </div>
        <div class="w-8 h-8 rounded-full bg-[#101827] text-white flex items-center justify-center font-bold text-xs font-display shadow-2xs border border-slate-700">
          ${user.name.charAt(0)}
        </div>
        <button onclick="CatalogIQ_Auth.logout()" 
                class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-[#E83E4F] hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-all font-sans" 
                title="Sign out of CatalogIQ">
          <span class="material-symbols-outlined text-[16px]">logout</span>
          <span class="hidden md:inline">Logout</span>
        </button>
      </div>
    `;
  }
};

// =========================================================================
// SEARCH PRIORITY THRESHOLDS & SCORING RULES
// =========================================================================
const Priority = {
  /**
   * Calculate search alert priority from Opportunity Score
   * >= 90 -> Critical
   * >= 80 -> High Priority
   * < 80  -> Normal
   */
  fromScore(score) {
    const val = Number(score) || 0;
    if (val >= 90) {
      return {
        level: 'CRITICAL',
        label: 'Critical',
        badgeClass: 'bg-rose-100 text-rose-900 border border-rose-300 font-bold',
        pillClass: 'bg-rose-50 text-rose-800 border-rose-200',
        dotColor: 'bg-rose-600',
        isHighPriority: true,
        isCritical: true
      };
    }
    if (val >= 80) {
      return {
        level: 'HIGH_PRIORITY',
        label: 'High Priority',
        badgeClass: 'bg-amber-100 text-amber-900 border border-amber-300 font-semibold',
        pillClass: 'bg-amber-50 text-amber-900 border-amber-200',
        dotColor: 'bg-amber-500',
        isHighPriority: true,
        isCritical: false
      };
    }
    return {
      level: 'NORMAL',
      label: 'Normal',
      badgeClass: 'bg-slate-100 text-slate-700 border border-slate-200',
      pillClass: 'bg-slate-50 text-slate-700 border-slate-200',
      dotColor: 'bg-slate-400',
      isHighPriority: false,
      isCritical: false
    };
  }
};

// =========================================================================
// HIGH-PRIORITY EMAIL ALERTS & HISTORY MANAGEMENT
// =========================================================================
const Alerts = {
  HISTORY_KEY: 'catalogiq_alert_history',

  getHistory() {
    try {
      const raw = localStorage.getItem(this.HISTORY_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  },

  sendCatalogAlert(alertData, recipient) {
    const cleanRecipient = (recipient || '').trim();
    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(cleanRecipient)) {
      return {
        success: false,
        error: 'Please enter a valid recipient email address.'
      };
    }

    const priorityInfo = Priority.fromScore(alertData.opportunity_score);
    const dateFormatted = new Date().toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });

    const alertRecord = {
      id: 'ALT-' + Date.now(),
      date: dateFormatted,
      timestamp: new Date().toISOString(),
      query: alertData.query,
      query_id: alertData.query_id || '',
      priority: priorityInfo.label,
      opportunity_score: Number(alertData.opportunity_score).toFixed(1),
      search_volume: alertData.search_volume || 0,
      coverage: alertData.coverage != null ? alertData.coverage : '0%',
      root_cause: alertData.root_cause || 'Attribute Gap',
      affected_products: alertData.affected_products || 0,
      recipient: cleanRecipient,
      status: 'Queued',
      subject: `CatalogIQ Alert: High-Priority Search — ${alertData.query}`,
      body: `CatalogIQ has identified a high-priority catalog issue.\n\nSearch:\n${alertData.query}\n\nOpportunity Score:\n${Number(alertData.opportunity_score).toFixed(1)}\n\nSearch Volume:\n${Number(alertData.search_volume).toLocaleString()}\n\nCoverage:\n${alertData.coverage}\n\nRoot Cause:\n${alertData.root_cause}\n\nAffected Products:\n${alertData.affected_products}\n\nRecommended Action:\n${alertData.recommended_action || 'Review and enrich the affected product attributes to improve search eligibility.'}`
    };

    const history = this.getHistory();
    history.unshift(alertRecord);
    localStorage.setItem(this.HISTORY_KEY, JSON.stringify(history));

    return {
      success: true,
      message: 'Alert queued successfully',
      record: alertRecord
    };
  }
};

// =========================================================================
// FORMATTING UTILITIES
// =========================================================================
const Format = {
  number(n) {
    if (n == null || isNaN(n)) return '0';
    return Number(n).toLocaleString();
  },
  compactNumber(n) {
    if (n == null || isNaN(n)) return '0';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return n.toString();
  },
  percent(val, decimals = 1) {
    if (val == null || isNaN(val)) return '0%';
    const pct = val <= 1.0 && val >= 0 ? val * 100 : val;
    return `${pct.toFixed(decimals)}%`;
  },
  rootCauseLabel(rc) {
    if (rc === 'ATTRIBUTE_GAP') return 'Attribute Gap';
    if (rc === 'INVENTORY_GAP') return 'Inventory Gap';
    if (rc === 'NO_CATALOG_GAP_DETECTED') return 'No Gap Detected';
    return rc || 'Unknown';
  },
  rootCauseBadgeClasses(rc) {
    if (rc === 'ATTRIBUTE_GAP') {
      return 'bg-rose-50 text-rose-800 border border-rose-200/80';
    }
    if (rc === 'INVENTORY_GAP') {
      return 'bg-amber-50 text-amber-900 border border-amber-200/80';
    }
    return 'bg-emerald-50 text-emerald-800 border border-emerald-200/80';
  },
  healthTierBadgeClasses(tier) {
    if (tier === 'Critical') {
      return 'bg-rose-50 text-rose-800 border border-rose-200/80';
    }
    if (tier === 'Needs Attention') {
      return 'bg-amber-50 text-amber-900 border border-amber-200/80';
    }
    if (tier === 'Good') {
      return 'bg-blue-50 text-blue-800 border border-blue-200/80';
    }
    return 'bg-emerald-50 text-emerald-800 border border-emerald-200/80';
  },
  scoreColor(score) {
    if (score >= 80) return 'text-rose-600';
    if (score >= 60) return 'text-amber-600';
    return 'text-slate-600';
  }
};

window.CatalogIQ_API = API;
window.CatalogIQ_Auth = Auth;
window.CatalogIQ_Priority = Priority;
window.CatalogIQ_Alerts = Alerts;
window.CatalogIQ_Format = Format;

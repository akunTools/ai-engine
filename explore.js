// explore.js — Content Exploration System with Progressive Enhancement
(function() {
  'use strict';

  // ============================================================
  // CONFIGURATION
  // ============================================================
  const DEFAULT_CONFIG = {
    type: 'all',
    itemsPerPage: 20,
    cacheKey: 'explore_cache',
    cacheTTL: 5 * 60 * 1000,
    debounceDelay: 300,
  };

  // ============================================================
  // STATE
  // ============================================================
  let state = {
    q: '',
    cluster: 'all',
    type: 'all',
    sort: 'newest',
    page: 1,
  };

  let allData = { articles: [], tools: [] };
  let filteredData = [];
  let totalPages = 1;
  let config = {};

  // ============================================================
  // DOM REFS
  // ============================================================
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ============================================================
  // UTILITY FUNCTIONS
  // ============================================================
  function debounce(fn, delay) {
    let timer;
    return function(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function getQueryParams() {
    const params = new URLSearchParams(window.location.search);
    return {
      q: params.get('q') || '',
      cluster: params.get('cluster') || 'all',
      type: params.get('type') || 'all',
      sort: params.get('sort') || 'newest',
      page: parseInt(params.get('page'), 10) || 1,
    };
  }

  function updateURL(state) {
    const params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.cluster !== 'all') params.set('cluster', state.cluster);
    if (state.type !== 'all') params.set('type', state.type);
    if (state.sort !== 'newest') params.set('sort', state.sort);
    if (state.page > 1) params.set('page', state.page);
    const newUrl = window.location.pathname + '?' + params.toString();
    history.pushState(state, '', newUrl);
  }

  function savePreference(key, value) {
    try {
      const prefs = JSON.parse(localStorage.getItem('explore_prefs') || '{}');
      prefs[key] = value;
      localStorage.setItem('explore_prefs', JSON.stringify(prefs));
    } catch (_) {}
  }

  function loadPreference(key, fallback) {
    try {
      const prefs = JSON.parse(localStorage.getItem('explore_prefs') || '{}');
      return prefs[key] !== undefined ? prefs[key] : fallback;
    } catch (_) { return fallback; }
  }

  // ============================================================
  // DATA FETCHING & CACHING
  // ============================================================
  async function fetchData() {
    try {
      const cached = localStorage.getItem(config.cacheKey);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        if (Date.now() - timestamp < config.cacheTTL) {
          return data;
        }
      }
    } catch (_) {}

    const response = await fetch('/content-index.json?_=' + Date.now());
    if (!response.ok) throw new Error('Failed to fetch content data.');
    const data = await response.json();

    try {
      localStorage.setItem(config.cacheKey, JSON.stringify({
        data: data,
        timestamp: Date.now(),
      }));
    } catch (_) {}

    return data;
  }

  // ============================================================
  // FILTERING, SORTING, PAGINATION
  // ============================================================
  function getClusters(data) {
    const clusters = new Set();
    data.articles.forEach(a => { if (a.cluster) clusters.add(a.cluster); });
    data.tools.forEach(t => { if (t.cluster) clusters.add(t.cluster); });
    return Array.from(clusters).sort();
  }

  function filterData(data, state) {
    let items = [];
    if (state.type === 'all' || state.type === 'articles') {
      items = items.concat(data.articles.map(a => ({ ...a, _type: 'article' })));
    }
    if (state.type === 'all' || state.type === 'tools') {
      items = items.concat(data.tools.map(t => ({ ...t, _type: 'tool' })));
    }

    if (state.cluster !== 'all') {
      items = items.filter(item => item.cluster === state.cluster);
    }

    if (state.q.trim()) {
      const q = state.q.trim().toLowerCase();
      items = items.filter(item => {
        const title = (item.title || '').toLowerCase();
        const excerpt = (item.excerpt || '').toLowerCase();
        return title.includes(q) || excerpt.includes(q);
      });
    }

    switch (state.sort) {
      case 'newest':
        items.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
        break;
      case 'oldest':
        items.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
        break;
      case 'alpha':
        items.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
        break;
      case 'alpha-desc':
        items.sort((a, b) => (b.title || '').localeCompare(a.title || ''));
        break;
      default:
        break;
    }

    return items;
  }

  function paginate(items, page, perPage) {
    const start = (page - 1) * perPage;
    const end = start + perPage;
    return items.slice(start, end);
  }

  // ============================================================
  // RENDER
  // ============================================================
  function renderResults(items, totalItems, currentPage, perPage) {
    const container = document.getElementById('explore-results-dynamic');
    const info = document.getElementById('explore-info');
    const pagination = document.getElementById('explore-pagination');

    if (!container) return;

    if (info) {
      const start = totalItems > 0 ? (currentPage - 1) * perPage + 1 : 0;
      const end = Math.min(currentPage * perPage, totalItems);
      info.textContent = 'Showing ' + start + '–' + end + ' of ' + totalItems + ' results';
    }

    if (items.length === 0) {
      container.innerHTML = '<div style="text-align:center;padding:48px 0;color:var(--muted);"><p style="font-size:1.125rem;">No content found.</p><p style="font-size:0.9375rem;">Try changing your filters or search keywords.</p></div>';
    } else {
      let html = '';
      items.forEach(item => {
        const url = item._type === 'article' ? '/articles/' + item.slug : '/tools/' + item.slug;
        const icon = item._type === 'article' ? '📄' : '⚡';
        const typeLabel = item._type === 'article' ? 'Article' : 'Tool';
        const clusterLabel = item.cluster ? '<span style="font-size:0.75rem;color:var(--subtle);background:var(--border);padding:2px 8px;border-radius:4px;margin-left:8px;">' + item.cluster + '</span>' : '';

        html += '<a href="' + url + '" class="article-item" style="display:flex;align-items:flex-start;justify-content:space-between;gap:24px;padding:20px 0;border-bottom:1px solid var(--border);text-decoration:none;color:inherit;">';
        html += '<div style="display:flex;flex-direction:column;gap:6px;flex:1;min-width:0;">';
        html += '<span style="font-size:0.75rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">' + icon + ' ' + typeLabel + clusterLabel + '</span>';
        html += '<span style="font-size:1rem;font-weight:600;color:var(--text);line-height:1.4;">' + highlightText(item.title || item.slug, state.q) + '</span>';
        if (item.excerpt) {
          html += '<span style="font-size:0.875rem;color:var(--muted);line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + highlightText(item.excerpt, state.q) + '</span>';
        }
        html += '</div>';
        if (item.date) {
          html += '<span style="font-family:monospace;font-size:0.8125rem;color:var(--muted);white-space:nowrap;flex-shrink:0;padding-top:4px;">' + formatDate(item.date) + '</span>';
        }
        html += '</a>';
      });
      container.innerHTML = html;
    }

    if (pagination) {
      totalPages = Math.ceil(totalItems / perPage);
      renderPagination(pagination, currentPage, totalPages);
    }
  }

  function highlightText(text, query) {
    if (!query.trim()) return text;
    const q = query.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp('(' + q + ')', 'gi');
    return text.replace(regex, '<mark style="background:var(--accent-light);color:var(--text);padding:0 2px;border-radius:2px;">$1</mark>');
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (_) { return dateStr; }
  }

  function renderPagination(container, currentPage, totalPages) {
    if (totalPages <= 1) {
      container.innerHTML = '';
      return;
    }

    let html = '<div style="display:flex;gap:8px;justify-content:center;align-items:center;margin-top:32px;flex-wrap:wrap;">';

    html += '<button class="pagination-btn" data-page="' + (currentPage - 1) + '" ' + (currentPage <= 1 ? 'disabled' : '') + ' style="padding:8px 16px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--text);cursor:pointer;font-size:0.875rem;min-height:44px;' + (currentPage <= 1 ? 'opacity:0.5;pointer-events:none;' : '') + '">← Prev</button>';

    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage < maxVisible - 1) startPage = Math.max(1, endPage - maxVisible + 1);

    if (startPage > 1) {
      html += '<button class="pagination-btn" data-page="1" style="padding:8px 16px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--text);cursor:pointer;font-size:0.875rem;min-height:44px;">1</button>';
      if (startPage > 2) html += '<span style="padding:8px 8px;color:var(--muted);">…</span>';
    }

    for (let i = startPage; i <= endPage; i++) {
      const isActive = i === currentPage;
      html += '<button class="pagination-btn" data-page="' + i + '" style="padding:8px 16px;border:1px solid var(--border);border-radius:var(--r);background:' + (isActive ? 'var(--accent)' : 'var(--surface)') + ';color:' + (isActive ? '#fff' : 'var(--text)') + ';cursor:pointer;font-size:0.875rem;min-height:44px;font-weight:' + (isActive ? '700' : '400') + ';">' + i + '</button>';
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) html += '<span style="padding:8px 8px;color:var(--muted);">…</span>';
      html += '<button class="pagination-btn" data-page="' + totalPages + '" style="padding:8px 16px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--text);cursor:pointer;font-size:0.875rem;min-height:44px;">' + totalPages + '</button>';
    }

    html += '<button class="pagination-btn" data-page="' + (currentPage + 1) + '" ' + (currentPage >= totalPages ? 'disabled' : '') + ' style="padding:8px 16px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--text);cursor:pointer;font-size:0.875rem;min-height:44px;' + (currentPage >= totalPages ? 'opacity:0.5;pointer-events:none;' : '') + '">Next →</button>';

    html += '</div>';
    container.innerHTML = html;

    container.querySelectorAll('.pagination-btn').forEach(btn => {
      btn.addEventListener('click', function(e) {
        const page = parseInt(this.dataset.page, 10);
        if (!isNaN(page) && page >= 1 && page <= totalPages) {
          state.page = page;
          updateAndRender();
        }
      });
    });
  }

  // ============================================================
  // PROGRESSIVE ENHANCEMENT CORE
  // ============================================================
  function enableDynamicMode() {
    const staticContainer = document.getElementById('explore-results-static');
    const dynamicContainer = document.getElementById('explore-results-dynamic');
    const controls = document.querySelector('.explore-controls');

    if (staticContainer) staticContainer.style.display = 'none';
    if (dynamicContainer) dynamicContainer.style.display = 'block';
    if (controls) controls.style.display = 'flex';

    updateAndRender();
  }

  // ============================================================
  // UPDATE & RENDER CYCLE
  // ============================================================
  function updateAndRender() {
    filteredData = filterData(allData, state);
    const totalItems = filteredData.length;
    const paginated = paginate(filteredData, state.page, config.itemsPerPage);

    updateURL(state);
    renderResults(paginated, totalItems, state.page, config.itemsPerPage);
    updateFilterUI();

    savePreference('lastState', state);
  }

  // ============================================================
  // UI UPDATES
  // ============================================================
  function updateFilterUI() {
    const searchInput = document.getElementById('explore-search');
    if (searchInput && searchInput.value !== state.q) {
      searchInput.value = state.q;
    }

    const clusterSelect = document.getElementById('explore-cluster');
    if (clusterSelect) {
      clusterSelect.value = state.cluster;
    }

    const typeSelect = document.getElementById('explore-type');
    if (typeSelect) {
      typeSelect.value = state.type;
    }

    const sortSelect = document.getElementById('explore-sort');
    if (sortSelect) {
      sortSelect.value = state.sort;
    }

    const clearBtn = document.getElementById('explore-clear');
    if (clearBtn) {
      const hasFilters = state.q || state.cluster !== 'all' || state.type !== config.type || state.sort !== 'newest';
      clearBtn.style.display = hasFilters ? 'inline-flex' : 'none';
    }
  }

  // ============================================================
  // INIT
  // ============================================================
  async function init(scriptElement) {
    const configAttr = scriptElement.getAttribute('data-config');
    config = { ...DEFAULT_CONFIG };
    if (configAttr) {
      try {
        const userConfig = JSON.parse(configAttr);
        Object.assign(config, userConfig);
      } catch (_) {}
    }

    const urlState = getQueryParams();
    const savedPrefs = loadPreference('lastState', {});
    state = {
      q: urlState.q || savedPrefs.q || '',
      cluster: urlState.cluster || savedPrefs.cluster || 'all',
      type: urlState.type || savedPrefs.type || config.type,
      sort: urlState.sort || savedPrefs.sort || 'newest',
      page: urlState.page || savedPrefs.page || 1,
    };

    if (config.type !== 'all' && state.type === 'all') {
      state.type = config.type;
    }

    try {
      allData = await fetchData();
    } catch (err) {
      console.error('Failed to load data:', err);
      return;
    }

    const clusterSelect = document.getElementById('explore-cluster');
    if (clusterSelect) {
      const clusters = getClusters(allData);
      while (clusterSelect.options.length > 1) clusterSelect.remove(1);
      clusters.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        clusterSelect.appendChild(opt);
      });
      clusterSelect.value = state.cluster;
    }

    setupEventListeners();
    enableDynamicMode();
  }

  // ============================================================
  // EVENT LISTENERS
  // ============================================================
  function setupEventListeners() {
    const searchInput = document.getElementById('explore-search');
    if (searchInput) {
      const handler = debounce(function() {
        state.q = this.value.trim();
        state.page = 1;
        updateAndRender();
      }, config.debounceDelay);
      searchInput.addEventListener('input', handler);
      searchInput.addEventListener('search', function() {
        state.q = this.value.trim();
        state.page = 1;
        updateAndRender();
      });
    }

    const clusterSelect = document.getElementById('explore-cluster');
    if (clusterSelect) {
      clusterSelect.addEventListener('change', function() {
        state.cluster = this.value;
        state.page = 1;
        updateAndRender();
      });
    }

    const typeSelect = document.getElementById('explore-type');
    if (typeSelect) {
      typeSelect.addEventListener('change', function() {
        state.type = this.value;
        state.page = 1;
        updateAndRender();
      });
    }

    const sortSelect = document.getElementById('explore-sort');
    if (sortSelect) {
      sortSelect.addEventListener('change', function() {
        state.sort = this.value;
        state.page = 1;
        updateAndRender();
      });
    }

    const clearBtn = document.getElementById('explore-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function() {
        state.q = '';
        state.cluster = 'all';
        state.type = config.type;
        state.sort = 'newest';
        state.page = 1;
        updateAndRender();
      });
    }

    window.addEventListener('popstate', function(e) {
      if (e.state) {
        Object.assign(state, e.state);
        updateAndRender();
      } else {
        const urlState = getQueryParams();
        Object.assign(state, urlState);
        updateAndRender();
      }
    });
  }

  // ============================================================
  // START
  // ============================================================
  document.addEventListener('DOMContentLoaded', function() {
    const script = document.querySelector('script[data-explore]');
    if (script) {
      init(script);
    } else {
      console.warn('explore.js: No script with data-explore found.');
    }
  });

})();
/**
 * Vectra Frontend Dashboard Logic — app.js
 * Connects the UI to FastAPI endpoints, manages layout states, 
 * local storage logs, collection bookmarks, and custom theme assets.
 */

const API_BASE = window.location.origin;

// ── DOM References ───────────────────────────────────────────
const dropzone        = document.getElementById('dropzone');
const dropzoneIdle    = document.getElementById('dropzone-idle');
const dropzonePreview = document.getElementById('dropzone-preview');
const previewImg      = document.getElementById('preview-img');
const previewClear    = document.getElementById('preview-clear');
const fileInput       = document.getElementById('file-input');

const textModifier    = document.getElementById('text-modifier');
const filterCategory  = document.getElementById('filter-category');
const filterPrice     = document.getElementById('filter-price');
const priceDisplay    = document.getElementById('price-display');
const filterInstock   = document.getElementById('filter-instock');
const filterTopN      = document.getElementById('filter-topn');
const topnDisplay     = document.getElementById('topn-display');
const searchBtn       = document.getElementById('search-btn');

const statusDot       = document.getElementById('status-dot');
const statusText      = document.getElementById('status-text');

// Live Preview Panel
const previewStatusDot  = document.getElementById('preview-status-dot');
const previewWaiting    = document.getElementById('preview-waiting');
const previewReady      = document.getElementById('preview-ready');
const previewDone       = document.getElementById('preview-done');
const previewThumb      = document.getElementById('preview-thumb');
const previewDbCount    = document.getElementById('preview-db-count');
const metricRetrieved   = document.getElementById('metric-retrieved');
const metricReturned    = document.getElementById('metric-returned');
const metricLatency     = document.getElementById('metric-latency');
const metricFilters     = document.getElementById('metric-filters');

// Views inside Search Tab
const searchBuilderView = document.getElementById('search-builder-view');
const searchResultsView = document.getElementById('search-results-view');
const resultsLoading    = document.getElementById('results-loading');
const resultsError      = document.getElementById('results-error');
const resultsContainer  = document.getElementById('results-container');
const resultsGrid       = document.getElementById('results-grid');
const resultsMeta       = document.getElementById('results-meta');
const btnLoadMore       = document.getElementById('btn-load-more');
const btnBackSearch     = document.querySelectorAll('#btn-back-search');
const errorRetry        = document.getElementById('error-retry');
const errorTitle        = document.getElementById('error-title');
const errorDetail       = document.getElementById('error-detail');

// Breadcrumbs DOM
const breadcrumbImg     = document.getElementById('breadcrumb-query-img');
const breadcrumbText    = document.getElementById('breadcrumb-query-text');
const breadcrumbFilters = document.getElementById('breadcrumb-filters');
const resultsCountLabel = document.getElementById('results-count-label');

// Catalog DOM
const catalogGrid     = document.getElementById('catalog-grid');
const catalogCount    = document.getElementById('catalog-count');

// History DOM
const historyListContainer = document.getElementById('history-list');

// Collections DOM
const collectionsGridContainer = document.getElementById('collections-grid');

// Pipeline loading steps
const stepEmbed       = document.getElementById('step-embed');
const stepRetrieve    = document.getElementById('step-retrieve');
const stepRerank      = document.getElementById('step-rerank');

// ── State ─────────────────────────────────────────────────────
let uploadedFile = null;
let currentTab = 'search';
let activeSearchFilters = null;
let currentResults = [];
let topNRequested = 10;

// ── Init & Event Listeners ────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupTabNavigation();
  setupDragAndDrop();
  setupSlidersAndInputs();
  setupThemeSelection();
  checkHealth();
  loadCatalog();
  renderHistory();
  renderCollections();
  
  // Refresh health status every 30s
  setInterval(checkHealth, 30000);
});

// ── API Health Check ──────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      const data = await res.json();
      statusDot.className = 'status-dot online';
      statusText.textContent = `Online · ${data.products_indexed} products indexed`;
      // Update Live Preview DB count
      if (previewDbCount) previewDbCount.textContent = `${data.products_indexed} products`;
    } else {
      throw new Error('Non-OK response');
    }
  } catch {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'API offline';
  }
}

// ── Tab Management ────────────────────────────────────────────
function setupTabNavigation() {
  const menuItems = document.querySelectorAll('.menu-item');
  const tabPanes = document.querySelectorAll('.tab-pane');

  menuItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetTab = item.dataset.tab;
      switchTab(targetTab);
    });
  });
}

function switchTab(tabId) {
  currentTab = tabId;
  
  const menuItems = document.querySelectorAll('.menu-item');
  const tabPanes = document.querySelectorAll('.tab-pane');

  // Helper transition function
  const applyViewChanges = () => {
    menuItems.forEach(btn => {
      if (btn.dataset.tab === tabId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    tabPanes.forEach(pane => {
      if (pane.id === `tab-${tabId}`) {
        pane.classList.remove('hidden');
        pane.classList.add('active');
      } else {
        pane.classList.add('hidden');
        pane.classList.remove('active');
      }
    });

    // Populate data based on tab
    if (tabId === 'history') {
      renderHistory();
    } else if (tabId === 'collections') {
      renderCollections();
    } else if (tabId === 'catalog') {
      loadCatalog();
    }
  };

  // Modern browser View Transition if supported
  if (document.startViewTransition) {
    document.startViewTransition(applyViewChanges);
  } else {
    applyViewChanges();
  }
}

// ── Drag and Drop Upload ──────────────────────────────────────
function setupDragAndDrop() {
  dropzone.addEventListener('click', (e) => {
    if (e.target === previewClear || previewClear.contains(e.target)) return;
    if (!uploadedFile) fileInput.click();
  });

  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });

  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) setFile(file);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) setFile(fileInput.files[0]);
  });

  previewClear.addEventListener('click', (e) => {
    e.stopPropagation();
    clearFile();
  });
}

function setFile(file) {
  uploadedFile = file;
  const url = URL.createObjectURL(file);
  previewImg.src = url;
  dropzoneIdle.classList.add('hidden');
  dropzonePreview.classList.remove('hidden');
  searchBtn.disabled = false;
  updateLivePreview('ready', url);
}

function clearFile() {
  uploadedFile = null;
  previewImg.src = '';
  fileInput.value = '';
  dropzoneIdle.classList.remove('hidden');
  dropzonePreview.classList.add('hidden');
  searchBtn.disabled = true;
  updateLivePreview('waiting');
}

// ── Live Preview Panel ────────────────────────────────────────
function updateLivePreview(state, data) {
  previewWaiting.classList.add('hidden');
  previewReady.classList.add('hidden');
  previewDone.classList.add('hidden');

  if (state === 'waiting') {
    previewWaiting.classList.remove('hidden');
    previewStatusDot.className = 'preview-status-dot';
  } else if (state === 'ready') {
    previewReady.classList.remove('hidden');
    previewStatusDot.className = 'preview-status-dot ready';
    if (previewThumb && data) previewThumb.src = data;
  } else if (state === 'done') {
    previewDone.classList.remove('hidden');
    previewStatusDot.className = 'preview-status-dot done';
    metricRetrieved.textContent = data.total_retrieved;
    metricReturned.textContent  = data.total_returned;
    metricLatency.textContent   = `${data.retrieval_latency_ms.toFixed(1)}ms`;
    // Show which filters were applied
    const filterParts = [];
    if (data.filters_applied?.category)      filterParts.push(data.filters_applied.category);
    if (data.filters_applied?.in_stock_only) filterParts.push('In Stock');
    if (data.filters_applied?.text_modifier) filterParts.push('Text fusion');
    metricFilters.textContent = filterParts.length
      ? `✓ ${filterParts.join(' · ')}`
      : '✓ None (all products)';
  }
}

// ── Input Slider Displays ─────────────────────────────────────
function setupSlidersAndInputs() {
  filterPrice.addEventListener('input', () => {
    const val = parseInt(filterPrice.value);
    priceDisplay.textContent = `₹${val.toLocaleString('en-IN')}`;
    filterPrice.setAttribute('aria-valuenow', val);
  });

  filterTopN.addEventListener('input', () => {
    topnDisplay.textContent = filterTopN.value;
  });
}

// ── Active Searching Pipeline ─────────────────────────────────
searchBtn.addEventListener('click', runSearch);
errorRetry.addEventListener('click', runSearch);

btnBackSearch.forEach(btn => {
  btn.addEventListener('click', () => {
    const transitionBack = () => {
      searchResultsView.classList.add('hidden');
      searchBuilderView.classList.remove('hidden');
    };
    if (document.startViewTransition) {
      document.startViewTransition(transitionBack);
    } else {
      transitionBack();
    }
  });
});

async function runSearch() {
  if (!uploadedFile) return;

  activeSearchFilters = {
    category:      filterCategory.value || null,
    max_price:     parseFloat(filterPrice.value),
    in_stock_only: filterInstock.checked,
    text_modifier: textModifier.value.trim() || null,
    text_weight:   0.3,
    top_n:         parseInt(filterTopN.value)
  };
  
  topNRequested = activeSearchFilters.top_n;

  // View switch with transition
  const transitionToLoader = () => {
    searchBuilderView.classList.add('hidden');
    searchResultsView.classList.remove('hidden');
    showSearchLoading();
  };

  if (document.startViewTransition) {
    document.startViewTransition(transitionToLoader);
  } else {
    transitionToLoader();
  }

  // Populate Query Breadcrumbs
  breadcrumbImg.src = previewImg.src;
  breadcrumbText.textContent = activeSearchFilters.text_modifier 
    ? `modifier: "${activeSearchFilters.text_modifier}"` 
    : 'No text modifier';

  // Build filters list
  const filterStrings = [];
  if (activeSearchFilters.category) filterStrings.push(activeSearchFilters.category);
  filterStrings.push(`Max ₹${activeSearchFilters.max_price.toLocaleString('en-IN')}`);
  if (activeSearchFilters.in_stock_only) filterStrings.push('In Stock');
  
  breadcrumbFilters.innerHTML = filterStrings.map(f => `<span class="filter-badge">${f}</span>`).join('');
  resultsCountLabel.textContent = `Showing top ${activeSearchFilters.top_n} matches`;

  // Start animated loader sequence
  showSearchLoading();

  // Generate thumbnail for History log
  const thumbnailBase64 = await generateThumbnail(uploadedFile);

  const formData = new FormData();
  formData.append('image', uploadedFile);
  formData.append('filters', JSON.stringify(activeSearchFilters));

  try {
    const res = await fetch(`${API_BASE}/search`, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    
    // Clear step timers
    psTimers.forEach(clearTimeout);
    psTimers = [];

    // Complete pipeline visual with real API data
    completePipelineNode(data);

    // Update Live Preview Panel with real metrics
    updateLivePreview('done', data);

    // Log this search into local storage history
    saveSearchToHistory({
      imageThumbnail: thumbnailBase64,
      text_modifier: activeSearchFilters.text_modifier,
      filters: filterStrings,
      timestamp: new Date().getTime(),
      filtersState: activeSearchFilters,
      rawFile: uploadedFile
    });

    // Display Results
    setTimeout(() => {
      renderSearchResults(data);
    }, 600);

  } catch (err) {
    clearTimeout(stepsTimer1);
    clearTimeout(stepsTimer2);
    showSearchError('Retrieval Pipeline Interrupted', err.message);
  }
}



// ── Pipeline Stepper Animation (5-stage) ─────────────────────
const PS_STEPS = [
  { id: 'ps-step-0', badgeId: 'ps-badge-0' },
  { id: 'ps-step-1', badgeId: 'ps-badge-1' },
  { id: 'ps-step-2', badgeId: 'ps-badge-2' },
  { id: 'ps-step-3', badgeId: 'ps-badge-3' },
  { id: 'ps-step-4', badgeId: 'ps-badge-4' },
];
let psTimers = [];

function showSearchLoading() {
  resultsLoading.classList.remove('hidden');
  resultsError.classList.add('hidden');
  resultsContainer.classList.add('hidden');

  // Reset all steps
  PS_STEPS.forEach(({ id, badgeId }) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'ps-step pending';
    el.querySelector('.ps-dot').innerHTML = '';
    const badge = document.getElementById(badgeId);
    if (badge) badge.textContent = '';
  });

  // Activate step 0 immediately
  _psActivate(0);

  // Sequenced stagger timers
  psTimers = [
    setTimeout(() => _psComplete(0, 'avg 28ms'), 600),
    setTimeout(() => _psActivate(1),             620),
    setTimeout(() => _psComplete(1, '50 found'),  1100),
    setTimeout(() => _psActivate(2),              1120),
    setTimeout(() => _psComplete(2, 'filtering'), 1700),
    setTimeout(() => _psActivate(3),              1720),
    // Step 3 (reranker) + step 4 completed by API response
  ];
}

function _psActivate(idx) {
  const el = document.getElementById(PS_STEPS[idx].id);
  if (!el) return;
  el.className = 'ps-step active';
  el.querySelector('.ps-dot').innerHTML = '<div class="ps-spinner"></div>';
}

function _psComplete(idx, label) {
  const el = document.getElementById(PS_STEPS[idx].id);
  if (!el) return;
  el.className = 'ps-step done';
  el.querySelector('.ps-dot').innerHTML = '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="2,6 5,9 10,3"/></svg>';
  const badge = document.getElementById(PS_STEPS[idx].badgeId);
  if (badge) badge.textContent = label;
}

function completePipelineNode(data) {
  psTimers.forEach(clearTimeout);
  psTimers = [];
  // Complete all with real data
  _psComplete(0, 'avg 28ms');
  _psComplete(1, `${data?.total_retrieved ?? 50} found`);
  const sqlPassed = data?.filters_applied ? Object.values(data.filters_applied).filter(Boolean).length > 0 : false;
  _psComplete(2, sqlPassed ? 'filtered' : 'no filter');
  _psComplete(3, `${data?.retrieval_latency_ms?.toFixed(1) ?? '?'}ms`);
  _psActivate(4);
  setTimeout(() => _psComplete(4, `Top ${data?.total_returned ?? '?'}`), 200);
}

function showSearchError(title, detail) {
  errorTitle.textContent = title;
  errorDetail.textContent = detail;
  resultsLoading.classList.add('hidden');
  resultsContainer.classList.add('hidden');
  resultsError.classList.remove('hidden');
}

// ── Search Results Rendering ──────────────────────────────────
let _lastResultsData = null;

function renderSearchResults(data) {
  _lastResultsData = data;

  // Fill retrieval summary bar
  const rsRetrieved = document.getElementById('rs-retrieved');
  const rsReranked  = document.getElementById('rs-reranked');
  const rsLatency   = document.getElementById('rs-latency');
  if (rsRetrieved) rsRetrieved.textContent = data.total_retrieved;
  if (rsReranked)  rsReranked.textContent  = data.total_returned;
  if (rsLatency)   rsLatency.textContent   = `${data.retrieval_latency_ms.toFixed(1)}ms`;

  // Simulate candidate ranks from similarity ordering
  const withCandRank = [...data.results]
    .map((p, i) => ({ ...p, _finalRank: i + 1 }))
    .sort((a, b) => b.similarity - a.similarity)
    .map((p, i) => ({ ...p, _candRank: i + 1 }))
    .sort((a, b) => a._finalRank - b._finalRank);

  resultsGrid.innerHTML = '';
  currentResults = data.results;

  if (!withCandRank.length) {
    resultsGrid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--text-secondary);padding:60px 0">No matching products found. Try relaxing your filters.</div>`;
    btnLoadMore.classList.add('hidden');
  } else {
    withCandRank.forEach((p, i) => {
      const card = createProductCard(p, i);
      setTimeout(() => resultsGrid.appendChild(card), i * 60);
    });
    btnLoadMore.classList.toggle('hidden', data.results.length < topNRequested);
  }

  resultsLoading.classList.add('hidden');
  resultsError.classList.add('hidden');
  resultsContainer.classList.remove('hidden');

  // Wire sort + view toggle
  _wireResultsControls(withCandRank);
}

function _wireResultsControls(items) {
  const sortSel     = document.getElementById('rs-sort');
  const gridBtn     = document.getElementById('view-grid-btn');
  const listBtn     = document.getElementById('view-list-btn');
  const backSearch2 = document.getElementById('btn-back-search-2');

  if (sortSel) {
    sortSel.onchange = () => {
      const sorted = [...items];
      if (sortSel.value === 'price-asc')  sorted.sort((a, b) => a.price - b.price);
      if (sortSel.value === 'price-desc') sorted.sort((a, b) => b.price - a.price);
      if (sortSel.value === 'relevance')  sorted.sort((a, b) => a._finalRank - b._finalRank);
      resultsGrid.innerHTML = '';
      sorted.forEach((p, i) => {
        const card = createProductCard(p, i);
        setTimeout(() => resultsGrid.appendChild(card), i * 40);
      });
    };
  }
  if (gridBtn && listBtn) {
    gridBtn.onclick = () => { resultsGrid.classList.remove('list-view'); gridBtn.classList.add('active'); listBtn.classList.remove('active'); };
    listBtn.onclick = () => { resultsGrid.classList.add('list-view');    listBtn.classList.add('active'); gridBtn.classList.remove('active'); };
  }
  if (backSearch2) backSearch2.onclick = () => btnBackSearch[0]?.click();
}

function createProductCard(p, index) {
  const card = document.createElement('div');
  card.className = 'product-card';
  card.setAttribute('tabindex', '0');
  card.setAttribute('role', 'button');
  card.setAttribute('aria-label', `${p.name}, Price ₹${p.price}`);
  
  // Set custom cascade property for stagger animation delay
  card.style.setProperty('--i', index);

  const isSaved = checkIsBookmarked(p.id);

  const imgPath = p.image_path
    ? `/images/${encodeURIComponent(p.image_path.replace('data/', ''))}`
    : null;

  const clipSim    = (p.similarity * 100).toFixed(0);
  const ceScore    = p.rerank_score != null ? p.rerank_score.toFixed(3) : null;
  const scoreLabel = ceScore ? `${clipSim}% sim` : `${clipSim}% sim`;

  // Build explainability reasons
  const reasons = generateExplainability(p, activeSearchFilters, index);

  card.innerHTML = `
    <div class="product-card-rank">${index + 1}</div>
    <button class="product-card-bookmark ${isSaved ? 'saved' : ''}" aria-label="Save product" data-prod-id="${p.id}">
      <svg width="14" height="13" viewBox="0 0 14 13" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M7 12.35l-.85-.77C2.92 8.62 1 6.89 1 4.75 1 3.01 2.37 1.65 4.1 1.65c.98 0 1.91.45 2.9 1.17.99-.72 1.92-1.17 2.9-1.17 1.73 0 3.1 1.36 3.1 3.1 0 2.14-1.92 3.87-5.15 6.84L7 12.35z"/></svg>
    </button>
    <span class="product-card-similarity-badge">${scoreLabel}</span>
    <div class="product-card-img-wrap">
      ${imgPath 
        ? `<img class="product-card-img" src="${imgPath}" alt="${p.name}" loading="lazy" />`
        : `<div class="product-card-img-placeholder" style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:36px;background:var(--bg-input)">${getCategoryEmoji(p.category)}</div>`
      }
    </div>
    <div class="product-card-body">
      <span class="product-card-name" title="${p.name}">${p.name}</span>
      <span class="product-card-meta">${p.color ? p.color + ' · ' : ''}${p.subcategory || p.category}</span>
      <div class="product-card-footer">
        <span class="product-card-price">₹${parseFloat(p.price).toLocaleString('en-IN')}</span>
        <span class="badge-stock ${p.in_stock ? 'in' : 'out'}">${p.in_stock ? 'In Stock' : 'Out'}</span>
      </div>

      <!-- Explainability reasons -->
      <div class="explain-reasons">
        ${reasons.map(r => `<span class="explain-reason ${r.type}">${r.text}</span>`).join('')}
      </div>

      <!-- Pipeline Inspector -->
      <div class="pipeline-inspector">
        <button class="inspector-toggle" aria-expanded="false">
          Pipeline Inspector
          <span class="toggle-chevron">›</span>
        </button>
        <div class="inspector-panel hidden">
          <div class="inspector-row">
            <span class="inspector-label">CLIP Similarity</span>
            <span class="inspector-value accent">${(p.similarity * 100).toFixed(1)}%</span>
          </div>
          <div class="inspector-row">
            <span class="inspector-label">SQL Filter</span>
            <span class="inspector-value success">✓ Passed</span>
          </div>
          ${ceScore ? `
          <div class="inspector-row">
            <span class="inspector-label">Cross-Encoder</span>
            <span class="inspector-value accent">${ceScore}</span>
          </div>` : ''}
          <div class="inspector-row">
            <span class="inspector-label">Final Rank</span>
            <span class="inspector-value">#${index + 1}</span>
          </div>
        </div>
      </div>
    </div>
  `;

  // ── Event Bindings ───────────────────────────────────────────
  card.addEventListener('click', e => {
    if (e.target.closest('.product-card-bookmark')) return;
    if (e.target.closest('.inspector-toggle')) return;
    useProductAsQuery(p);
  });
  card.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    if (e.target.closest('.product-card-bookmark')) return;
    if (e.target.closest('.inspector-toggle')) return;
    useProductAsQuery(p);
  });

  card.querySelector('.product-card-bookmark').addEventListener('click', e => {
    e.stopPropagation();
    toggleBookmark(p, card.querySelector('.product-card-bookmark'));
  });

  const inspectorToggle = card.querySelector('.inspector-toggle');
  const inspectorPanel  = card.querySelector('.inspector-panel');
  if (inspectorToggle && inspectorPanel) {
    inspectorToggle.addEventListener('click', e => {
      e.stopPropagation();
      const open = !inspectorPanel.classList.contains('hidden');
      inspectorPanel.classList.toggle('hidden', open);
      inspectorToggle.classList.toggle('open', !open);
      inspectorToggle.setAttribute('aria-expanded', String(!open));
    });
  }

  return card;
}

// ── Star builder ─────────────────────────────────────────────
function _buildStars(rating) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  let html = '';
  for (let i = 0; i < 5; i++) {
    if (i < full)     html += '<span class="star full">★</span>';
    else if (i === full && half) html += '<span class="star half">★</span>';
    else html += '<span class="star empty">☆</span>';
  }
  return html;
}

// ── Explainability Reason Generator ──────────────────────────
function generateExplainability(product, filters, index) {
  const reasons = [];
  const sim  = product.similarity;
  const ce   = product.rerank_score;

  // Visual similarity
  if (sim >= 0.80)      reasons.push({ text: '✓ Strong visual match', type: 'positive' });
  else if (sim >= 0.60) reasons.push({ text: '✓ Good visual match',   type: 'positive' });
  else                  reasons.push({ text: '~ Moderate similarity',  type: 'neutral'  });

  // Text modifier effect (cross-encoder lifted it if CE > raw sim signal)
  if (filters?.text_modifier) {
    const modifier = filters.text_modifier.toLowerCase();
    // Check if product color or name mentions the modifier keywords
    const productText = `${product.name} ${product.color || ''}`.toLowerCase();
    const keywords    = modifier.replace(/^(but|in|for|with)\s*/i, '').split(/\s+/);
    const matched     = keywords.some(kw => kw.length > 2 && productText.includes(kw));
    if (matched) {
      reasons.push({ text: `✓ Matches "${filters.text_modifier}"`, type: 'positive' });
    } else {
      reasons.push({ text: `✓ Modifier applied`, type: 'positive' });
    }
  }

  // Category filter match
  if (filters?.category && product.category === filters.category) {
    reasons.push({ text: `✓ ${product.category}`, type: 'positive' });
  }

  // Cross-encoder boosted (top-3 by reranker)
  if (ce !== null && index < 3) {
    reasons.push({ text: '✓ CE top-ranked', type: 'positive' });
  }

  // Stock status
  if (product.in_stock) {
    reasons.push({ text: '✓ In stock', type: 'positive' });
  }

  return reasons;
}

function getCategoryEmoji(cat) {
  const map = { Apparel: '👗', Footwear: '👟', Electronics: '📱', Home: '🏠', Beauty: '✨' };
  return map[cat] || '📦';
}

// ── Search Redirection ────────────────────────────────────────
async function useProductAsQuery(product) {
  if (!product.image_path) return;
  try {
    const res = await fetch(`/images/${encodeURIComponent(product.image_path.replace('data/', ''))}`);
    const blob = await res.blob();
    const file = new File([blob], 'product.jpg', { type: blob.type });
    
    setFile(file);
    
    // Auto switch tab back to Search Builder
    switchTab('search');
    
    // Switch views to Search Builder
    searchResultsView.classList.add('hidden');
    searchBuilderView.classList.remove('hidden');
    
    // Focus search button
    searchBtn.scrollIntoView({ behavior: 'smooth' });
    searchBtn.focus();
  } catch (err) {
    console.error('Failed to redirect catalog search query:', err);
  }
}

// ── Catalog Tab Loading ───────────────────────────────────────
async function loadCatalog(category = '') {
  catalogGrid.innerHTML = '<div class="catalog-loading">Loading indexed database catalog...</div>';

  try {
    const params = new URLSearchParams({ limit: 60, offset: 0 });
    if (category) params.append('category', category);

    const res = await fetch(`${API_BASE}/products?${params}`);
    const data = await res.json();

    catalogGrid.innerHTML = '';
    catalogCount.textContent = `Indexed Database holds ${data.total} products total · Showing top ${data.products.length}`;

    data.products.forEach(p => {
      const card = document.createElement('div');
      card.className = 'catalog-card';
      card.setAttribute('tabindex', '0');
      card.setAttribute('role', 'button');
      card.setAttribute('aria-label', `Use ${p.name} as query`);
      card.title = 'Click to use this item as a search query';

      const imgPath = p.image_path
        ? `/images/${encodeURIComponent(p.image_path.replace('data/', ''))}`
        : null;

      card.innerHTML = `
        ${imgPath
          ? `<img src="${imgPath}" alt="${p.name}" loading="lazy" />`
          : `<div style="height:140px;display:flex;align-items:center;justify-content:center;font-size:28px;background:var(--bg-input)">${getCategoryEmoji(p.category)}</div>`
        }
        <div class="catalog-card-body">
          <div class="catalog-card-name" title="${p.name}">${p.name}</div>
          <div class="catalog-card-sub">${p.color ? p.color + ' · ' : ''}${p.category}</div>
          <div class="catalog-card-price">₹${parseFloat(p.price).toLocaleString('en-IN')}</div>
          <div class="catalog-card-hint">Click to trigger search ➔</div>
        </div>
      `;

      card.addEventListener('click', () => useProductAsQuery(p));
      card.addEventListener('keydown', e => { if (e.key === 'Enter') useProductAsQuery(p); });
      catalogGrid.appendChild(card);
    });
  } catch (err) {
    catalogGrid.innerHTML = `<div class="catalog-loading" style="color:var(--danger)">Failed to synchronize database products: ${err.message}</div>`;
  }
}

// Bind Category filter pills inside Catalog Tab
document.querySelectorAll('.filter-pill').forEach(pill => {
  pill.addEventListener('click', () => {
    document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    loadCatalog(pill.dataset.cat);
  });
});

// ── Search History Logs ───────────────────────────────────────
function saveSearchToHistory(logItem) {
  let logs = JSON.parse(localStorage.getItem('vectra_history') || '[]');
  
  // Unshift log item
  logs.unshift(logItem);
  
  // Cap at 15 history logs
  if (logs.length > 15) {
    logs.pop();
  }
  
  localStorage.setItem('vectra_history', JSON.stringify(logs));
}

function renderHistory() {
  const logs = JSON.parse(localStorage.getItem('vectra_history') || '[]');
  historyListContainer.innerHTML = '';

  if (!logs.length) {
    historyListContainer.innerHTML = `
      <div class="history-empty-state">
        <span class="empty-icon">⏳</span>
        <h3>No past searches</h3>
        <p>Your local search runs will appear here for easy recall.</p>
      </div>
    `;
    return;
  }

  logs.forEach(log => {
    const div = document.createElement('div');
    div.className = 'history-item';
    
    const timeFormatted = new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const filtersLabel = log.filters.length ? log.filters.join(' · ') : 'No filters applied';

    div.innerHTML = `
      <img class="history-item-img" src="${log.imageThumbnail}" alt="Past query representation" />
      <div class="history-item-meta">
        <span class="history-item-text">${log.text_modifier ? `"${log.text_modifier}"` : 'Visual Search Query'}</span>
        <span class="history-item-filters">${filtersLabel}</span>
      </div>
      <span class="history-item-time">${timeFormatted}</span>
    `;

    div.addEventListener('click', () => reRunHistorySearch(log));
    historyListContainer.appendChild(div);
  });
}

async function reRunHistorySearch(log) {
  // Convert base64 thumbnail back to blob to trigger upload file state
  try {
    const res = await fetch(log.imageThumbnail);
    const blob = await res.blob();
    const file = new File([blob], 'history_query.jpg', { type: blob.type });

    setFile(file);
    
    // Set filters
    textModifier.value = log.filtersState.text_modifier || '';
    filterCategory.value = log.filtersState.category || '';
    filterPrice.value = log.filtersState.max_price || 5000;
    filterPrice.dispatchEvent(new Event('input'));
    filterInstock.checked = log.filtersState.in_stock_only;
    filterTopN.value = log.filtersState.top_n || 10;
    filterTopN.dispatchEvent(new Event('input'));

    switchTab('search');
    runSearch();
  } catch (err) {
    console.error('Failed to reload history search:', err);
  }
}

// Helper to generate a small base64 thumbnail image from File upload using HTML5 Canvas
function generateThumbnail(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const max_size = 80;
        let width = img.width;
        let height = img.height;

        if (width > height) {
          if (width > max_size) {
            height *= max_size / width;
            width = max_size;
          }
        } else {
          if (height > max_size) {
            width *= max_size / height;
            height = max_size;
          }
        }
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL('image/jpeg', 0.8));
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

// ── Saved Collections Bookmarks ───────────────────────────────
function checkIsBookmarked(prodId) {
  let bookmarks = JSON.parse(localStorage.getItem('vectra_collections') || '[]');
  return bookmarks.some(p => p.id === prodId);
}

function toggleBookmark(product, buttonEl) {
  let bookmarks = JSON.parse(localStorage.getItem('vectra_collections') || '[]');
  const index = bookmarks.findIndex(p => p.id === product.id);

  if (index !== -1) {
    // Remove
    bookmarks.splice(index, 1);
    buttonEl.classList.remove('saved');
  } else {
    // Add
    bookmarks.push(product);
    buttonEl.classList.add('saved');
  }

  localStorage.setItem('vectra_collections', JSON.stringify(bookmarks));
  
  // If active tab is collections, re-render immediately
  if (currentTab === 'collections') {
    renderCollections();
  }
}

function renderCollections() {
  const bookmarks = JSON.parse(localStorage.getItem('vectra_collections') || '[]');
  collectionsGridContainer.innerHTML = '';

  if (!bookmarks.length) {
    collectionsGridContainer.innerHTML = `
      <div class="collections-empty-state" style="grid-column: 1/-1;">
        <span class="empty-icon">💖</span>
        <h3>No bookmarks yet</h3>
        <p>Save visually appealing products from search results using the heart button to view them here.</p>
      </div>
    `;
    return;
  }

  bookmarks.forEach((p, index) => {
    const card = createProductCard(p, index);
    collectionsGridContainer.appendChild(card);
  });
}

// ── Visual Themes Selection ───────────────────────────────────
function initTheme() {
  const savedTheme = localStorage.getItem('vectra_theme') || 'indigo-dark';
  applyTheme(savedTheme);
}

function setupThemeSelection() {
  const themeCards = document.querySelectorAll('.theme-select-card');
  
  themeCards.forEach(card => {
    card.addEventListener('click', () => {
      const themeId = card.dataset.themeId;
      applyTheme(themeId);
    });
  });
}

function applyTheme(themeId) {
  document.documentElement.setAttribute('data-theme', themeId);
  localStorage.setItem('vectra_theme', themeId);

  // Update active state on select cards
  const themeCards = document.querySelectorAll('.theme-select-card');
  themeCards.forEach(card => {
    if (card.dataset.themeId === themeId) {
      card.classList.add('active');
    } else {
      card.classList.remove('active');
    }
  });
}

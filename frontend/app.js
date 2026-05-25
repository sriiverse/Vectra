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
}

function clearFile() {
  uploadedFile = null;
  previewImg.src = '';
  fileInput.value = '';
  dropzoneIdle.classList.remove('hidden');
  dropzonePreview.classList.add('hidden');
  searchBtn.disabled = true;
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

  // Start animated loader sequence (independent of exact timings but updated by steps)
  let stepsTimer1 = setTimeout(() => advancePipelineNode(stepRetrieve, 'line-1', 'dot-1'), 700);
  let stepsTimer2 = setTimeout(() => advancePipelineNode(stepRerank, 'line-2', 'dot-2'), 1400);

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
    clearTimeout(stepsTimer1);
    clearTimeout(stepsTimer2);
    
    // Force complete pipeline visual
    completePipelineNode();

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

// ── Pipeline Animation Helpers ────────────────────────────────
function showSearchLoading() {
  resultsLoading.classList.remove('hidden');
  resultsError.classList.add('hidden');
  resultsContainer.classList.add('hidden');
  
  // Reset nodes
  document.querySelectorAll('.network-node').forEach(n => n.className = 'network-node');
  document.querySelector('.network-node.node-1').classList.add('active');
  
  const svg = document.querySelector('.network-lines');
  svg.querySelector('.line-1').setAttribute('class', 'line-1');
  svg.querySelector('.line-2').setAttribute('class', 'line-2');
  svg.querySelector('.dot-1').setAttribute('class', 'dot-1');
  svg.querySelector('.dot-2').setAttribute('class', 'dot-2');
  svg.querySelector('.dot-3').setAttribute('class', 'dot-3');

  document.querySelector('.loader-status-text').textContent = 'Generating CLIP query representations...';
}

function advancePipelineNode(nodeEl, lineClass, dotClass) {
  // Mark previous active nodes as done
  document.querySelectorAll('.network-node.active').forEach(n => {
    n.classList.remove('active');
    n.classList.add('done');
  });

  nodeEl.classList.add('active');
  
  const svg = document.querySelector('.network-lines');
  if (lineClass === 'line-1') {
    svg.querySelector('.line-1').classList.add('active-line');
    svg.querySelector('.dot-1').classList.add('done-circle');
    svg.querySelector('.dot-2').classList.add('active-circle');
    document.querySelector('.loader-status-text').textContent = 'Querying pgvector HNSW database...';
  } else if (lineClass === 'line-2') {
    svg.querySelector('.line-1').setAttribute('class', 'line-1 done-line');
    svg.querySelector('.line-2').classList.add('active-line');
    svg.querySelector('.dot-2').classList.add('done-circle');
    svg.querySelector('.dot-3').classList.add('active-circle');
    document.querySelector('.loader-status-text').textContent = 'Cross-encoder scoring candidate names...';
  }
}

function completePipelineNode() {
  document.querySelectorAll('.network-node').forEach(n => {
    n.className = 'network-node done';
  });
  const svg = document.querySelector('.network-lines');
  svg.querySelector('.line-1').setAttribute('class', 'line-1 done-line');
  svg.querySelector('.line-2').setAttribute('class', 'line-2 done-line');
  svg.querySelector('.dot-1').setAttribute('class', 'dot-1 done-circle');
  svg.querySelector('.dot-2').setAttribute('class', 'dot-2 done-circle');
  svg.querySelector('.dot-3').setAttribute('class', 'dot-3 done-circle');
  document.querySelector('.loader-status-text').textContent = 'Retrieval complete! Rendering results...';
}

function showSearchError(title, detail) {
  errorTitle.textContent = title;
  errorDetail.textContent = detail;
  resultsLoading.classList.add('hidden');
  resultsContainer.classList.add('hidden');
  resultsError.classList.remove('hidden');
}

// ── Search Results Rendering ──────────────────────────────────
function renderSearchResults(data) {
  resultsMeta.innerHTML = `
    <span class="meta-item">Retrieved <strong>${data.total_retrieved}</strong> candidates</span>
    <span class="meta-divider">·</span>
    <span class="meta-item">Reranked to <strong>${data.total_returned}</strong> results</span>
    <span class="meta-divider">·</span>
    <span class="meta-item">Retrieval Latency: <strong>${data.retrieval_latency_ms.toFixed(1)}ms</strong></span>
  `;

  resultsGrid.innerHTML = '';
  currentResults = data.results;

  if (!data.results.length) {
    resultsGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 60px 0;">No matching products found. Try relaxing your price or category filters.</div>`;
    btnLoadMore.classList.add('hidden');
  } else {
    data.results.forEach((p, i) => {
      const card = createProductCard(p, i);
      resultsGrid.appendChild(card);
    });

    if (data.results.length < topNRequested) {
      btnLoadMore.classList.add('hidden');
    } else {
      btnLoadMore.classList.remove('hidden');
    }
  }

  resultsLoading.classList.add('hidden');
  resultsError.classList.add('hidden');
  resultsContainer.classList.remove('hidden');
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

  const scoreLabel = p.rerank_score != null 
    ? `rank ${p.rerank_score.toFixed(2)}`
    : `sim ${(p.similarity * 100).toFixed(0)}%`;

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
        <span class="badge-stock ${p.in_stock ? 'in' : 'out'}">${p.in_stock ? 'In Stock' : 'Out of Stock'}</span>
      </div>
    </div>
  `;

  // Bind click handlers
  card.addEventListener('click', (e) => {
    // Exclude bookmark button
    if (e.target.closest('.product-card-bookmark')) return;
    useProductAsQuery(p);
  });
  
  card.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      if (e.target.closest('.product-card-bookmark')) return;
      useProductAsQuery(p);
    }
  });

  const bookmarkBtn = card.querySelector('.product-card-bookmark');
  bookmarkBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleBookmark(p, bookmarkBtn);
  });

  return card;
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

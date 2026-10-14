/**
 * TrendCore Frontend Engine
 * Tagline: Trade. Learn. Grow.
 */

// --- Dark Mode Controller ---
(function initTheme() {
  const savedTheme = localStorage.getItem('trendcore_theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('trendcore_theme', next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const icon = document.getElementById('theme-toggle-icon');
  if (icon) {
    icon.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}

// --- Toast Notification Engine ---
function showToast(title, message, type = 'info') {
  let container = document.getElementById('tc-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'tc-toast-container';
    container.className = 'tc-toast-container';
    document.body.appendChild(container);
  }

  const icons = {
    success: '✅',
    error: '❌',
    info: '🔔',
    warning: '⚠️'
  };

  const toast = document.createElement('div');
  toast.className = `tc-toast ${type}`;
  toast.innerHTML = `
    <div style="font-size: 1.25rem;">${icons[type] || '🔔'}</div>
    <div style="flex: 1;">
      <div style="font-weight: 700; font-size: 0.875rem; color: var(--text-primary);">${title}</div>
      <div style="font-size: 0.8125rem; color: var(--text-secondary); margin-top: 2px;">${message}</div>
    </div>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;">&times;</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --- Indian Currency Formatter ---
function formatINR(number) {
  const val = Math.abs(Number(number) || 0).toFixed(2);
  const parts = val.split('.');
  let integerPart = parts[0];
  const decimalPart = parts[1];

  let lastThree = integerPart.substring(integerPart.length - 3);
  const otherNumbers = integerPart.substring(0, integerPart.length - 3);
  if (otherNumbers !== '') {
    lastThree = ',' + lastThree;
  }
  const formatted = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree;
  return (number < 0 ? '-' : '') + '₹' + formatted + '.' + decimalPart;
}

// --- Global Search Modal ---
function openSearchModal() {
  const modal = document.getElementById('searchModal');
  if (modal) {
    modal.classList.add('active');
    const input = document.getElementById('globalSearchInput');
    if (input) {
      input.focus();
      input.select();
    }
  }
}

function closeSearchModal() {
  const modal = document.getElementById('searchModal');
  if (modal) {
    modal.classList.remove('active');
  }
}

// Handle Search Keydown (Escape, Shortcut Ctrl+K or /)
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeSearchModal();
    closeAllDropdowns();
  }
  if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA')) {
    e.preventDefault();
    openSearchModal();
  }
});

let searchDebounceTimer;
function handleGlobalSearch(query) {
  clearTimeout(searchDebounceTimer);
  const resultsContainer = document.getElementById('searchResultsList');
  if (!resultsContainer) return;

  if (!query || query.trim().length === 0) {
    resultsContainer.innerHTML = `
      <div style="padding: 2rem; text-align: center; color: var(--text-muted); font-size: 0.875rem;">
        Type stock symbol or company name (e.g. RELIANCE, TCS, INFY)
      </div>
    `;
    return;
  }

  resultsContainer.innerHTML = `
    <div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); font-size: 0.875rem;">
      Searching Indian equities...
    </div>
  `;

  searchDebounceTimer = setTimeout(() => {
    fetch(`/api/search?q=${encodeURIComponent(query.trim())}`)
      .then(res => res.json())
      .then(data => {
        if (!data.results || data.results.length === 0) {
          resultsContainer.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: var(--text-muted);">
              No stocks found matching "<strong>${query}</strong>"
            </div>
          `;
          return;
        }

        let html = '';
        data.results.forEach(stock => {
          const isPos = stock.change_pct >= 0;
          html += `
            <a href="/stock/${stock.symbol}" class="tc-search-item" onclick="closeSearchModal()">
              <div>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <span style="font-weight: 700; color: var(--text-primary); font-size: 0.9375rem;">
                    ${stock.symbol}
                  </span>
                  <span style="font-size: 0.6875rem; font-weight: 700; color: var(--brand-primary); background: var(--brand-cyan-light); padding: 0.1rem 0.4rem; border-radius: var(--radius-sm);">
                    ${stock.exchange || 'NSE/BSE'}
                  </span>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${stock.name} • ${stock.sector}</div>
              </div>
              <div style="text-align: right;">
                <div style="font-weight: 700; color: var(--text-primary);">${formatINR(stock.current_price)}</div>
                <div style="font-size: 0.75rem; font-weight: 600;" class="${isPos ? 'text-positive' : 'text-negative'}">
                  ${isPos ? '+' : ''}${stock.change_pct.toFixed(2)}%
                </div>
              </div>
            </a>
          `;
        });
        resultsContainer.innerHTML = html;
      })
      .catch(err => {
        console.error("Search error:", err);
      });
  }, 200);
}

// --- Watchlist Star Toggle ---
function toggleWatchlist(symbol, btnElement) {
  fetch('/api/watchlist/toggle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol: symbol })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      const isIn = data.is_in_watchlist;
      if (btnElement) {
        if (isIn) {
          btnElement.classList.add('active');
          btnElement.innerHTML = '★';
          btnElement.style.color = '#eab308';
        } else {
          btnElement.classList.remove('active');
          btnElement.innerHTML = '☆';
          btnElement.style.color = 'var(--text-muted)';
        }
      }
      showToast(isIn ? "Watchlist Added" : "Watchlist Removed", data.message, isIn ? "success" : "info");
    } else {
      showToast("Error", data.message, "error");
    }
  })
  .catch(err => {
    console.error(err);
    showToast("Error", "Could not update watchlist.", "error");
  });
}

// --- Dropdowns Management ---
function toggleDropdown(id) {
  const target = document.getElementById(id);
  if (!target) return;
  const isShowing = target.classList.contains('show');
  closeAllDropdowns();
  if (!isShowing) {
    target.classList.add('show');
    if (id === 'notifDropdown') {
      markNotificationsRead();
    }
  }
}

function closeAllDropdowns() {
  document.querySelectorAll('.tc-dropdown-menu').forEach(menu => {
    menu.classList.remove('show');
  });
}

document.addEventListener('click', function(e) {
  if (!e.target.closest('.tc-dropdown-container')) {
    closeAllDropdowns();
  }
});

// Mobile Drawer
function toggleMobileNav() {
  const drawer = document.getElementById('mobileDrawer');
  const overlay = document.getElementById('drawerOverlay');
  if (drawer && overlay) {
    const isOpen = drawer.classList.contains('open');
    if (isOpen) {
      drawer.classList.remove('open');
      overlay.classList.remove('active');
    } else {
      drawer.classList.add('open');
      overlay.classList.add('active');
    }
  }
}

// Notifications mark read
function markNotificationsRead() {
  fetch('/api/notifications/mark-read', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      const badge = document.getElementById('notifBadge');
      if (badge) badge.style.display = 'none';
    })
    .catch(err => console.error(err));
}

// --- Stock Chart Renderer ---
let stockChartInstance = null;
function renderStockChart(canvasId, chartData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const isPositive = chartData.change >= 0;
  const primaryColor = isPositive ? '#10b981' : '#ef4444';
  const fillColor = isPositive ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)';

  if (stockChartInstance) {
    stockChartInstance.destroy();
  }

  stockChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: chartData.labels,
      datasets: [{
        label: chartData.symbol,
        data: chartData.prices,
        borderColor: primaryColor,
        backgroundColor: fillColor,
        borderWidth: 2.2,
        fill: true,
        tension: 0.25,
        pointRadius: 0,
        pointHitRadius: 10,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: primaryColor,
        pointHoverBorderColor: '#ffffff',
        pointHoverBorderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index'
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#94a3b8',
          bodyColor: '#ffffff',
          bodyFont: { weight: 'bold', size: 14 },
          padding: 12,
          cornerRadius: 8,
          displayColors: false,
          callbacks: {
            label: function(context) {
              return 'Price: ' + formatINR(context.raw);
            }
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: 8,
            color: '#94a3b8',
            font: { size: 11 }
          }
        },
        y: {
          position: 'right',
          grid: {
            color: 'rgba(148, 163, 184, 0.15)',
            drawBorder: false
          },
          ticks: {
            color: '#94a3b8',
            font: { size: 11 },
            callback: function(val) {
              return '₹' + Number(val).toLocaleString('en-IN');
            }
          }
        }
      }
    }
  });
}

function switchChartTimeframe(symbol, timeframe, btnElement) {
  // Update button active states
  document.querySelectorAll('.tc-timeframe-btn').forEach(b => b.classList.remove('active'));
  if (btnElement) btnElement.classList.add('active');

  fetch(`/api/stock/${symbol}/chart?timeframe=${timeframe}`)
    .then(res => res.json())
    .then(data => {
      if (data.success && data.data) {
        renderStockChart('stockChartCanvas', data.data);
        // Update timeframe stats if elements exist
        const tfHigh = document.getElementById('tfHigh');
        const tfLow = document.getElementById('tfLow');
        const tfChange = document.getElementById('tfChange');
        if (tfHigh) tfHigh.textContent = formatINR(data.data.high);
        if (tfLow) tfLow.textContent = formatINR(data.data.low);
        if (tfChange) {
          const isPos = data.data.change >= 0;
          tfChange.innerHTML = `<span class="${isPos ? 'text-positive' : 'text-negative'}">${isPos ? '+' : ''}${formatINR(data.data.change)} (${isPos ? '+' : ''}${data.data.change_pct}%)</span>`;
        }
      }
    })
    .catch(err => console.error(err));
}

// --- Trading Panel Interactive Math ---
let currentAction = 'BUY';
let currentOrderType = 'MARKET';

function setTradeAction(action) {
  currentAction = action;
  const buyBtn = document.getElementById('tabBuy');
  const sellBtn = document.getElementById('tabSell');
  const submitBtn = document.getElementById('tradeSubmitBtn');
  const actionLabel = document.getElementById('tradeActionLabel');

  if (action === 'BUY') {
    if (buyBtn) buyBtn.className = 'tc-segmented-tab active-buy';
    if (sellBtn) sellBtn.className = 'tc-segmented-tab';
    if (submitBtn) {
      submitBtn.className = 'btn btn-buy btn-block btn-lg';
      submitBtn.textContent = `BUY ${window.TC_STOCK_SYMBOL || 'STOCK'}`;
    }
    if (actionLabel) actionLabel.textContent = 'Virtual Balance Available:';
  } else {
    if (buyBtn) buyBtn.className = 'tc-segmented-tab';
    if (sellBtn) sellBtn.className = 'tc-segmented-tab active-sell';
    if (submitBtn) {
      submitBtn.className = 'btn btn-sell btn-block btn-lg';
      submitBtn.textContent = `SELL ${window.TC_STOCK_SYMBOL || 'STOCK'}`;
    }
    if (actionLabel) actionLabel.textContent = 'Shares Owned:';
  }
  recalculateTrade();
}

function setOrderType(type) {
  currentOrderType = type;
  const mktBtn = document.getElementById('typeMarketBtn');
  const lmtBtn = document.getElementById('typeLimitBtn');
  const limitField = document.getElementById('limitPriceGroup');

  if (type === 'MARKET') {
    if (mktBtn) mktBtn.classList.add('active');
    if (lmtBtn) lmtBtn.classList.remove('active');
    if (limitField) limitField.style.display = 'none';
  } else {
    if (mktBtn) mktBtn.classList.remove('active');
    if (lmtBtn) lmtBtn.classList.add('active');
    if (limitField) limitField.style.display = 'block';
  }
  recalculateTrade();
}

function changeQty(delta) {
  const qtyInput = document.getElementById('tradeQty');
  if (!qtyInput) return;
  let val = parseInt(qtyInput.value, 10) || 1;
  val = Math.max(1, val + delta);
  qtyInput.value = val;
  recalculateTrade();
}

function setExactQty(amount) {
  const qtyInput = document.getElementById('tradeQty');
  if (!qtyInput) return;
  let val = parseInt(qtyInput.value, 10) || 0;
  qtyInput.value = val + amount;
  recalculateTrade();
}

function setMaxQty() {
  const qtyInput = document.getElementById('tradeQty');
  if (!qtyInput) return;

  const currentPrice = window.TC_CURRENT_PRICE || 1;
  const userBalance = window.TC_USER_BALANCE || 0;
  const ownedShares = window.TC_USER_HOLDING_QTY || 0;

  if (currentAction === 'BUY') {
    const maxAffordable = Math.floor(userBalance / currentPrice);
    qtyInput.value = Math.max(1, maxAffordable);
  } else {
    qtyInput.value = Math.max(1, ownedShares);
  }
  recalculateTrade();
}

function recalculateTrade() {
  const qtyInput = document.getElementById('tradeQty');
  const estAmountEl = document.getElementById('estimatedAmountText');
  const limitInput = document.getElementById('tradeLimitPrice');
  const warningEl = document.getElementById('tradeWarningText');

  if (!qtyInput || !estAmountEl) return;

  const qty = parseInt(qtyInput.value, 10) || 0;
  let price = window.TC_CURRENT_PRICE || 0;

  if (currentOrderType === 'LIMIT' && limitInput) {
    const customPrice = parseFloat(limitInput.value);
    if (!isNaN(customPrice) && customPrice > 0) {
      price = customPrice;
    }
  }

  const total = qty * price;
  estAmountEl.textContent = formatINR(total);

  if (warningEl) {
    warningEl.textContent = '';
    warningEl.style.display = 'none';

    if (currentAction === 'BUY') {
      const balance = window.TC_USER_BALANCE || 0;
      if (total > balance) {
        warningEl.textContent = `Insufficient paper balance! (Short by ${formatINR(total - balance)})`;
        warningEl.style.display = 'block';
      }
    } else if (currentAction === 'SELL') {
      const owned = window.TC_USER_HOLDING_QTY || 0;
      if (qty > owned) {
        warningEl.textContent = `Cannot sell more than ${owned} shares owned!`;
        warningEl.style.display = 'block';
      }
    }
  }
}

function executeTrade() {
  const qtyInput = document.getElementById('tradeQty');
  const limitInput = document.getElementById('tradeLimitPrice');
  const submitBtn = document.getElementById('tradeSubmitBtn');

  if (!qtyInput) return;
  const qty = parseInt(qtyInput.value, 10) || 0;

  if (qty <= 0) {
    showToast("Invalid Quantity", "Please enter at least 1 share.", "warning");
    return;
  }

  let targetPrice = null;
  if (currentOrderType === 'LIMIT') {
    targetPrice = parseFloat(limitInput.value);
    if (isNaN(targetPrice) || targetPrice <= 0) {
      showToast("Invalid Target Price", "Please enter a valid limit target price.", "warning");
      return;
    }
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing Paper Order...';
  }

  fetch('/api/trade/place', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol: window.TC_STOCK_SYMBOL,
      action: currentAction,
      order_type: currentOrderType,
      quantity: qty,
      target_price: targetPrice
    })
  })
  .then(res => res.json())
  .then(data => {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = `${currentAction} ${window.TC_STOCK_SYMBOL}`;
    }

    if (data.success) {
      showToast("Order Successful!", data.message, "success");
      // Update local balance state
      if (data.new_balance !== undefined) {
        window.TC_USER_BALANCE = data.new_balance;
        const balEls = document.querySelectorAll('.user-balance-display');
        balEls.forEach(el => el.textContent = formatINR(data.new_balance));
      }
      setTimeout(() => {
        window.location.reload();
      }, 1200);
    } else {
      showToast("Order Failed", data.message, "error");
    }
  })
  .catch(err => {
    console.error(err);
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = `${currentAction} ${window.TC_STOCK_SYMBOL}`;
    }
    showToast("System Error", "Could not process order.", "error");
  });
}

// --- Order Cancellation ---
function cancelOpenOrder(orderId, btnElement) {
  if (!confirm("Are you sure you want to cancel this pending limit order? Any escrowed virtual cash will be refunded.")) {
    return;
  }

  fetch(`/api/order/cancel/${orderId}`, { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast("Order Cancelled", data.message, "info");
        setTimeout(() => window.location.reload(), 1000);
      } else {
        showToast("Cancellation Failed", data.message, "error");
      }
    })
    .catch(err => {
      console.error(err);
      showToast("Error", "Could not cancel order.", "error");
    });
}

// --- Reset Virtual Balance ---
function resetVirtualPortfolio() {
  if (!confirm("Reset your virtual portfolio back to ₹10,00,000? All current simulated holdings will be cleared.")) {
    return;
  }

  fetch('/api/profile/reset-balance', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast("Portfolio Reset", data.message, "success");
        setTimeout(() => window.location.href = '/dashboard', 1000);
      }
    })
    .catch(err => console.error(err));
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  updateThemeIcon(currentTheme);

  // Recalculate trade amounts if trading panel exists
  if (document.getElementById('tradeQty')) {
    recalculateTrade();
  }
});

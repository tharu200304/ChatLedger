// ChatLedger Client Application Logic
let currentOrders = [];
let selectedOrderId = null;
let currentCatalog = [];
let activeFilter = 'all';
let searchQuery = '';

// DOM Elements
const engineStatusDot = document.getElementById('engineStatusDot');
const engineStatusText = document.getElementById('engineStatusText');
const engineStatusBadge = document.getElementById('engineStatusBadge');
const brandTitle = document.getElementById('brandTitle');
const sellerSubtitle = document.getElementById('sellerSubtitle');

const statTodayBakes = document.getElementById('statTodayBakes');
const statPendingReview = document.getElementById('statPendingReview');
const statTotalRevenue = document.getElementById('statTotalRevenue');
const statChangedCancelled = document.getElementById('statChangedCancelled');
const loraCountBadge = document.getElementById('loraCountBadge');

const ordersListContainer = document.getElementById('ordersListContainer');
const searchOrdersInput = document.getElementById('searchOrdersInput');
const statusFilterPills = document.getElementById('statusFilterPills');

const chatStream = document.getElementById('chatStream');
const chatTimeWindow = document.getElementById('chatTimeWindow');

const inspectorEmptyState = document.getElementById('inspectorEmptyState');
const inspectorContent = document.getElementById('inspectorContent');
const inspectorStatusAlert = document.getElementById('inspectorStatusAlert');
const inspectorAlertIcon = document.getElementById('inspectorAlertIcon');
const inspectorAlertText = document.getElementById('inspectorAlertText');

const editCustomerName = document.getElementById('editCustomerName');
const editCustomerPhone = document.getElementById('editCustomerPhone');
const btnWhatsAppDirect = document.getElementById('btnWhatsAppDirect');
const editDeliveryDate = document.getElementById('editDeliveryDate');
const editDeliveryTime = document.getElementById('editDeliveryTime');
const editDeliveryArea = document.getElementById('editDeliveryArea');
const editDeliveryAddress = document.getElementById('editDeliveryAddress');
const editPaymentStatus = document.getElementById('editPaymentStatus');
const editUserNotes = document.getElementById('editUserNotes');
const editTotalAmount = document.getElementById('editTotalAmount');
const orderConfidenceBadge = document.getElementById('orderConfidenceBadge');
const inspectorWarningFlags = document.getElementById('inspectorWarningFlags');
const itemsTableBody = document.getElementById('itemsTableBody');

const btnConfirmOrder = document.getElementById('btnConfirmOrder');
const btnSaveOrder = document.getElementById('btnSaveOrder');
const btnCancelOrder = document.getElementById('btnCancelOrder');
const btnDeleteOrder = document.getElementById('btnDeleteOrder');
const btnAddItemRow = document.getElementById('btnAddItemRow');

// Modals
const modalUpload = document.getElementById('modalUpload');
const modalExport = document.getElementById('modalExport');
const modalCatalog = document.getElementById('modalCatalog');
const modalLora = document.getElementById('modalLora');
const modalSettings = document.getElementById('modalSettings');

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadCatalog();
  checkSystemStatus();
  loadOrders();
});

function initEventListeners() {
  // Search and filter
  searchOrdersInput.addEventListener('input', (e) => {
    searchQuery = e.target.value.toLowerCase();
    renderOrdersSidebar();
  });

  statusFilterPills.addEventListener('click', (e) => {
    if (e.target.classList.contains('pill')) {
      document.querySelectorAll('.filter-pills .pill').forEach(p => p.classList.remove('active'));
      e.target.classList.add('active');
      activeFilter = e.target.dataset.filter;
      renderOrdersSidebar();
    }
  });

  // Modal open buttons
  document.getElementById('btnOpenUpload').addEventListener('click', () => openModal(modalUpload));
  document.getElementById('btnOpenExport').addEventListener('click', () => openModal(modalExport));
  document.getElementById('btnOpenCatalog').addEventListener('click', () => {
    openModal(modalCatalog);
    renderCatalogTable();
  });
  document.getElementById('btnOpenLora').addEventListener('click', () => {
    openModal(modalLora);
    checkSystemStatus();
  });
  document.getElementById('btnOpenSettings').addEventListener('click', () => {
    openModal(modalSettings);
    loadSettings();
  });

  // Modal close buttons
  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('data-close');
      const target = document.getElementById(modalId);
      if (target) closeModal(target);
    });
  });

  // Close modals clicking on backdrop
  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal(modal);
    });
  });

  // Load demo chats button
  document.getElementById('btnLoadDemo').addEventListener('click', loadDemoChats);

  // Inspector order actions
  btnConfirmOrder.addEventListener('click', confirmCurrentOrder);
  btnSaveOrder.addEventListener('click', saveCurrentOrder);
  btnCancelOrder.addEventListener('click', markCurrentOrderCancelled);
  btnDeleteOrder.addEventListener('click', deleteCurrentOrder);
  btnAddItemRow.addEventListener('click', addNewItemRow);

  // Drag and drop chat file
  setupDragAndDrop();

  // Excel exports
  document.getElementById('btnExportProduction').addEventListener('click', () => {
    const d = document.getElementById('exportTargetDate').value;
    const url = `/api/export/production${d ? '?date=' + d : ''}`;
    window.open(url, '_blank');
    closeModal(modalExport);
    showToast('Kitchen Production Sheet downloaded');
  });

  document.getElementById('btnExportDelivery').addEventListener('click', () => {
    const d = document.getElementById('exportTargetDate').value;
    const url = `/api/export/delivery${d ? '?date=' + d : ''}`;
    window.open(url, '_blank');
    closeModal(modalExport);
    showToast('Delivery Route Sheet downloaded');
  });

  document.getElementById('btnExportPayments').addEventListener('click', () => {
    window.open('/api/export/payment-pending', '_blank');
    closeModal(modalExport);
    showToast('Payment Pending Tracker downloaded');
  });

  // LoRA Downloads
  document.getElementById('btnDownloadLoraAlpaca').addEventListener('click', () => {
    window.open('/api/export/lora?format=alpaca', '_blank');
  });
  document.getElementById('btnDownloadLoraShareGPT').addEventListener('click', () => {
    window.open('/api/export/lora?format=sharegpt', '_blank');
  });

  // Settings
  document.getElementById('btnSaveSettings').addEventListener('click', saveSettingsForm);
}

// Fetch system health & configuration
async function checkSystemStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();

    if (data.ollama_online) {
      engineStatusBadge.classList.remove('ollama-offline');
      engineStatusText.textContent = `Ollama (${data.active_model}) Active`;
    } else {
      engineStatusBadge.classList.add('ollama-offline');
      engineStatusText.textContent = `⚡ Local English Engine (Offline Ready)`;
    }

    sellerSubtitle.textContent = `${data.seller_name} (Local & Private)`;
    loraCountBadge.textContent = data.total_corrections;
    document.getElementById('modalLoraCount').textContent = data.total_corrections;
  } catch (err) {
    console.error('Failed to get status:', err);
  }
}

// Fetch Catalog
async function loadCatalog() {
  try {
    const res = await fetch('/api/catalog');
    currentCatalog = await res.json();
  } catch (err) {
    console.error('Failed to load catalog:', err);
  }
}

// Fetch Orders
async function loadOrders(preserveSelectedId = null) {
  try {
    const res = await fetch('/api/orders');
    currentOrders = await res.json();
    updateStatsBanner();
    renderOrdersSidebar();

    if (preserveSelectedId) {
      selectOrder(preserveSelectedId);
    } else if (currentOrders.length > 0 && !selectedOrderId) {
      selectOrder(currentOrders[0].id);
    } else if (selectedOrderId) {
      const stillExists = currentOrders.find(o => o.id === selectedOrderId);
      if (stillExists) {
        selectOrder(selectedOrderId);
      } else if (currentOrders.length > 0) {
        selectOrder(currentOrders[0].id);
      } else {
        clearInspector();
      }
    } else {
      clearInspector();
    }
  } catch (err) {
    console.error('Failed to load orders:', err);
    showToast('Error loading orders', 'error');
  }
}

// Update Header Stats Banner
function updateStatsBanner() {
  statTodayBakes.textContent = currentOrders.length;
  const pending = currentOrders.filter(o => o.status !== 'confirmed').length;
  statPendingReview.textContent = pending;

  const totalRev = currentOrders.reduce((sum, o) => {
    return o.status !== 'cancelled' ? sum + (o.total_amount || 0) : sum;
  }, 0);
  statTotalRevenue.textContent = `${totalRev.toLocaleString()} LKR`;

  const changedOrCancelled = currentOrders.filter(o => o.status === 'changed' || o.status === 'cancelled').length;
  statChangedCancelled.textContent = changedOrCancelled;
}

// Render Orders Sidebar
function renderOrdersSidebar() {
  ordersListContainer.innerHTML = '';

  const filtered = currentOrders.filter(o => {
    // Filter by status
    if (activeFilter !== 'all' && o.status !== activeFilter) {
      return false;
    }
    // Search query
    if (searchQuery) {
      const matchName = (o.customer_name || '').toLowerCase().includes(searchQuery);
      const matchPhone = (o.customer_phone || '').toLowerCase().includes(searchQuery);
      const matchArea = (o.area || '').toLowerCase().includes(searchQuery);
      const matchItem = (o.items || []).some(it => (it.product_name || '').toLowerCase().includes(searchQuery));
      return matchName || matchPhone || matchArea || matchItem;
    }
    return true;
  });

  if (filtered.length === 0) {
    ordersListContainer.innerHTML = `
      <div class="empty-state" style="padding: 2rem 1rem;">
        <p style="font-size: 0.85rem;">No orders match this filter.</p>
      </div>
    `;
    return;
  }

  filtered.forEach(order => {
    const card = document.createElement('div');
    card.className = `order-item-card ${order.id === selectedOrderId ? 'active' : ''}`;
    card.onclick = () => selectOrder(order.id);

    let tagClass = 'tag-new';
    if (order.status === 'changed') tagClass = 'tag-changed';
    else if (order.status === 'cancelled') tagClass = 'tag-cancelled';
    else if (order.status === 'confirmed') tagClass = 'tag-confirmed';

    const itemsSummary = (order.items || [])
      .map(it => `${it.quantity}x ${it.product_name} (${it.variant || 'std'})`)
      .join(', ') || 'No items';

    const confidencePct = Math.round((order.confidence_score || 0.9) * 100);

    card.innerHTML = `
      <div class="order-card-header">
        <span class="order-customer-name">${escapeHtml(order.customer_name || 'Customer')}</span>
        <span class="order-tag ${tagClass}">${escapeHtml(order.status || 'new')}</span>
      </div>
      <div class="order-card-meta">
        <span>📅 ${escapeHtml(order.delivery_date || 'TBD')}</span>
        <span>📍 ${escapeHtml(order.area || 'Local')}</span>
      </div>
      <div class="order-card-items-preview">
        ${escapeHtml(itemsSummary)}
      </div>
      <div class="order-card-footer">
        <span class="order-price">${(order.total_amount || 0).toLocaleString()} LKR</span>
        <div class="confidence-indicator" title="Confidence: ${confidencePct}%">
          <div class="confidence-bar">
            <div class="confidence-fill" style="width: ${confidencePct}%;"></div>
          </div>
          <span>${confidencePct}%</span>
        </div>
      </div>
    `;

    ordersListContainer.appendChild(card);
  });
}

// Select Order and Populate Workspace
async function selectOrder(orderId) {
  selectedOrderId = orderId;
  renderOrdersSidebar(); // update active card highlight

  try {
    const res = await fetch(`/api/orders/${orderId}`);
    if (!res.ok) throw new Error('Order not found');
    const order = await res.json();

    populateChatStream(order);
    populateInspector(order);
  } catch (err) {
    console.error('Failed to fetch order details:', err);
    showToast('Failed to load order details', 'error');
  }
}

// Populate WhatsApp Chat Stream
function populateChatStream(order) {
  chatStream.innerHTML = '';
  chatTimeWindow.textContent = `${order.thread_message_count || 0} messages • ${order.thread_start_time || ''}`;

  const msgs = order.thread_messages || [];
  if (msgs.length === 0) {
    chatStream.innerHTML = `<div class="empty-state"><p>No chat messages recorded.</p></div>`;
    return;
  }

  msgs.forEach(m => {
    const bubble = document.createElement('div');
    const isSeller = !m.is_customer;
    bubble.className = `chat-bubble ${isSeller ? 'seller' : 'customer'}`;
    bubble.id = `msg-bubble-${m.message_index}`;

    // Highlight if this message was a source for the order
    const isSource = (order.source_message_ids || []).includes(m.message_index);
    if (isSource) {
      bubble.classList.add('highlighted-source');
    }

    bubble.innerHTML = `
      <div class="chat-bubble-header">
        <span class="chat-sender-name">${escapeHtml(m.sender)}</span>
        <div>
          <span class="msg-index-badge">#${m.message_index}</span>
          <span>${escapeHtml(m.timestamp || '')}</span>
        </div>
      </div>
      <div class="chat-bubble-text">${escapeHtml(m.message_text)}</div>
    `;

    chatStream.appendChild(bubble);
  });
}

// Highlight source message in chat when clicking an item
function highlightMessageSource(sourceIds) {
  document.querySelectorAll('.chat-bubble').forEach(b => b.classList.remove('highlighted-source'));

  if (!sourceIds || sourceIds.length === 0) return;

  sourceIds.forEach(id => {
    const target = document.getElementById(`msg-bubble-${id}`);
    if (target) {
      target.classList.add('highlighted-source');
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
}

// Populate Right Inspector Form
function populateInspector(order) {
  inspectorEmptyState.style.display = 'none';
  inspectorContent.style.display = 'flex';

  // Status Alert
  if (order.status === 'cancelled') {
    inspectorStatusAlert.style.display = 'flex';
    inspectorStatusAlert.className = 'order-alert-box alert-cancelled';
    inspectorAlertIcon.textContent = '🛑';
    inspectorAlertText.textContent = 'Customer requested cancellation for this order. Do not bake!';
  } else if (order.status === 'changed') {
    inspectorStatusAlert.style.display = 'flex';
    inspectorStatusAlert.className = 'order-alert-box alert-changed';
    inspectorAlertIcon.textContent = '⚠️';
    inspectorAlertText.textContent = 'Delivery date or items were modified in the chat thread. Verify details!';
  } else {
    inspectorStatusAlert.style.display = 'none';
  }

  editCustomerName.value = order.customer_name || '';
  editCustomerPhone.value = order.customer_phone || '';

  // Direct WhatsApp Link
  if (order.customer_phone) {
    const cleanPhone = order.customer_phone.replace(/[^\d]/g, '');
    btnWhatsAppDirect.href = `https://wa.me/${cleanPhone}`;
    btnWhatsAppDirect.style.display = 'inline-flex';
  } else {
    btnWhatsAppDirect.style.display = 'none';
  }

  editDeliveryDate.value = order.delivery_date || '';
  editDeliveryTime.value = order.delivery_time || '';
  editDeliveryArea.value = order.area || '';
  editDeliveryAddress.value = order.delivery_address || '';
  editPaymentStatus.value = order.payment_status || 'pending';
  editUserNotes.value = order.user_notes || '';

  const conf = Math.round((order.confidence_score || 0.9) * 100);
  orderConfidenceBadge.innerHTML = `
    <div class="confidence-bar">
      <div class="confidence-fill" style="width: ${conf}%;"></div>
    </div>
    <span>Confidence: ${conf}%</span>
  `;

  // Flags
  inspectorWarningFlags.innerHTML = '';
  (order.flags || []).forEach(flag => {
    const chip = document.createElement('span');
    chip.className = 'pill';
    chip.style.background = 'rgba(245, 158, 11, 0.2)';
    chip.style.color = '#fbbf24';
    chip.textContent = `⚠️ ${flag.replace(/_/g, ' ')}`;
    inspectorWarningFlags.appendChild(chip);
  });

  // Render Items Table
  renderItemsTable(order.items || []);
  calculateTotal();
}

// Render Order Items Table with Catalog Selection
function renderItemsTable(items) {
  itemsTableBody.innerHTML = '';

  items.forEach((item, index) => {
    const tr = document.createElement('tr');
    tr.dataset.index = index;

    // Generate options for catalog items
    let optionsHtml = `<option value="">-- Custom Product --</option>`;
    currentCatalog.forEach(cat => {
      const isSelected = item.catalog_id === cat.id || item.product_name.toLowerCase() === cat.name.toLowerCase();
      optionsHtml += `<option value="${cat.id}" ${isSelected ? 'selected' : ''} data-price="${cat.price}" data-variant="${cat.variant}">${cat.name} (${cat.variant}) - ${cat.price} LKR</option>`;
    });

    const sourceIds = JSON.stringify(item.source_message_ids || []);

    tr.innerHTML = `
      <td>
        <input type="text" class="form-input item-name-input" value="${escapeHtml(item.product_name || '')}" style="width: 100%; margin-bottom: 0.25rem;">
        <select class="form-select item-catalog-select" style="width: 100%; font-size: 0.72rem;">
          ${optionsHtml}
        </select>
        ${item.notes ? `<span class="custom-notes-badge">📝 ${escapeHtml(item.notes)}</span>` : ''}
      </td>
      <td>
        <input type="text" class="form-input item-variant-input" value="${escapeHtml(item.variant || '')}" style="width: 100%;">
      </td>
      <td>
        <input type="number" step="0.5" min="0.5" class="form-input item-qty-input" value="${item.quantity || 1}" style="width: 100%; text-align: center;">
      </td>
      <td>
        <input type="number" step="50" class="form-input item-price-input" value="${item.unit_price || 0}" style="width: 100%; text-align: right;">
      </td>
      <td class="item-subtotal" style="font-weight: 700; text-align: right; color: var(--accent-gold);">
        ${((item.quantity || 1) * (item.unit_price || 0)).toLocaleString()}
      </td>
      <td style="text-align: center;">
        <button class="btn btn-secondary btn-sm" onclick="highlightMessageSource(${sourceIds})" title="Highlight source in chat">🔍</button>
        <button class="btn btn-danger btn-sm" onclick="removeItemRow(${index})" title="Remove item">✕</button>
      </td>
    `;

    // Row change events
    const catSelect = tr.querySelector('.item-catalog-select');
    const nameInput = tr.querySelector('.item-name-input');
    const variantInput = tr.querySelector('.item-variant-input');
    const qtyInput = tr.querySelector('.item-qty-input');
    const priceInput = tr.querySelector('.item-price-input');
    const subtotalCell = tr.querySelector('.item-subtotal');

    catSelect.addEventListener('change', () => {
      const selectedOption = catSelect.options[catSelect.selectedIndex];
      if (selectedOption.value) {
        const catItem = currentCatalog.find(c => c.id == selectedOption.value);
        if (catItem) {
          nameInput.value = catItem.name;
          variantInput.value = catItem.variant;
          priceInput.value = catItem.price;
          updateRowSubtotal();
        }
      }
    });

    const updateRowSubtotal = () => {
      const qty = parseFloat(qtyInput.value) || 0;
      const pr = parseFloat(priceInput.value) || 0;
      const sub = qty * pr;
      subtotalCell.textContent = sub.toLocaleString();
      calculateTotal();
    };

    qtyInput.addEventListener('input', updateRowSubtotal);
    priceInput.addEventListener('input', updateRowSubtotal);

    itemsTableBody.appendChild(tr);
  });
}

function addNewItemRow() {
  const tr = document.createElement('tr');
  const index = itemsTableBody.children.length;
  tr.dataset.index = index;

  let optionsHtml = `<option value="">-- Choose from Catalog --</option>`;
  currentCatalog.forEach(cat => {
    optionsHtml += `<option value="${cat.id}" data-price="${cat.price}" data-variant="${cat.variant}">${cat.name} (${cat.variant}) - ${cat.price} LKR</option>`;
  });

  tr.innerHTML = `
    <td>
      <input type="text" class="form-input item-name-input" placeholder="Product name" style="width: 100%; margin-bottom: 0.25rem;">
      <select class="form-select item-catalog-select" style="width: 100%; font-size: 0.72rem;">
        ${optionsHtml}
      </select>
    </td>
    <td>
      <input type="text" class="form-input item-variant-input" placeholder="1kg / Box 6" style="width: 100%;">
    </td>
    <td>
      <input type="number" step="0.5" min="0.5" class="form-input item-qty-input" value="1" style="width: 100%; text-align: center;">
    </td>
    <td>
      <input type="number" step="50" class="form-input item-price-input" value="0" style="width: 100%; text-align: right;">
    </td>
    <td class="item-subtotal" style="font-weight: 700; text-align: right; color: var(--accent-gold);">0</td>
    <td style="text-align: center;">
      <button class="btn btn-danger btn-sm" onclick="removeItemRow(${index})">✕</button>
    </td>
  `;

  const catSelect = tr.querySelector('.item-catalog-select');
  const nameInput = tr.querySelector('.item-name-input');
  const variantInput = tr.querySelector('.item-variant-input');
  const qtyInput = tr.querySelector('.item-qty-input');
  const priceInput = tr.querySelector('.item-price-input');
  const subtotalCell = tr.querySelector('.item-subtotal');

  catSelect.addEventListener('change', () => {
    const selectedOption = catSelect.options[catSelect.selectedIndex];
    if (selectedOption.value) {
      const catItem = currentCatalog.find(c => c.id == selectedOption.value);
      if (catItem) {
        nameInput.value = catItem.name;
        variantInput.value = catItem.variant;
        priceInput.value = catItem.price;
        const sub = (parseFloat(qtyInput.value) || 1) * catItem.price;
        subtotalCell.textContent = sub.toLocaleString();
        calculateTotal();
      }
    }
  });

  const updateRowSubtotal = () => {
    const qty = parseFloat(qtyInput.value) || 0;
    const pr = parseFloat(priceInput.value) || 0;
    subtotalCell.textContent = (qty * pr).toLocaleString();
    calculateTotal();
  };

  qtyInput.addEventListener('input', updateRowSubtotal);
  priceInput.addEventListener('input', updateRowSubtotal);

  itemsTableBody.appendChild(tr);
}

window.removeItemRow = function(index) {
  const row = itemsTableBody.querySelector(`tr[data-index="${index}"]`);
  if (row) {
    row.remove();
    calculateTotal();
  }
};

function calculateTotal() {
  let total = 0;
  itemsTableBody.querySelectorAll('tr').forEach(row => {
    const qty = parseFloat(row.querySelector('.item-qty-input')?.value || 0);
    const pr = parseFloat(row.querySelector('.item-price-input')?.value || 0);
    total += qty * pr;
  });
  editTotalAmount.textContent = `${total.toLocaleString(undefined, { minimumFractionDigits: 2 })} LKR`;
}

// Gather Current Inspector Form Payload
function getInspectorPayload() {
  const items = [];
  itemsTableBody.querySelectorAll('tr').forEach(row => {
    const catSelect = row.querySelector('.item-catalog-select');
    const name = row.querySelector('.item-name-input').value.trim();
    if (!name) return;

    const variant = row.querySelector('.item-variant-input').value.trim();
    const qty = parseFloat(row.querySelector('.item-qty-input').value) || 1.0;
    const price = parseFloat(row.querySelector('.item-price-input').value) || 0.0;
    const catId = catSelect && catSelect.value ? parseInt(catSelect.value) : null;

    items.push({
      catalog_id: catId,
      product_name: name,
      quantity: qty,
      variant: variant,
      unit_price: price,
      total_price: qty * price,
      notes: '',
      source_message_ids: []
    });
  });

  return {
    customer_name: editCustomerName.value.trim(),
    customer_phone: editCustomerPhone.value.trim(),
    delivery_date: editDeliveryDate.value,
    delivery_time: editDeliveryTime.value.trim(),
    area: editDeliveryArea.value.trim(),
    delivery_address: editDeliveryAddress.value.trim(),
    payment_status: editPaymentStatus.value,
    user_notes: editUserNotes.value.trim(),
    items: items
  };
}

// Confirm Order (Saves correction & ground truth)
async function confirmCurrentOrder() {
  if (!selectedOrderId) return;
  const payload = getInspectorPayload();

  try {
    // 1. Update order with any manual edits
    await fetch(`/api/orders/${selectedOrderId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    // 2. Mark confirmed & write to continuous learning dataset
    const res = await fetch(`/api/orders/${selectedOrderId}/confirm`, {
      method: 'POST'
    });
    const result = await res.json();

    showToast('✓ Order Confirmed! Saved to continuous learning dataset.');
    await checkSystemStatus();
    await loadOrders(selectedOrderId);
  } catch (err) {
    console.error('Confirmation failed:', err);
    showToast('Failed to confirm order', 'error');
  }
}

// Save Edits
async function saveCurrentOrder() {
  if (!selectedOrderId) return;
  const payload = getInspectorPayload();

  try {
    const res = await fetch(`/api/orders/${selectedOrderId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Save failed');

    showToast('Order edits saved successfully');
    await loadOrders(selectedOrderId);
  } catch (err) {
    console.error('Save failed:', err);
    showToast('Failed to save edits', 'error');
  }
}

// Mark Order Cancelled
async function markCurrentOrderCancelled() {
  if (!selectedOrderId) return;
  try {
    await fetch(`/api/orders/${selectedOrderId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'cancelled' })
    });
    showToast('Order marked as CANCELLED (excluded from baking)');
    await loadOrders(selectedOrderId);
  } catch (err) {
    showToast('Error marking cancelled', 'error');
  }
}

// Delete Order
async function deleteCurrentOrder() {
  if (!selectedOrderId) return;
  if (!confirm('Are you sure you want to delete this order?')) return;

  try {
    await fetch(`/api/orders/${selectedOrderId}`, { method: 'DELETE' });
    showToast('Order deleted');
    selectedOrderId = null;
    await loadOrders();
  } catch (err) {
    showToast('Failed to delete order', 'error');
  }
}

function clearInspector() {
  inspectorEmptyState.style.display = 'flex';
  inspectorContent.style.display = 'none';
  chatStream.innerHTML = `<div class="empty-state"><p>No chat selected</p></div>`;
}

// Load Demo Chats
async function loadDemoChats() {
  try {
    showToast('Processing realistic English baking chats...', 'info');
    const res = await fetch('/api/load-sample-chats?engine=auto', { method: 'POST' });
    const data = await res.json();
    showToast(`Loaded ${data.results.length} demo WhatsApp orders!`);
    await loadOrders();
  } catch (err) {
    console.error('Error loading demo chats:', err);
    showToast('Failed to load demo chats', 'error');
  }
}

// Drag & Drop WhatsApp Export (.txt)
function setupDragAndDrop() {
  const dropZone = document.getElementById('chatDropZone');
  const fileInput = document.getElementById('chatFileInput');
  const uploadProgress = document.getElementById('uploadProgress');

  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) handleFileUpload(files[0]);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) handleFileUpload(fileInput.files[0]);
  });

  async function handleFileUpload(file) {
    if (!file.name.endsWith('.txt')) {
      alert('Please upload a WhatsApp .txt export file');
      return;
    }

    uploadProgress.style.display = 'block';
    const enginePref = document.getElementById('selectEnginePreference').value;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('engine', enginePref);

    try {
      const res = await fetch('/api/upload-chat', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      uploadProgress.style.display = 'none';
      closeModal(modalUpload);
      showToast(`Processed ${data.total_messages} messages! Created ${data.orders_created} order(s).`);
      await loadOrders(data.order_ids[0]);
    } catch (err) {
      uploadProgress.style.display = 'none';
      console.error('Upload failed:', err);
      showToast('Error parsing WhatsApp export', 'error');
    }
  }
}

// Catalog Table Rendering & Management
function renderCatalogTable() {
  const tbody = document.getElementById('catalogTableBody');
  tbody.innerHTML = '';

  currentCatalog.forEach(item => {
    const tr = document.createElement('tr');
    const aliases = (item.aliases || []).join(', ');
    tr.innerHTML = `
      <td style="font-weight: 600;">${escapeHtml(item.name)}</td>
      <td><span class="pill">${escapeHtml(item.category)}</span></td>
      <td>${escapeHtml(item.variant)}</td>
      <td style="font-weight: 700; color: var(--accent-gold);">${(item.price).toLocaleString()} LKR</td>
      <td style="font-size: 0.75rem; color: var(--text-dim); max-width: 200px;">${escapeHtml(aliases)}</td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm" onclick="editCatalogPrice(${item.id}, ${item.price})">Edit</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

window.editCatalogPrice = async function(id, currentPrice) {
  const newPrice = prompt('Enter new price in LKR:', currentPrice);
  if (newPrice !== null && !isNaN(newPrice)) {
    const cat = currentCatalog.find(c => c.id === id);
    if (cat) {
      cat.price = parseFloat(newPrice);
      await fetch(`/api/catalog/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cat)
      });
      await loadCatalog();
      renderCatalogTable();
      showToast('Catalog price updated');
    }
  }
};

document.getElementById('btnAddNewCatalogItem').addEventListener('click', async () => {
  const name = prompt('Product Name (e.g. Passion Fruit Gateau):');
  if (!name) return;
  const variant = prompt('Variant (e.g. 1kg, 500g, Box of 6):', '1kg') || '1kg';
  const priceStr = prompt('Price in LKR:', '3500');
  const price = parseFloat(priceStr) || 0;
  const category = prompt('Category (Cakes, Desserts, Savories):', 'Cakes') || 'Cakes';
  const aliasesStr = prompt('Product Aliases (comma-separated):', name.toLowerCase()) || '';
  const aliases = aliasesStr.split(',').map(s => s.trim()).filter(Boolean);

  const payload = {
    name, category, variant, price, aliases
  };

  await fetch('/api/catalog', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  await loadCatalog();
  renderCatalogTable();
  showToast('New product added to catalog');
});

// Settings Modal
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    document.getElementById('settingSellerName').value = data.seller_name || '';
    document.getElementById('settingSellerPhone').value = data.seller_phone || '';
    document.getElementById('settingCurrency').value = data.currency || 'LKR';
    document.getElementById('settingOllamaUrl').value = data.ollama_url || '';
    document.getElementById('settingOllamaModel').value = data.ollama_model || 'qwen3:8b';
  } catch (err) {
    console.error('Failed to load settings:', err);
  }
}

async function saveSettingsForm() {
  const payload = {
    seller_name: document.getElementById('settingSellerName').value,
    seller_phone: document.getElementById('settingSellerPhone').value,
    currency: document.getElementById('settingCurrency').value,
    ollama_url: document.getElementById('settingOllamaUrl').value,
    ollama_model: document.getElementById('settingOllamaModel').value
  };

  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    closeModal(modalSettings);
    showToast('Settings saved!');
    checkSystemStatus();
  } catch (err) {
    showToast('Failed to save settings', 'error');
  }
}

// Modal Helpers
function openModal(modal) {
  modal.classList.add('open');
}

function closeModal(modal) {
  modal.classList.remove('open');
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = 'toast';
  const icon = type === 'error' ? '❌' : (type === 'success' ? '✓' : '💡');
  toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Utility: HTML Escape
function escapeHtml(str) {
  if (typeof str !== 'string') return str ?? '';
  return str.replace(/[&<>"']/g, match => {
    const escapeMap = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    };
    return escapeMap[match];
  });
}

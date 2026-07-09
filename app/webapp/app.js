const API_URL = '/api';

const STATUS_LABELS = {
    'new': 'Новый',
    'confirmed': 'Подтверждён',
    'in_progress': 'В обработке',
    'ready': 'Готов к выдаче',
    'delivering': 'Доставляется',
    'completed': 'Выполнен',
    'cancelled': 'Отменён',
    'pending_sync': 'Ожидает синхронизации',
    'sync_error': 'Ошибка синхронизации',
};

const CATEGORY_ICONS = {
    'iPhone': '📱',
    'iPad': '📲',
    'Mac': '💻',
    'Watch': '⌚',
    'AirPods': '🎧',
    'Vision': '👓',
    'Samsung': '📱',
    'default': '📦',
};

const CATEGORY_DESC = {
    'iPhone': 'Выбрать модель и цену',
    'iPad': 'Для учёбы / чтения / работы',
    'Mac': 'Для работы и творчества',
    'Watch': 'Умные часы Apple',
    'AirPods': 'Беспроводные наушники',
    'Vision': 'Apple Vision Pro',
    'Samsung': 'Открыть каталог',
    'default': 'Посмотреть товары',
};

const app = {
    tg: window.Telegram.WebApp,
    user: null,
    products: [],
    categories: [],
    shops: [],
    cart: [],
    selectedShop: null,
    currentCategory: null,
    currentSearch: '',
    phoneSaved: false,
    tradein: null,
    activeGiveawayId: null,
};

function getCategoryIcon(name) {
    if (!name) return CATEGORY_ICONS.default;
    const key = Object.keys(CATEGORY_ICONS).find(k => name.toLowerCase().includes(k.toLowerCase()));
    return CATEGORY_ICONS[key || 'default'];
}

function getCategoryDesc(name) {
    if (!name) return CATEGORY_DESC.default;
    const key = Object.keys(CATEGORY_DESC).find(k => name.toLowerCase().includes(k.toLowerCase()));
    return CATEGORY_DESC[key || 'default'];
}

function getParentCategory(name) {
    if (!name) return 'iPhone';
    const lower = name.toLowerCase();
    if (lower.includes('iphone')) return 'iPhone';
    if (lower.includes('ipad')) return 'iPad';
    if (lower.includes('mac')) return 'Mac';
    if (lower.includes('watch') || lower.includes('apple watch')) return 'Watch';
    if (lower.includes('airpods')) return 'AirPods';
    if (lower.includes('vision')) return 'Vision';
    if (lower.includes('samsung')) return 'Samsung';
    return name.split(' ')[0];
}

function getProductImagePlaceholder(name) {
    const emoji = getCategoryIcon(name);
    return `<div class="product-img-placeholder">${emoji}</div>`;
}

function getProductImage(product, variant = 'card') {
    if (product.photo_url) {
        const cls = variant === 'detail' ? 'product-detail-img' : 'product-img';
        return `<img class="${cls}" src="${escapeHtml(product.photo_url)}" alt="${escapeHtml(product.name)}" loading="lazy" onerror="this.outerHTML=getProductImagePlaceholder('${escapeJsString(product.category || '')}')">`;
    }
    return getProductImagePlaceholder(product.category || product.name);
}

function getProductTags(p) {
    const tags = [];
    if (p.category && p.category.toLowerCase().includes('iphone')) tags.push('Apple');
    if (p.name.toLowerCase().includes('esim')) tags.push('eSIM');
    if (p.color) tags.push(p.color);
    if (p.memory) tags.push(p.memory);
    if (tags.length === 0) tags.push(p.category || 'Apple');
    return tags.slice(0, 4);
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeJsString(text) {
    if (!text) return '';
    return String(text).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function init() {
    app.tg.ready();
    app.tg.expand();
    app.tg.setHeaderColor('#f5f6f8');
    app.tg.setBackgroundColor('#f5f6f8');

    if (app.tg.initDataUnsafe && app.tg.initDataUnsafe.user) {
        app.user = app.tg.initDataUnsafe.user;
    }

    loadData().then(() => {
        renderHome();
        renderCategoryChips();
        bindEvents();
    }).catch(err => {
        console.error('loadData error:', err);
        document.getElementById('categories-grid').innerHTML = '<div class="empty-state">Ошибка загрузки данных</div>';
    });
}

async function loadData() {
    const [productsRes, categoriesRes, shopsRes, giveawaysRes] = await Promise.all([
        fetch(`${API_URL}/products`),
        fetch(`${API_URL}/categories`),
        fetch(`${API_URL}/shops`),
        fetch(`${API_URL}/giveaways`),
    ]);
    app.products = await productsRes.json();
    app.categories = await categoriesRes.json();
    app.shops = await shopsRes.json();
    app.giveawaysList = await giveawaysRes.json();
    if (app.shops.length > 0) {
        app.selectedShop = app.shops[0];
    }
}

function getHomeCategories() {
    if (app.categories.length > 0) {
        return app.categories.filter(c => c.name).sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || a.name.localeCompare(b.name));
    }
    const parents = new Set();
    app.products.forEach(p => {
        if (p.category) parents.add(getParentCategory(p.category));
    });
    return Array.from(parents).sort().map(name => ({ name }));
}

function renderHome() {
    const categoriesGrid = document.getElementById('categories-grid');
    const homeCategories = getHomeCategories();

    if (homeCategories.length === 0) {
        categoriesGrid.innerHTML = '<div class="empty-state">Категории не найдены</div>';
        return;
    }

    categoriesGrid.innerHTML = homeCategories.map(c => {
        const name = c.name || c;
        const desc = c.description || getCategoryDesc(name);
        const image = c.image_url ? `<img class="category-img" src="${c.image_url}" alt="${escapeHtml(name)}" loading="lazy" onerror="this.style.display='none'">` : '';
        const icon = !c.image_url ? `<div class="category-icon">${c.icon_emoji || getCategoryIcon(name)}</div>` : '';
        const tileClass = `category-card category-tile-${c.tile_size || 'medium'}`;
        return `
        <div class="${tileClass}" data-category="${escapeHtml(name)}">
            <div class="category-left">
                ${image}
                ${icon}
                <div class="category-info">
                    <div class="category-name">${escapeHtml(name)}</div>
                    <div class="category-desc">${escapeHtml(desc)}</div>
                </div>
            </div>
            <div class="category-arrow">›</div>
        </div>
        `;
    }).join('');
}

function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(name).classList.add('active');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const navMap = { home: 'home', catalog: 'catalog', giveaways: 'nav-giveaways', 'giveaway-results-screen': 'nav-giveaways', tradein: 'nav-tradein' };
    const navSelector = navMap[name];
    if (navSelector) {
        const el = navSelector.startsWith('nav-') ? document.getElementById(navSelector) : document.querySelector(`[data-screen="${navSelector}"]`);
        el?.classList.add('active');
    }
}

function getCategoryCount(category) {
    return app.products.filter(p => p.category && (p.category === category || getParentCategory(p.category) === category)).length;
}

function renderCategoryChips() {
    const chips = document.getElementById('category-chips');
    if (!chips) return;

    const counts = {};
    app.products.forEach(p => {
        if (p.category) {
            counts[p.category] = (counts[p.category] || 0) + 1;
        }
    });

    const allCategories = ['Все', ...Object.keys(counts).sort()];
    chips.innerHTML = allCategories.map(c => {
        const count = c === 'Все' ? app.products.length : (counts[c] || 0);
        const active = (c === 'Все' && !app.currentCategory) || c === app.currentCategory ? 'active' : '';
        return `<div class="chip ${active}" data-category="${escapeHtml(c)}">${escapeHtml(c)}<span class="chip-count">${count}</span></div>`;
    }).join('');
}

function renderCatalog(category, search = '') {
    app.currentCategory = category;
    app.currentSearch = search;

    const title = category || 'Каталог';
    document.getElementById('catalog-title').textContent = title;
    document.getElementById('catalog-search-input').value = search;

    renderCategoryChips();

    let filtered = app.products;
    if (category && category !== 'Все') {
        filtered = filtered.filter(p => p.category === category || getParentCategory(p.category) === category);
    }
    if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter(p =>
            p.name.toLowerCase().includes(q) ||
            (p.sku && p.sku.toLowerCase().includes(q))
        );
    }

    const grid = document.getElementById('products-grid');
    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state">Ничего не найдено</div>';
        return;
    }

    grid.innerHTML = filtered.map(p => {
        const img = getProductImage(p, 'card');
        const oldPrice = p.old_price
            ? `<div class="product-old-price">${formatPrice(p.old_price)} ₽</div>`
            : '';
        const tags = getProductTags(p).map(t => `<span class="product-tag-small">${escapeHtml(t)}</span>`).join('');
        return `
        <div class="product-card" data-product-id="${p.id}">
            ${img}
            <div class="product-info">
                <div class="product-name">${escapeHtml(p.name)}</div>
                ${oldPrice}
                <div class="product-price">${formatPrice(p.price)} ₽</div>
                <div class="product-tags-row">${tags}</div>
            </div>
        </div>
        `;
    }).join('');
}

function renderProduct(productId) {
    const p = app.products.find(x => x.id === productId);
    if (!p) return;
    const container = document.getElementById('product-detail');
    const img = getProductImage(p, 'detail');

    const oldPrice = p.old_price
        ? `<div class="product-detail-old-price">${formatPrice(p.old_price)} ₽</div>`
        : '';

    const tags = getProductTags(p).map(t => `<span class="product-tag">${escapeHtml(t)}</span>`).join('');

    const specsMap = p.specs && typeof p.specs === 'object' ? p.specs : {};
    let specsHtml = '';
    for (const [section, fields] of Object.entries(specsMap)) {
        if (typeof fields !== 'object' || fields === null) continue;
        const rows = Object.entries(fields).map(([k, v]) => `
            <tr><td>${escapeHtml(k)}</td><td>${escapeHtml(String(v))}</td></tr>
        `).join('');
        if (!rows) continue;
        specsHtml += `
            <div class="product-section">
                <div class="product-section-title">${escapeHtml(section)}</div>
                <table class="product-specs">${rows}</table>
            </div>
        `;
    }
    if (!specsHtml) {
        specsHtml = `<div class="product-section"><div class="product-section-title">Характеристики</div><table class="product-specs"><tr><td>Модель</td><td>${escapeHtml(p.name)}</td></tr></table></div>`;
    }

    const colorHtml = p.color ? `<div class="product-color-line"><span class="product-color-dot"></span> ${escapeHtml(p.color)}</div>` : '';

    container.innerHTML = `
        <div class="product-detail">
            ${img}
            <div class="product-detail-body">
                <div class="product-detail-name">${escapeHtml(p.name)}</div>
                ${colorHtml}
                <div class="product-detail-price">${formatPrice(p.price)} ₽</div>
                ${oldPrice}
                <div class="product-tags">${tags}</div>

                <div class="product-section">
                    <div class="product-section-title">Описание</div>
                    <div class="product-section-text">${escapeHtml(p.description || (p.name + ' — отличный выбор. Свяжитесь с менеджером для уточнения деталей.'))}</div>
                </div>

                ${specsHtml}
            </div>
            <div class="product-actions">
                <button class="order-btn" data-product-id="${p.id}">Заказать</button>
            </div>
        </div>
    `;
}

function renderCart() {
    const container = document.getElementById('cart-content');
    if (app.cart.length === 0) {
        container.innerHTML = '<div class="empty-state">Корзина пуста</div>';
        return;
    }
    let total = 0;
    const itemsHtml = app.cart.map(item => {
        const product = app.products.find(p => p.id === item.product_id);
        const itemTotal = product.price * item.quantity;
        total += itemTotal;
        return `
            <div class="cart-item">
                <div class="cart-item-info">
                    <div class="cart-item-name">${escapeHtml(product.name)}</div>
                    <div class="cart-item-price">${item.quantity} шт. × ${formatPrice(product.price)} ₽ = ${formatPrice(itemTotal)} ₽</div>
                </div>
                <button class="cart-item-remove" data-product-id="${item.product_id}">🗑️</button>
            </div>
        `;
    }).join('');
    container.innerHTML = itemsHtml + `
        <div class="cart-total">Итого: ${formatPrice(total)} ₽</div>
        <button class="submit-btn" id="checkout-btn">Оформить заказ</button>
    `;
}

async function renderOrders() {
    const container = document.getElementById('orders-content');
    container.innerHTML = '<div class="loading">Загрузка заказов...</div>';
    try {
        const res = await fetch(`${API_URL}/orders`, {
            headers: { 'X-Telegram-Init-Data': app.tg.initData || '' },
        });
        const orders = await res.json();
        if (!orders.length) {
            container.innerHTML = '<div class="empty-state">У вас пока нет заказов</div>';
            return;
        }
        container.innerHTML = orders.map(o => {
            const items = o.items.map(i => `${i.quantity} × ${escapeHtml(i.name)}`).join(', ');
            const status = STATUS_LABELS[o.status] || o.status;
            return `
            <div class="order-card">
                <div class="order-header">
                    <div class="order-number">№ ${escapeHtml(o.number)}</div>
                    <div class="order-status status-${o.status}">${escapeHtml(status)}</div>
                </div>
                <div class="order-date">${formatDate(o.created_at)}</div>
                <div class="order-items">${escapeHtml(items)}</div>
                <div class="order-shop">${escapeHtml(o.shop || '')}</div>
                <div class="order-total">${formatPrice(o.total)} ₽</div>
                <div class="order-sync">CRM: ${o.sync_status === 'success' ? 'создан' : escapeHtml(o.sync_status)}</div>
            </div>
            `;
        }).join('');
    } catch (err) {
        container.innerHTML = '<div class="empty-state">Не удалось загрузить заказы</div>';
    }
}

function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('ru-RU');
}

function updateCartBadge() {
    const badge = document.getElementById('cart-badge');
    if (!badge) return;
    const count = app.cart.reduce((sum, i) => sum + i.quantity, 0);
    badge.textContent = count;
    badge.classList.toggle('show', count > 0);
}

function renderOrderForm() {
    const select = document.getElementById('order-shop');
    select.innerHTML = app.shops.map(s => `<option value="${s.id}" ${app.selectedShop && app.selectedShop.id === s.id ? 'selected' : ''}>${escapeHtml(s.name)}</option>`).join('');

    if (app.user) {
        document.getElementById('order-name').value = app.user.first_name || '';
    }
}

function addToCart(productId) {
    const existing = app.cart.find(i => i.product_id === productId);
    if (existing) {
        existing.quantity += 1;
    } else {
        app.cart.push({ product_id: productId, quantity: 1 });
    }
    updateCartBadge();
    if (app.tg.HapticFeedback) {
        app.tg.HapticFeedback.notificationOccurred('success');
    }
}

const TRADEIN_DEVICES = [
    { type: 'iPhone', name: 'iPhone', models: 'От XR и новее', image: '/webapp/images/cat-iphone.jpg', color: '#f3e8ff' },
    { type: 'iPad', name: 'iPad', models: '8-12 / mini / Air / Pro', image: '/webapp/images/cat-ipad.jpg', color: '#e0f2fe' },
    { type: 'Apple Watch', name: 'Apple Watch', models: 'SE 1-2 / S8-S10 / Ultra 1-2', image: '/webapp/images/cat-watch.jpg', color: '#ffe4e6' },
    { type: 'MacBook', name: 'MacBook', models: 'Air 13/15, Pro 13/14/16', image: '/webapp/images/cat-mac.jpg', color: '#d1fae5' },
];

function renderTradeIn() {
    const grid = document.getElementById('tradein-devices');
    grid.innerHTML = TRADEIN_DEVICES.map(d => `
        <div class="tradein-device" data-type="${escapeHtml(d.type)}">
            <div class="tradein-device-img-wrap" style="background:${d.color}">
                <img src="${d.image}" alt="${escapeHtml(d.name)}" loading="lazy" onerror="this.style.display='none'">
            </div>
            <div class="tradein-device-name">${escapeHtml(d.name)}</div>
            <div class="tradein-device-models">${escapeHtml(d.models)}</div>
        </div>
    `).join('');
}

const TRADEIN_MODELS = {
    'iPhone': [
        'iPhone 17 Pro Max', 'iPhone 17 Pro', 'iPhone 17', 'iPhone 17 Air',
        'iPhone 16 Pro Max', 'iPhone 16 Pro', 'iPhone 16 Plus', 'iPhone 16',
        'iPhone 15 Pro Max', 'iPhone 15 Pro', 'iPhone 15 Plus', 'iPhone 15',
        'iPhone 14 Pro Max', 'iPhone 14 Pro', 'iPhone 14 Plus', 'iPhone 14',
        'iPhone 13 Pro Max', 'iPhone 13 Pro', 'iPhone 13', 'iPhone 11',
    ],
    'iPad': ['iPad Pro', 'iPad Air', 'iPad mini', 'iPad (9-12 поколения)'],
    'Apple Watch': ['Ultra 1-2', 'Series 8-10', 'SE 1-2'],
    'MacBook': ['MacBook Pro 16', 'MacBook Pro 14', 'MacBook Pro 13', 'MacBook Air 15', 'MacBook Air 13'],
};

const TRADEIN_MEMORY = ['64 ГБ', '128 ГБ', '256 ГБ', '512 ГБ', '1 ТБ'];
const TRADEIN_BATTERY = ['Отличное (90–100%)', 'Хорошее (80–89%)', 'Удовлетворительное (70–79%)', 'Ниже 70%'];
const TRADEIN_CONDITION = ['Как новое', 'Есть мелкие следы использования', 'Есть заметные повреждения', 'Не включается / разбит экран'];

const TRADEIN_STEP_ORDER = ['device', 'model', 'memory', 'battery', 'condition', 'confirm'];

function startTradeinWizard() {
    app.tradein = { step: 'device' };
    renderTradeinBody();
}

function tradeinSelectDevice(type) {
    app.tradein = { step: 'model', device_type: type };
    renderTradeinBody();
}

function tradeinBack() {
    if (!app.tradein || app.tradein.step === 'device') {
        app.tradein = null;
        showScreen('home');
        return;
    }
    const idx = TRADEIN_STEP_ORDER.indexOf(app.tradein.step);
    app.tradein.step = TRADEIN_STEP_ORDER[Math.max(0, idx - 1)];
    renderTradeinBody();
}

function radioRowHtml(value) {
    return `<div class="radio-row" data-value="${escapeHtml(value)}"><span>${escapeHtml(value)}</span><span class="radio-dot"></span></div>`;
}

function wizardShell(progress, title, rowsHtml) {
    return `
        <div class="wizard-progress"><div class="wizard-progress-fill" style="width:${progress}%"></div></div>
        <div class="wizard-step-title">${escapeHtml(title)}</div>
        <div id="wizard-choices">${rowsHtml}</div>
        <button class="submit-btn" id="wizard-next" disabled>Далее</button>
    `;
}

function bindWizardChoice(onSelect) {
    let selected = null;
    const choices = document.getElementById('wizard-choices');
    const nextBtn = document.getElementById('wizard-next');
    choices.addEventListener('click', e => {
        const row = e.target.closest('.radio-row');
        if (!row) return;
        selected = row.dataset.value;
        choices.querySelectorAll('.radio-row').forEach(r => r.classList.toggle('selected', r === row));
        nextBtn.disabled = false;
    });
    nextBtn.addEventListener('click', () => {
        if (selected) onSelect(selected);
    });
}

function wizardSummaryRow(label, value) {
    return `<div class="wizard-summary-row"><span class="wizard-summary-label">${escapeHtml(label)}</span><span class="wizard-summary-value">${escapeHtml(value || '—')}</span></div>`;
}

function renderTradeinBody() {
    const body = document.getElementById('tradein-body');
    const step = app.tradein ? app.tradein.step : 'device';

    if (step === 'device') {
        body.innerHTML = `
            <div class="section-header"><span class="section-title">Выберите устройство</span></div>
            <div class="tradein-device-grid" id="tradein-devices"></div>
            <div class="section-header" style="margin-top:24px;"><span class="section-title">Как это работает</span></div>
            <div class="how-it-works">
                <div class="how-step">
                    <div class="how-number">1</div>
                    <div class="how-info">
                        <div class="how-title">Оцените устройство</div>
                        <div class="how-desc">Ответьте на несколько вопросов о состоянии</div>
                    </div>
                </div>
                <div class="how-step">
                    <div class="how-number">2</div>
                    <div class="how-info">
                        <div class="how-title">Принесите в магазин</div>
                        <div class="how-desc">Проведём диагностику за 15 минут</div>
                    </div>
                </div>
                <div class="how-step">
                    <div class="how-number">3</div>
                    <div class="how-info">
                        <div class="how-title">Получите скидку</div>
                        <div class="how-desc">Используйте при покупке нового устройства</div>
                    </div>
                </div>
            </div>
        `;
        renderTradeIn();
        return;
    }

    const stepIndex = { model: 1, memory: 2, battery: 3, condition: 4, confirm: 5 }[step];
    const progress = Math.round((stepIndex / 5) * 100);

    if (step === 'model') {
        const models = TRADEIN_MODELS[app.tradein.device_type] || TRADEIN_MODELS['iPhone'];
        body.innerHTML = wizardShell(progress, 'Выберите модель', models.map(radioRowHtml).join(''));
        bindWizardChoice(value => {
            app.tradein.model = value;
            app.tradein.step = 'memory';
            renderTradeinBody();
        });
        return;
    }
    if (step === 'memory') {
        body.innerHTML = wizardShell(progress, 'Объём памяти', TRADEIN_MEMORY.map(radioRowHtml).join(''));
        bindWizardChoice(value => {
            app.tradein.memory = value;
            app.tradein.step = 'battery';
            renderTradeinBody();
        });
        return;
    }
    if (step === 'battery') {
        body.innerHTML = wizardShell(progress, 'Оцените состояние батареи', TRADEIN_BATTERY.map(radioRowHtml).join(''));
        bindWizardChoice(value => {
            app.tradein.battery = value;
            app.tradein.step = 'condition';
            renderTradeinBody();
        });
        return;
    }
    if (step === 'condition') {
        body.innerHTML = wizardShell(progress, 'Состояние устройства', TRADEIN_CONDITION.map(radioRowHtml).join(''));
        bindWizardChoice(value => {
            app.tradein.condition = value;
            app.tradein.step = 'confirm';
            renderTradeinBody();
        });
        return;
    }
    if (step === 'confirm') {
        const t = app.tradein;
        body.innerHTML = `
            <div class="wizard-progress"><div class="wizard-progress-fill" style="width:100%"></div></div>
            <div class="wizard-step-title">Подтвердите данные</div>
            <div class="wizard-summary">
                ${wizardSummaryRow('Тип устройства', t.device_type)}
                ${wizardSummaryRow('Модель', t.model)}
                ${wizardSummaryRow('Конфигурация', t.memory)}
                ${wizardSummaryRow('Состояние батареи', t.battery)}
                ${wizardSummaryRow('Состояние устройства', t.condition)}
            </div>
            <button class="submit-btn" id="tradein-submit">Подтвердить</button>
        `;
        document.getElementById('tradein-submit').addEventListener('click', submitTradein);
    }
}

async function submitTradein() {
    const t = app.tradein;
    const btn = document.getElementById('tradein-submit');
    btn.disabled = true;
    btn.textContent = 'Отправка...';
    const { ok, data } = await apiFetch('/tradeins', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            device_type: t.device_type,
            model: t.model,
            memory: t.memory,
            battery: t.battery,
            condition: t.condition,
        }),
    });
    if (ok) {
        showToast('Заявка на Trade-in отправлена!');
        app.tradein = null;
        showScreen('home');
    } else {
        btn.disabled = false;
        btn.textContent = 'Подтвердить';
        app.tg.showAlert('Ошибка: ' + (data && data.detail ? data.detail : 'не удалось отправить заявку'));
    }
}

function getActiveGiveaway() {
    if (!app.giveawaysList) return null;
    return app.giveawaysList.find(g => g.status === 'active') || null;
}

function applyGiveawayStats(data) {
    const statValues = document.querySelectorAll('#giveaways .giveaway-stat-value');
    if (statValues[0]) statValues[0].innerHTML = `${data.my_tickets} <span>билетов</span>`;
    if (statValues[1]) statValues[1].textContent = data.invited_count;
}

async function openGiveawaysScreen() {
    showScreen('giveaways');
    const active = getActiveGiveaway();
    app.activeGiveawayId = active ? active.id : null;
    if (!active) return;
    const { ok, data } = await apiFetch(`/giveaways/${active.id}`);
    if (ok && data) applyGiveawayStats(data);
}

async function joinActiveGiveaway() {
    if (!app.activeGiveawayId) {
        app.tg.showAlert('Сейчас нет активных розыгрышей.');
        return;
    }
    const { ok, data } = await apiFetch(`/giveaways/${app.activeGiveawayId}/join`, { method: 'POST' });
    if (ok) {
        applyGiveawayStats(data);
        showToast('Вы участвуете в розыгрыше!');
    } else {
        app.tg.showAlert('Ошибка: ' + (data && data.detail ? data.detail : 'попробуйте позже'));
    }
}

async function inviteToActiveGiveaway() {
    if (!app.activeGiveawayId) return;
    const { ok, data } = await apiFetch(`/giveaways/${app.activeGiveawayId}/invite`, { method: 'POST' });
    if (ok) {
        applyGiveawayStats(data);
        showToast('Спасибо за приглашение!');
    } else {
        app.tg.showAlert('Сначала подтвердите участие в розыгрыше.');
    }
}

async function openGiveawayResults() {
    showScreen('giveaway-results-screen');
    const container = document.getElementById('giveaway-results-content');
    const completed = (app.giveawaysList || []).filter(g => g.status === 'completed');
    if (!completed.length) {
        container.innerHTML = '<div class="empty-state">История завершённых розыгрышей пока пуста.</div>';
        return;
    }
    container.innerHTML = completed.map(g => `
        <div class="result-card">
            <div class="result-card-title">${escapeHtml(g.title)}</div>
            <div class="result-card-date">Завершён ${formatDate(g.created_at)}</div>
            <div class="result-card-winners">🏆 0 победителей</div>
        </div>
    `).join('');
}

function formatPrice(value) {
    if (value === null || value === undefined) return '-';
    return Math.round(value).toLocaleString('ru-RU');
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toast.classList.remove('show'), 2500);
}

function closeSheet() {
    document.getElementById('sheet-overlay').classList.remove('show');
}

function openSheet({ title, text = '', bodyHtml = '', confirmText = 'Отправить', cancelText = 'Отмена', showCancel = true, onConfirm }) {
    document.getElementById('sheet-title').textContent = title;
    document.getElementById('sheet-text').innerHTML = text;
    document.getElementById('sheet-body').innerHTML = bodyHtml;
    const confirmBtn = document.getElementById('sheet-confirm');
    confirmBtn.textContent = confirmText;
    confirmBtn.classList.toggle('hidden', !confirmText);
    const cancelBtn = document.getElementById('sheet-cancel');
    cancelBtn.textContent = cancelText;
    cancelBtn.classList.toggle('hidden', !showCancel);

    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
    if (onConfirm) {
        newConfirmBtn.addEventListener('click', onConfirm);
    }

    document.getElementById('sheet-overlay').classList.add('show');
}

async function apiFetch(path, options = {}) {
    const headers = Object.assign({ 'X-Telegram-Init-Data': app.tg.initData || '' }, options.headers || {});
    const res = await fetch(`${API_URL}${path}`, Object.assign({}, options, { headers }));
    let data = null;
    try {
        data = await res.json();
    } catch (e) {
        data = null;
    }
    return { ok: res.ok, status: res.status, data };
}

function openPhoneSheet(onSaved) {
    openSheet({
        title: 'Укажите номер телефона',
        text: 'Без номера нельзя подключить бонусную программу и оформить заявку. Менеджер свяжется с вами по этому номеру.',
        bodyHtml: '<input type="tel" class="sheet-input" id="phone-input" placeholder="+7 900 000-00-00">',
        confirmText: 'Сохранить',
        onConfirm: async () => {
            const phone = document.getElementById('phone-input').value.trim();
            if (!phone) return;
            const { ok, data } = await apiFetch('/profile/phone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone }),
            });
            if (ok) {
                app.phoneSaved = true;
                closeSheet();
                document.getElementById('loyalty-banner')?.classList.add('hidden');
                showToast('Телефон сохранён');
                if (onSaved) onSaved();
            } else {
                app.tg.showAlert('Ошибка: ' + (data && data.detail ? data.detail : 'не удалось сохранить телефон'));
            }
        },
    });
}

async function sendLead(source, { productId = null, message = null, silent = false } = {}) {
    const { ok, status, data } = await apiFetch('/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, product_id: productId, message }),
    });
    if (ok) {
        app.phoneSaved = true;
        if (!silent) showToast('Заявка отправлена. Менеджер свяжется с вами в течение 5 минут.');
        return true;
    }
    if (status === 409 && data && data.detail === 'phone_required') {
        openPhoneSheet(() => sendLead(source, { productId, message, silent }));
        return false;
    }
    app.tg.showAlert('Ошибка: ' + (data && data.detail ? data.detail : 'не удалось отправить заявку'));
    return false;
}

function confirmProductOrder(product) {
    openSheet({
        title: 'Подтвердите заявку',
        text: 'После оформления заявки менеджер свяжется с вами в течение 5 минут в рабочее время.',
        bodyHtml: `
            <div class="sheet-product-card">
                <div class="sheet-product-name">${escapeHtml(product.name)}</div>
                <div class="sheet-product-price">${formatPrice(product.price)} ₽</div>
            </div>
        `,
        confirmText: 'Отправить заявку',
        onConfirm: async () => {
            const success = await sendLead('product', { productId: product.id });
            if (success) closeSheet();
        },
    });
}

function confirmBestPrice() {
    openSheet({
        title: 'Узнать лучшую цену',
        text: 'Ответим за 2–5 минут. Подберём и забронируем.',
        confirmText: 'Написать менеджеру',
        onConfirm: async () => {
            const success = await sendLead('best_price');
            if (success) closeSheet();
        },
    });
}

function confirmContactManager() {
    openSheet({
        title: 'Написать менеджеру',
        text: 'Оставьте заявку — менеджер скоро свяжется с вами в рабочее время.',
        confirmText: 'Связаться с менеджером',
        onConfirm: async () => {
            const success = await sendLead('contact_manager');
            if (success) closeSheet();
        },
    });
}

function bindEvents() {
    document.querySelectorAll('[data-screen="home"], [data-screen="catalog"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const screen = btn.dataset.screen;
            if (screen === 'catalog') {
                renderCatalog(null);
            }
            showScreen(screen);
        });
    });

    document.getElementById('nav-giveaways').addEventListener('click', openGiveawaysScreen);
    document.getElementById('nav-tradein').addEventListener('click', () => {
        startTradeinWizard();
        showScreen('tradein');
    });

    document.getElementById('categories-grid').addEventListener('click', e => {
        const card = e.target.closest('.category-card');
        if (!card) return;
        renderCatalog(card.dataset.category);
        showScreen('catalog');
    });

    function doSearch(inputId) {
        const input = document.getElementById(inputId);
        const q = input.value.trim();
        renderCatalog(null, q);
        showScreen('catalog');
    }

    document.getElementById('search-go').addEventListener('click', () => doSearch('search-input'));
    document.getElementById('search-input').addEventListener('keypress', e => {
        if (e.key === 'Enter') doSearch('search-input');
    });

    document.getElementById('catalog-search-go').addEventListener('click', () => doSearch('catalog-search-input'));
    document.getElementById('catalog-search-input').addEventListener('keypress', e => {
        if (e.key === 'Enter') doSearch('catalog-search-input');
    });

    document.getElementById('category-chips').addEventListener('click', e => {
        const chip = e.target.closest('.chip');
        if (!chip) return;
        const cat = chip.dataset.category;
        renderCatalog(cat === 'Все' ? null : cat, app.currentSearch);
    });

    document.getElementById('back-home').addEventListener('click', () => showScreen('home'));
    document.getElementById('back-catalog').addEventListener('click', () => showScreen('catalog'));
    document.getElementById('back-cart').addEventListener('click', () => showScreen('home'));
    document.getElementById('back-order').addEventListener('click', () => showScreen('cart'));
    document.getElementById('back-orders').addEventListener('click', () => showScreen('home'));
    document.getElementById('back-tradein').addEventListener('click', tradeinBack);
    document.getElementById('back-giveaways').addEventListener('click', () => showScreen('home'));
    document.getElementById('back-giveaway-results').addEventListener('click', () => showScreen('giveaways'));
    document.getElementById('success-home').addEventListener('click', () => showScreen('home'));

    document.getElementById('tradein-start').addEventListener('click', () => {
        document.getElementById('tradein-devices').scrollIntoView({ behavior: 'smooth' });
    });
    document.getElementById('tradein-devices').addEventListener('click', e => {
        const card = e.target.closest('.tradein-device');
        if (!card) return;
        tradeinSelectDevice(card.dataset.type);
    });
    document.getElementById('giveaway-join').addEventListener('click', joinActiveGiveaway);
    document.getElementById('giveaway-invite').addEventListener('click', inviteToActiveGiveaway);
    document.getElementById('giveaway-results').addEventListener('click', openGiveawayResults);

    document.getElementById('products-grid').addEventListener('click', e => {
        const card = e.target.closest('.product-card');
        if (!card) return;
        renderProduct(parseInt(card.dataset.productId));
        showScreen('product');
    });

    document.getElementById('product-detail').addEventListener('click', e => {
        const orderBtn = e.target.closest('.order-btn');
        if (!orderBtn) return;
        const productId = parseInt(orderBtn.dataset.productId);
        const product = app.products.find(p => p.id === productId);
        if (product) confirmProductOrder(product);
    });

    document.getElementById('cart-content').addEventListener('click', e => {
        const removeBtn = e.target.closest('.cart-item-remove');
        if (removeBtn) {
            const id = parseInt(removeBtn.dataset.productId);
            app.cart = app.cart.filter(i => i.product_id !== id);
            updateCartBadge();
            renderCart();
            return;
        }
        const btn = e.target.closest('#checkout-btn');
        if (!btn) return;
        renderOrderForm();
        showScreen('order');
    });

    document.getElementById('order-form').addEventListener('submit', async e => {
        e.preventDefault();
        if (app.cart.length === 0) {
            app.tg.showAlert('Корзина пуста');
            return;
        }
        const payload = {
            telegram_id: app.user ? app.user.id : 0,
            name: document.getElementById('order-name').value,
            phone: document.getElementById('order-phone').value,
            city: document.getElementById('order-city').value,
            delivery: document.getElementById('order-delivery').value,
            shop_id: parseInt(document.getElementById('order-shop').value),
            comment: document.getElementById('order-comment').value,
            items: app.cart,
        };
        try {
            const res = await fetch(`${API_URL}/orders`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': app.tg.initData || '',
                },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (res.ok) {
                app.cart = [];
                updateCartBadge();
                document.getElementById('success-text').textContent = `Заказ №${data.number} на сумму ${formatPrice(data.total)} ₽`;
                showScreen('success');
            } else {
                app.tg.showAlert('Ошибка: ' + (data.detail || 'не удалось создать заказ'));
            }
        } catch (err) {
            app.tg.showAlert('Ошибка сети: ' + err.message);
        }
    });

    document.getElementById('chat-fab').addEventListener('click', confirmContactManager);

    document.getElementById('loyalty-btn').addEventListener('click', () => openPhoneSheet());

    document.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', () => {
            const action = el.dataset.action;
            if (action === 'tradein') {
                startTradeinWizard();
                showScreen('tradein');
            } else if (action === 'best-price') {
                confirmBestPrice();
            } else if (action === 'giveaways') {
                openGiveawaysScreen();
            }
        });
    });

    document.querySelector('.scenarios-section').addEventListener('click', e => {
        const card = e.target.closest('[data-lead-source]');
        if (!card) return;
        sendLead(card.dataset.leadSource);
    });

    document.getElementById('sheet-close').addEventListener('click', closeSheet);
    document.getElementById('sheet-cancel').addEventListener('click', closeSheet);
    document.getElementById('sheet-overlay').addEventListener('click', e => {
        if (e.target.id === 'sheet-overlay') closeSheet();
    });
}

init();

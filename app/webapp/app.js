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
        return `<img class="${cls}" src="${product.photo_url}" alt="${escapeHtml(product.name)}" onerror="this.outerHTML=getProductImagePlaceholder('${escapeJsString(product.category || '')}')">`;
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
    const [productsRes, categoriesRes, shopsRes] = await Promise.all([
        fetch(`${API_URL}/products`),
        fetch(`${API_URL}/categories`),
        fetch(`${API_URL}/shops`),
    ]);
    app.products = await productsRes.json();
    app.categories = await categoriesRes.json();
    app.shops = await shopsRes.json();
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
    const navMap = { home: 'home', catalog: 'catalog', cart: 'nav-cart', orders: 'nav-orders' };
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
                <button class="add-to-cart-btn" data-product-id="${p.id}">В корзину</button>
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
        const telegramId = app.user ? app.user.id : 0;
        const res = await fetch(`${API_URL}/orders?telegram_id=${telegramId}`);
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

function formatPrice(value) {
    if (value === null || value === undefined) return '-';
    return Math.round(value).toLocaleString('ru-RU');
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

    document.getElementById('nav-giveaways').addEventListener('click', () => {
        showScreen('giveaways');
    });

    document.getElementById('nav-tradein').addEventListener('click', () => {
        renderTradeIn();
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
    document.getElementById('back-tradein').addEventListener('click', () => showScreen('home'));
    document.getElementById('back-giveaways').addEventListener('click', () => showScreen('home'));
    document.getElementById('success-home').addEventListener('click', () => showScreen('home'));

    document.getElementById('tradein-start').addEventListener('click', () => {
        app.tg.showAlert('Оценка Trade-in запускается в основном боте. Отправьте /tradein');
    });
    document.getElementById('tradein-devices').addEventListener('click', e => {
        const card = e.target.closest('.tradein-device');
        if (!card) return;
        app.tg.showAlert('Trade-in ' + card.dataset.type + ': отправьте заявку через основного бота /tradein');
    });
    document.getElementById('giveaway-join').addEventListener('click', () => {
        app.tg.showAlert('Розыгрыш завершён. Следите за новыми акциями в канале!');
    });
    document.getElementById('giveaway-invite').addEventListener('click', () => {
        app.tg.showAlert('Поделитесь ссылкой на бота, чтобы пригласить друзей.');
    });
    document.getElementById('giveaway-results').addEventListener('click', () => {
        app.tg.showAlert('Результаты публикуются в канале.');
    });

    document.getElementById('products-grid').addEventListener('click', e => {
        const card = e.target.closest('.product-card');
        if (!card) return;
        renderProduct(parseInt(card.dataset.productId));
        showScreen('product');
    });

    document.getElementById('product-detail').addEventListener('click', e => {
        const addBtn = e.target.closest('.add-to-cart-btn');
        const orderBtn = e.target.closest('.order-btn');
        if (!addBtn && !orderBtn) return;
        const productId = parseInt((addBtn || orderBtn).dataset.productId);
        addToCart(productId);
        if (orderBtn) {
            renderOrderForm();
            showScreen('order');
        } else {
            app.tg.showAlert('Товар добавлен в корзину');
        }
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
                headers: { 'Content-Type': 'application/json' },
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

    document.getElementById('chat-fab').addEventListener('click', () => {
        app.tg.showAlert('Напишите менеджеру в основном боте.');
    });

    document.getElementById('loyalty-btn').addEventListener('click', () => {
        app.tg.showAlert('Завершение профиля доступно в основном боте.');
    });

    document.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', () => {
            const action = el.dataset.action;
            if (action === 'tradein') {
                renderTradeIn();
                showScreen('tradein');
            } else if (action === 'contact') {
                app.tg.showAlert('Заявка менеджеру оформляется через бота. Нажмите «Написать менеджеру»');
            } else if (action === 'giveaways') {
                showScreen('giveaways');
            }
        });
    });
}

init();

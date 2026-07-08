const API_URL = '/api';

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
    const key = Object.keys(CATEGORY_ICONS).find(k => name.toLowerCase().includes(k.toLowerCase()));
    return CATEGORY_ICONS[key || 'default'];
}

function getCategoryDesc(name) {
    const key = Object.keys(CATEGORY_DESC).find(k => name.toLowerCase().includes(k.toLowerCase()));
    return CATEGORY_DESC[key || 'default'];
}

function getParentCategory(name) {
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

function getProductTags(p) {
    const tags = [];
    if (p.category) tags.push('Apple');
    if (p.name.toLowerCase().includes('esim')) tags.push('Apple iPhone 17 (eSim)');
    if (p.name.toLowerCase().includes('new') || p.name.toLowerCase().includes('новый')) tags.push('New');
    if (p.name.toLowerCase().includes('ru') || p.description?.toLowerCase().includes('rustore')) tags.push('Без RuStore');
    if (tags.length === 0) tags.push(p.category || 'Apple');
    return tags.slice(0, 4);
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
    const parents = new Set();
    app.products.forEach(p => {
        if (p.category) parents.add(getParentCategory(p.category));
    });
    return Array.from(parents).sort();
}

function renderHome() {
    const categoriesGrid = document.getElementById('categories-grid');
    const homeCategories = getHomeCategories();

    if (homeCategories.length === 0) {
        categoriesGrid.innerHTML = '<div class="empty-state">Категории не найдены</div>';
        return;
    }

    categoriesGrid.innerHTML = homeCategories.map(c => `
        <div class="category-card" data-category="${c}">
            <div class="category-icon">${getCategoryIcon(c)}</div>
            <div class="category-info">
                <div class="category-name">${c}</div>
                <div class="category-desc">${getCategoryDesc(c)}</div>
            </div>
        </div>
    `).join('');
}

function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(name).classList.add('active');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    if (name === 'home') document.querySelector('[data-screen="home"]')?.classList.add('active');
    if (name === 'catalog') document.querySelector('[data-screen="catalog"]')?.classList.add('active');
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
        return `<div class="chip ${active}" data-category="${c}">${c}<span class="chip-count">${count}</span></div>`;
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
        const img = p.photo_url
            ? `<img class="product-img" src="${p.photo_url}" alt="${p.name}" onerror="this.outerHTML=getProductImagePlaceholder('${p.category || ''}')">`
            : getProductImagePlaceholder(p.category || p.name);
        const oldPrice = p.old_price
            ? `<div class="product-old-price">${formatPrice(p.old_price)} ₽</div>`
            : '';
        return `
        <div class="product-card" data-product-id="${p.id}">
            ${img}
            <div class="product-info">
                <div class="product-name">${p.name}</div>
                ${oldPrice}
                <div class="product-price">${formatPrice(p.price)} ₽</div>
                <div class="product-stock">${p.stock > 0 ? 'В наличии' : 'Нет в наличии'}</div>
            </div>
        </div>
        `;
    }).join('');
}

function renderProduct(productId) {
    const p = app.products.find(x => x.id === productId);
    if (!p) return;
    const container = document.getElementById('product-detail');
    const img = p.photo_url
        ? `<img class="product-detail-img" src="${p.photo_url}" alt="${p.name}" onerror="this.outerHTML=getProductImagePlaceholder('${p.category || ''}')">`
        : getProductImagePlaceholder(p.category || p.name).replace('product-img-placeholder', 'product-detail-img-placeholder');

    const oldPrice = p.old_price
        ? `<div class="product-detail-old-price">${formatPrice(p.old_price)} ₽</div>`
        : '';

    const tags = getProductTags(p).map(t => `<span class="product-tag">${t}</span>`).join('');

    const specs = [
        ['Серия', getParentCategory(p.category || 'iPhone')],
        ['Память', extractMemory(p.name) || '—'],
        ['Диагональ', '6.3"'],
        ['Разрешение', '2622 × 1206 пикселей'],
    ];

    const specsRows = specs.map(([k, v]) => `
        <tr><td>${k}</td><td>${v}</td></tr>
    `).join('');

    container.innerHTML = `
        <div class="product-detail">
            ${img}
            <div class="product-detail-body">
                <div class="product-detail-name">${p.name}</div>
                <div class="product-detail-price">${formatPrice(p.price)} ₽</div>
                ${oldPrice}
                <div class="product-tags">${tags}</div>

                <div class="product-section">
                    <div class="product-section-title">Описание</div>
                    <div class="product-section-text">${p.description || (p.name + ' — отличный выбор. Свяжитесь с менеджером для уточнения деталей.')}</div>
                </div>

                <div class="product-section">
                    <div class="product-section-title">Характеристики</div>
                    <table class="product-specs">${specsRows}</table>
                </div>

                <button class="add-to-cart-btn" data-product-id="${p.id}">В корзину</button>
                <button class="order-btn" data-product-id="${p.id}">Заказать</button>
            </div>
        </div>
    `;
}

function extractMemory(name) {
    const match = name.match(/(\d+\s*(GB|Gb|гб|ГБ|TB|Tb|тб|ТБ))/i);
    return match ? match[1] : '';
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
                    <div class="cart-item-name">${product.name}</div>
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

function updateCartBadge() {
    const badge = document.getElementById('cart-badge');
    const count = app.cart.reduce((sum, i) => sum + i.quantity, 0);
    badge.textContent = count;
    badge.classList.toggle('show', count > 0);
}

function renderOrderForm() {
    const select = document.getElementById('order-shop');
    select.innerHTML = app.shops.map(s => `<option value="${s.id}" ${app.selectedShop && app.selectedShop.id === s.id ? 'selected' : ''}>${s.name}</option>`).join('');

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

    document.getElementById('nav-cart').addEventListener('click', () => {
        renderCart();
        showScreen('cart');
    });

    document.getElementById('nav-orders').addEventListener('click', () => {
        app.tg.showAlert('История заказов доступна в основном боте.');
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
    document.getElementById('success-home').addEventListener('click', () => showScreen('home'));

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

    document.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', () => {
            const action = el.dataset.action;
            if (action === 'tradein') {
                app.tg.showAlert('Trade-in оформляется через основного бота. Отправьте /tradein');
            } else if (action === 'contact') {
                app.tg.showAlert('Заявка менеджеру оформляется через бота. Нажмите «Написать менеджеру»');
            } else if (action === 'giveaways') {
                app.tg.showAlert('Розыгрыши проводятся в канале. Следите за анонсами!');
            }
        });
    });
}

init();

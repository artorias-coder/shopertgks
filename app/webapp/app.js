const API_URL = '/api';

const app = {
    tg: window.Telegram.WebApp,
    user: null,
    products: [],
    categories: [],
    shops: [],
    cart: [],
    selectedShop: null,
    currentCategory: null,
};

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

function renderHome() {
    const shopsRow = document.getElementById('shops-row');
    shopsRow.innerHTML = app.shops.map(s => `
        <div class="shop-chip ${app.selectedShop && app.selectedShop.id === s.id ? 'active' : ''}" data-shop-id="${s.id}" style="border-color:${s.color}; ${app.selectedShop && app.selectedShop.id === s.id ? `background:${s.color};color:#fff` : ''}">
            ${s.name}
        </div>
    `).join('');

    const categoriesGrid = document.getElementById('categories-grid');
    categoriesGrid.innerHTML = app.categories.map(c => `
        <div class="category-card" data-category="${c}">
            <div class="category-name">${c}</div>
            <div class="category-desc">Выбрать модель и цену</div>
        </div>
    `).join('');
}

function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(name).classList.add('active');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    if (name === 'home') document.querySelector('[data-screen="home"]').classList.add('active');
    if (name === 'catalog') document.querySelector('[data-screen="catalog"]').classList.add('active');
}

function renderCatalog(category, search = '') {
    app.currentCategory = category;
    document.getElementById('catalog-title').textContent = category || 'Каталог';

    let filtered = app.products;
    if (category) {
        filtered = filtered.filter(p => p.category === category);
    }
    if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter(p => p.name.toLowerCase().includes(q) || (p.sku && p.sku.toLowerCase().includes(q)));
    }

    const grid = document.getElementById('products-grid');
    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state">Ничего не найдено</div>';
        return;
    }

    grid.innerHTML = filtered.map(p => {
        const priceText = p.old_price
            ? `<div class="product-old-price">Стоимость: ${formatPrice(p.old_price)} ₽</div>
               <div class="product-price">Стоимость по акции: ${formatPrice(p.price)} ₽</div>`
            : `<div class="product-price">${formatPrice(p.price)} ₽</div>`;
        return `
        <div class="product-card" data-product-id="${p.id}">
            <img class="product-img" src="${p.photo_url || ''}" alt="${p.name}" onerror="this.style.display='none'">
            <div class="product-info">
                <div class="product-name">${p.name}</div>
                ${priceText}
                <div class="product-stock">${p.stock > 0 ? `В наличии: ${p.stock} шт.` : 'Нет в наличии'}</div>
            </div>
        </div>
        `;
    }).join('');
}

function renderProduct(productId) {
    const p = app.products.find(x => x.id === productId);
    if (!p) return;
    const container = document.getElementById('product-detail');
    const priceText = p.old_price
        ? `<div class="product-detail-old-price">Стоимость: ${formatPrice(p.old_price)} ₽</div>
           <div class="product-detail-price">Стоимость по акции: ${formatPrice(p.price)} ₽</div>`
        : `<div class="product-detail-price">${formatPrice(p.price)} ₽</div>`;

    container.innerHTML = `
        <img class="product-detail-img" src="${p.photo_url || ''}" alt="${p.name}" onerror="this.style.display='none'">
        <div class="product-detail-info">
            <div class="product-detail-name">${p.name}</div>
            ${priceText}
            <div class="product-detail-stock">${p.stock > 0 ? `В наличии: ${p.stock} шт.` : 'Нет в наличии'}</div>
            <div class="product-detail-desc">${p.description || ''}</div>
            <button class="add-to-cart-btn" data-product-id="${p.id}">В корзину</button>
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
                <div class="cart-item-name">${product.name}</div>
                <div class="cart-item-price">${item.quantity} шт. × ${formatPrice(product.price)} ₽ = ${formatPrice(itemTotal)} ₽</div>
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

    document.getElementById('shops-row').addEventListener('click', e => {
        const chip = e.target.closest('.shop-chip');
        if (!chip) return;
        app.selectedShop = app.shops.find(s => s.id === parseInt(chip.dataset.shopId));
        renderHome();
    });

    document.getElementById('categories-grid').addEventListener('click', e => {
        const card = e.target.closest('.category-card');
        if (!card) return;
        renderCatalog(card.dataset.category);
        showScreen('catalog');
    });

    document.getElementById('search-input').addEventListener('input', e => {
        const q = e.target.value.trim();
        if (q.length > 2) {
            renderCatalog(null, q);
            showScreen('catalog');
        }
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
        const btn = e.target.closest('.add-to-cart-btn');
        if (!btn) return;
        const productId = parseInt(btn.dataset.productId);
        const existing = app.cart.find(i => i.product_id === productId);
        if (existing) {
            existing.quantity += 1;
        } else {
            app.cart.push({ product_id: productId, quantity: 1 });
        }
        updateCartBadge();
        app.tg.showAlert('Товар добавлен в корзину');
    });

    document.getElementById('cart-content').addEventListener('click', e => {
        const btn = e.target.closest('#checkout-btn');
        if (!btn) return;
        renderOrderForm();
        showScreen('order');
    });

    document.getElementById('order-form').addEventListener('submit', async e => {
        e.preventDefault();
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

    document.querySelectorAll('.action-card').forEach(card => {
        card.addEventListener('click', () => {
            const action = card.dataset.action;
            if (action === 'tradein') {
                app.tg.showAlert('Trade-in оформляется через основного бота. Отправьте /tradein');
            } else if (action === 'contact') {
                app.tg.showAlert('Заявка менеджеру оформляется через бота. Нажмите «Написать менеджеру»');
            }
        });
    });
}

init();

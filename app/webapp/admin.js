const API_BASE = '/admin/api';

function $(id) { return document.getElementById(id); }

let currentImageFile = null;

async function api(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, options);
    if (res.status === 401) {
        $('admin-panel').style.display = 'none';
        $('login-box').style.display = 'block';
        throw new Error('Unauthorized');
    }
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
    }
    return res.json();
}

async function login() {
    const password = $('admin-password').value;
    try {
        await fetch('/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `password=${encodeURIComponent(password)}`,
        });
        $('login-box').style.display = 'none';
        $('admin-panel').style.display = 'block';
        $('login-error').style.display = 'none';
        await loadCategories();
        await loadProducts();
    } catch (e) {
        $('login-error').style.display = 'block';
    }
}

async function logout() {
    await fetch('/admin/logout', { method: 'POST' }).catch(() => {});
    document.cookie = 'admin_token=; Max-Age=0; path=/';
    location.reload();
}

async function uploadFile(file) {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/admin/api/upload', { method: 'POST', body: form });
    if (res.status === 401) throw new Error('Unauthorized');
    const data = await res.json();
    return data.url;
}

async function loadCategories() {
    const cats = await api('/categories');
    $('categories-list').innerHTML = cats.map(c => `
        <div class="category-edit" data-id="${c.id}">
            <img src="${escapeHtml(c.image_url || '')}" alt="" onerror="this.style.display='none'">
            <div class="form-row">
                <label>Название</label>
                <input type="text" class="edit-cat-name" value="${escapeHtml(c.name)}">
            </div>
            <div class="form-row">
                <label>Описание</label>
                <input type="text" class="edit-cat-desc" value="${escapeHtml(c.description || '')}">
            </div>
            <div class="form-row">
                <label>Иконка</label>
                <input type="text" class="edit-cat-icon" value="${escapeHtml(c.icon_emoji || '')}">
            </div>
            <div class="form-row">
                <label>URL картинки</label>
                <input type="text" class="edit-cat-image" value="${escapeHtml(c.image_url || '')}">
            </div>
            <div class="form-row">
                <label>Заменить картинку</label>
                <input type="file" class="edit-cat-file" accept="image/*">
            </div>
            <div class="form-row">
                <label>Размер плитки</label>
                <select class="edit-cat-tile">
                    <option value="medium" ${c.tile_size === 'medium' ? 'selected' : ''}>Средний</option>
                    <option value="wide" ${c.tile_size === 'wide' ? 'selected' : ''}>Широкий</option>
                    <option value="large" ${c.tile_size === 'large' ? 'selected' : ''}>Большой</option>
                </select>
            </div>
            <div class="form-row">
                <label>Сортировка</label>
                <input type="number" class="edit-cat-sort" value="${c.sort_order}">
            </div>
            <div class="form-row">
                <label><input type="checkbox" class="edit-cat-active" ${c.is_active ? 'checked' : ''}> Активна</label>
            </div>
            <button class="btn btn-primary save-cat">Сохранить</button>
            <button class="btn btn-danger delete-cat">Удалить</button>
        </div>
    `).join('') || '<div style="color:#999;">Нет категорий</div>';

    document.querySelectorAll('.save-cat').forEach(btn => {
        btn.addEventListener('click', async e => {
            const card = e.target.closest('.category-edit');
            await saveCategory(card);
        });
    });
    document.querySelectorAll('.delete-cat').forEach(btn => {
        btn.addEventListener('click', async e => {
            const card = e.target.closest('.category-edit');
            if (confirm('Удалить категорию?')) await deleteCategory(card.dataset.id);
        });
    });
}

async function saveCategory(card) {
    const id = card.dataset.id;
    const fileInput = card.querySelector('.edit-cat-file');
    let imageUrl = card.querySelector('.edit-cat-image').value;
    if (fileInput.files && fileInput.files[0]) {
        imageUrl = await uploadFile(fileInput.files[0]);
    }
    const body = {
        name: card.querySelector('.edit-cat-name').value,
        description: card.querySelector('.edit-cat-desc').value,
        icon_emoji: card.querySelector('.edit-cat-icon').value,
        image_url: imageUrl || null,
        tile_size: card.querySelector('.edit-cat-tile').value,
        sort_order: parseInt(card.querySelector('.edit-cat-sort').value) || 0,
        is_active: card.querySelector('.edit-cat-active').checked,
    };
    await api(`/categories/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    alert('Сохранено');
    await loadCategories();
}

async function deleteCategory(id) {
    await api(`/categories/${id}`, { method: 'DELETE' });
    await loadCategories();
}

async function addCategory() {
    const file = $('cat-image').files[0];
    let imageUrl = null;
    if (file) imageUrl = await uploadFile(file);
    const body = {
        name: $('cat-name').value,
        description: $('cat-desc').value,
        icon_emoji: $('cat-icon').value,
        image_url: imageUrl,
        tile_size: $('cat-tile').value,
        sort_order: parseInt($('cat-sort').value) || 0,
        is_active: true,
    };
    await api('/categories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    $('cat-name').value = '';
    $('cat-desc').value = '';
    $('cat-icon').value = '';
    $('cat-image').value = '';
    $('cat-image-preview').style.display = 'none';
    await loadCategories();
}

async function loadProducts(q = '') {
    const products = await api(`/products?q=${encodeURIComponent(q)}`);
    $('products-list').innerHTML = products.map(p => `
        <tr class="product-row" data-id="${p.id}">
            <td><input type="text" class="edit-prod-name" value="${escapeHtml(p.name)}"></td>
            <td><input type="text" class="edit-prod-category" value="${escapeHtml(p.category || '')}"></td>
            <td><input type="number" class="edit-prod-price" value="${p.price || ''}"></td>
            <td><input type="text" class="edit-prod-color" value="${escapeHtml(p.color || '')}"></td>
            <td><input type="text" class="edit-prod-memory" value="${escapeHtml(p.memory || '')}"></td>
            <td>
                <input type="text" class="edit-prod-photo" value="${escapeHtml(p.photo_url || '')}" placeholder="URL">
                <input type="file" class="edit-prod-file" accept="image/*" style="margin-top:4px;">
            </td>
            <td><input type="number" class="edit-prod-stock" value="${p.stock || 0}"></td>
            <td><button class="btn btn-primary save-prod">Сохр.</button></td>
        </tr>
    `).join('') || '<tr><td colspan="8" style="text-align:center; color:#999;">Нет товаров</td></tr>';

    document.querySelectorAll('.save-prod').forEach(btn => {
        btn.addEventListener('click', async e => {
            const row = e.target.closest('.product-row');
            await saveProduct(row);
        });
    });
}

async function saveProduct(row) {
    const id = row.dataset.id;
    const fileInput = row.querySelector('.edit-prod-file');
    let photoUrl = row.querySelector('.edit-prod-photo').value;
    if (fileInput.files && fileInput.files[0]) {
        photoUrl = await uploadFile(fileInput.files[0]);
    }
    const body = {
        name: row.querySelector('.edit-prod-name').value,
        category: row.querySelector('.edit-prod-category').value,
        price: parseFloat(row.querySelector('.edit-prod-price').value) || 0,
        color: row.querySelector('.edit-prod-color').value,
        memory: row.querySelector('.edit-prod-memory').value,
        photo_url: photoUrl || null,
        stock: parseInt(row.querySelector('.edit-prod-stock').value) || 0,
    };
    await api(`/products/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    alert('Сохранено');
    await loadProducts($('product-search').value);
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

document.addEventListener('DOMContentLoaded', () => {
    $('admin-login-btn').addEventListener('click', login);
    $('admin-logout').addEventListener('click', logout);
    $('cat-add-btn').addEventListener('click', addCategory);
    $('cat-image').addEventListener('change', e => {
        const file = e.target.files[0];
        if (file) {
            const url = URL.createObjectURL(file);
            $('cat-image-preview').src = url;
            $('cat-image-preview').style.display = 'block';
        }
    });

    document.querySelectorAll('.admin-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
            tab.classList.add('active');
            $(`tab-${tab.dataset.tab}`).classList.add('active');
        });
    });

    $('product-search-btn').addEventListener('click', () => loadProducts($('product-search').value));
    $('product-search').addEventListener('keypress', e => {
        if (e.key === 'Enter') loadProducts($('product-search').value);
    });
});

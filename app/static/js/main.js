// ─── CART MANAGEMENT ───────────────────────────────────────

function getCart() {
    return JSON.parse(localStorage.getItem('cart')) || [];
}

function saveCart(cart) {
    localStorage.setItem('cart', JSON.stringify(cart));
}

function addToCart(productId) {
    let cart = getCart();
    const existing = cart.find(item => item.id === productId);
    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({ id: productId, quantity: 1 });
    }
    saveCart(cart);
    showToast('Added to cart! 🛒');
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        background: #4a1259;
        color: white;
        padding: 15px 25px;
        border-radius: 10px;
        font-size: 1rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        z-index: 9999;
        animation: fadeIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ─── SEARCH & FILTER ───────────────────────────────────────

const searchInput = document.getElementById('searchInput');
const categoryFilter = document.getElementById('categoryFilter');

if (searchInput) {
    searchInput.addEventListener('input', filterProducts);
}

if (categoryFilter) {
    categoryFilter.addEventListener('change', filterProducts);
}

function filterProducts() {
    const search = searchInput ? searchInput.value.toLowerCase() : '';
    const category = categoryFilter ? categoryFilter.value : '';
    const cards = document.querySelectorAll('.product-card');

    cards.forEach(card => {
        const name = card.querySelector('h3').textContent.toLowerCase();
        const cardCategory = card.dataset.category;
        const matchSearch = name.includes(search);
        const matchCategory = category === '' || cardCategory === category;
        card.style.display = matchSearch && matchCategory ? 'block' : 'none';
    });
}
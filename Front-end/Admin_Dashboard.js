const API_BASE_URL = "http://127.0.0.1:8000";

// ============================================================
// 1. Auth Helpers
// ============================================================
function getToken() {
    return localStorage.getItem("admin_token") || "";
}

function authHeaders() {
    return { "Authorization": `Bearer ${getToken()}` };
}

function isLoggedIn() {
    return !!getToken();
}

function logout() {
    localStorage.removeItem("admin_token");
    document.getElementById("loginModal").classList.remove("hidden");
    document.getElementById("mainContent").classList.add("hidden");
}

// ============================================================
// 2. Admin Login
// ============================================================
async function adminLogin() {
    const email    = document.getElementById("adminEmail").value.trim();
    const password = document.getElementById("adminPassword").value;
    const errorEl  = document.getElementById("loginError");
    errorEl.innerText = "";

    if (!email || !password) {
        errorEl.innerText = "Please enter email and password.";
        return;
    }

    try {
        // Step 1: Login
        const res = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) { errorEl.innerText = data.detail || "Login failed."; return; }

        // Step 2: Store token and check role
        localStorage.setItem("admin_token", data.token);
        const profileRes = await fetch(`${API_BASE_URL}/profile`, {
            headers: authHeaders()
        });
        const profile = await profileRes.json();

        if (profile.role !== "Admin") {
            localStorage.removeItem("admin_token");
            errorEl.innerText = "Access denied: Admin accounts only.";
            return;
        }

        // Step 3: Show dashboard
        document.getElementById("loginModal").classList.add("hidden");
        document.getElementById("mainContent").classList.remove("hidden");
        document.getElementById("adminName").innerText = data.username;
        initDashboard();

    } catch (err) {
        errorEl.innerText = "Connection error. Is the server running?";
        console.error(err);
    }
}

// ============================================================
// 3. Init
// ============================================================
function initDashboard() {
    loadDashboardStats();
    loadUsers();
    loadClothes();
    loadContactMessages();
}

document.addEventListener("DOMContentLoaded", () => {
    if (isLoggedIn()) {
        document.getElementById("loginModal").classList.add("hidden");
        document.getElementById("mainContent").classList.remove("hidden");
        initDashboard();
    } else {
        document.getElementById("loginModal").classList.remove("hidden");
        document.getElementById("mainContent").classList.add("hidden");
    }
});

// ============================================================
// 4. Tabs
// ============================================================
function showTab(tab, element) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.getElementById(tab)?.classList.remove('hidden');
    document.getElementById('pageTitle').innerText =
        tab.charAt(0).toUpperCase() + tab.slice(1);

    document.querySelectorAll('.tab').forEach(el => {
        el.classList.remove('active-tab', 'bg-purple-600', 'text-white');
    });
    if (element) {
        element.classList.add('active-tab', 'bg-purple-600', 'text-white');
    }
}

// ============================================================
// 5. Dashboard Stats  ← يجيب من الداتابيز فعلاً
// ============================================================
async function loadDashboardStats() {
    try {
        const [usersRes, clothesRes, msgsRes] = await Promise.all([
            fetch(`${API_BASE_URL}/admin/users`,            { headers: authHeaders() }),
            fetch(`${API_BASE_URL}/clothes`),
            fetch(`${API_BASE_URL}/admin/contact-messages`, { headers: authHeaders() })
        ]);

        const users    = usersRes.ok    ? await usersRes.json()    : [];
        const clothes  = clothesRes.ok  ? await clothesRes.json()  : [];
        const messages = msgsRes.ok     ? await msgsRes.json()     : [];

        const cards = document.querySelectorAll('#dashboard .glass p');
        if (cards.length >= 4) {
            cards[0].innerText = users.length;
            cards[1].innerText = "0";
            cards[2].innerText = clothes.length;
            cards[3].innerText = messages.length;
        }
    } catch (err) {
        console.error("Stats error:", err);
    }
}

// ============================================================
// 6. Users  ← يجيب ويمسح من الداتابيز
// ============================================================
async function loadUsers() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/users`, { headers: authHeaders() });

        // لو الـ token انتهى أو مش Admin
        if (res.status === 401 || res.status === 403) { logout(); return; }
        if (!res.ok) return;

        const users = await res.json();
        const tbody = document.getElementById('usersTable');
        if (!tbody) return;
        tbody.innerHTML = '';

        users.forEach(user => {
            const tr = document.createElement('tr');
            tr.className = 'border-t text-gray-800';
            tr.innerHTML = `
                <td class="p-2">${user.username || 'N/A'}</td>
                <td>${user.email}</td>
                <td>
                    <span class="${user.is_verified ? 'text-green-600' : 'text-yellow-500'} font-bold">
                        ${user.is_verified ? 'Active' : 'Unverified'}
                    </span>
                </td>
                <td>${user.role}</td>
                <td class="space-x-2">
                    <button onclick="deleteUser(${user.id}, '${user.email}')"
                        class="px-3 py-1 bg-red-500 text-white rounded-lg hover:opacity-90">Delete</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Users error:", err);
    }
}

function searchUsers() {
    const q = document.getElementById("userSearch").value.toLowerCase();
    document.querySelectorAll("#usersTable tr").forEach(row => {
        const name  = row.cells[0]?.innerText.toLowerCase() || "";
        const email = row.cells[1]?.innerText.toLowerCase() || "";
        row.style.display = (name.includes(q) || email.includes(q)) ? "" : "none";
    });
}

async function deleteUser(id, email) {
    if (!confirm(`Delete user: ${email}?`)) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/users/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        if (res.ok) {
            showToast("✅ User deleted successfully");
            loadUsers();
            loadDashboardStats();
        } else {
            const d = await res.json();
            alert(d.detail || "Failed to delete user");
        }
    } catch (err) { console.error(err); }
}

// ============================================================
// 7. Clothes  ← يجيب / يضيف / يمسح من الداتابيز
// ============================================================
async function loadClothes() {
    try {
        const res = await fetch(`${API_BASE_URL}/clothes`);
        if (!res.ok) return;
        const items = await res.json();

        const grid = document.getElementById('clothesGrid');
        if (!grid) return;
        grid.innerHTML = '';

        if (items.length === 0) {
            grid.innerHTML = '<p class="text-gray-500 col-span-3 text-center py-10">No clothes found in database.</p>';
            return;
        }

        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'glass p-4 rounded-2xl';
            const imgUrl = item.image_url
                ? `${API_BASE_URL}${item.image_url}`
                : 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab';

            card.innerHTML = `
                <img src="${imgUrl}" class="rounded-xl mb-3 h-40 w-full object-cover"
                     onerror="this.src='https://images.unsplash.com/photo-1521572163474-6864f9cf17ab'">
                <h4 class="font-bold text-gray-900">${item.name || 'No Name'}</h4>
                <p class="text-gray-500 text-sm">Category: ${item.category || 'N/A'}</p>
                <p class="text-gray-500 text-sm">Brand: ${item.brand || 'N/A'}</p>
                <p class="text-purple-700 text-sm font-bold mt-1">${item.price ? '$' + item.price : ''}</p>
                <div class="flex gap-2 mt-3">
                    <button onclick="deleteClothing(${item.id})"
                        class="px-3 py-1 bg-red-500 text-white rounded-lg hover:opacity-90">Delete</button>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch (err) { console.error("Clothes error:", err); }
}

// ─── Add Clothing Modal ───────────────────────────────────────
function showAddClothingModal() {
    document.getElementById('addClothingModal').classList.remove('hidden');
}
function closeAddClothingModal() {
    document.getElementById('addClothingModal').classList.add('hidden');
    document.getElementById('addClothingForm').reset();
}

async function submitAddClothing() {
    const name      = document.getElementById('clothName').value.trim();
    const category  = document.getElementById('clothCategory').value;
    const brand     = document.getElementById('clothBrand').value.trim();
    const price     = document.getElementById('clothPrice').value || "0";
    const fileInput = document.getElementById('clothImage');

    if (!name || !category) { alert("Name and Category are required."); return; }
    if (!fileInput.files[0]) { alert("Please select a clothing image."); return; }

    // الـ backend بيطلب FormData مش JSON
    const formData = new FormData();
    formData.append('name',     name);
    formData.append('category', category);
    formData.append('brand',    brand);
    formData.append('price',    price);
    formData.append('size_xs',  0);
    formData.append('size_s',   0);
    formData.append('size_m',   0);
    formData.append('size_l',   0);
    formData.append('size_xl',  0);
    formData.append('size_xxl', 0);
    formData.append('file',     fileInput.files[0]);

    const btn = document.getElementById('addClothingBtn');
    btn.disabled = true;
    btn.innerText = 'Adding...';

    try {
        // ملاحظة: لا تضع Content-Type هنا — المتصفح بيضيفه تلقائياً مع الـ boundary
        const res = await fetch(`${API_BASE_URL}/admin/clothes`, {
            method: 'POST',
            headers: { "Authorization": `Bearer ${getToken()}` },
            body: formData
        });

        const data = await res.json();
        if (res.ok) {
            showToast("✅ Clothing added successfully!");
            closeAddClothingModal();
            loadClothes();
            loadDashboardStats();
        } else {
            alert(data.detail || "Failed to add clothing");
        }
    } catch (err) {
        console.error(err);
        alert("Connection error");
    } finally {
        btn.disabled = false;
        btn.innerText = 'Add Clothing';
    }
}

async function deleteClothing(id) {
    if (!confirm(`Delete clothing item #${id}?`)) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/clothes/${id}`, {
            method: 'DELETE',
            headers: authHeaders()
        });
        if (res.ok) {
            showToast("✅ Clothing deleted successfully");
            loadClothes();
            loadDashboardStats();
        } else {
            const d = await res.json();
            alert(d.detail || "Failed to delete clothing");
        }
    } catch (err) { console.error(err); }
}

// ============================================================
// 8. Contact Messages  ← يجيب من الداتابيز
// ============================================================
async function loadContactMessages() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/contact-messages`, {
            headers: authHeaders()
        });
        if (!res.ok) return;
        const messages = await res.json();

        const tbody = document.getElementById('contactTable');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (messages.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center py-6 text-gray-400">No messages found.</td></tr>';
            return;
        }

        messages.forEach(msg => {
            const tr = document.createElement('tr');
            tr.className = 'border-t text-gray-800';
            tr.innerHTML = `
                <td class="p-2">${msg.name || 'N/A'}</td>
                <td>${msg.email || 'N/A'}</td>
                <td>${msg.subject || 'N/A'}</td>
                <td>
                    <button class="px-3 py-1 bg-purple-600 text-white rounded-lg hover:opacity-90"
                        onclick="viewMessage(this)" 
                        data-name="${(msg.name || '').replace(/"/g, '&quot;')}"
                        data-subject="${(msg.subject || '').replace(/"/g, '&quot;')}"
                        data-message="${(msg.message || '').replace(/"/g, '&quot;')}">
                        View
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) { console.error("Messages error:", err); }
}

function viewMessage(btn) {
    const name    = btn.dataset.name;
    const subject = btn.dataset.subject;
    const body    = btn.dataset.message;
    document.getElementById('msgContent').innerHTML =
        `<b>From:</b> ${name}<br><b>Subject:</b> ${subject}<br><br><b>Message:</b><br>${body}`;
    document.getElementById('messageModal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('messageModal').classList.add('hidden');
}

// ============================================================
// 9. Reports (placeholder)
// ============================================================


// ============================================================
// 10. Toast Notification
// ============================================================
function showToast(msg) {
    const toast = document.createElement('div');
    toast.className =
        'fixed bottom-6 right-6 bg-green-600 text-white px-6 py-3 rounded-xl shadow-xl z-50 transition-all duration-300';
    toast.innerText = msg;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 400);
    }, 2800);
}

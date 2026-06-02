const GENERATE_ENDPOINT = "/generate";

const form = document.getElementById("generateForm");
const previewArea = document.getElementById("previewArea");
const logoInput = document.getElementById("logoInput");
const logoStatus = document.getElementById("logoStatus");
const foodImageInput = document.getElementById("foodImageInput");
const foodImageText = document.getElementById("foodImageText");
const foodImageSubText = document.getElementById("foodImageSubText");
const generateButton = document.getElementById("generateButton");
const regenerateButton = document.getElementById("regenerateButton");
const downloadButton = document.getElementById("downloadButton");

const loginOpenBtn = document.getElementById("loginOpenBtn");
const recentLoginBtn = document.getElementById("recentLoginBtn");
const authModal = document.getElementById("authModal");
const authCloseBtn = document.getElementById("authCloseBtn");
const loginTabBtn = document.getElementById("loginTabBtn");
const registerTabBtn = document.getElementById("registerTabBtn");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const authMessage = document.getElementById("authMessage");
const userBox = document.getElementById("userBox");
const userEmailText = document.getElementById("userEmailText");
const logoutBtn = document.getElementById("logoutBtn");

const recentGrid = document.getElementById("recentGrid");
const recentLockLayer = document.getElementById("recentLockLayer");

const viewAllDesignsBtn = document.getElementById("viewAllDesignsBtn");
const designsModal = document.getElementById("designsModal");
const designsCloseBtn = document.getElementById("designsCloseBtn");
const myDesignsGrid = document.getElementById("myDesignsGrid");

let latestDownloadUrl = "";
let allUserDesigns = [];
let currentDesignFilter = "all";

function showAuthMessage(message) {
  if (!authMessage) return;
  authMessage.textContent = message;
  authMessage.classList.remove("hidden");
}

function clearAuthMessage() {
  if (!authMessage) return;
  authMessage.textContent = "";
  authMessage.classList.add("hidden");
}

function openAuthModal() {
  clearAuthMessage();
  authModal?.classList.remove("hidden");
}

function closeAuthModal() {
  authModal?.classList.add("hidden");
}

function showLoginTab() {
  loginTabBtn?.classList.add("btn-primary");
  loginTabBtn?.classList.remove("btn-secondary");
  registerTabBtn?.classList.add("btn-secondary");
  registerTabBtn?.classList.remove("btn-primary");
  loginForm?.classList.remove("hidden");
  registerForm?.classList.add("hidden");
  clearAuthMessage();
}

function showRegisterTab() {
  registerTabBtn?.classList.add("btn-primary");
  registerTabBtn?.classList.remove("btn-secondary");
  loginTabBtn?.classList.add("btn-secondary");
  loginTabBtn?.classList.remove("btn-primary");
  registerForm?.classList.remove("hidden");
  loginForm?.classList.add("hidden");
  clearAuthMessage();
}

function saveSession(data, email) {
  localStorage.setItem("food_ai_token", data.access_token || "");
  localStorage.setItem("food_ai_refresh_token", data.refresh_token || "");
  localStorage.setItem("food_ai_user_id", data.user?.id || "");
  localStorage.setItem("food_ai_user_email", email || data.user?.email || "");
  updateAuthUI();
}

function clearSession() {
  localStorage.removeItem("food_ai_token");
  localStorage.removeItem("food_ai_refresh_token");
  localStorage.removeItem("food_ai_user_id");
  localStorage.removeItem("food_ai_user_email");
  updateAuthUI();
}

function getToken() {
  return localStorage.getItem("food_ai_token") || "";
}

function getUserEmail() {
  return localStorage.getItem("food_ai_user_email") || "";
}

function isLoggedIn() {
  return !!getToken();
}

function updateAuthUI() {
  const token = getToken();
  const email = getUserEmail();

  if (token && email) {
    loginOpenBtn?.classList.add("hidden");
    userBox?.classList.remove("hidden");
    userBox?.classList.add("flex");
    if (userEmailText) userEmailText.textContent = email;
    recentLockLayer?.classList.add("hidden");
    loadRecentDesigns();
  } else {
    loginOpenBtn?.classList.remove("hidden");
    userBox?.classList.add("hidden");
    userBox?.classList.remove("flex");
    if (userEmailText) userEmailText.textContent = "";
    recentLockLayer?.classList.remove("hidden");
  }
}

loginOpenBtn?.addEventListener("click", openAuthModal);
recentLoginBtn?.addEventListener("click", openAuthModal);
authCloseBtn?.addEventListener("click", closeAuthModal);

authModal?.addEventListener("click", function (event) {
  if (event.target === authModal) closeAuthModal();
});

loginTabBtn?.addEventListener("click", showLoginTab);
registerTabBtn?.addEventListener("click", showRegisterTab);

logoutBtn?.addEventListener("click", function () {
  clearSession();
  alert("已退出登录");
});

registerForm?.addEventListener("submit", async function (event) {
  event.preventDefault();
  clearAuthMessage();

  const email = document.getElementById("registerEmail")?.value.trim();
  const password = document.getElementById("registerPassword")?.value;

  if (!email || !password) {
    showAuthMessage("请输入 Email 和 Password");
    return;
  }

  try {
    const response = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.msg || data.error_description || data.error || data.message || "注册失败");
    }

    showAuthMessage("注册成功。请检查邮箱验证，或直接尝试登录。");
    showLoginTab();

    const loginEmail = document.getElementById("loginEmail");
    if (loginEmail) loginEmail.value = email;
  } catch (error) {
    showAuthMessage("注册失败：" + error.message);
  }
});

loginForm?.addEventListener("submit", async function (event) {
  event.preventDefault();
  clearAuthMessage();

  const email = document.getElementById("loginEmail")?.value.trim();
  const password = document.getElementById("loginPassword")?.value;

  if (!email || !password) {
    showAuthMessage("请输入 Email 和 Password");
    return;
  }

  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.msg || data.error_description || data.error || data.message || "登录失败");
    }

    saveSession(data, email);
    closeAuthModal();
    alert("登录成功");
  } catch (error) {
    showAuthMessage("登录失败：" + error.message);
  }
});

logoInput?.addEventListener("change", function () {
  if (logoInput.files && logoInput.files[0]) {
    logoStatus.textContent = "✓ " + logoInput.files[0].name + " uploaded";
    logoStatus.className = "text-sm font-bold text-green-600";
  } else {
    logoStatus.textContent = "Transparent PNG recommended";
    logoStatus.className = "text-sm font-semibold text-gray-400";
  }
});

foodImageInput?.addEventListener("change", function () {
  if (foodImageInput.files && foodImageInput.files[0]) {
    foodImageText.textContent = "✓ Food image uploaded";
    foodImageSubText.textContent = foodImageInput.files[0].name;
    foodImageSubText.className = "mt-1 text-xs font-semibold text-green-600";
  } else {
    foodImageText.textContent = "Drop Food Image Here";
    foodImageSubText.textContent = "PNG / JPG supported";
    foodImageSubText.className = "mt-1 text-xs text-gray-400";
  }
});

function setLoadingState() {
  generateButton.disabled = true;
  generateButton.textContent = "Generating...";
  regenerateButton.disabled = true;
  downloadButton.disabled = true;

  previewArea.className = "preview-box checker relative grid place-items-center rounded-[28px] border border-[#B2EBF2] shadow-2xl";
  previewArea.innerHTML = `
    <div class="text-center px-6">
      <div class="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl bg-white shadow-lg">
        <span class="text-2xl">⏳</span>
      </div>
      <p class="text-xl font-black text-gray-800">Generating...</p>
      <p class="mt-2 text-sm font-medium text-gray-400">AI is creating your food visual. This may take a while.</p>
    </div>
  `;
}

function resetButtonState() {
  generateButton.disabled = false;
  generateButton.textContent = "Generate Visuals";
}

function showError(message) {
  previewArea.className = "preview-box checker relative grid place-items-center rounded-[28px] border border-[#B2EBF2] shadow-2xl";
  previewArea.innerHTML = `
    <div class="text-center px-6">
      <div class="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl bg-white shadow-lg">
        <span class="text-2xl">⚠️</span>
      </div>
      <p class="text-xl font-black text-red-600">Generate Failed</p>
      <p class="mt-2 text-sm font-medium text-gray-500">${message}</p>
    </div>
  `;
}

function showGeneratedImage(imageUrl, downloadUrl) {
  latestDownloadUrl = downloadUrl || imageUrl;

  previewArea.className = "preview-box relative overflow-hidden rounded-[28px] border border-[#B2EBF2] shadow-2xl bg-white";
  previewArea.innerHTML = `
    <img src="${imageUrl}?t=${Date.now()}" class="h-full w-full object-contain bg-white" alt="Generated food visual" />
  `;

  regenerateButton.disabled = false;
  downloadButton.disabled = false;
}

async function generateVisual() {
  if (!isLoggedIn()) {
    openAuthModal();
    showAuthMessage("请先登录或注册后再生成图片。");
    return;
  }

  if (!foodImageInput.files || !foodImageInput.files[0]) {
    showError("Please upload food image first.");
    return;
  }

  setLoadingState();

  try {
    const formData = new FormData(form);
    formData.append("user_id", localStorage.getItem("food_ai_user_id") || "");
    formData.append("user_email", localStorage.getItem("food_ai_user_email") || "");

    const response = await fetch(GENERATE_ENDPOINT, {
      method: "POST",
      body: formData
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("Server did not return JSON. Please check Railway logs.");
    }

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Generate failed.");
    }

    showGeneratedImage(data.image_url, data.download_url);
    saveWork(data.image_url, data.download_url);
    loadRecentDesigns();
  } catch (error) {
    showError(error.message || "Generate failed.");
  } finally {
    resetButtonState();
  }
}

form?.addEventListener("submit", function (event) {
  event.preventDefault();
  generateVisual();
});

regenerateButton?.addEventListener("click", generateVisual);

downloadButton?.addEventListener("click", async function () {
  if (!latestDownloadUrl) return;
  await downloadImage(latestDownloadUrl);
});

async function downloadImage(imageUrl) {
  try {
    const response = await fetch(imageUrl);
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = blobUrl;
    a.download = "food-ai-design.png";
    document.body.appendChild(a);
    a.click();

    a.remove();
    window.URL.revokeObjectURL(blobUrl);
  } catch {
    alert("Download failed. Please try again.");
  }
}

function saveWork(imageUrl, downloadUrl) {
  const works = JSON.parse(localStorage.getItem("food_ai_works") || "[]");

  works.unshift({
    imageUrl,
    downloadUrl: downloadUrl || imageUrl,
    time: new Date().toLocaleString()
  });

  localStorage.setItem("food_ai_works", JSON.stringify(works.slice(0, 20)));
}

async function loadRecentDesigns() {
  if (!recentGrid) return;

  const userId = localStorage.getItem("food_ai_user_id") || "";
  if (!userId) return;

  try {
    const response = await fetch(`/api/my-designs?user_id=${encodeURIComponent(userId)}`);
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Failed to load designs");
    }

    const works = data.items || [];

    if (!works.length) {
      recentGrid.innerHTML = `
        <div class="col-span-full rounded-3xl bg-white p-8 text-center">
          <p class="text-lg font-black text-gray-800">No designs yet</p>
          <p class="mt-1 text-sm text-gray-500">生成第一张作品后会显示在这里。</p>
        </div>
      `;
      return;
    }

    recentGrid.innerHTML = works.slice(0, 6).map(function (item) {
      return `
        <a href="${item.image_url}" target="_blank" class="block overflow-hidden rounded-3xl bg-white shadow">
          <img src="${item.image_url}" class="aspect-[4/3] w-full object-cover" alt="Food AI Design">
          <div class="p-3">
            <p class="text-xs font-bold text-gray-700">${item.title || "Food Design"}</p>
            <p class="mt-1 text-xs font-semibold text-gray-500">${new Date(item.created_at).toLocaleString()}</p>
          </div>
        </a>
      `;
    }).join("");
  } catch (error) {
    recentGrid.innerHTML = `
      <div class="col-span-full rounded-3xl bg-white p-8 text-center">
        <p class="text-lg font-black text-red-600">Failed to load designs</p>
        <p class="mt-1 text-sm text-gray-500">${error.message}</p>
      </div>
    `;
  }
}

async function loadAllDesigns() {
  if (!myDesignsGrid) return;

  const userId = localStorage.getItem("food_ai_user_id") || "";

  if (!userId) {
    openAuthModal();
    showAuthMessage("请先登录查看 My Designs。");
    return;
  }

  myDesignsGrid.innerHTML = `
    <div class="col-span-full rounded-3xl bg-white p-8 text-center">
      <p class="text-lg font-black text-gray-800">Loading...</p>
    </div>
  `;

  try {
    const response = await fetch(`/api/my-designs?user_id=${encodeURIComponent(userId)}&limit=100`);
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Failed to load designs");
    }

    allUserDesigns = data.items || [];
    renderMyDesigns();
  } catch (error) {
    myDesignsGrid.innerHTML = `
      <div class="col-span-full rounded-3xl bg-white p-8 text-center">
        <p class="text-lg font-black text-red-600">Failed to load designs</p>
        <p class="mt-1 text-sm text-gray-500">${error.message}</p>
      </div>
    `;
  }
}

function renderMyDesigns() {
  if (!myDesignsGrid) return;

  const filtered = allUserDesigns.filter(function (item) {
    if (currentDesignFilter === "all") return true;
    return (item.visual_type || "").toLowerCase() === currentDesignFilter;
  });

  if (!filtered.length) {
    myDesignsGrid.innerHTML = `
      <div class="col-span-full rounded-3xl bg-white p-8 text-center">
        <p class="text-lg font-black text-gray-800">No designs found</p>
        <p class="mt-1 text-sm text-gray-500">这个分类暂时没有作品。</p>
      </div>
    `;
    return;
  }

  myDesignsGrid.innerHTML = filtered.map(function (item) {
    const imageUrl = item.image_url;
    const title = item.title || "Food Design";
    const type = item.visual_type || "design";
    const dateText = item.created_at ? new Date(item.created_at).toLocaleString() : "";

    return `
      <div class="overflow-hidden rounded-3xl bg-white shadow">
        <a href="${imageUrl}" target="_blank">
          <img src="${imageUrl}" class="aspect-[4/3] w-full object-cover" alt="Food AI Design">
        </a>

        <div class="p-3">
          <p class="truncate text-sm font-black text-gray-800">${title}</p>
          <p class="mt-1 text-xs font-semibold uppercase text-gray-400">${type}</p>
          <p class="mt-1 text-xs text-gray-400">${dateText}</p>

          <div class="mt-3 grid grid-cols-2 gap-2">
            <a href="${imageUrl}" target="_blank" class="btn-secondary px-3 py-2 text-center text-xs">Open</a>
            <button type="button" class="download-design-btn btn-primary px-3 py-2 text-xs" data-url="${imageUrl}">
              Download
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

viewAllDesignsBtn?.addEventListener("click", function () {
  if (!isLoggedIn()) {
    openAuthModal();
    showAuthMessage("请先登录查看 My Designs。");
    return;
  }

  designsModal?.classList.remove("hidden");
  loadAllDesigns();
});

designsCloseBtn?.addEventListener("click", function () {
  designsModal?.classList.add("hidden");
});

designsModal?.addEventListener("click", function (event) {
  if (event.target === designsModal) {
    designsModal.classList.add("hidden");
  }
});

document.querySelectorAll(".design-filter").forEach(function (btn) {
  btn.addEventListener("click", function () {
    currentDesignFilter = btn.dataset.filter || "all";

    document.querySelectorAll(".design-filter").forEach(function (item) {
      item.classList.remove("btn-primary");
      item.classList.add("btn-secondary");
    });

    btn.classList.add("btn-primary");
    btn.classList.remove("btn-secondary");

    renderMyDesigns();
  });
});

myDesignsGrid?.addEventListener("click", async function (event) {
  const btn = event.target.closest(".download-design-btn");
  if (!btn) return;

  const imageUrl = btn.dataset.url;
  if (!imageUrl) return;

  await downloadImage(imageUrl);
});

showLoginTab();
updateAuthUI();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/static/service-worker.js").catch(function () {});
  });
}
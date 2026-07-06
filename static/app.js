const GENERATE_ENDPOINT = "/generate";

const form = document.getElementById("generateForm");
const previewArea = document.getElementById("previewArea");
const logoInput = document.getElementById("logoInput");
const logoStatus = document.getElementById("logoStatus");
const foodImageInput = document.getElementById("foodImageInput");
const foodImageText = document.getElementById("foodImageText");
const foodImageSubText = document.getElementById("foodImageSubText");
const productBundleOptions = document.getElementById("productBundleOptions");
const sideImageInput = document.getElementById("sideImageInput");
const drinkImageInput = document.getElementById("drinkImageInput");
const sideImageStatus = document.getElementById("sideImageStatus");
const drinkImageStatus = document.getElementById("drinkImageStatus");
const titleInput = form?.querySelector('input[name="title"]');
const typeInputs = Array.from(document.querySelectorAll('input[name="type"]'));
const platformPackSelect = document.getElementById("platformPackSelect");
const platformPackHint = document.getElementById("platformPackHint");
const generateButton = document.getElementById("generateButton");
const regenerateButton = document.getElementById("regenerateButton");
const downloadButton = document.getElementById("downloadButton");

const photoQualityPanel = document.getElementById("photoQualityPanel");
const photoQualityScore = document.getElementById("photoQualityScore");
const photoQualitySummary = document.getElementById("photoQualitySummary");
const photoQualityList = document.getElementById("photoQualityList");

const deliveryPackPanel = document.getElementById("deliveryPackPanel");
const deliveryPackTitle = document.getElementById("deliveryPackTitle");
const deliveryPackItems = document.getElementById("deliveryPackItems");
const bundleDownloadButton = document.getElementById("bundleDownloadButton");

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

const planInfoBox = document.getElementById("planInfoBox");
const planText = document.getElementById("planText");
const usageText = document.getElementById("usageText");

const recentGrid = document.getElementById("recentGrid");
const recentLockLayer = document.getElementById("recentLockLayer");

const viewAllDesignsBtn = document.getElementById("viewAllDesignsBtn");
const designsModal = document.getElementById("designsModal");
const designsCloseBtn = document.getElementById("designsCloseBtn");
const myDesignsGrid = document.getElementById("myDesignsGrid");

let latestDownloadUrl = "";
let latestBundleDownloadUrl = "";
let latestGeneratedItems = [];
let allUserDesigns = [];
let currentDesignFilter = "all";

const PLATFORM_HINTS = {
  single: "选择交付包后，系统会一次生成多个可下载规格。",
  grabfood_menu: "会生成 Product 720×720 与 Banner 1080×600，适合菜单和店铺活动图。",
  foodpanda_menu: "会生成 Product 720×720 与 Poster 1080×1080，适合菜单主图和促销图。",
  malaysia_starter: "会生成 Product、Banner、Poster，一次交付餐饮老板最常用的三种素材。"
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

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
  loadProfile();
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
    planInfoBox?.classList.remove("hidden");
    planInfoBox?.classList.add("flex");
    recentLockLayer?.classList.add("hidden");
    loadRecentDesigns();
  } else {
    loginOpenBtn?.classList.remove("hidden");
    userBox?.classList.add("hidden");
    userBox?.classList.remove("flex");
    if (userEmailText) userEmailText.textContent = "";
    if (planText) planText.textContent = "";
    if (usageText) usageText.textContent = "";
    planInfoBox?.classList.add("hidden");
    planInfoBox?.classList.remove("flex");
    recentLockLayer?.classList.remove("hidden");
  }
}

async function loadProfile() {
  const userId = localStorage.getItem("food_ai_user_id") || "";
  const email = localStorage.getItem("food_ai_user_email") || "";
  if (!userId) return;

  try {
    const response = await fetch(`/api/profile?user_id=${encodeURIComponent(userId)}&email=${encodeURIComponent(email)}`);
    const data = await response.json();
    if (!response.ok || !data.success || !data.profile) return;

    const profile = data.profile;
    planInfoBox?.classList.remove("hidden");
    planInfoBox?.classList.add("flex");

    if ((profile.plan || "").toLowerCase() === "pro") {
      if (planText) planText.textContent = "PRO PLAN";
      if (usageText) usageText.textContent = "Unlimited";
      return;
    }

    const used = profile.trial_used ?? 0;
    const limit = profile.trial_limit ?? 10;
    if (planText) planText.textContent = "TRIAL PLAN";
    if (usageText) usageText.textContent = `${used} / ${limit} Used`;
  } catch (error) {
    console.log("Profile load failed:", error);
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

function getSelectedType() {
  return document.querySelector('input[name="type"]:checked')?.value || "poster";
}

function getSelectedPack() {
  return platformPackSelect?.value || "single";
}

function updateFormMode() {
  const type = getSelectedType();
  const pack = getSelectedPack();
  const isSingleProduct = type === "product" && pack === "single";
  const hasProductOutput = isSingleProduct || pack !== "single";

  productBundleOptions?.classList.toggle("hidden", !hasProductOutput);

  if (foodImageInput) {
    if (isSingleProduct) {
      foodImageInput.setAttribute("multiple", "multiple");
    } else {
      foodImageInput.removeAttribute("multiple");
    }
  }

  if (titleInput) {
    titleInput.required = !isSingleProduct;
    titleInput.placeholder = isSingleProduct ? "Product 标签：Chef Recommend / Must Try（可不填）" : "例如：香煎猪扒饭";
  }

  if (platformPackHint) {
    platformPackHint.textContent = PLATFORM_HINTS[pack] || PLATFORM_HINTS.single;
  }

  if (foodImageText) {
    foodImageText.textContent = isSingleProduct ? "Drop Product Images Here" : "Drop Food Image Here";
  }

  if (foodImageSubText && (!foodImageInput?.files || !foodImageInput.files.length)) {
    foodImageSubText.textContent = isSingleProduct ? "可多选 PNG / JPG 批量生成 720×720" : "PNG / JPG supported";
  }
}

typeInputs.forEach(input => input.addEventListener("change", updateFormMode));
platformPackSelect?.addEventListener("change", updateFormMode);

function renderPhotoQuality(report) {
  if (!photoQualityPanel || !photoQualityScore || !photoQualitySummary || !photoQualityList) return;
  if (!report) {
    photoQualityPanel.classList.add("hidden");
    return;
  }

  photoQualityPanel.classList.remove("hidden");
  photoQualityScore.textContent = report.score ? `${report.score}/100` : "--";
  photoQualitySummary.textContent = report.summary || `${report.width || ""}×${report.height || ""}`;

  const suggestions = report.suggestions?.length
    ? report.suggestions
    : [`图片尺寸：${report.width || "-"}×${report.height || "-"}`];

  photoQualityList.innerHTML = suggestions.map(item => `<li>${escapeHtml(item)}</li>`).join("");
}

function inspectLocalPhoto(file) {
  if (!file) {
    renderPhotoQuality(null);
    return;
  }

  const objectUrl = URL.createObjectURL(file);
  const img = new Image();

  img.onload = function () {
    const minEdge = Math.min(img.naturalWidth, img.naturalHeight);
    let score = minEdge >= 1000 ? 86 : minEdge >= 750 ? 76 : minEdge >= 512 ? 62 : 48;
    const suggestions = [];

    if (minEdge < 750) {
      suggestions.push("分辨率偏低，建议使用原图或靠近食物重拍。");
    }
    if (img.naturalWidth / img.naturalHeight > 1.65 || img.naturalHeight / img.naturalWidth > 1.65) {
      score -= 8;
      suggestions.push("画面比例较极端，建议让食物居中并保留四周空间。");
    }
    if (!suggestions.length) {
      suggestions.push("尺寸适合生成，后端会继续检查亮度、清晰度和对比度。");
    }

    renderPhotoQuality({
      score: Math.max(40, score),
      summary: `本地初检：${img.naturalWidth}×${img.naturalHeight}`,
      width: img.naturalWidth,
      height: img.naturalHeight,
      suggestions
    });

    URL.revokeObjectURL(objectUrl);
  };

  img.onerror = function () {
    URL.revokeObjectURL(objectUrl);
    renderPhotoQuality({
      score: 0,
      summary: "无法读取图片尺寸",
      suggestions: ["请换一张 PNG、JPG 或 WEBP 食物图片。"]
    });
  };

  img.src = objectUrl;
}

logoInput?.addEventListener("change", function () {
  if (logoInput.files && logoInput.files[0]) {
    logoStatus.textContent = "已上传 " + logoInput.files[0].name;
    logoStatus.className = "text-sm font-bold text-green-600";
  } else {
    logoStatus.textContent = "Transparent PNG recommended";
    logoStatus.className = "text-sm font-semibold text-gray-400";
  }
});

foodImageInput?.addEventListener("change", function () {
  const count = foodImageInput.files ? foodImageInput.files.length : 0;
  const isSingleProduct = getSelectedType() === "product" && getSelectedPack() === "single";

  if (count > 0) {
    foodImageText.textContent = isSingleProduct && count > 1 ? `${count} product images uploaded` : "Food image uploaded";
    foodImageSubText.textContent = count > 1 ? `${count} files selected for batch generation` : foodImageInput.files[0].name;
    foodImageSubText.className = "mt-1 text-xs font-semibold text-green-600";
    inspectLocalPhoto(foodImageInput.files[0]);
  } else {
    foodImageText.textContent = isSingleProduct ? "Drop Product Images Here" : "Drop Food Image Here";
    foodImageSubText.textContent = isSingleProduct ? "可多选 PNG / JPG 批量生成 720×720" : "PNG / JPG supported";
    foodImageSubText.className = "mt-1 text-xs text-gray-400";
    renderPhotoQuality(null);
  }
});

sideImageInput?.addEventListener("change", function () {
  if (sideImageInput.files && sideImageInput.files[0]) {
    sideImageStatus.textContent = "已上传 " + sideImageInput.files[0].name;
    sideImageStatus.className = "text-xs font-bold text-green-600";
  } else {
    sideImageStatus.textContent = "No side uploaded";
    sideImageStatus.className = "text-xs font-semibold text-gray-400";
  }
});

drinkImageInput?.addEventListener("change", function () {
  if (drinkImageInput.files && drinkImageInput.files[0]) {
    drinkImageStatus.textContent = "已上传 " + drinkImageInput.files[0].name;
    drinkImageStatus.className = "text-xs font-bold text-green-600";
  } else {
    drinkImageStatus.textContent = "No drink uploaded";
    drinkImageStatus.className = "text-xs font-semibold text-gray-400";
  }
});

function setLoadingState() {
  generateButton.disabled = true;
  generateButton.textContent = "Generating...";
  regenerateButton.disabled = true;
  downloadButton.disabled = true;
  bundleDownloadButton.disabled = true;
  deliveryPackPanel?.classList.add("hidden");

  previewArea.className = "preview-box relative grid place-items-center";
  previewArea.innerHTML = `
    <div class="text-center px-6">
      <div class="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-white text-sm font-black shadow">WAIT</div>
      <p class="text-xl font-black text-gray-800">Generating...</p>
      <p class="mt-2 text-sm font-bold text-gray-500">AI is creating platform-ready delivery assets.</p>
    </div>
  `;
}

function resetButtonState() {
  generateButton.disabled = false;
  generateButton.textContent = "Generate Delivery Assets";
}

function showError(message) {
  previewArea.className = "preview-box relative grid place-items-center";
  previewArea.innerHTML = `
    <div class="text-center px-6">
      <div class="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-white text-sm font-black shadow">ERR</div>
      <p class="text-xl font-black text-red-600">Generate Failed</p>
      <p class="mt-2 text-sm font-bold text-gray-500">${escapeHtml(message)}</p>
    </div>
  `;
}

function showDeliveryPack(data) {
  latestBundleDownloadUrl = data.bundle_download_url || "";

  if (!deliveryPackPanel || !deliveryPackTitle || !deliveryPackItems) return;

  const pack = data.platform_pack;
  const items = data.items || [];
  if (!pack && items.length <= 1) {
    deliveryPackPanel.classList.add("hidden");
    return;
  }

  deliveryPackPanel.classList.remove("hidden");
  deliveryPackTitle.textContent = pack?.label || "Generated Assets";

  deliveryPackItems.innerHTML = items.map(item => `
    <div class="delivery-card">
      <p class="text-sm font-black text-gray-800">${escapeHtml(item.label || item.type || "Asset")}</p>
      <p class="mt-1 text-xs font-semibold text-gray-500">${item.width || "-"}×${item.height || "-"}</p>
      <p class="mt-1 text-xs font-medium text-gray-400">${escapeHtml(item.type || "")}</p>
    </div>
  `).join("");

  bundleDownloadButton.disabled = !latestBundleDownloadUrl;
}

function showGeneratedImage(data) {
  latestGeneratedItems = data.items?.length
    ? data.items
    : [{ image_url: data.image_url, download_url: data.download_url || data.image_url, filename: data.filename }];
  latestDownloadUrl = latestGeneratedItems[0].download_url || latestGeneratedItems[0].image_url;

  previewArea.className = "preview-box relative overflow-hidden bg-white";

  if (latestGeneratedItems.length > 1) {
    previewArea.innerHTML = `
      <div class="grid h-full w-full grid-cols-2 gap-3 overflow-y-auto bg-white p-4 md:grid-cols-3">
        ${latestGeneratedItems.map(function (item, index) {
          const img = item.image_url;
          const dl = item.download_url || img;
          return `
            <div class="overflow-hidden rounded-2xl border border-[#d7e4e7] bg-white shadow-sm">
              <img src="${img}?t=${Date.now()}" class="aspect-square w-full object-contain bg-white" alt="${escapeHtml(item.label || `Generated ${index + 1}`)}">
              <div class="p-3">
                <p class="truncate text-xs font-black text-gray-700">${escapeHtml(item.label || `Asset ${index + 1}`)}</p>
                <button type="button" class="batch-download mt-2 w-full rounded-xl border border-[#d7e4e7] px-3 py-2 text-xs font-black text-[#006064]" data-url="${escapeHtml(dl)}" data-filename="${escapeHtml(item.filename || "food-ai-design.png")}">Download</button>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;

    previewArea.querySelectorAll(".batch-download").forEach(function (btn) {
      btn.addEventListener("click", function () {
        downloadImage(btn.getAttribute("data-url"), btn.getAttribute("data-filename"));
      });
    });
  } else {
    previewArea.innerHTML = `<img src="${data.image_url}?t=${Date.now()}" class="h-full w-full object-contain bg-white" alt="Generated food visual" />`;
  }

  if (data.quality_reports && data.quality_reports[0]) {
    renderPhotoQuality(data.quality_reports[0]);
  }

  showDeliveryPack(data);
  regenerateButton.disabled = false;
  downloadButton.disabled = false;
}

async function generateVisual() {
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

    showGeneratedImage(data);
    saveWork(data.image_url, data.download_url);
    loadRecentDesigns();
    loadProfile();
  } catch (error) {
    showError(error.message || "Generate failed.");
    loadProfile();
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
  if (latestBundleDownloadUrl && latestGeneratedItems.length > 1) {
    window.location.href = latestBundleDownloadUrl;
    return;
  }

  if (!latestDownloadUrl) return;
  await downloadImage(latestDownloadUrl, latestGeneratedItems[0]?.filename);
});

bundleDownloadButton?.addEventListener("click", function () {
  if (latestBundleDownloadUrl) {
    window.location.href = latestBundleDownloadUrl;
  }
});

async function downloadImage(imageUrl, filename = "food-ai-design.png") {
  try {
    const response = await fetch(imageUrl);
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename || "food-ai-design.png";
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
            <p class="text-xs font-bold text-gray-700">${escapeHtml(item.title || "Food Design")}</p>
            <p class="mt-1 text-xs font-semibold text-gray-500">${new Date(item.created_at).toLocaleString()}</p>
          </div>
        </a>
      `;
    }).join("");
  } catch (error) {
    recentGrid.innerHTML = `
      <div class="col-span-full rounded-3xl bg-white p-8 text-center">
        <p class="text-lg font-black text-red-600">Failed to load designs</p>
        <p class="mt-1 text-sm text-gray-500">${escapeHtml(error.message)}</p>
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
        <p class="mt-1 text-sm text-gray-500">${escapeHtml(error.message)}</p>
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
          <p class="truncate text-sm font-black text-gray-800">${escapeHtml(title)}</p>
          <p class="mt-1 text-xs font-semibold uppercase text-gray-400">${escapeHtml(type)}</p>
          <p class="mt-1 text-xs text-gray-400">${escapeHtml(dateText)}</p>
          <div class="mt-3 grid grid-cols-2 gap-2">
            <a href="${imageUrl}" target="_blank" class="btn-secondary px-3 py-2 text-center text-xs">Open</a>
            <button type="button" class="download-design-btn btn-primary px-3 py-2 text-xs" data-url="${imageUrl}">Download</button>
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
updateFormMode();

if (isLoggedIn()) {
  loadProfile();
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/static/service-worker.js").catch(function () {});
  });
}

const SOCIAL_ENDPOINT = "/generate-social-kit";

const form = document.getElementById("socialKitForm");
const outputGrid = document.getElementById("outputGrid");
const generateButton = document.getElementById("generateButton");
const downloadAllButton = document.getElementById("downloadAllButton");
const foodImageInput = document.getElementById("foodImageInput");
const foodImageText = document.getElementById("foodImageText");
const foodImageSubText = document.getElementById("foodImageSubText");
const sideInput = document.getElementById("sideInput");
const drinkInput = document.getElementById("drinkInput");
const logoInput = document.getElementById("logoInput");
const sideStatus = document.getElementById("sideStatus");
const drinkStatus = document.getElementById("drinkStatus");
const logoStatus = document.getElementById("logoStatus");
const userEmailText = document.getElementById("userEmailText");
const logoutBtn = document.getElementById("logoutBtn");

const photoQualityPanel = document.getElementById("photoQualityPanel");
const photoQualityScore = document.getElementById("photoQualityScore");
const photoQualitySummary = document.getElementById("photoQualitySummary");
const photoQualityList = document.getElementById("photoQualityList");

let latestItems = [];
let latestBundleDownloadUrl = "";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getToken() {
  return localStorage.getItem("food_ai_token") || "";
}

function getUserId() {
  return localStorage.getItem("food_ai_user_id") || "";
}

function getUserEmail() {
  return localStorage.getItem("food_ai_user_email") || "";
}

function isLoggedIn() {
  return !!getToken() && !!getUserId();
}

function updateHeader() {
  const email = getUserEmail();
  if (email) {
    userEmailText.textContent = email;
    userEmailText.classList.remove("hidden");
    logoutBtn.classList.remove("hidden");
  }
}

logoutBtn?.addEventListener("click", function () {
  localStorage.removeItem("food_ai_token");
  localStorage.removeItem("food_ai_refresh_token");
  localStorage.removeItem("food_ai_user_id");
  localStorage.removeItem("food_ai_user_email");
  window.location.href = "/";
});

function bindFileStatus(input, label, emptyText, uploadedText) {
  input?.addEventListener("change", function () {
    if (input.files && input.files[0]) {
      label.textContent = uploadedText + ": " + input.files[0].name;
      label.className = "mt-2 truncate text-xs font-bold text-green-600";
    } else {
      label.textContent = emptyText;
      label.className = "mt-2 truncate text-xs font-semibold text-gray-400";
    }
  });
}

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

foodImageInput?.addEventListener("change", function () {
  if (foodImageInput.files && foodImageInput.files[0]) {
    foodImageText.textContent = "Main food uploaded";
    foodImageSubText.textContent = foodImageInput.files[0].name;
    foodImageSubText.className = "mt-1 text-xs font-semibold text-green-600";
    inspectLocalPhoto(foodImageInput.files[0]);
  } else {
    foodImageText.textContent = "Upload Main Food";
    foodImageSubText.textContent = "PNG / JPG supported";
    foodImageSubText.className = "mt-1 text-xs text-gray-400";
    renderPhotoQuality(null);
  }
});

bindFileStatus(sideInput, sideStatus, "No side", "Side uploaded");
bindFileStatus(drinkInput, drinkStatus, "No drink", "Drink uploaded");
bindFileStatus(logoInput, logoStatus, "Transparent PNG recommended", "Logo uploaded");

function getSelectedOutputLabels() {
  const labels = {
    feed: ["Feed", "1080×1080"],
    portrait: ["Portrait", "1080×1350"],
    story: ["Story / Status", "1080×1920"],
    facebook_ad: ["Facebook Ad", "1200×628"]
  };

  const selected = [...document.querySelectorAll('input[name="outputs"]:checked')].map(input => input.value);
  return selected.map(value => ({ value, label: labels[value]?.[0] || value, size: labels[value]?.[1] || "" }));
}

function setLoadingState() {
  generateButton.disabled = true;
  generateButton.textContent = "Generating Social Kit...";
  downloadAllButton.disabled = true;

  const selected = getSelectedOutputLabels();
  outputGrid.innerHTML = selected.map(item => `
    <div class="output-card">
      <div class="output-empty checker grid place-items-center p-6 text-center">
        <div>
          <div class="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-white text-xs font-black shadow-lg">WAIT</div>
          <p class="font-black text-gray-800">Generating ${escapeHtml(item.label)}</p>
          <p class="mt-1 text-xs font-semibold text-gray-400">${escapeHtml(item.size)}</p>
        </div>
      </div>
    </div>
  `).join("");
}

function resetButtonState() {
  generateButton.disabled = false;
  generateButton.textContent = "Generate Social Media Kit";
}

function showError(message) {
  outputGrid.innerHTML = `
    <div class="output-card md:col-span-2">
      <div class="output-empty checker grid place-items-center p-6 text-center">
        <div>
          <div class="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-white text-xs font-black shadow-lg">ERR</div>
          <p class="font-black text-red-600">Generate Failed</p>
          <p class="mt-2 text-sm font-medium text-gray-500">${escapeHtml(message)}</p>
        </div>
      </div>
    </div>
  `;
}

function showResults(data) {
  latestItems = data.items || [];
  latestBundleDownloadUrl = data.bundle_download_url || "";

  if (data.quality_reports && data.quality_reports[0]) {
    renderPhotoQuality(data.quality_reports[0]);
  }

  if (!latestItems.length) {
    showError("No image was generated.");
    return;
  }

  outputGrid.innerHTML = latestItems.map(item => `
    <div class="output-card">
      <a href="${item.image_url}" target="_blank" class="block bg-white">
        <img src="${item.image_url}?t=${Date.now()}" class="w-full bg-white object-contain" alt="${escapeHtml(item.label)}">
      </a>
      <div class="flex items-center justify-between gap-3 p-4">
        <div>
          <p class="text-sm font-black text-gray-800">${escapeHtml(item.label)}</p>
          <p class="mt-1 text-xs font-semibold text-gray-500">${item.width}×${item.height}</p>
        </div>
        <button type="button" class="btn-secondary px-4 py-3 text-xs" onclick="downloadImage('${item.download_url || item.image_url}', '${item.filename || "food-ai-social-kit.png"}')">Download</button>
      </div>
    </div>
  `).join("");

  downloadAllButton.disabled = !latestBundleDownloadUrl;
}

async function downloadImage(imageUrl, filename = "food-ai-social-kit.png") {
  try {
    const response = await fetch(imageUrl);
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename || "food-ai-social-kit.png";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(blobUrl);
  } catch {
    alert("Download failed. Please try again.");
  }
}

window.downloadImage = downloadImage;

downloadAllButton?.addEventListener("click", function () {
  if (latestBundleDownloadUrl) {
    window.location.href = latestBundleDownloadUrl;
  }
});

async function generateSocialKit() {
  if (!isLoggedIn()) {
    alert("请先在 Product Studio 登录后再使用 Social Media Kit。");
    window.location.href = "/";
    return;
  }

  if (!foodImageInput.files || !foodImageInput.files[0]) {
    showError("Please upload main food image first.");
    return;
  }

  const selected = document.querySelectorAll('input[name="outputs"]:checked');
  if (!selected.length) {
    showError("Please select at least one output size.");
    return;
  }

  setLoadingState();

  try {
    const formData = new FormData(form);
    formData.append("user_id", getUserId());
    formData.append("user_email", getUserEmail());

    const response = await fetch(SOCIAL_ENDPOINT, {
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

    showResults(data);
  } catch (error) {
    showError(error.message || "Generate failed.");
  } finally {
    resetButtonState();
  }
}

form?.addEventListener("submit", function (event) {
  event.preventDefault();
  generateSocialKit();
});

updateHeader();

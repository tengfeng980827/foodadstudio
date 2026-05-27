const GENERATE_ENDPOINT = "/generate";

const screens = {
  home: document.getElementById("homeScreen"),
  create: document.getElementById("createScreen"),
  templates: document.getElementById("templatesScreen"),
  works: document.getElementById("worksScreen"),
};

function switchTab(tab) {
  Object.values(screens).forEach((screen) => {
    if (screen) screen.classList.remove("active");
  });

  if (screens[tab]) {
    screens[tab].classList.add("active");
  } else {
    screens.home.classList.add("active");
  }

  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
}

document.querySelectorAll("[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => {
    switchTab(btn.dataset.tab);
  });
});

document.getElementById("goCreateBtn")?.addEventListener("click", () => {
  switchTab("create");
});

document.querySelectorAll(".size-card").forEach((card) => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".size-card").forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");

    const size = card.dataset.size;
    const select = document.getElementById("canvasSize");
    if (select && size !== "custom") select.value = size;

    switchTab("create");
  });
});

const form = document.getElementById("generateForm");
const loadingBox = document.getElementById("loadingBox");
const resultImage = document.getElementById("resultImage");
const downloadBtn = document.getElementById("downloadBtn");

form?.addEventListener("submit", async (e) => {
  e.preventDefault();

  loadingBox.classList.remove("hidden");
  resultImage.classList.add("hidden");
  downloadBtn.classList.add("hidden");

  const formData = new FormData(form);

  try {
    const res = await fetch(GENERATE_ENDPOINT, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error("生成失败");
    }

    const data = await res.json();

    const imageUrl =
      data.image_url ||
      data.url ||
      data.output_url ||
      data.result ||
      data.image;

    if (!imageUrl) {
      throw new Error("后端没有返回图片链接");
    }

    resultImage.src = imageUrl;
    downloadBtn.href = imageUrl;

    resultImage.classList.remove("hidden");
    downloadBtn.classList.remove("hidden");

    saveWork(imageUrl);
    renderWorks();
  } catch (err) {
    alert("生成失败：" + err.message);
  } finally {
    loadingBox.classList.add("hidden");
  }
});

function saveWork(imageUrl) {
  const works = JSON.parse(localStorage.getItem("food_ai_works") || "[]");

  works.unshift({
    imageUrl,
    time: new Date().toLocaleString(),
  });

  localStorage.setItem("food_ai_works", JSON.stringify(works.slice(0, 20)));
}

function renderWorks() {
  const worksList = document.getElementById("worksList");
  if (!worksList) return;

  const works = JSON.parse(localStorage.getItem("food_ai_works") || "[]");

  if (!works.length) {
    worksList.innerHTML = `
      <div class="empty-state">
        暂时还没有作品，先去生成第一张吧。
      </div>
    `;
    return;
  }

  worksList.innerHTML = works
    .map(
      (item) => `
      <div class="work-item">
        <img src="${item.imageUrl}" alt="生成作品" />
        <p>${item.time}</p>
      </div>
    `
    )
    .join("");
}

renderWorks();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

const loginOpenBtn = document.getElementById("loginOpenBtn");
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

function showAuthMessage(message) {
  authMessage.textContent = message;
  authMessage.classList.remove("hidden");
}

function clearAuthMessage() {
  authMessage.textContent = "";
  authMessage.classList.add("hidden");
}

function openAuthModal() {
  clearAuthMessage();
  authModal.classList.remove("hidden");
}

function closeAuthModal() {
  authModal.classList.add("hidden");
}

function showLoginTab() {
  loginTabBtn.classList.add("active");
  registerTabBtn.classList.remove("active");
  loginForm.classList.remove("hidden");
  registerForm.classList.add("hidden");
  clearAuthMessage();
}

function showRegisterTab() {
  registerTabBtn.classList.add("active");
  loginTabBtn.classList.remove("active");
  registerForm.classList.remove("hidden");
  loginForm.classList.add("hidden");
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

function updateAuthUI() {
  const token = getToken();
  const email = getUserEmail();

  if (token && email) {
    loginOpenBtn.classList.add("hidden");
    userBox.classList.remove("hidden");
    userEmailText.textContent = email;
  } else {
    loginOpenBtn.classList.remove("hidden");
    userBox.classList.add("hidden");
    userEmailText.textContent = "";
  }
}

loginOpenBtn?.addEventListener("click", openAuthModal);
authCloseBtn?.addEventListener("click", closeAuthModal);

authModal?.addEventListener("click", (e) => {
  if (e.target === authModal) closeAuthModal();
});

loginTabBtn?.addEventListener("click", showLoginTab);
registerTabBtn?.addEventListener("click", showRegisterTab);

logoutBtn?.addEventListener("click", () => {
  clearSession();
  alert("已退出登录");
});

registerForm?.addEventListener("submit", async (e) => {
  e.preventDefault();

  clearAuthMessage();

  const email = document.getElementById("registerEmail").value.trim();
  const password = document.getElementById("registerPassword").value;

  try {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.msg || data.error || data.message || "注册失败");
    }

    showAuthMessage("注册成功，请检查邮箱验证，或直接尝试登录。");
    showLoginTab();
    document.getElementById("loginEmail").value = email;
  } catch (err) {
    showAuthMessage("注册失败：" + err.message);
  }
});

loginForm?.addEventListener("submit", async (e) => {
  e.preventDefault();

  clearAuthMessage();

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.msg || data.error || data.message || "登录失败");
    }

    saveSession(data, email);
    closeAuthModal();
    alert("登录成功");
  } catch (err) {
    showAuthMessage("登录失败：" + err.message);
  }
});

updateAuthUI();
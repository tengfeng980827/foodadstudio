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
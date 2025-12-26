const API_BASE_URL = "https://ton-backend.com"; // à adapter

const form = document.getElementById("download-form");
const urlInput = document.getElementById("video-url");
const analyzeBtn = document.getElementById("analyze-btn");
const errorBox = document.getElementById("error-box");
const infoBox = document.getElementById("info-box");
const videoMetaBlock = document.getElementById("video-meta");
const thumbEl = document.getElementById("thumb");
const titleEl = document.getElementById("title");
const platformLabelEl = document.getElementById("platform-label");
const formatsContainer = document.getElementById("formats");
const placeholder = document.getElementById("placeholder");

document.getElementById("year").textContent = new Date().getFullYear();

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

function showInfo(msg) {
  infoBox.textContent = msg;
  infoBox.classList.remove("hidden");
}

function clearInfo() {
  infoBox.classList.add("hidden");
  infoBox.textContent = "";
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  clearInfo();

  const url = urlInput.value.trim();
  if (!url) {
    showError("Merci de coller un lien valide.");
    return;
  }

  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyse en cours…";

  placeholder.classList.remove("hidden");
  videoMetaBlock.classList.add("hidden");
  formatsContainer.classList.add("hidden");
  formatsContainer.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Analyse impossible. Vérifiez le lien.");
    }

    const data = await res.json();
    renderVideoInfo(data);
    renderFormats(data);
  } catch (err) {
    showError(err.message || "Une erreur s'est produite.");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyser";
  }
});

function renderVideoInfo(data) {
  placeholder.classList.add("hidden");
  videoMetaBlock.classList.remove("hidden");

  thumbEl.src = data.thumbnail || "";
  thumbEl.style.display = data.thumbnail ? "block" : "none";
  titleEl.textContent = data.title || "Vidéo détectée";
  platformLabelEl.textContent = `${data.platform.toUpperCase()} • Durée : ${data.duration || "N/A"}`;
}

function renderFormats(data) {
  formatsContainer.classList.remove("hidden");
  formatsContainer.innerHTML = "";

  const formats = data.formats || [];
  if (!formats.length) {
    formatsContainer.innerHTML = "<p>Aucun format téléchargeable trouvé.</p>";
    return;
  }

  formats.forEach((f) => {
    const row = document.createElement("div");
    row.className = "format-row";

    const main = document.createElement("div");
    main.className = "format-main";
    main.textContent = `${f.quality || f.resolution || "Auto"} • ${f.ext || "mp4"}`;

    const meta = document.createElement("div");
    meta.className = "format-meta";
    meta.textContent = `${f.filesize_human || "Taille inconnue"}`;

    const type = document.createElement("div");
    type.className = "format-type";
    type.textContent = f.is_audio ? "Audio" : "Vidéo";

    const btn = document.createElement("button");
    btn.className = "format-btn";
    btn.textContent = "Télécharger";

    btn.addEventListener("click", () => {
      const params = new URLSearchParams({
        url: data.original_url,
        format_id: f.format_id,
      });
      window.location.href = `${API_BASE_URL}/api/download?${params.toString()}`;
    });

    const left = document.createElement("div");
    left.appendChild(main);
    left.appendChild(meta);

    row.appendChild(left);
    row.appendChild(type);
    row.appendChild(btn);

    formatsContainer.appendChild(row);
  });
}

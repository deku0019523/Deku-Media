# deku_media_single_file.py

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from pathlib import Path
import uuid
import yt_dlp

# ==========================
# Config et initialisation
# ==========================

app = FastAPI(title="Deku-Media 2.0 - Single File")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


# ==========================
# Utilitaires yt-dlp
# ==========================

def detect_platform(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u:
        return "instagram"
    if "facebook.com" in u or "fb.watch" in u:
        return "facebook"
    if "pinterest." in u:
        return "pinterest"
    if "twitter.com" in u or "x.com" in u:
        return "twitter"
    return "unknown"


def get_video_info(url: str) -> dict:
    """
    Analyse une URL et retourne les infos + formats.
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    for f in info.get("formats", []):
        if not f.get("url"):
            continue

        is_audio = f.get("vcodec") == "none"
        resolution = f"{f.get('width') or ''}x{f.get('height') or ''}".strip("x")
        quality = f.get("format_note") or resolution or ("audio" if is_audio else "video")

        size_bytes = f.get("filesize") or f.get("filesize_approx")
        if size_bytes:
            size_mb = size_bytes / (1024 * 1024)
            size_str = f"{size_mb:.1f} Mo"
        else:
            size_str = "Taille inconnue"

        formats.append({
            "format_id": f.get("format_id"),
            "ext": f.get("ext"),
            "resolution": resolution,
            "quality": quality,
            "is_audio": is_audio,
            "filesize_human": size_str,
        })

    def sort_key(fmt):
        q = fmt["quality"] or ""
        if "K" in q:
            try:
                return int(q.replace("K", "")) * 1000
            except ValueError:
                pass
        try:
            h = int((fmt["resolution"] or "0x0").split("x")[1])
        except Exception:
            h = 0
        return h

    formats = sorted(formats, key=sort_key)

    thumb = info.get("thumbnail")
    title = info.get("title")
    duration = info.get("duration")  # secondes

    if duration:
        minutes = duration // 60
        seconds = duration % 60
        duration_str = f"{minutes}m{seconds:02d}s"
    else:
        duration_str = None

    return {
        "title": title,
        "thumbnail": thumb,
        "duration": duration_str,
        "platform": detect_platform(url),
        "formats": formats,
        "original_url": url,
    }


def download_video(url: str, format_id: str, output_dir: str) -> str:
    """
    Télécharge la vidéo/audio pour format_id et renvoie le chemin final.
    """
    ydl_opts = {
        "format": format_id,
        "outtmpl": f"{output_dir}/%(title).80s-%(id)s.%(ext)s",
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        info = ydl.extract_info(url, download=False)
        filename = ydl.prepare_filename(info)
    return filename


# ==========================
# Schémas API
# ==========================

class AnalyzeRequest(BaseModel):
    url: HttpUrl


class AnalyzeResponse(BaseModel):
    title: str | None
    thumbnail: str | None
    duration: str | None
    platform: str
    formats: list[dict]
    original_url: str


# ==========================
# Route HTML (frontend)
# ==========================

HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>Deku-Media 2.0 - Téléchargement Vidéos</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    :root {
      --bg: #050816;
      --bg-alt: #0b1020;
      --accent: #22c55e;
      --accent-soft: rgba(34, 197, 94, 0.1);
      --text: #f9fafb;
      --muted: #9ca3af;
      --error: #f97373;
      --info: #3b82f6;
      --radius: 12px;
      --shadow-soft: 0 18px 40px rgba(15, 23, 42, 0.6);
    }

    *,
    *::before,
    *::after {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
      background: radial-gradient(circle at top, #111827 0, #020617 45%, #000 100%);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }

    .container {
      width: 100%;
      max-width: 1100px;
      margin: 0 auto;
      padding: 0 1.25rem;
    }

    .dm-header {
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(18px);
      background: linear-gradient(to bottom, rgba(2, 6, 23, 0.9), transparent);
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    }

    .header-inner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.75rem 0;
    }

    .logo {
      font-weight: 800;
      letter-spacing: 0.04em;
      display: flex;
      align-items: baseline;
      gap: 0.15rem;
    }

    .logo-main {
      font-size: 1.1rem;
      color: var(--accent);
    }

    .logo-sub {
      font-size: 0.9rem;
      color: var(--muted);
    }

    .nav {
      display: flex;
      gap: 1.2rem;
      font-size: 0.9rem;
    }

    .nav a {
      color: var(--muted);
      text-decoration: none;
      position: relative;
      padding-bottom: 0.2rem;
    }

    .nav a:hover {
      color: var(--text);
    }

    .nav a::after {
      content: "";
      position: absolute;
      left: 0;
      bottom: 0;
      width: 0;
      height: 2px;
      background: var(--accent);
      transition: width 0.2s ease-out;
    }

    .nav a:hover::after {
      width: 100%;
    }

    .hero {
      padding: 4rem 0 3rem;
    }

    .hero-inner {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
      gap: 2rem;
      align-items: flex-start;
    }

    .hero-text h1 {
      font-size: clamp(1.9rem, 3vw, 2.4rem);
      margin: 0 0 0.75rem;
    }

    .hero-text p {
      margin: 0 0 1.5rem;
      color: var(--muted);
    }

    .download-form label {
      font-size: 0.9rem;
      color: var(--muted);
      display: block;
      margin-bottom: 0.35rem;
    }

    .input-group {
      display: flex;
      gap: 0.6rem;
      margin-bottom: 0.35rem;
    }

    .input-group input {
      flex: 1;
      padding: 0.75rem 0.9rem;
      border-radius: var(--radius);
      border: 1px solid rgba(148, 163, 184, 0.35);
      background: rgba(15, 23, 42, 0.8);
      color: var(--text);
      outline: none;
    }

    .input-group input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.4);
    }

    .input-group button {
      padding: 0.75rem 1.2rem;
      border-radius: var(--radius);
      border: none;
      background: linear-gradient(135deg, #22c55e, #16a34a);
      color: #0b1120;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }

    .input-group button:disabled {
      opacity: 0.6;
      cursor: wait;
    }

    .input-hint {
      font-size: 0.78rem;
      color: var(--muted);
    }

    .alert {
      margin-top: 0.75rem;
      padding: 0.6rem 0.8rem;
      border-radius: 0.75rem;
      font-size: 0.82rem;
    }

    .alert-error {
      background: rgba(239, 68, 68, 0.12);
      color: #fecaca;
      border: 1px solid rgba(248, 113, 113, 0.5);
    }

    .alert-info {
      background: rgba(59, 130, 246, 0.12);
      color: #bfdbfe;
      border: 1px solid rgba(96, 165, 250, 0.5);
    }

    .hidden {
      display: none !important;
    }

    .hero-card {
      background: radial-gradient(circle at top left, #1e293b 0, #020617 60%);
      border-radius: 1.4rem;
      padding: 1.2rem;
      box-shadow: var(--shadow-soft);
      border: 1px solid rgba(148, 163, 184, 0.3);
      min-height: 220px;
    }

    .hero-card p {
      color: var(--muted);
      font-size: 0.9rem;
    }

    #video-meta {
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr);
      gap: 0.75rem;
      margin-bottom: 1rem;
    }

    #thumb {
      width: 100%;
      border-radius: 0.8rem;
      object-fit: cover;
    }

    #title {
      font-size: 1rem;
      margin: 0 0 0.35rem;
    }

    #platform-label {
      font-size: 0.8rem;
      color: var(--muted);
    }

    .formats-list {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }

    .format-row {
      display: grid;
      grid-template-columns: 1.2fr 0.9fr auto;
      gap: 0.6rem;
      align-items: center;
      padding: 0.4rem 0.5rem;
      border-radius: 0.8rem;
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(51, 65, 85, 0.9);
    }

    .format-main {
      font-size: 0.86rem;
    }

    .format-meta {
      font-size: 0.78rem;
      color: var(--muted);
    }

    .format-type {
      font-size: 0.8rem;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      justify-self: flex-start;
    }

    .format-btn {
      padding: 0.45rem 0.75rem;
      border-radius: 999px;
      border: none;
      background: rgba(34, 197, 94, 0.15);
      color: var(--accent);
      font-size: 0.78rem;
      cursor: pointer;
      white-space: nowrap;
    }

    .format-btn:hover {
      background: rgba(34, 197, 94, 0.3);
    }

    .section {
      padding: 3rem 0;
    }

    .section-alt {
      background: radial-gradient(circle at top, #020617 0, #020617 40%, #000 100%);
    }

    .section h2 {
      margin-top: 0;
      margin-bottom: 1.5rem;
    }

    .steps {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.5rem;
    }

    .step {
      background: rgba(15, 23, 42, 0.9);
      border-radius: 1rem;
      padding: 1rem;
      border: 1px solid rgba(148, 163, 184, 0.2);
    }

    .step-number {
      display: inline-flex;
      width: 1.6rem;
      height: 1.6rem;
      border-radius: 999px;
      align-items: center;
      justify-content: center;
      font-size: 0.8rem;
      background: var(--accent-soft);
      color: var(--accent);
      margin-bottom: 0.4rem;
    }

    .platform-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 1rem;
    }

    .platform-item {
      padding: 0.9rem 1rem;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid rgba(148, 163, 184, 0.25);
      font-size: 0.9rem;
      text-align: center;
    }

    .platform-item.yt { border-color: #ef4444; }
    .platform-item.tiktok { border-color: #0ea5e9; }
    .platform-item.insta { border-color: #db2777; }
    .platform-item.fb { border-color: #3b82f6; }
    .platform-item.pin { border-color: #f97316; }
    .platform-item.tw { border-color: #e5e7eb; }

    .faq-list details {
      background: rgba(15, 23, 42, 0.95);
      border-radius: 0.9rem;
      padding: 0.7rem 0.9rem;
      margin-bottom: 0.6rem;
      border: 1px solid rgba(148, 163, 184, 0.2);
    }

    .faq-list summary {
      cursor: pointer;
      font-size: 0.9rem;
      list-style: none;
    }

    .faq-list summary::-webkit-details-marker {
      display: none;
    }

    .dm-footer {
      border-top: 1px solid rgba(148, 163, 184, 0.25);
      padding: 1rem 0;
      background: #020617;
    }

    .footer-inner {
      text-align: center;
      font-size: 0.8rem;
      color: var(--muted);
    }

    @media (max-width: 800px) {
      .hero-inner {
        grid-template-columns: minmax(0, 1fr);
      }

      .hero-card {
        order: -1;
      }

      .nav {
        display: none;
      }
    }

    @media (max-width: 480px) {
      .input-group {
        flex-direction: column;
      }

      .format-row {
        grid-template-columns: 1.4fr auto;
        grid-template-rows: auto auto;
      }

      .format-type {
        justify-self: flex-end;
      }
    }
  </style>
</head>
<body>
  <header class="dm-header">
    <div class="container header-inner">
      <div class="logo">
        <span class="logo-main">Deku</span><span class="logo-sub">-Media 2.0</span>
      </div>
      <nav class="nav">
        <a href="#home">Accueil</a>
        <a href="#how-it-works">Comment ça marche</a>
        <a href="#platforms">Plateformes</a>
        <a href="#faq">FAQ</a>
        <a href="#legal">Mentions légales</a>
      </nav>
    </div>
  </header>

  <main>
    <section id="home" class="hero">
      <div class="container hero-inner">
        <div class="hero-text">
          <h1>Téléchargez vos vidéos en 1 clic</h1>
          <p>Deku-Media 2.0 permet de télécharger des vidéos multi-plateformes via un simple lien, sans inscription.</p>
          <form id="download-form" class="download-form">
            <label for="video-url">Collez le lien de la vidéo</label>
            <div class="input-group">
              <input type="url" id="video-url" placeholder="https://youtu.be/..." required />
              <button type="submit" id="analyze-btn">Analyser</button>
            </div>
            <p class="input-hint">YouTube, TikTok, Instagram, Facebook, Pinterest, X (Twitter)...</p>
          </form>

          <div id="error-box" class="alert alert-error hidden"></div>
          <div id="info-box" class="alert alert-info hidden"></div>
        </div>

        <div class="hero-card" id="result-card" aria-live="polite">
          <div id="placeholder">
            <p>Les formats disponibles s’afficheront ici après l’analyse.</p>
          </div>
          <div id="video-meta" class="hidden">
            <img id="thumb" alt="Miniature vidéo" />
            <h2 id="title"></h2>
            <p id="platform-label"></p>
          </div>
          <div id="formats" class="formats-list hidden"></div>
        </div>
      </div>
    </section>

    <section id="how-it-works" class="section">
      <div class="container">
        <h2>Comment ça marche ?</h2>
        <div class="steps">
          <div class="step">
            <span class="step-number">1</span>
            <h3>Collez le lien</h3>
            <p>Copiez l’URL de la vidéo depuis YouTube, TikTok, Instagram, Facebook, etc.</p>
          </div>
          <div class="step">
            <span class="step-number">2</span>
            <h3>Analyse automatique</h3>
            <p>La plateforme est détectée et les formats disponibles sont listés (144p à 4K, audio seul si possible).</p>
          </div>
          <div class="step">
            <span class="step-number">3</span>
            <h3>Téléchargez</h3>
            <p>Choisissez la qualité et cliquez sur « Télécharger ».</p>
          </div>
        </div>
      </div>
    </section>

    <section id="platforms" class="section section-alt">
      <div class="container">
        <h2>Plateformes prises en charge</h2>
        <div class="platform-grid">
          <div class="platform-item yt">YouTube</div>
          <div class="platform-item tiktok">TikTok</div>
          <div class="platform-item insta">Instagram</div>
          <div class="platform-item fb">Facebook</div>
          <div class="platform-item pin">Pinterest</div>
          <div class="platform-item tw">X / Twitter</div>
        </div>
      </div>
    </section>

    <section id="faq" class="section">
      <div class="container">
        <h2>FAQ</h2>
        <div class="faq-list">
          <details>
            <summary>Le service est-il gratuit ?</summary>
            <p>Oui, Deku-Media 2.0 permet le téléchargement sans inscription et sans frais cachés.</p>
          </details>
          <details>
            <summary>Puis-je télécharger en 4K ?</summary>
            <p>Si la vidéo source propose la 4K, elle sera listée dans les formats disponibles.</p>
          </details>
          <details>
            <summary>Est-ce légal de télécharger des vidéos ?</summary>
            <p>Le téléchargement de contenus protégés par le droit d’auteur sans autorisation peut être contraire à la loi et aux CGU des plateformes. Utilisez cet outil uniquement pour des contenus dont vous avez les droits. [web:20][web:23][web:32]</p>
          </details>
          <details>
            <summary>Mes données sont-elles enregistrées ?</summary>
            <p>Aucune inscription n’est requise. Les liens ne sont pas stockés au-delà du traitement technique.</p>
          </details>
        </div>
      </div>
    </section>

    <section id="legal" class="section section-alt">
      <div class="container">
        <h2>Mentions légales & Politique de confidentialité</h2>
        <p>Deku-Media 2.0 est un outil technique. Vous êtes seul responsable de l’usage des fichiers téléchargés. Le site suit les bonnes pratiques de sécurité et de confidentialité des données. [web:26]</p>
      </div>
    </section>
  </main>

  <footer class="dm-footer">
    <div class="container footer-inner">
      <p>© <span id="year"></span> Deku-Media 2.0 — Tous droits réservés.</p>
    </div>
  </footer>

  <script>
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
        const res = await fetch("/api/analyze", {
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
      platformLabelEl.textContent = (data.platform || "inconnu").toUpperCase() + " • Durée : " + (data.duration || "N/A");
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
        main.textContent = (f.quality || f.resolution || "Auto") + " • " + (f.ext || "mp4");

        const meta = document.createElement("div");
        meta.className = "format-meta";
        meta.textContent = f.filesize_human || "Taille inconnue";

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
          window.location.href = "/api/download?" + params.toString();
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
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


# ==========================
# API Routes
# ==========================

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_video(payload: AnalyzeRequest):
    url = str(payload.url)
    try:
        info = get_video_info(url)
        if not info["formats"]:
            raise HTTPException(status_code=400, detail="Aucun format disponible pour ce lien.")
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analyse impossible : {e}")


@app.get("/api/download")
def download_endpoint(
    url: str = Query(...),
    format_id: str = Query(...)
):
    if not url or not format_id:
        raise HTTPException(status_code=400, detail="Paramètres manquants.")

    temp_dir = DOWNLOAD_DIR / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path = download_video(url, format_id, str(temp_dir))
        file_path = Path(file_path)
        if not file_path.exists():
            raise HTTPException(status_code=500, detail="Fichier introuvable après téléchargement.")

        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Téléchargement impossible : {e}")
    finally:
        # Nettoyage différé possible via cron/task externe
        pass


# ==========================
# Lancement (uvicorn)
# ==========================
# uvicorn deku_media_single_file:app --reload --port 8000

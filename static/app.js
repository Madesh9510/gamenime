let debounceTimer = null;
let currentView = "home"; // "home" | "favorites" — "search" no longer used here; search is a real page now

const GENRES = ["action", "adventure", "rpg", "shooter", "puzzle", "racing", "sports", "strategy", "indie", "casual", "simulation", "platformer"];
const PLATFORMS = [
  { value: "pc", label: "PC" },
  { value: "ps5", label: "PlayStation 5" },
  { value: "xbox-series", label: "Xbox Series X/S" },
  { value: "switch", label: "Nintendo Switch" },
  { value: "ps4", label: "PlayStation 4" },
  { value: "xbox-one", label: "Xbox One" },
];
const FAV_KEY = "pixelscope_favorites";
const RECENT_KEY = "pixelscope_recent";

// ---- Translations (add a new language by adding one more block below) ----
const translations = {
  en: {
    tagline: "Search any game. See real ratings. Instantly.",
    surpriseMe: "🎲 Surprise Me",
    favorites: "☆ Favorites",
    advanced: "Advanced",
    search: "Search",
    searchPlaceholder: "Search for a game… e.g. Red Dead Redemption",
    recentlyViewed: "Recently Viewed",
    recommended: "🤖 Recommended For You",
  },
  es: {
    tagline: "Busca cualquier juego. Ve valoraciones reales. Al instante.",
    surpriseMe: "🎲 Sorpréndeme",
    favorites: "☆ Favoritos",
    advanced: "Avanzado",
    search: "Buscar",
    searchPlaceholder: "Busca un juego… ej. Red Dead Redemption",
    recentlyViewed: "Vistos Recientemente",
    recommended: "🤖 Recomendado Para Ti",
  },
  fr: {
    tagline: "Recherchez n'importe quel jeu. Voyez de vraies notes. Instantanément.",
    surpriseMe: "🎲 Surprends-moi",
    favorites: "☆ Favoris",
    advanced: "Avancé",
    search: "Rechercher",
    searchPlaceholder: "Rechercher un jeu… ex. Red Dead Redemption",
    recentlyViewed: "Vus Récemment",
    recommended: "🤖 Recommandé Pour Vous",
  },
  de: {
    tagline: "Finde jedes Spiel. Sieh echte Bewertungen. Sofort.",
    surpriseMe: "🎲 Überrasch Mich",
    favorites: "☆ Favoriten",
    advanced: "Erweitert",
    search: "Suchen",
    searchPlaceholder: "Nach einem Spiel suchen… z.B. Red Dead Redemption",
    recentlyViewed: "Kürzlich Angesehen",
    recommended: "🤖 Für Dich Empfohlen",
  },
  hi: {
    tagline: "कोई भी गेम खोजें। असली रेटिंग देखें। तुरंत।",
    surpriseMe: "🎲 मुझे चौंकाएं",
    favorites: "☆ पसंदीदा",
    advanced: "उन्नत खोज",
    search: "खोजें",
    searchPlaceholder: "गेम खोजें… जैसे Red Dead Redemption",
    recentlyViewed: "हाल ही में देखे गए",
    recommended: "🤖 आपके लिए सुझाव",
  },
  ja: {
    tagline: "ゲームを検索。実際の評価を見る。すぐに。",
    surpriseMe: "🎲 おまかせ",
    favorites: "☆ お気に入り",
    advanced: "詳細検索",
    search: "検索",
    searchPlaceholder: "ゲームを検索… 例: Red Dead Redemption",
    recentlyViewed: "最近見たゲーム",
    recommended: "🤖 あなたへのおすすめ",
  },
};
let currentLang = localStorage.getItem("pixelscope_lang") || "en";

function applyTranslations() {
  const dict = translations[currentLang] || translations.en;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) el.textContent = dict[key];
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (dict[key]) el.placeholder = dict[key];
  });
}

const langSelect = document.getElementById("langSelect");
if (langSelect) {
  langSelect.value = currentLang;
  langSelect.addEventListener("change", () => {
    currentLang = langSelect.value;
    localStorage.setItem("pixelscope_lang", currentLang);
    applyTranslations();
  });
}
applyTranslations();

const input = document.getElementById("searchInput");
const statusEl = document.getElementById("status");
const genreFilter = document.getElementById("genreFilter");
const platformFilter = document.getElementById("platformFilter");
const yearFilter = document.getElementById("yearFilter");
const ratingFilter = document.getElementById("ratingFilter");
const typeFilter = document.getElementById("typeFilter");
const filtersToggle = document.getElementById("filtersToggle");
const filtersPanel = document.getElementById("filtersPanel");
const advancedSearchBtn = document.getElementById("advancedSearchBtn");
const suggestDropdown = document.getElementById("suggestDropdown");
const glowBackdrop = document.getElementById("glowBackdrop");
const favToggle = document.getElementById("favToggle");
const themeToggle = document.getElementById("themeToggle");
const backToTopBtn = document.getElementById("backToTopBtn");

const homeSections = document.getElementById("homeSections");
const recentSection = document.getElementById("recentSection");
const recentGrid = document.getElementById("recentGrid");
const searchResultsView = document.getElementById("searchResultsView");
const backToHomeBtn = document.getElementById("backToHomeBtn");
const favoritesView = document.getElementById("favoritesView");
const favoritesGrid = document.getElementById("favoritesGrid");

// ---- Cursor-follow ambient glow ----
document.addEventListener("mousemove", (e) => {
  glowBackdrop.style.setProperty("--mx", `${e.clientX}px`);
  glowBackdrop.style.setProperty("--my", `${e.clientY}px`);
});

// ---- Parallax hero blobs + back to top ----
const heroBlobs = document.querySelectorAll(".hero-blob");
window.addEventListener("scroll", () => {
  const offset = window.scrollY;
  heroBlobs.forEach((el, i) => {
    el.style.transform = `translateY(${offset * (0.12 + i * 0.08)}px)`;
  });
  backToTopBtn.classList.toggle("visible", offset > 400);
});
backToTopBtn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

// ---- Theme toggle ----
function applyThemeLabel() {
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  themeToggle.textContent = isLight ? "☀️ Light" : "🌙 Dark";
}
applyThemeLabel();
themeToggle.addEventListener("click", () => {
  const isLight = document.documentElement.getAttribute("data-theme") === "light";
  if (isLight) {
    document.documentElement.removeAttribute("data-theme");
    localStorage.setItem("pixelscope_theme", "dark");
  } else {
    document.documentElement.setAttribute("data-theme", "light");
    localStorage.setItem("pixelscope_theme", "light");
  }
  applyThemeLabel();
});

// ---- Favorites (saved locally in this browser, no account needed) ----
function getFavorites() {
  try { return JSON.parse(localStorage.getItem(FAV_KEY) || "{}"); }
  catch (err) { return {}; }
}
function isFavorite(id) { return !!getFavorites()[id]; }
function saveFavorite(item) {
  const favs = getFavorites();
  favs[item.id] = item;
  localStorage.setItem(FAV_KEY, JSON.stringify(favs));
}
function removeFavorite(id) {
  const favs = getFavorites();
  delete favs[id];
  localStorage.setItem(FAV_KEY, JSON.stringify(favs));
}
function escapeAttr(str) { return String(str || "").replace(/"/g, "&quot;"); }

function syncFavButtonStates() {
  document.querySelectorAll(".fav-btn[data-id]").forEach((btn) => {
    if (isFavorite(btn.dataset.id)) btn.classList.add("active");
  });
}

// ---- Recently viewed (edit/delete supported here; written from game_detail.html) ----
function getRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); }
  catch (err) { return []; }
}

function removeFromRecent(id) {
  const recent = getRecent().filter((g) => String(g.id) !== String(id));
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
  renderRecent();
}

function clearRecent() {
  localStorage.setItem(RECENT_KEY, "[]");
  renderRecent();
}

function recentCardHTML(item) {
  return `
    <div class="card recent-card">
      <a href="/game/${item.id}">
        <div class="card-media">${imgTag(item.image, item.name)}</div>
        <div class="card-body">
          <h3>${item.name}</h3>
          ${item.publisher ? `<p class="publisher">${item.publisher}</p>` : ""}
          <p class="meta">${item.released || "Unknown"} ${item.genres ? "· " + item.genres : ""}</p>
        </div>
      </a>
      <button class="recent-remove-btn" data-recent-id="${item.id}" title="Remove from Recently Viewed">✕</button>
    </div>
  `;
}

function renderRecent() {
  if (!recentSection) return;
  const recent = getRecent();
  if (recent.length === 0) {
    recentSection.style.display = "none";
    return;
  }
  recentSection.style.display = "block";
  recentGrid.innerHTML = recent.map(recentCardHTML).join("");
}

document.addEventListener("click", (e) => {
  const removeBtn = e.target.closest(".recent-remove-btn");
  if (!removeBtn) return;
  e.preventDefault();
  e.stopPropagation();
  removeFromRecent(removeBtn.dataset.recentId);
});

const clearRecentBtn = document.getElementById("clearRecentBtn");
if (clearRecentBtn) clearRecentBtn.addEventListener("click", clearRecent);

// ---- View switching ----
function showView(view) {
  currentView = view;
  if (homeSections) homeSections.style.display = view === "home" ? "block" : "none";
  if (recentSection) recentSection.style.display = view === "home" && getRecent().length ? "block" : "none";
  if (searchResultsView) searchResultsView.style.display = view === "search" ? "block" : "none";
  if (favoritesView) favoritesView.style.display = view === "favorites" ? "block" : "none";
  if (statusEl) statusEl.textContent = "";
}

favToggle.addEventListener("click", () => {
  if (currentView === "favorites") {
    favToggle.textContent = "☆ Favorites";
    favToggle.classList.remove("active");
    showView("home");
  } else {
    favToggle.textContent = "★ Viewing Favorites";
    favToggle.classList.add("active");
    loadFavorites();
  }
});

if (backToHomeBtn) {
  backToHomeBtn.addEventListener("click", () => {
    input.value = "";
    favToggle.textContent = "☆ Favorites";
    favToggle.classList.remove("active");
    showView("home");
  });
}

function loadFavorites() {
  if (!favoritesGrid) return;
  showView("favorites");
  const favs = Object.values(getFavorites());
  if (favs.length === 0) {
    favoritesGrid.innerHTML = "";
    statusEl.textContent = "No favorites yet — click the ♥ on any game to save it here.";
    return;
  }
  favoritesGrid.innerHTML = favs.map((item, i) => cardHTML(item, i)).join("");
}

// ---- Filters ----
function populateFilters() {
  genreFilter.innerHTML = '<option value="">All genres</option>' +
    GENRES.map((g) => `<option value="${g}">${g}</option>`).join("");
  platformFilter.innerHTML = '<option value="">All platforms</option>' +
    PLATFORMS.map((p) => `<option value="${p.value}">${p.label}</option>`).join("");

  const currentYear = new Date().getFullYear();
  let yearOptions = '<option value="">All years</option>';
  for (let y = currentYear; y >= 1985; y--) {
    yearOptions += `<option value="${y}">${y}</option>`;
  }
  yearFilter.innerHTML = yearOptions;
}
populateFilters();

filtersToggle.addEventListener("click", () => {
  filtersPanel.classList.toggle("open");
  filtersToggle.classList.toggle("active");
});

genreFilter.addEventListener("change", () => { if (input.value.trim()) fetchSuggestions(); });
yearFilter.addEventListener("change", () => { if (input.value.trim()) fetchSuggestions(); });

// ---- Skeleton loading placeholders ----
function skeletonHTML(count) {
  return Array.from({ length: count }).map(() => `
    <div class="card skeleton-card">
      <div class="card-media skeleton-shimmer"></div>
      <div class="card-body">
        <div class="skeleton-line skeleton-shimmer" style="width:70%"></div>
        <div class="skeleton-line skeleton-shimmer" style="width:45%"></div>
      </div>
    </div>
  `).join("");
}

// ---- Home page sections ----
async function loadSection(sectionName, gridId) {
  const grid = document.getElementById(gridId);
  grid.innerHTML = skeletonHTML(4);
  try {
    const res = await fetch(`/section/${sectionName}`);
    const data = await res.json();
    if (data.error || data.length === 0) {
      grid.innerHTML = `<p class="suggest-empty">Couldn't load this section right now.</p>`;
      return;
    }
    grid.innerHTML = data.map((item, i) => cardHTML(item, i)).join("");
  } catch (err) {
    grid.innerHTML = `<p class="suggest-empty">Network error.</p>`;
  }
}

function loadAllHomeSections() {
  loadSection("awards", "awardsGrid");
  loadSection("upcoming", "upcomingGrid");
  loadSection("trending", "trendingGrid");
  loadSection("top-rated", "topRatedGrid");
  loadSection("new-releases", "newReleasesGrid");
  loadSection("popular-week", "popularWeekGrid");
  loadSection("editors-picks", "editorsPicksGrid");
}

// ---- Recommended For You (genre-based, built from your favorites) ----
function computeFavoriteGenreSlugs() {
  const favs = Object.values(getFavorites());
  const counts = {};
  favs.forEach((f) => {
    (f.genres || "").split(",").map((g) => g.trim().toLowerCase()).filter(Boolean).forEach((g) => {
      counts[g] = (counts[g] || 0) + 1;
    });
  });
  return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 2).map(([g]) => g);
}

async function loadRecommended() {
  const section = document.getElementById("recommendedSection");
  const grid = document.getElementById("recommendedGrid");
  if (!section || !grid) return;
  const favs = Object.values(getFavorites());

  if (favs.length === 0) { section.style.display = "none"; return; }
  const genreSlugs = computeFavoriteGenreSlugs();
  if (genreSlugs.length === 0) { section.style.display = "none"; return; }

  grid.innerHTML = skeletonHTML(4);
  section.style.display = "block";

  try {
    const res = await fetch(`/section/recommended?genres=${encodeURIComponent(genreSlugs.join(","))}`);
    const data = await res.json();
    if (data.error || !data.length) { section.style.display = "none"; return; }
    const favIds = new Set(favs.map((f) => String(f.id)));
    const filtered = data.filter((g) => !favIds.has(String(g.id)));
    if (filtered.length === 0) { section.style.display = "none"; return; }
    grid.innerHTML = filtered.map((item, i) => cardHTML(item, i)).join("");
  } catch (err) {
    section.style.display = "none";
  }
}

// ---- Search: build filter params, then redirect to the real /search page ----
function buildSearchParams(page) {
  const params = new URLSearchParams();
  const q = input.value.trim();
  if (q) params.set("q", q);
  if (genreFilter.value) params.set("genre", genreFilter.value);
  if (platformFilter.value) params.set("platform", platformFilter.value);
  if (yearFilter.value) params.set("year", yearFilter.value);
  if (ratingFilter.value) params.set("min_rating", ratingFilter.value);
  if (typeFilter.value) params.set("type", typeFilter.value);
  if (page) params.set("page", page);
  return params;
}

function goToSearchPage() {
  window.location.href = `/search?${buildSearchParams(1).toString()}`;
}

advancedSearchBtn.addEventListener("click", goToSearchPage);

function imgTag(url, alt) {
  if (!url) return `<div class="no-image">No image</div>`;
  return `<img src="${url}" alt="${alt}" loading="lazy"
    onload="this.classList.add('loaded')"
    onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'no-image',textContent:'No image'}))">`;
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const target = new Date(dateStr + "T00:00:00");
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.round((target - now) / 86400000);
}

function countdownLabel(days) {
  if (days === null) return "";
  if (days < 0) return "Released";
  if (days === 0) return "Out today!";
  if (days === 1) return "Tomorrow";
  return `In ${days} days`;
}

function cardHTML(item, index) {
  const fav = isFavorite(item.id);
  let topBadge = "";
  if (item.award_label) {
    topBadge = `<span class="top-badge award-badge">🏆 ${item.award_label}</span>`;
  } else if (item.release_date) {
    topBadge = `<span class="top-badge countdown-badge">${countdownLabel(daysUntil(item.release_date))}</span>`;
  }

  return `
    <a class="card" href="/game/${item.id}" style="animation-delay:${index * 45}ms">
      <div class="card-media">
        ${imgTag(item.image, item.name)}
        ${topBadge}
        <button class="fav-btn ${fav ? "active" : ""}"
          data-id="${item.id}"
          data-name="${escapeAttr(item.name)}"
          data-image="${item.image || ""}"
          data-released="${item.released || ""}"
          data-genres="${escapeAttr(item.genres || "")}"
          data-publisher="${escapeAttr(item.publisher || "")}">♥</button>
      </div>
      <div class="card-body">
        <h3>${item.name}</h3>
        ${item.publisher ? `<p class="publisher">${item.publisher}</p>` : ""}
        <p class="meta">${item.released || "Unknown"} ${item.genres ? "· " + item.genres : ""}</p>
      </div>
    </a>
  `;
}

document.addEventListener("click", (e) => {
  const favBtn = e.target.closest(".fav-btn");
  if (!favBtn) return;
  e.preventDefault();
  e.stopPropagation();

  const id = favBtn.dataset.id;
  if (isFavorite(id)) {
    removeFavorite(id);
    favBtn.classList.remove("active");
    if (currentView === "favorites") loadFavorites();
  } else {
    saveFavorite({
      id, name: favBtn.dataset.name, image: favBtn.dataset.image,
      released: favBtn.dataset.released, genres: favBtn.dataset.genres,
      publisher: favBtn.dataset.publisher,
    });
    favBtn.classList.add("active");
  }
  // Micro-interaction: a little "pop" on click
  favBtn.classList.remove("pop");
  void favBtn.offsetWidth; // restart animation
  favBtn.classList.add("pop");

  if (currentView === "home") loadRecommended();
});

// ---- Inline search suggestions dropdown (quick typeahead) ----
async function fetchSuggestions() {
  const query = input.value.trim();
  if (!query) {
    suggestDropdown.classList.remove("open");
    suggestDropdown.innerHTML = "";
    return;
  }

  const params = new URLSearchParams({ q: query });
  if (genreFilter.value) params.set("genre", genreFilter.value);
  if (yearFilter.value) params.set("year", yearFilter.value);

  try {
    const res = await fetch(`/search/games?${params.toString()}`);
    const data = await res.json();

    if (data.error || data.length === 0) {
      suggestDropdown.innerHTML = `<p class="suggest-empty">No games found for "${query}"</p>`;
      suggestDropdown.classList.add("open");
      return;
    }

    suggestDropdown.innerHTML = data.slice(0, 7).map(suggestionHTML).join("");
    suggestDropdown.classList.add("open");
  } catch (err) {
    suggestDropdown.innerHTML = `<p class="suggest-empty">Network error.</p>`;
    suggestDropdown.classList.add("open");
  }
}

function suggestionHTML(item) {
  const img = item.image
    ? `<img src="${item.image}" alt="${item.name}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'suggest-noimg'}))">`
    : `<div class="suggest-noimg"></div>`;

  return `
    <a class="suggest-item" href="/game/${item.id}">
      ${img}
      <div class="suggest-text">
        <span class="suggest-title">${item.name}</span>
        <span class="suggest-meta">${item.publisher ? item.publisher + " · " : ""}${item.released || "Unknown"}</span>
      </div>
    </a>
  `;
}

input.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fetchSuggestions, 400);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    suggestDropdown.classList.remove("open");
    goToSearchPage();
  }
});

input.addEventListener("focus", () => {
  if (input.value.trim() && suggestDropdown.innerHTML) suggestDropdown.classList.add("open");
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-shell")) {
    suggestDropdown.classList.remove("open");
  }
});

// ---- Voice search (Chrome/Edge only — Web Speech API) ----
const micBtn = document.getElementById("micBtn");
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognitionAPI) {
  const recognition = new SpeechRecognitionAPI();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  micBtn.addEventListener("click", () => {
    micBtn.classList.add("listening");
    try { recognition.start(); } catch (err) { micBtn.classList.remove("listening"); }
  });

  recognition.addEventListener("result", (e) => {
    const transcript = e.results[0][0].transcript;
    input.value = transcript;
    fetchSuggestions();
  });

  recognition.addEventListener("end", () => micBtn.classList.remove("listening"));
  recognition.addEventListener("error", () => micBtn.classList.remove("listening"));
} else {
  micBtn.style.display = "none";
}

// ---- Init ----
if (homeSections) {
  renderRecent();
  loadRecommended();
  loadAllHomeSections();
}
syncFavButtonStates();

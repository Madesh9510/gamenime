let debounceTimer = null;
let currentView = "popular"; // "popular" | "favorites"

const GENRES = ["action", "adventure", "rpg", "shooter", "puzzle", "racing", "sports", "strategy", "indie", "casual", "simulation", "platformer"];
const FAV_KEY = "pixelscope_favorites";

const input = document.getElementById("searchInput");
const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");
const headingEl = document.getElementById("resultsHeading");
const genreFilter = document.getElementById("genreFilter");
const yearFilter = document.getElementById("yearFilter");
const filtersToggle = document.getElementById("filtersToggle");
const filtersPanel = document.getElementById("filtersPanel");
const suggestDropdown = document.getElementById("suggestDropdown");
const glowBackdrop = document.getElementById("glowBackdrop");
const favToggle = document.getElementById("favToggle");

// ---- Cursor-follow ambient glow ----
document.addEventListener("mousemove", (e) => {
  glowBackdrop.style.setProperty("--mx", `${e.clientX}px`);
  glowBackdrop.style.setProperty("--my", `${e.clientY}px`);
});

// ---- Favorites (saved locally in this browser, no account needed) ----
function getFavorites() {
  try {
    return JSON.parse(localStorage.getItem(FAV_KEY) || "{}");
  } catch (err) {
    return {};
  }
}

function isFavorite(id) {
  return !!getFavorites()[id];
}

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

function escapeAttr(str) {
  return String(str || "").replace(/"/g, "&quot;");
}

favToggle.addEventListener("click", () => {
  if (currentView === "favorites") {
    currentView = "popular";
    favToggle.textContent = "☆ Favorites";
    favToggle.classList.remove("active");
    input.value = "";
    loadPopular();
  } else {
    currentView = "favorites";
    favToggle.textContent = "★ Viewing Favorites";
    favToggle.classList.add("active");
    loadFavorites();
  }
});

function loadFavorites() {
  const favs = Object.values(getFavorites());
  headingEl.style.display = "block";
  headingEl.textContent = "My Favorites";
  statusEl.textContent = "";

  if (favs.length === 0) {
    resultsEl.innerHTML = "";
    statusEl.textContent = "No favorites yet — click the ♥ on any game to save it here.";
    return;
  }
  resultsEl.innerHTML = favs.map((item, i) => cardHTML(item, i)).join("");
}

// ---- Filters ----
function populateFilters() {
  genreFilter.innerHTML = '<option value="">All genres</option>' +
    GENRES.map((g) => `<option value="${g}">${g}</option>`).join("");

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

// ---- Popular grid (default view) ----
async function loadPopular() {
  headingEl.style.display = "none";
  statusEl.textContent = "";
  resultsEl.innerHTML = skeletonHTML(10);
  try {
    const res = await fetch("/popular/games");
    const data = await res.json();
    if (data.error || data.length === 0) {
      statusEl.textContent = "Couldn't load picks right now.";
      resultsEl.innerHTML = "";
      return;
    }
    resultsEl.innerHTML = data.map((item, i) => cardHTML(item, i)).join("");
  } catch (err) {
    statusEl.textContent = "Network error.";
    resultsEl.innerHTML = "";
  }
}

function imgTag(url, alt) {
  if (!url) return `<div class="no-image">No image</div>`;
  return `<img src="${url}" alt="${alt}" loading="lazy"
    onload="this.classList.add('loaded')"
    onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'no-image',textContent:'No image'}))">`;
}

function cardHTML(item, index) {
  const fav = isFavorite(item.id);
  return `
    <a class="card" href="/game/${item.id}" style="animation-delay:${index * 45}ms">
      <div class="card-media">
        ${imgTag(item.image, item.name)}
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

resultsEl.addEventListener("click", (e) => {
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
});

// ---- Inline search suggestions dropdown ----
async function fetchSuggestions() {
  const query = input.value.trim();
  if (!query) {
    suggestDropdown.classList.remove("open");
    suggestDropdown.innerHTML = "";
    return;
  }

  const genre = genreFilter.value;
  const year = yearFilter.value;
  const params = new URLSearchParams({ q: query });
  if (genre) params.set("genre", genre);
  if (year) params.set("year", year);

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

input.addEventListener("focus", () => {
  if (input.value.trim() && suggestDropdown.innerHTML) suggestDropdown.classList.add("open");
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-shell")) {
    suggestDropdown.classList.remove("open");
  }
});

loadPopular();

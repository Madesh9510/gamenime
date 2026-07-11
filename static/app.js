let currentMode = "games";

const tabs = document.querySelectorAll(".tab");
const input = document.getElementById("searchInput");
const btn = document.getElementById("searchBtn");
const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentMode = tab.dataset.mode;
    input.placeholder = currentMode === "games"
      ? "Search for a game…"
      : "Search for an anime…";
    resultsEl.innerHTML = "";
    statusEl.textContent = "";
  });
});

async function runSearch() {
  const query = input.value.trim();
  if (!query) return;

  statusEl.textContent = "Searching…";
  resultsEl.innerHTML = "";

  try {
    const res = await fetch(`/search/${currentMode}?q=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (data.error) {
      statusEl.textContent = "Something went wrong. Try again.";
      return;
    }
    if (data.length === 0) {
      statusEl.textContent = `No results for "${query}".`;
      return;
    }

    statusEl.textContent = "";
    resultsEl.innerHTML = data.map(renderCard).join("");
  } catch (err) {
    statusEl.textContent = "Network error. Is the server running?";
  }
}

function renderCard(item) {
  const maxScore = currentMode === "games" ? 5 : 10;
  const rating = item.rating ? Number(item.rating).toFixed(1) : "—";
  const filled = item.rating ? Math.round((item.rating / maxScore) * 5) : 0;
  const bar = "█".repeat(filled) + "░".repeat(5 - filled);

  const img = item.image
    ? `<img src="${item.image}" alt="${item.name}" loading="lazy">`
    : `<div class="no-image">No image</div>`;

  return `
    <article class="card">
      ${img}
      <div class="card-body">
        <h3>${item.name}</h3>
        <p class="meta">${item.released || "Unknown"} ${item.genres ? "· " + item.genres : ""}</p>
        <div class="rating">
          <span class="rating-bar">${bar}</span>
          <span class="rating-num">${rating}</span>
        </div>
      </div>
    </article>
  `;
}

btn.addEventListener("click", runSearch);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") runSearch();
});

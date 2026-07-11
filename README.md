# PixelScope — Game & Anime Search Starter

A small Flask app you can run locally, then deploy to Render — same idea as
your friend's MovieNexus, but for video games (with ratings) and anime.

## What it does
- Search bar with two modes: Games and Anime
- Games come from the RAWG.io API (ratings, cover art, release year, genres)
- Anime comes from the Jikan API (free wrapper around MyAnimeList — no key needed)

## 1. Run it locally

**Step 1 — Get a free RAWG API key**
Go to https://rawg.io/apidocs, sign up, and copy your API key. It's free and
takes about a minute.

**Step 2 — Install dependencies**
```bash
cd gamenime
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Step 3 — Set your API key**
```bash
export RAWG_API_KEY=your_key_here     # on Windows: set RAWG_API_KEY=your_key_here
```
(Or just paste it directly into `app.py` where it says `PUT_YOUR_RAWG_KEY_HERE`
while you're testing locally — just don't commit it to GitHub like that.)

**Step 4 — Run**
```bash
python app.py
```
Open http://127.0.0.1:5000 in your browser.

## 2. Deploy to Render (free)

1. Push this folder to a GitHub repo.
2. Go to https://render.com → New → Web Service → connect your repo.
3. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Under Environment, add a variable: `RAWG_API_KEY` = your key.
5. Deploy. Render gives you a live `.onrender.com` URL, just like your friend's.

## 3. Where to go next
Ideas to extend this, roughly in order of difficulty:
- Add a "details" page per game/anime (RAWG and Jikan both have `/games/{id}`
  and `/anime/{id}` endpoints with trailers, screenshots, descriptions).
- Add filters (genre, platform, year) using RAWG's query parameters.
- Cache API responses (e.g. with `flask-caching`) so repeated searches are
  instant and you don't hit API rate limits.
- Add a watchlist/favorites feature using a database (SQLite is the easiest
  starting point) with simple login.
- Swap the plain CSS for something more custom once you're comfortable —
  the structure will stay the same.

## API docs (bookmark these)
- RAWG: https://rawg.io/apidocs
- Jikan: https://docs.api.jikan.moe/

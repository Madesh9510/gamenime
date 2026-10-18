# PixelScope

A Flask-based game discovery platform — like Steam, but for browsing and tracking games. Pulls live data from RAWG, Steam, and CheapShark APIs.

## What it does

- Home feed with curated sections: Trending, AAA Blockbusters, Highest Rated, New Releases, Action, RPG, Multiplayer, Editor's Picks, Upcoming, and Game of the Year Winners
- Game detail page with description, PC requirements, trailer (autoplay), screenshots, similar games, PC price in INR, Steam reviews, store links, platforms, and tags
- Advanced search with filters: genre, platform, year, min rating, game type
- Watchlist — save games to your personal list
- Library — track games as Want to Play, Playing, or Completed
- Deals page — live PC game deals from CheapShark with INR pricing
- Gaming news feed from Eurogamer, PC Gamer, Rock Paper Shotgun, Game Rant, and VG247
- User accounts — register, login, logout with SQLite database
- Admin panel — manage GOTY winners, NSFW keywords, news feeds, users, and cache
- Description and PC requirements fall back to Steam API when RAWG doesn't have the data

## Run it locally

**Step 1 — Get a free RAWG API key**
Go to https://rawg.io/apidocs, sign up, and copy your key.

**Step 2 — Install dependencies**
```bash
cd pixelscope
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Step 3 — Set your API key**
```bash
export RAWG_API_KEY=your_key_here     # Windows: set RAWG_API_KEY=your_key_here
```

**Step 4 — Run**
```bash
python app.py
```
Open http://127.0.0.1:5000 in your browser.

## Deploy to Render

1. Push this folder to a GitHub repo.
2. Go to https://render.com → New → Web Service → connect your repo.
3. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Under Environment, add: `RAWG_API_KEY` = your key.
5. Deploy. Render gives you a live `.onrender.com` URL.

## API docs

- RAWG: https://rawg.io/apidocs
- Steam Store API: https://store.steampowered.com/api/appdetails
- CheapShark: https://apidocs.cheapshark.com

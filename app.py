from flask import Flask, render_template, request, jsonify, redirect
import requests
import os
import re
import random

app = Flask(__name__)

# Get a free key at https://rawg.io/apidocs (takes 1 minute, no credit card)
RAWG_API_KEY = os.environ.get("RAWG_API_KEY", "b425b09cad4a4586aee27e3a12b89229")
RAWG_BASE_URL = "https://api.rawg.io/api"

# PC + console platform IDs only (excludes iOS=3, Android=21, and other mobile-only platforms)
NON_MOBILE_PLATFORMS = "4,187,18,16,15,186,1,14,80,7,11,10"

STORE_NAMES = {
    1: "Steam", 2: "Xbox Store", 3: "PlayStation Store", 4: "App Store",
    5: "GOG", 6: "Nintendo eShop", 7: "Xbox 360 Store", 8: "Google Play",
    9: "itch.io", 11: "Epic Games",
}


def resize_image(url, width):
    """Ask RAWG's image proxy for a smaller version so pages load fast."""
    if not url:
        return url
    return url.replace("media.rawg.io/media/", f"media.rawg.io/media/resize/{width}/-/", 1)


def year_only(date_str):
    if not date_str:
        return None
    return date_str[:4]


def format_game(g):
    publishers = g.get("publishers") or []
    return {
        "id": g.get("id"),
        "name": g.get("name"),
        "image": resize_image(g.get("background_image"), 640),
        "rating": g.get("rating"),          # RAWG community score, 0-5
        "released": year_only(g.get("released")),
        "genres": ", ".join(genre["name"] for genre in g.get("genres", [])),
        "publisher": publishers[0]["name"] if publishers else None,
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/search/games")
def search_games():
    query = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    year = request.args.get("year", "").strip()
    if not query:
        return jsonify([])

    params = {
        "key": RAWG_API_KEY, "search": query, "page_size": 8,
        "platforms": NON_MOBILE_PLATFORMS,
    }
    if genre:
        params["genres"] = genre
    if year:
        params["dates"] = f"{year}-01-01,{year}-12-31"

    try:
        resp = requests.get(f"{RAWG_BASE_URL}/games", params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print("RAWG SEARCH ERROR:", repr(e))
        return jsonify({"error": "Could not reach RAWG API"}), 502

    return jsonify([format_game(g) for g in data.get("results", [])])


@app.route("/popular/games")
def popular_games():
    """Curated PC/console trending titles, ordered by community activity."""
    try:
        resp = requests.get(
            f"{RAWG_BASE_URL}/games",
            params={
                "key": RAWG_API_KEY, "ordering": "-added", "page_size": 10,
                "platforms": NON_MOBILE_PLATFORMS,
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print("RAWG POPULAR ERROR:", repr(e))
        return jsonify({"error": "Could not reach RAWG API"}), 502

    return jsonify([format_game(g) for g in data.get("results", [])])


def get_steam_rating(appid):
    """Best-effort fetch of Steam's public review summary. Returns None if unavailable."""
    try:
        resp = requests.get(
            f"https://store.steampowered.com/appreviews/{appid}",
            params={"json": 1, "language": "all", "num_per_page": 0},
            timeout=6,
        )
        resp.raise_for_status()
        summary = resp.json().get("query_summary", {})
        total = summary.get("total_reviews", 0)
        if not total:
            return None
        positive_pct = round((summary.get("total_positive", 0) / total) * 100)
        return {
            "description": summary.get("review_score_desc"),
            "positive_pct": positive_pct,
            "total_reviews": total,
        }
    except (requests.RequestException, ValueError, ZeroDivisionError, KeyError):
        return None


def get_screenshots(game_id):
    try:
        resp = requests.get(
            f"{RAWG_BASE_URL}/games/{game_id}/screenshots",
            params={"key": RAWG_API_KEY},
            timeout=8,
        )
        resp.raise_for_status()
        shots = resp.json().get("results", [])
        return [resize_image(s.get("image"), 1280) for s in shots[:6] if s.get("image")]
    except requests.RequestException as e:
        print("RAWG SCREENSHOTS ERROR:", repr(e))
        return []


@app.route("/game/random")
def random_game():
    try:
        resp = requests.get(
            f"{RAWG_BASE_URL}/games",
            params={
                "key": RAWG_API_KEY, "ordering": "-added", "page_size": 40,
                "platforms": NON_MOBILE_PLATFORMS,
            },
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return render_template("error.html", message="Couldn't find a game right now."), 502
        pick = random.choice(results)
        return redirect(f"/game/{pick['id']}")
    except requests.RequestException as e:
        print("RAWG RANDOM ERROR:", repr(e))
        return render_template("error.html", message="Couldn't find a game right now."), 502


@app.route("/game/<int:game_id>")
def game_detail(game_id):
    try:
        resp = requests.get(f"{RAWG_BASE_URL}/games/{game_id}", params={"key": RAWG_API_KEY}, timeout=8)
        resp.raise_for_status()
        g = resp.json()
    except requests.RequestException as e:
        print("RAWG DETAIL ERROR:", repr(e))
        return render_template("error.html", message="Couldn't load this game right now."), 502

    stores = []
    steam_appid = None
    try:
        store_resp = requests.get(
            f"{RAWG_BASE_URL}/games/{game_id}/stores", params={"key": RAWG_API_KEY}, timeout=8
        )
        store_resp.raise_for_status()
        for s in store_resp.json().get("results", []):
            store_id = s.get("store_id")
            url = s.get("url")
            if not url:
                continue
            stores.append({"name": STORE_NAMES.get(store_id, "Store"), "url": url})
            if store_id == 1:
                match = re.search(r"/app/(\d+)", url)
                if match:
                    steam_appid = match.group(1)
    except requests.RequestException as e:
        print("RAWG STORES ERROR:", repr(e))

    steam_rating = get_steam_rating(steam_appid) if steam_appid else None
    screenshots = get_screenshots(game_id)

    publishers = g.get("publishers") or []
    description = (g.get("description_raw") or "").strip()
    if not description:
        description = "No description available for this title yet."
    elif len(description) < 80:
        description += "\n\n(Our data source has limited info on this particular title.)"

    esrb = g.get("esrb_rating")
    raw_tags = g.get("tags") or []
    tags = [t["name"] for t in raw_tags if t.get("language") == "eng"][:6]

    clip = g.get("clip") or None
    trailer = None
    if clip and clip.get("clip"):
        trailer = {"video": clip.get("clip"), "preview": clip.get("preview")}

    game = {
        "id": g.get("id"),
        "name": g.get("name"),
        "image": resize_image(g.get("background_image"), 1280),
        "rating": g.get("rating"),
        "released": year_only(g.get("released")),
        "genres": ", ".join(genre["name"] for genre in g.get("genres", [])),
        "publisher": publishers[0]["name"] if publishers else None,
        "platforms": [p["platform"]["name"] for p in (g.get("platforms") or [])],
        "description": description,
        "stores": stores,
        "steam_rating": steam_rating,
        "screenshots": screenshots,
        "esrb": esrb["name"] if esrb else None,
        "tags": tags,
        "trailer": trailer,
    }
    return render_template("game_detail.html", game=game)


if __name__ == "__main__":
    app.run(debug=True)

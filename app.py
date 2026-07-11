from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

# Get a free key at https://rawg.io/apidocs (takes 1 minute, no credit card)
RAWG_API_KEY = os.environ.get("RAWG_API_KEY", "b425b09cad4a4586aee27e3a12b89229")
RAWG_BASE_URL = "https://api.rawg.io/api"

# Jikan needs no API key at all
JIKAN_BASE_URL = "https://api.jikan.moe/v4"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/search/games")
def search_games():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    try:
        resp = requests.get(
            f"{RAWG_BASE_URL}/games",
            params={"key": RAWG_API_KEY, "search": query, "page_size": 12},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return jsonify({"error": "Could not reach RAWG API"}), 502

    results = []
    for g in data.get("results", []):
        results.append({
            "id": g.get("id"),
            "name": g.get("name"),
            "image": g.get("background_image"),
            "rating": g.get("rating"),          # 0-5 scale
            "released": g.get("released"),
            "genres": ", ".join(genre["name"] for genre in g.get("genres", [])),
        })
    return jsonify(results)


@app.route("/search/anime")
def search_anime():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    try:
        resp = requests.get(
            f"{JIKAN_BASE_URL}/anime",
            params={"q": query, "limit": 12},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return jsonify({"error": "Could not reach Jikan API"}), 502

    results = []
    for a in data.get("data", []):
        results.append({
            "id": a.get("mal_id"),
            "name": a.get("title"),
            "image": (a.get("images") or {}).get("jpg", {}).get("image_url"),
            "rating": a.get("score"),            # 0-10 scale
            "released": a.get("year"),
            "genres": ", ".join(genre["name"] for genre in a.get("genres", [])),
        })
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)

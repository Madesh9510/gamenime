from flask import Flask, render_template, request, jsonify, redirect, session, g
import requests
import os
import re
import random
import datetime
import json
import sqlite3
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "pixelscope-secret-2024")

RAWG_API_KEY   = os.environ.get("RAWG_API_KEY", "b425b09cad4a4586aee27e3a12b89229")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "pixelscope123")
RAWG_BASE_URL  = "https://api.rawg.io/api"
SETTINGS_FILE  = "settings.json"
DATABASE       = "pixelscope.db"

NON_MOBILE_PLATFORMS = "4,187,18,16,15,186,1,14,80,7,11,10"
PLATFORM_OPTIONS = {"pc":4,"ps5":187,"xbox-series":186,"switch":7,"ps4":18,"xbox-one":1}
STORE_NAMES = {1:"Steam",2:"Xbox Store",3:"PlayStation Store",4:"App Store",5:"GOG",
               6:"Nintendo eShop",7:"Xbox 360 Store",8:"Google Play",9:"itch.io",11:"Epic Games"}

SECTION_TITLES = {
    "trending":    "🔥 Trending Now",
    "aaa":         "💰 AAA Blockbusters",
    "top-rated":   "⭐ Highest Rated",
    "new-releases":"🆕 New Releases",
    "action":      "⚔️ Action Games",
    "rpg":         "🧙 RPG Games",
    "popular-week":"🎮 Popular This Week",
    "multiplayer": "🌐 Multiplayer",
    "editors-picks":"💎 Editor's Picks",
    "upcoming":    "📅 Upcoming Releases",
    "awards":      "🏆 Game of the Year Winners",
}

_DEFAULT_GOTY = [
    {"name":"Clair Obscur: Expedition 33","year":2025},{"name":"Astro Bot","year":2024},
    {"name":"Baldur's Gate 3","year":2023},{"name":"Elden Ring","year":2022},
    {"name":"It Takes Two","year":2021},{"name":"The Last of Us Part II","year":2020},
    {"name":"Sekiro: Shadows Die Twice","year":2019},
]
_DEFAULT_NSFW  = ["hentai","nsfw","porn","erotic","sex simulator","adult visual novel","femboy"]
_DEFAULT_FEEDS = [
    {"url":"https://www.eurogamer.net/rss/eurogamer_news_articles.rss","name":"Eurogamer","enabled":True},
    {"url":"https://www.pcgamer.com/rss/news/","name":"PC Gamer","enabled":True},
    {"url":"https://www.rockpapershotgun.com/feed/","name":"Rock Paper Shotgun","enabled":True},
    {"url":"https://gamerant.com/feed/","name":"Game Rant","enabled":True},
    {"url":"https://www.vg247.com/feed","name":"VG247","enabled":True},
]

_trailer_cache  = {}
_news_cache     = {"data":None,"fetched_at":None}
_inr_rate_cache = {"rate":None,"fetched_at":None}
_jikan_cache    = {}


# ── database ──────────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g,'_database',None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g,'_database',None)
    if db is not None: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                email    TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col in ["is_admin INTEGER DEFAULT 0", "last_login TIMESTAMP"]:
            try: db.execute(f"ALTER TABLE users ADD COLUMN {col}")
            except Exception: pass
        db.commit()
        if not db.execute("SELECT id FROM users WHERE username='admin'").fetchone():
            db.execute("INSERT INTO users (username,email,password_hash,is_admin) VALUES (?,?,?,?)",
                ('admin','admin@pixelscope.local',generate_password_hash(ADMIN_PASSWORD),1))
            db.commit()

init_db()


# ── force login ───────────────────────────────────────────────────────────────

PUBLIC_PATHS = ('/login','/register','/logout','/static/')

@app.before_request
def require_login():
    if any(request.path.startswith(p) for p in PUBLIC_PATHS): return None
    if not session.get('user_id'):
        if request.path.startswith('/api/') or request.path.startswith('/search/'):
            return jsonify({"error":"Login required"}), 401
        return redirect(f'/login?next={request.path}')


# ── auth helpers ──────────────────────────────────────────────────────────────

def get_user_by_id(uid):
    row = get_db().execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    return dict(row) if row else None

def get_user_by_identifier(ident):
    row = get_db().execute("SELECT * FROM users WHERE username=? OR email=?",(ident,ident)).fetchone()
    return dict(row) if row else None

@app.context_processor
def inject_user():
    uid = session.get('user_id')
    if uid:
        try: return {'current_user': get_user_by_id(uid)}
        except Exception: pass
    return {'current_user': None}


# ── settings ──────────────────────────────────────────────────────────────────

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            s=json.load(f)
            s.setdefault("goty_winners",_DEFAULT_GOTY)
            s.setdefault("nsfw_keywords",_DEFAULT_NSFW)
            s.setdefault("news_feeds",_DEFAULT_FEEDS)
            return s
    except Exception:
        return {"goty_winners":_DEFAULT_GOTY,"nsfw_keywords":_DEFAULT_NSFW,"news_feeds":_DEFAULT_FEEDS}

def save_settings(s):
    try:
        with open(SETTINGS_FILE,"w") as f: json.dump(s,f,indent=2)
    except Exception as e: print("SETTINGS SAVE ERROR:",repr(e))

def get_goty():  return load_settings()["goty_winners"]
def get_nsfw():  return load_settings()["nsfw_keywords"]
def get_feeds(): return [(f["url"],f["name"]) for f in load_settings()["news_feeds"] if f.get("enabled",True)]


# ── rawg helpers ──────────────────────────────────────────────────────────────

def resize_image(url,width):
    if not url: return url
    return url.replace("media.rawg.io/media/",f"media.rawg.io/media/resize/{width}/-/",1)

def year_only(d): return d[:4] if d else None
def strip_tags(t): return re.sub(r"<[^>]+>","",t or "").strip()

def is_appropriate(g):
    esrb=g.get("esrb_rating")
    if esrb and esrb.get("name")=="Adults Only": return False
    return not any(kw in (g.get("name") or "").lower() for kw in get_nsfw())

def format_game(g):
    pub=g.get("publishers") or []
    return {"id":g.get("id"),"name":g.get("name"),
            "image":resize_image(g.get("background_image"),640),
            "rating":g.get("rating"),"released":year_only(g.get("released")),
            "genres":", ".join(x["name"] for x in g.get("genres",[])),
            "publisher":pub[0]["name"] if pub else None}

def rawg_games(params):
    try:
        r=requests.get(f"{RAWG_BASE_URL}/games",params=params,timeout=8)
        r.raise_for_status(); return r.json()
    except Exception as e: print("RAWG ERROR:",repr(e)); return None


# ── news ──────────────────────────────────────────────────────────────────────

def relative_time(date_str):
    try:
        dt=parsedate_to_datetime(date_str); now=datetime.datetime.now(dt.tzinfo)
        h=int((now-dt).total_seconds()/3600)
        if h<1: return "Just now"
        if h<24: return f"{h}h ago"
        return f"{h//24}d ago"
    except Exception: return ""

def extract_rss_image(item):
    for ns in ["http://search.yahoo.com/mrss/","http://www.rssboard.org/media-rss"]:
        t=item.find(f"{{{ns}}}thumbnail")
        if t is not None and t.get("url"): return t.get("url")
        c=item.find(f"{{{ns}}}content")
        if c is not None and c.get("url"):
            u=c.get("url")
            if any(e in u.lower() for e in [".jpg",".jpeg",".png",".webp"]): return u
    enc=item.find("enclosure")
    if enc is not None and enc.get("type","").startswith("image"): return enc.get("url")
    for tag in ["description","{http://purl.org/rss/1.0/modules/content/}encoded"]:
        m=re.search(r'<img[^>]+src=["\']([^"\']+)["\']',item.findtext(tag,""),re.I)
        if m: return m.group(1)
    return None

def fetch_rss(url,name,limit=5):
    try:
        r=requests.get(url,timeout=8,headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status(); root=ET.fromstring(r.content)
        ch=root.find("channel") or root; arts=[]
        for item in ch.findall("item")[:limit]:
            title=(item.findtext("title") or "").strip(); link=(item.findtext("link") or "").strip()
            if not title or not link: continue
            arts.append({"title":title,"link":link,"source":name,
                         "time":relative_time(item.findtext("pubDate","").strip()),
                         "image":extract_rss_image(item)})
        return arts
    except Exception as e: print(f"RSS ERROR ({name}):",repr(e)); return []

def get_cached_news():
    now=datetime.datetime.utcnow()
    if _news_cache["data"] and _news_cache["fetched_at"] and \
            (now-_news_cache["fetched_at"]).total_seconds()<1800: return _news_cache["data"]
    arts=[]
    with ThreadPoolExecutor(max_workers=5) as ex:
        for fut in [ex.submit(fetch_rss,u,n,5) for u,n in get_feeds()]:
            try: arts.extend(fut.result())
            except Exception: pass
    _news_cache["data"]=arts[:25]; _news_cache["fetched_at"]=now; return _news_cache["data"]


# ── sections ──────────────────────────────────────────────────────────────────

def curated_section(params,min_rating=3.2,limit=8,require_rating=True):
    params=dict(params); params["page_size"]=40
    data=rawg_games(params)
    if data is None: return None
    games=[g for g in data.get("results",[]) if is_appropriate(g)]
    if require_rating: games=[g for g in games if (g.get("rating") or 0)>=min_rating]
    return [format_game(g) for g in games[:limit]]

def get_section_games(name,limit=8):
    today=datetime.date.today(); base={"key":RAWG_API_KEY,"platforms":NON_MOBILE_PLATFORMS}
    GOTY=get_goty()
    if name=="trending":
        base["ordering"]="-added"; return curated_section(base,min_rating=3.2,limit=limit)
    if name=="top-rated":
        base["ordering"]="-rating"; return curated_section(base,min_rating=3.8,limit=limit)
    if name=="aaa":
        base["ordering"]="-rating"; base["metacritic"]="85,100"
        return curated_section(base,min_rating=4.0,limit=limit)
    if name=="action":
        base["genres"]="action"; base["ordering"]="-rating"
        return curated_section(base,min_rating=3.5,limit=limit)
    if name=="rpg":
        base["genres"]="role-playing-games-rpg"; base["ordering"]="-rating"
        return curated_section(base,min_rating=3.5,limit=limit)
    if name=="multiplayer":
        base["tags"]="multiplayer"; base["ordering"]="-added"
        return curated_section(base,min_rating=3.2,limit=limit)
    if name=="new-releases":
        base["ordering"]="-released"; s=today-datetime.timedelta(days=60)
        base["dates"]=f"{s.isoformat()},{today.isoformat()}"
        return curated_section(base,require_rating=False,limit=limit)
    if name=="popular-week":
        base["ordering"]="-added"; s=today-datetime.timedelta(days=7)
        base["dates"]=f"{s.isoformat()},{today.isoformat()}"
        return curated_section(base,min_rating=3.0,limit=limit)
    if name=="editors-picks":
        base["ordering"]="-rating"; s=today-datetime.timedelta(days=730)
        base["dates"]=f"{s.isoformat()},{today.isoformat()}"
        return curated_section(base,min_rating=4.0,limit=limit)
    if name=="upcoming":
        end=today+datetime.timedelta(days=45)
        base.update({"dates":f"{today.isoformat()},{end.isoformat()}","ordering":"released","page_size":40})
        data=rawg_games(base)
        if data is None: return None
        games=[]
        for g in [g for g in data.get("results",[]) if is_appropriate(g)][:limit]:
            card=format_game(g); card["release_date"]=g.get("released"); games.append(card)
        return games
    if name=="awards":
        games=[]
        for award in GOTY[:limit]:
            data=rawg_games({"key":RAWG_API_KEY,"search":award["name"],"page_size":1,"platforms":NON_MOBILE_PLATFORMS})
            if data and data.get("results"):
                g=data["results"][0]
                if is_appropriate(g):
                    card=format_game(g); card["award_label"]=f"GOTY {award['year']}"; games.append(card)
        return games
    return None

def perform_search(args):
    query=args.get("q","").strip(); genre=args.get("genre","").strip()
    year=args.get("year","").strip(); plat=args.get("platform","").strip()
    minr=args.get("min_rating","").strip(); gtype=args.get("type","").strip()
    page=args.get("page","1").strip() or "1"
    params={"key":RAWG_API_KEY,"page_size":16,"page":page,"platforms":NON_MOBILE_PLATFORMS}
    if query: params["search"]=query
    else:     params["ordering"]="-added"
    if genre: params["genres"]=genre
    if year:  params["dates"]=f"{year}-01-01,{year}-12-31"
    if plat in PLATFORM_OPTIONS: params["platforms"]=str(PLATFORM_OPTIONS[plat])
    if gtype: params["tags"]=gtype
    data=rawg_games(params)
    if data is None: return None,False,query
    results=[format_game(g) for g in [g for g in data.get("results",[]) if is_appropriate(g)]]
    if minr:
        try: t=float(minr); results=[r for r in results if (r["rating"] or 0)>=t]
        except ValueError: pass
    return results[:12],bool(data.get("next")),query

def get_youtube_trailer_id(game_name):
    if game_name in _trailer_cache: return _trailer_cache[game_name]
    try:
        r=requests.get("https://www.youtube.com/results",
            params={"search_query":f"{game_name} official trailer"},
            headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     "Accept-Language":"en-US,en;q=0.9"},timeout=8)
        r.raise_for_status()
        for vid in re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"',r.text):
            _trailer_cache[game_name]=vid; return vid
    except Exception as e: print("YOUTUBE TRAILER ERROR:",repr(e))
    return None


# ── price helpers ─────────────────────────────────────────────────────────────

def get_usd_to_inr_rate():
    now=datetime.datetime.utcnow(); c,ts=_inr_rate_cache["rate"],_inr_rate_cache["fetched_at"]
    if c and ts and (now-ts).total_seconds()<21600: return c
    try:
        r=requests.get("https://api.exchangerate-api.com/v4/latest/USD",timeout=5)
        r.raise_for_status(); rate=r.json().get("rates",{}).get("INR")
        if rate: _inr_rate_cache["rate"]=rate; _inr_rate_cache["fetched_at"]=now
        return rate
    except Exception: return c

def get_steam_rating(appid):
    try:
        r=requests.get(f"https://store.steampowered.com/appreviews/{appid}",
                       params={"json":1,"language":"all","num_per_page":0},timeout=6)
        r.raise_for_status(); s=r.json().get("query_summary",{}); t=s.get("total_reviews",0)
        if not t: return None
        return {"description":s.get("review_score_desc"),
                "positive_pct":round(s.get("total_positive",0)/t*100),"total_reviews":t}
    except Exception: return None

def get_pc_price(appid):
    if not appid: return None
    try:
        r=requests.get("https://www.cheapshark.com/api/1.0/deals",params={"steamAppID":appid},timeout=6)
        r.raise_for_status(); deals=r.json()
        if not deals: return None
        ch=min(deals,key=lambda d:float(d.get("salePrice",999999)))
        usd=float(ch.get("salePrice",0)); nor=float(ch.get("normalPrice",0))
        sav=float(ch.get("savings",0)); gid=ch.get("gameID"); rate=get_usd_to_inr_rate()
        if not rate: return None
        res={"price_inr":round(usd*rate),"normal_price_inr":round(nor*rate) if nor>usd else None,
             "savings_pct":round(sav),"historical_low_inr":None,"is_best_price":False,"is_near_low":False}
        if gid and usd>0:
            try:
                gr=requests.get("https://www.cheapshark.com/api/1.0/games",params={"id":gid},timeout=5)
                gr.raise_for_status(); hist=gr.json().get("cheapestPriceEver") or {}
                h=float(hist["price"]) if hist.get("price") else None
                if h and h>0:
                    res["historical_low_inr"]=round(h*rate)
                    if usd<=h*1.01: res["is_best_price"]=True
                    elif usd<=h*1.10: res["is_near_low"]=True
            except Exception: pass
        return res
    except Exception: return None

def get_screenshots(game_id):
    try:
        r=requests.get(f"{RAWG_BASE_URL}/games/{game_id}/screenshots",params={"key":RAWG_API_KEY},timeout=8)
        r.raise_for_status()
        return [resize_image(s.get("image"),1280) for s in r.json().get("results",[])[:6] if s.get("image")]
    except Exception: return []

def get_similar_games(game_id):
    try:
        r=requests.get(f"{RAWG_BASE_URL}/games/{game_id}/suggested",
                       params={"key":RAWG_API_KEY,"page_size":8},timeout=8)
        r.raise_for_status()
        return [format_game(g) for g in [g for g in r.json().get("results",[]) if is_appropriate(g)][:6]]
    except Exception: return []

def get_pc_requirements(platforms_field):
    for p in (platforms_field or []):
        if p.get("platform",{}).get("slug")=="pc":
            reqs=p.get("requirements_en") or p.get("requirements") or {}
            mn=strip_tags(reqs.get("minimum")); rc=strip_tags(reqs.get("recommended"))
            if mn or rc: return {"minimum":mn,"recommended":rc}
    return None

def get_steam_app_details(appid):
    if not appid: return None
    try:
        r=requests.get("https://store.steampowered.com/api/appdetails",
                       params={"appids":appid,"l":"en"},timeout=8)
        r.raise_for_status()
        d=r.json().get(str(appid),{})
        return d.get("data") if d.get("success") else None
    except Exception as e: print("STEAM APPDETAILS ERROR:",repr(e)); return None

def cache_age(fa):
    if not fa: return "never fetched"
    m=int((datetime.datetime.utcnow()-fa).total_seconds()/60)
    if m<1: return "just now"
    if m<60: return f"{m}m ago"
    return f"{m//60}h ago"


# ── auth routes ───────────────────────────────────────────────────────────────

@app.route("/login",methods=["GET","POST"])
def login_page():
    if session.get('user_id'): return redirect("/")
    if request.method=="POST":
        identifier=request.form.get("identifier","").strip()
        password=request.form.get("password","")
        user=get_user_by_identifier(identifier)
        if user and check_password_hash(user["password_hash"],password):
            session["user_id"]=user["id"]
            try:
                db=get_db()
                db.execute("UPDATE users SET last_login=? WHERE id=?",
                           (datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),user["id"]))
                db.commit()
            except Exception: pass
            return redirect(request.args.get("next","/"))
        return render_template("login.html",login_error="Incorrect username/email or password.")
    return render_template("login.html")

@app.route("/register",methods=["POST"])
def register():
    username=request.form.get("username","").strip()
    email=request.form.get("email","").strip().lower()
    password=request.form.get("password","")
    if len(username)<3:
        return render_template("login.html",register_error="Username must be at least 3 characters.",show_register=True)
    if not re.match(r'^[a-zA-Z0-9_]+$',username):
        return render_template("login.html",register_error="Username: letters, numbers and _ only.",show_register=True)
    if len(password)<6:
        return render_template("login.html",register_error="Password must be at least 6 characters.",show_register=True)
    try:
        db=get_db()
        db.execute("INSERT INTO users (username,email,password_hash) VALUES (?,?,?)",
                   (username,email,generate_password_hash(password)))
        db.commit()
        user=get_user_by_identifier(username)
        session["user_id"]=user["id"]
        return redirect("/")
    except sqlite3.IntegrityError as e:
        msg="Username already taken." if "username" in str(e) else "Email already registered."
        return render_template("login.html",register_error=msg,show_register=True)

@app.route("/logout",methods=["POST"])
def logout():
    session.pop("user_id",None); return redirect("/login")


# ── main routes ───────────────────────────────────────────────────────────────

@app.route("/")
def home(): return render_template("index.html")

@app.route("/watchlist")
def watchlist(): return render_template("watchlist.html")

@app.route("/library")
def library(): return render_template("library.html")

@app.route("/api/news")
def api_news(): return jsonify(get_cached_news())

@app.route("/search/games")
def search_games():
    q=request.args.get("q","").strip()
    if not q: return jsonify([])
    params={"key":RAWG_API_KEY,"search":q,"page_size":12,"platforms":NON_MOBILE_PLATFORMS}
    genre=request.args.get("genre","").strip(); year=request.args.get("year","").strip()
    if genre: params["genres"]=genre
    if year:  params["dates"]=f"{year}-01-01,{year}-12-31"
    data=rawg_games(params)
    if data is None: return jsonify({"error":"Could not reach RAWG API"}),502
    return jsonify([format_game(g) for g in [g for g in data.get("results",[]) if is_appropriate(g)][:8]])

@app.route("/search/advanced")
def search_advanced():
    r,hm,_=perform_search(request.args)
    if r is None: return jsonify({"error":"Could not reach RAWG API"}),502
    return jsonify({"results":r,"has_more":hm})

@app.route("/search")
def search_page():
    r,hm,q=perform_search(request.args)
    if r is None: return render_template("error.html",message="Couldn't search right now."),502
    return render_template("search_results.html",results=r,has_more=hm,query=q,mode="game",
        filters={"q":q,"genre":request.args.get("genre",""),"platform":request.args.get("platform",""),
                 "year":request.args.get("year",""),"min_rating":request.args.get("min_rating",""),
                 "type":request.args.get("type","")})

@app.route("/section/<name>")
def home_section(name):
    if name=="recommended":
        genres=request.args.get("genres","").strip()
        if not genres: return jsonify([])
        games=curated_section({"key":RAWG_API_KEY,"platforms":NON_MOBILE_PLATFORMS,"genres":genres,"ordering":"-rating"},min_rating=3.5,limit=8)
    else:
        games=get_section_games(name,limit=int(request.args.get("limit",8)))
    if games is None: return jsonify({"error":"Could not reach RAWG API"}),502
    return jsonify(games)

@app.route("/section-page/<name>")
def section_page(name):
    if name not in SECTION_TITLES: return render_template("error.html",message="Section not found."),404
    games=get_section_games(name,limit=32)
    if games is None: return render_template("error.html",message="Couldn't load this section."),502
    return render_template("section_page.html",title=SECTION_TITLES[name],games=games)

@app.route("/game/random")
def random_game():
    data=rawg_games({"key":RAWG_API_KEY,"ordering":"-added","page_size":40,"platforms":NON_MOBILE_PLATFORMS})
    if not data or not data.get("results"): return render_template("error.html",message="Couldn't find a game."),502
    candidates=[g for g in data["results"] if is_appropriate(g)]
    if not candidates: return render_template("error.html",message="Couldn't find a game."),502
    return redirect(f"/game/{random.choice(candidates)['id']}")

@app.route("/api/trailer")
def api_trailer():
    name=request.args.get("name","").strip()
    if not name: return jsonify({"error":"missing name"}),400
    vid=get_youtube_trailer_id(name)
    return jsonify({"video_id":vid}) if vid else (jsonify({"error":"not found"}),404)


# ── deals ─────────────────────────────────────────────────────────────────────

@app.route("/deals")
def deals_page():
    store=request.args.get("store","").strip()
    min_disc=request.args.get("min_disc","0").strip()
    min_steam=request.args.get("min_steam","0").strip()
    sort_by=request.args.get("sort","Savings").strip()
    params={"sortBy":sort_by,"desc":1,"pageSize":60,"onSale":1}
    if store and store.isdigit(): params["storeID"]=store
    rate=get_usd_to_inr_rate() or 84
    deals_out=[]; error_msg=None
    try:
        r=requests.get("https://www.cheapshark.com/api/1.0/deals",params=params,timeout=12,
                       headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        r.raise_for_status(); raw=r.json()
        min_d=float(min_disc or "0"); min_s=float(min_steam or "0")
        for d in raw:
            try:
                sav=float(d.get("savings","0") or 0); steam=float(d.get("steamRatingPercent","0") or 0)
                if min_d>0 and sav<min_d: continue
                if min_s>0 and steam<min_s: continue
                usd_sale=float(d.get("salePrice","0") or 0); usd_norm=float(d.get("normalPrice","0") or 0)
                sid=0
                try: sid=int(d.get("storeID","0") or 0)
                except Exception: pass
                deals_out.append({
                    "title":d.get("title","Unknown"),"thumb":d.get("thumb"),
                    "sale_inr":round(usd_sale*rate),"normal_inr":round(usd_norm*rate) if usd_norm>usd_sale else None,
                    "savings_pct":round(sav),"store_name":STORE_NAMES.get(sid,"Store"),
                    "metacritic":d.get("metacriticScore",""),"steam_pct":d.get("steamRatingPercent",""),
                    "deal_id":d.get("dealID",""),"is_free":usd_sale==0,"is_best_price":sav>=90,
                })
            except Exception: continue
    except Exception as e: print("CHEAPSHARK ERROR:",repr(e)); error_msg="Could not reach CheapShark. Try again shortly."
    return render_template("deals.html",deals=deals_out,rate=rate,error_msg=error_msg,
        filters={"store":store,"min_disc":min_disc,"min_steam":min_steam,"sort":sort_by})


# ── admin ─────────────────────────────────────────────────────────────────────

def admin_ok(): return session.get("admin_logged_in") is True

def get_all_users():
    try:
        rows=get_db().execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception: return []

@app.route("/admin",methods=["GET"])
def admin():
    if not admin_ok(): return render_template("admin.html",logged_in=False,error=None)
    s=load_settings(); fa=_news_cache.get("fetched_at"); ia=_inr_rate_cache.get("fetched_at")
    users=get_all_users()
    stats={"trailer_count":len(_trailer_cache),"news_count":len(_news_cache.get("data") or []),
           "news_age":cache_age(fa),"inr_rate":round(_inr_rate_cache.get("rate") or 0,2),
           "inr_age":cache_age(ia),"goty_count":len(s["goty_winners"]),"jikan_count":len(_jikan_cache),
           "total_users":len(users),"admin_count":sum(1 for u in users if u.get("is_admin"))}
    return render_template("admin.html",logged_in=True,stats=stats,settings=s,users=users,
                           section=request.args.get("section",""),msg=request.args.get("msg",""))

@app.route("/admin/login",methods=["POST"])
def admin_login():
    if request.form.get("password","") == ADMIN_PASSWORD:
        session["admin_logged_in"]=True; return redirect("/admin")
    return render_template("admin.html",logged_in=False,error="Incorrect password.")

@app.route("/admin/logout",methods=["POST"])
def admin_logout(): session.pop("admin_logged_in",None); return redirect("/admin")

@app.route("/admin/users/delete",methods=["POST"])
def admin_user_delete():
    if not admin_ok(): return redirect("/admin")
    uid=request.form.get("user_id","")
    if uid:
        try:
            db=get_db()
            user=db.execute("SELECT is_admin FROM users WHERE id=?",(uid,)).fetchone()
            if user and not user["is_admin"]:
                db.execute("DELETE FROM users WHERE id=?",(uid,)); db.commit()
        except Exception as e: print("DELETE USER ERROR:",repr(e))
    return redirect("/admin?section=users&msg=User+deleted")

@app.route("/admin/clear-cache/<name>",methods=["POST"])
def admin_clear_cache(name):
    if not admin_ok(): return redirect("/admin")
    if name=="trailers": _trailer_cache.clear()
    elif name=="news":   _news_cache["data"]=None; _news_cache["fetched_at"]=None
    elif name=="inr":    _inr_rate_cache["rate"]=None; _inr_rate_cache["fetched_at"]=None
    elif name=="jikan":  _jikan_cache.clear()
    return redirect("/admin?section=cache&msg=Cache+cleared")

@app.route("/admin/goty/add",methods=["POST"])
def admin_goty_add():
    if not admin_ok(): return redirect("/admin")
    name=request.form.get("name","").strip(); year=request.form.get("year","").strip()
    if name and year:
        s=load_settings(); s["goty_winners"].insert(0,{"name":name,"year":int(year)})
        s["goty_winners"].sort(key=lambda x:x["year"],reverse=True); save_settings(s)
    return redirect("/admin?section=goty&msg=Added")

@app.route("/admin/goty/remove",methods=["POST"])
def admin_goty_remove():
    if not admin_ok(): return redirect("/admin")
    name=request.form.get("name",""); year=request.form.get("year","")
    s=load_settings()
    s["goty_winners"]=[g for g in s["goty_winners"] if not(g["name"]==name and str(g["year"])==year)]
    save_settings(s); return redirect("/admin?section=goty&msg=Removed")

@app.route("/admin/keywords/add",methods=["POST"])
def admin_kw_add():
    if not admin_ok(): return redirect("/admin")
    kw=request.form.get("keyword","").strip().lower()
    if kw:
        s=load_settings()
        if kw not in s["nsfw_keywords"]: s["nsfw_keywords"].append(kw); save_settings(s)
    return redirect("/admin?section=keywords&msg=Added")

@app.route("/admin/keywords/remove",methods=["POST"])
def admin_kw_remove():
    if not admin_ok(): return redirect("/admin")
    kw=request.form.get("keyword",""); s=load_settings()
    s["nsfw_keywords"]=[k for k in s["nsfw_keywords"] if k!=kw]; save_settings(s)
    return redirect("/admin?section=keywords&msg=Removed")

@app.route("/admin/feeds/toggle",methods=["POST"])
def admin_feeds_toggle():
    if not admin_ok(): return redirect("/admin")
    url=request.form.get("url",""); s=load_settings()
    for f in s["news_feeds"]:
        if f["url"]==url: f["enabled"]=not f.get("enabled",True); break
    save_settings(s); _news_cache["data"]=None; return redirect("/admin?section=feeds&msg=Updated")


# ── game detail ───────────────────────────────────────────────────────────────

@app.route("/game/<int:game_id>")
def game_detail(game_id):
    try:
        r=requests.get(f"{RAWG_BASE_URL}/games/{game_id}",params={"key":RAWG_API_KEY},timeout=8)
        r.raise_for_status(); g=r.json()
    except Exception: return render_template("error.html",message="Couldn't load this game right now."),502
    stores,steam_appid=[],None
    try:
        sr=requests.get(f"{RAWG_BASE_URL}/games/{game_id}/stores",params={"key":RAWG_API_KEY},timeout=8)
        sr.raise_for_status()
        for s in sr.json().get("results",[]):
            sid,url=s.get("store_id"),s.get("url")
            if not url: continue
            stores.append({"name":STORE_NAMES.get(sid,"Store"),"url":url})
            if sid==1:
                m=re.search(r"/app/(\d+)",url)
                if m: steam_appid=m.group(1)
    except Exception: pass
    pub=g.get("publishers") or []
    desc=(g.get("description_raw") or "").strip()
    requirements=get_pc_requirements(g.get("platforms"))
    if steam_appid and (not desc or not requirements):
        sd=get_steam_app_details(steam_appid)
        if sd:
            if not desc:
                desc=strip_tags(sd.get("detailed_description") or sd.get("short_description") or "")
            if not requirements:
                pc_reqs=sd.get("pc_requirements") or {}
                mn=strip_tags(pc_reqs.get("minimum",""))
                rc=strip_tags(pc_reqs.get("recommended",""))
                if mn or rc: requirements={"minimum":mn,"recommended":rc}
    if not desc: desc="No description available."
    esrb=g.get("esrb_rating"); clip=g.get("clip") or None; trailer=None
    if clip and clip.get("clip"):
        trailer={"video":clip["clip"],"preview":clip.get("preview"),"youtube_id":clip.get("video")}
    game={"id":g.get("id"),"name":g.get("name"),
          "image":resize_image(g.get("background_image"),1280),
          "rating":g.get("rating"),"released":year_only(g.get("released")),
          "genres":", ".join(x["name"] for x in g.get("genres",[])),
          "publisher":pub[0]["name"] if pub else None,
          "platforms":[p["platform"]["name"] for p in (g.get("platforms") or [])],
          "description":desc,"stores":stores,
          "steam_rating":get_steam_rating(steam_appid) if steam_appid else None,
          "pc_price":get_pc_price(steam_appid) if steam_appid else None,
          "screenshots":get_screenshots(game_id),
          "esrb":esrb["name"] if esrb else None,
          "tags":[t["name"] for t in (g.get("tags") or []) if t.get("language")=="eng"][:6],
          "trailer":trailer,"similar":get_similar_games(game_id),
          "requirements":requirements}
    return render_template("game_detail.html",game=game)


if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, os, secrets, random, json, datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

DATA_DIR = os.environ.get("RENDER_DISK_MOUNT_PATH") or os.path.dirname(__file__)
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "egg.db")

DEFAULT_SETTINGS = {
    "business_name": "Uproot",
    "campaign_name": "Easter Egg Experience",
    "instagram_handle": "@Uproot",
    "require_story_share": True,
    "prizes": [
        {"id": "5OFF", "title": "5% OFF", "subtitle": "Your next visit", "weight": 55, "active": True},
        {"id": "10OFF", "title": "10% OFF", "subtitle": "Your next visit", "weight": 25, "active": True},
        {"id": "DRINK", "title": "Free Drink", "subtitle": "One complimentary brunch beverage", "weight": 10, "active": True},
        {"id": "25GC", "title": "$25 Gift Card", "subtitle": "A little extra reason to come back", "weight": 8, "active": True},
        {"id": "BRUNCH2", "title": "FREE BRUNCH FOR 2", "subtitle": "Rare win. Big congratulations.", "weight": 2, "active": True},
    ]
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            first_name TEXT,
            instagram_handle TEXT,
            prize_id TEXT NOT NULL,
            prize_title TEXT NOT NULL,
            prize_subtitle TEXT,
            created_at TEXT NOT NULL,
            redeemed INTEGER DEFAULT 0,
            redeemed_at TEXT,
            redeemed_by TEXT
        )
    """)
    conn.commit()

    existing = cur.execute("SELECT value FROM settings WHERE key='config'").fetchone()
    if not existing:
        cur.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?)",
            ("config", json.dumps(DEFAULT_SETTINGS))
        )
        conn.commit()

    conn.close()


def load_settings():
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key='config'").fetchone()
    conn.close()
    if not row:
        return DEFAULT_SETTINGS
    try:
        return json.loads(row["value"])
    except Exception:
        return DEFAULT_SETTINGS


def save_settings(data):
    conn = get_db()
    conn.execute("REPLACE INTO settings(key, value) VALUES(?, ?)", ("config", json.dumps(data)))
    conn.commit()
    conn.close()


def choose_prize(prizes):
    active = [p for p in prizes if p.get("active") and int(p.get("weight", 0)) > 0]
    total = sum(int(p["weight"]) for p in active)
    if total <= 0:
        raise ValueError("No active prizes with positive weight.")

    pick = random.uniform(0, total)
    upto = 0
    for p in active:
        upto += int(p["weight"])
        if pick <= upto:
            return p
    return active[0]


def new_code(prize_id):
    return f"UP-{prize_id}-{secrets.token_hex(3).upper()}"


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("admin_authed") is not True:
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


with app.app_context():
    init_db()


@app.route("/")
def index():
    settings = load_settings()
    existing_code = session.get("claim_code")
    claim = None

    if existing_code:
        conn = get_db()
        claim = conn.execute("SELECT * FROM claims WHERE code=?", (existing_code,)).fetchone()
        conn.close()

    return render_template("index.html", settings=settings, claim=claim)


@app.post("/start")
def start():
    first_name = request.form.get("first_name", "").strip()
    instagram_handle = request.form.get("instagram_handle", "").strip()

    if not first_name or not instagram_handle:
        flash("Enter your first name and Instagram handle.")
        return redirect(url_for("index"))

    session["first_name"] = first_name
    session["instagram_handle"] = instagram_handle
    session["started"] = True
    return redirect(url_for("egg"))


@app.route("/egg")
def egg():
    if not session.get("started"):
        return redirect(url_for("index"))
    return render_template("egg.html", settings=load_settings())


@app.post("/reveal")
def reveal():
    if not session.get("started"):
        return redirect(url_for("index"))

    if session.get("claim_code"):
        return redirect(url_for("claim", code=session["claim_code"]))

    settings = load_settings()
    prize = choose_prize(settings["prizes"])
    code = new_code(prize["id"])
    now = datetime.datetime.utcnow().isoformat() + "Z"

    conn = get_db()
    conn.execute("""
        INSERT INTO claims(code, first_name, instagram_handle, prize_id, prize_title, prize_subtitle, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        code,
        session.get("first_name"),
        session.get("instagram_handle"),
        prize["id"],
        prize["title"],
        prize.get("subtitle", ""),
        now
    ))
    conn.commit()
    conn.close()

    session["claim_code"] = code
    return redirect(url_for("claim", code=code))


@app.route("/claim/<code>")
def claim(code):
    conn = get_db()
    claim = conn.execute("SELECT * FROM claims WHERE code=?", (code,)).fetchone()
    conn.close()

    if not claim:
        return "Claim not found", 404

    return render_template("claim.html", claim=claim, settings=load_settings())


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        expected = os.environ.get("ADMIN_PASSWORD", "uproot123")
        if password == expected:
            session["admin_authed"] = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Incorrect password."

    return render_template("login.html", error=error, settings=load_settings())


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def dashboard():
    conn = get_db()
    claims = conn.execute("SELECT * FROM claims ORDER BY id DESC").fetchall()
    conn.close()

    settings = load_settings()
    total = len(claims)
    redeemed = sum(1 for c in claims if c["redeemed"])

    return render_template(
        "admin.html",
        claims=claims,
        settings=settings,
        total=total,
        redeemed=redeemed
    )


@app.post("/admin/settings")
@admin_required
def update_settings():
    settings = load_settings()
    settings["business_name"] = request.form.get("business_name", settings["business_name"]).strip() or settings["business_name"]
    settings["campaign_name"] = request.form.get("campaign_name", settings["campaign_name"]).strip() or settings["campaign_name"]
    settings["instagram_handle"] = request.form.get("instagram_handle", settings["instagram_handle"]).strip() or settings["instagram_handle"]
    settings["require_story_share"] = request.form.get("require_story_share") == "on"

    prizes = []
    for i in range(5):
        prizes.append({
            "id": request.form.get(f"prize_id_{i}", "").strip() or f"P{i+1}",
            "title": request.form.get(f"prize_title_{i}", "").strip() or f"Prize {i+1}",
            "subtitle": request.form.get(f"prize_subtitle_{i}", "").strip(),
            "weight": max(0, int(request.form.get(f"prize_weight_{i}", "0") or 0)),
            "active": request.form.get(f"prize_active_{i}") == "on",
        })

    settings["prizes"] = prizes
    save_settings(settings)
    flash("Settings updated.")
    return redirect(url_for("dashboard"))


@app.post("/admin/redeem/<code>")
@admin_required
def redeem(code):
    staff = request.form.get("staff_name", "").strip() or "Staff"
    conn = get_db()
    row = conn.execute("SELECT redeemed FROM claims WHERE code=?", (code,)).fetchone()

    if not row:
        conn.close()
        flash("Claim not found.")
        return redirect(url_for("dashboard"))

    if row["redeemed"]:
        conn.close()
        flash("Claim already redeemed.")
        return redirect(url_for("dashboard"))

    conn.execute(
        "UPDATE claims SET redeemed=1, redeemed_at=?, redeemed_by=? WHERE code=?",
        (datetime.datetime.utcnow().isoformat() + "Z", staff, code)
    )
    conn.commit()
    conn.close()

    flash(f"{code} redeemed.")
    return redirect(url_for("dashboard"))


@app.get("/api/claim/<code>")
def api_claim(code):
    conn = get_db()
    row = conn.execute("SELECT * FROM claims WHERE code=?", (code,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({
        "ok": True,
        "code": row["code"],
        "prize_title": row["prize_title"],
        "prize_subtitle": row["prize_subtitle"],
        "redeemed": bool(row["redeemed"]),
        "first_name": row["first_name"],
        "instagram_handle": row["instagram_handle"],
    })


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)

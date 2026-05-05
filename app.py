from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta
import logging
import traceback

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

logging.basicConfig(level=logging.DEBUG)
app.config["PROPAGATE_EXCEPTIONS"] = True

# ================= DB =================

def init_db():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS awizacje (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        firma TEXT,
        rejestracja TEXT,
        kierowca TEXT,
        email TEXT,
        telefon TEXT,
        data_godzina TEXT,
        typ_ladunku TEXT,
        waga_ladunku TEXT,
        komentarz TEXT,
        status TEXT DEFAULT 'oczekująca'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE,
        haslo TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS logi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        akcja TEXT,
        data TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS permissions (
        login TEXT PRIMARY KEY,
        can_edit INTEGER DEFAULT 1,
        can_status INTEGER DEFAULT 1,
        calendar_only INTEGER DEFAULT 0,
        show_logi INTEGER DEFAULT 1,
        show_historia INTEGER DEFAULT 1,
        show_permissions INTEGER DEFAULT 1
    )''')

    conn.commit()
    conn.close()

init_db()

# ================= USERS =================

def create_users():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    users = [
        ("SK","1234"),
        ("JU","1234"),
        ("BL","1234"),
        ("KJ","1234"),
        ("TR","1234"),
        ("MAGAZYN","1234"),
        ("EK","1234"),
    ]

    for u,p in users:
        c.execute("INSERT OR IGNORE INTO users (login, haslo) VALUES (?,?)", (u,p))

        c.execute("""
            INSERT OR IGNORE INTO permissions VALUES (?,?,?,?,?,?,?)
        """, (u,1,1,0,1,1,1))

    conn.commit()
    conn.close()

create_users()

# ================= LOG =================

def log_action(user, akcja):
    try:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
                  (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except:
        pass

# ================= PERMISSIONS (DICT VERSION) =================

def get_perms(login):
    try:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()

        c.execute("""
            SELECT can_edit, can_status, calendar_only,
                   show_logi, show_historia, show_permissions
            FROM permissions WHERE login=?
        """, (login,))

        row = c.fetchone()
        conn.close()

        if not row:
            row = (1,1,0,1,1,1)

        return {
            "can_edit": row[0],
            "can_status": row[1],
            "calendar_only": row[2],
            "show_logi": row[3],
            "show_historia": row[4],
            "show_permissions": row[5]
        }

    except:
        return {
            "can_edit": 1,
            "can_status": 1,
            "calendar_only": 0,
            "show_logi": 1,
            "show_historia": 1,
            "show_permissions": 1
        }

# ================= SLOTY =================

def get_days_and_slots():
    today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)

    dni = []
    d = today
    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    godziny = []
    for s,e in [("07:30","09:30"),("11:00","13:15"),("14:15","20:00")]:
        t = datetime.strptime(s,"%H:%M")
        e = datetime.strptime(e,"%H:%M")
        while t < e:
            godziny.append(t.strftime("%H:%M"))
            t += timedelta(minutes=15)

    try:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT data_godzina FROM awizacje")
        rows = c.fetchall()
        conn.close()
    except:
        rows = []

    zajete = {}

    for r in rows:
        try:
            base = datetime.strptime(r[0], "%Y-%m-%dT%H:%M")
            for i in range(-3,4):
                key = (base + timedelta(minutes=15*i)).strftime("%Y-%m-%dT%H:%M")
                zajete[key] = True
        except:
            continue

    return dni, godziny, zajete

# ================= ADMIN =================

@app.route("/admin")
def admin():
    try:
        if not session.get("logged_in"):
            return redirect("/login")

        login = session.get("user", "UNKNOWN")

        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT * FROM awizacje ORDER BY id DESC")
        awizacje = c.fetchall()
        conn.close()

        dni, godziny, zajete = get_days_and_slots()
        perms = get_perms(login)

        return render_template(
            "admin.html",
            awizacje=awizacje,
            dni=dni,
            godziny=godziny,
            zajete=zajete,
            perms=perms
        )

    except Exception as e:
        traceback.print_exc()
        return f"ADMIN ERROR: {e}", 500

# ================= FORM =================

@app.route("/")
def index():
    dni, godziny, zajete = get_days_and_slots()

    return render_template(
        "form.html",
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        dane={},
        error=None
    )

# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        haslo = request.form["haslo"]

        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND haslo=?", (login,haslo))
        user = c.fetchone()
        conn.close()

        if user:
            session["logged_in"] = True
            session["user"] = login
            log_action(login,"LOGIN")
            return redirect("/admin")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= OTHER ROUTES =================

@app.route("/admin/logi")
def logi():
    return render_template("logi.html")

@app.route("/admin/historia")
def historia():
    return render_template("historia.html")

@app.route("/admin/permissions")
def permissions():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM permissions")
    users = c.fetchall()
    conn.close()

    return render_template("permissions.html", users=users)

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

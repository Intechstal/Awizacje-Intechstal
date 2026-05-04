from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

PERM_PASSWORD = "963852"

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

    c.execute('''CREATE TABLE IF NOT EXISTS permissions (
        login TEXT PRIMARY KEY,
        can_edit INTEGER DEFAULT 1,
        can_status INTEGER DEFAULT 1,
        calendar_only INTEGER DEFAULT 0,
        show_logi INTEGER DEFAULT 1,
        show_historia INTEGER DEFAULT 1,
        show_permissions INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS logi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        akcja TEXT,
        data TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# ================= USERS =================

def create_users():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    users = ["SK","JU","BL","KJ","TR","MAGAZYN","EK"]

    for u in users:
        try:
            c.execute("INSERT INTO users (login, haslo) VALUES (?,?)", (u, "1234"))
        except:
            pass

        try:
            c.execute("""INSERT OR IGNORE INTO permissions
                (login, can_edit, can_status, calendar_only, show_logi, show_historia, show_permissions)
                VALUES (?,?,?,?,?,?,?)""",
                (u,1,1,0,1,1,1))
        except:
            pass

    conn.commit()
    conn.close()

create_users()

# ================= LOGI =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
              (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# ================= PERMISSIONS =================

def get_perm(login):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("""SELECT can_edit, can_status, calendar_only,
                 show_logi, show_historia, show_permissions
                 FROM permissions WHERE login=?""", (login,))
    p = c.fetchone()
    conn.close()

    return p if p else (1,1,0,1,1,1)

# ================= SLOTY =================

def get_days_and_slots():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    dni = []
    d = today
    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    godziny = []
    for start, end in [("07:30","09:30"),("11:00","13:15"),("14:15","20:00")]:
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        while s < e:
            godziny.append(s.strftime("%H:%M"))
            s += timedelta(minutes=15)

    zajete = {}
    return dni, godziny, zajete

# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        haslo = request.form["haslo"]

        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND haslo=?", (login, haslo))
        user = c.fetchone()
        conn.close()

        if user:
            session["logged_in"] = True
            session["user"] = login
            log_action(login, "LOGIN")
            return redirect("/admin")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= FORM =================

@app.route("/")
def index():
    dni, godziny, zajete = get_days_and_slots()
    return render_template("form.html", dni=dni, godziny=godziny, zajete=zajete, dane={}, error=None)

# ================= ADMIN =================

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY id DESC")
    awizacje = c.fetchall()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    perms = get_perm(session["user"])

    return render_template(
        "admin.html",
        awizacje=awizacje,
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        perms=perms
    )

# ================= LOGI =================

@app.route("/admin/logi")
def logi():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM logi ORDER BY id DESC")
    logi = c.fetchall()
    conn.close()

    return render_template("logi.html", logi=logi)

# ================= HISTORIA =================

@app.route("/admin/historia")
def historia():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY data_godzina DESC")
    dane = c.fetchall()
    conn.close()

    return render_template("historia.html", awizacje=dane)

# ================= PERMISSIONS LOGIN =================

@app.route("/admin/permissions/login", methods=["GET","POST"])
def permissions_login():
    if request.method == "POST":
        if request.form["password"] == PERM_PASSWORD:
            session["perm_access"] = True
            return redirect("/admin/permissions")

    return render_template("permissions_login.html")

# ================= PERMISSIONS =================

@app.route("/admin/permissions", methods=["GET","POST"])
def permissions():
    if not session.get("logged_in"):
        return redirect("/login")

    if not session.get("perm_access"):
        return redirect("/admin/permissions/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        login = request.form["login"]

        c.execute("""UPDATE permissions SET
            can_edit=?,
            can_status=?,
            calendar_only=?,
            show_logi=?,
            show_historia=?,
            show_permissions=?
            WHERE login=?""",
            (
                "can_edit" in request.form,
                "can_status" in request.form,
                "calendar_only" in request.form,
                "show_logi" in request.form,
                "show_historia" in request.form,
                "show_permissions" in request.form,
                login
            ))

        conn.commit()

    c.execute("""SELECT login, can_edit, can_status, calendar_only,
                 show_logi, show_historia, show_permissions
                 FROM permissions""")

    users = c.fetchall()
    conn.close()

    return render_template("permissions.html", users=users)

# ================= RUN =================

aplication = app

if __name__ == "__main__":
    app.run()

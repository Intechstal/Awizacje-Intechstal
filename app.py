from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ================= TIME FIX =================

def now_pl():
    return datetime.utcnow() + timedelta(hours=2)

# ================= INIT DB =================

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
        show_permissions INTEGER DEFAULT 1,
        show_slots INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS slot_settings (
        typ TEXT PRIMARY KEY,
        zakres INTEGER
    )''')

    conn.commit()
    conn.close()

init_db()

# ================= LOGS =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
        (user, akcja, now_pl().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

# ================= USERS (MINIMUM) =================

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
        c.execute("INSERT OR IGNORE INTO users VALUES (?,?)", (u,p))
        c.execute("INSERT OR IGNORE INTO permissions (login) VALUES (?)", (u,))

    conn.commit()
    conn.close()

create_users()

# ================= FORM =================

@app.route("/")
def index():
    return render_template("form.html")

@app.route("/zapisz", methods=["POST"])
def zapisz():
    f = request.form

    if not f.get("data_godzina"):
        return "Brak daty", 500

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""INSERT INTO awizacje
    (firma,rejestracja,kierowca,email,telefon,data_godzina,typ_ladunku,waga_ladunku,komentarz)
    VALUES (?,?,?,?,?,?,?,?,?)""",
    (
        f.get("firma"),
        f.get("rejestracja"),
        f.get("kierowca"),
        f.get("email"),
        f.get("telefon"),
        f.get("data_godzina"),
        f.get("typ_ladunku"),
        f.get("waga_ladunku"),
        f.get("komentarz")
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")

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
            return redirect("/admin")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= ADMIN =================

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje")
    awizacje = c.fetchall()
    conn.close()

    return render_template("admin.html",
        awizacje=awizacje,
        perms=(1,1,0,1,1,1,1)
    )

# ================= STATUS =================

@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (request.form["status"], id))
    conn.commit()
    conn.close()
    return redirect("/admin")

# ================= EDIT =================

@app.route("/admin/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        f = request.form
        c.execute("""UPDATE awizacje SET
        firma=?,rejestracja=?,kierowca=?,email=?,telefon=?,data_godzina=?,typ_ladunku=?,waga_ladunku=?,komentarz=?
        WHERE id=?""",
        (f["firma"],f["rejestracja"],f["kierowca"],f["email"],f["telefon"],
         f["data_godzina"],f["typ_ladunku"],f["waga_ladunku"],f["komentarz"],id))
        conn.commit()
        conn.close()
        return redirect("/admin")

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    a = c.fetchone()
    conn.close()

    return render_template("edit.html", awizacja=a)

# ================= LOGI =================

@app.route("/admin/logi")
def logi():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM logi ORDER BY id DESC")
    logi = c.fetchall()
    conn.close()
    return render_template("logi.html", logi=logi)

# ================= HISTORIA =================

@app.route("/admin/historia")
def historia():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return render_template("historia.html", awizacje=data)

# ================= PERMISSIONS (FIX 404) =================

@app.route("/admin/permissions", methods=["GET","POST"])
def permissions():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        login = request.form["login"]

        c.execute("""
        UPDATE permissions SET
        can_edit=?,
        can_status=?,
        calendar_only=?,
        show_logi=?,
        show_historia=?,
        show_permissions=?,
        show_slots=?
        WHERE login=?
        """, (
            "can_edit" in request.form,
            "can_status" in request.form,
            "calendar_only" in request.form,
            "show_logi" in request.form,
            "show_historia" in request.form,
            "show_permissions" in request.form,
            "show_slots" in request.form,
            login
        ))
        conn.commit()

    c.execute("SELECT * FROM permissions")
    users = c.fetchall()
    conn.close()

    return render_template("permissions.html", users=users)

# ================= SLOTS (FIX 404) =================

@app.route("/admin/slots", methods=["GET","POST"])
def slots():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        c.execute("INSERT OR REPLACE INTO slot_settings VALUES (?,?)",
                  (request.form["typ"], request.form["zakres"]))
        conn.commit()

    c.execute("SELECT * FROM slot_settings")
    data = c.fetchall()
    conn.close()

    return render_template("slots.html", settings=data)

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ================= TIME =================

def now_pl():
    return datetime.utcnow() + timedelta(hours=2)

# ================= LOGS (NAPRAWIONE 100%) =================

def log_action(user, akcja):
    try:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()

        c.execute(
            "INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
            (user if user else "UNKNOWN", akcja,
             now_pl().strftime("%Y-%m-%d %H:%M:%S"))
        )

        conn.commit()
        conn.close()
    except Exception as e:
        print("LOG ERROR:", e)

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
        login TEXT,
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
        zakres INTEGER DEFAULT 3
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
    user = session.get("user", "FORM")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""INSERT INTO awizacje
    (firma,rejestracja,kierowca,email,telefon,data_godzina,typ_ladunku,waga_ladunku,komentarz)
    VALUES (?,?,?,?,?,?,?,?,?)""",
    (
        f.get("firma",""),
        f.get("rejestracja",""),
        f.get("kierowca",""),
        f.get("email",""),
        f.get("telefon",""),
        f.get("data_godzina",""),
        f.get("typ_ladunku",""),
        f.get("waga_ladunku",""),
        f.get("komentarz","")
    ))

    conn.commit()
    conn.close()

    log_action(user, "NOWA AWIZACJA")

    return redirect("/admin")

# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        haslo = request.form["haslo"]

        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND haslo=?", (login, haslo))
        u = c.fetchone()
        conn.close()

        if u:
            session["logged_in"] = True
            session["user"] = login
            log_action(login, "LOGIN")
            return redirect("/admin")

    return render_template("login.html")

@app.route("/logout")
def logout():
    user = session.get("user")
    log_action(user, "LOGOUT")
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
    c.execute("UPDATE awizacje SET status=? WHERE id=?",
              (request.form["status"], id))
    conn.commit()
    conn.close()

    log_action(session.get("user"), f"STATUS ID {id}")

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

        log_action(session.get("user"), f"EDYCJA ID {id}")
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
    data = c.fetchall()
    conn.close()
    return render_template("logi.html", logi=data)

# ================= HISTORIA =================

@app.route("/admin/historia")
def historia():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return render_template("historia.html", awizacje=data)

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

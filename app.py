from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ================= CZAS POLSKI (FIX 2H OFFSET) =================

def now_pl():
    return datetime.utcnow() + timedelta(hours=2)

# ================= LOGI =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
        (user, akcja, now_pl().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

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

    conn.commit()
    conn.close()

init_db()

# ================= USERS (ZACHOWANE) =================

def create_users():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    users = [
        ("SK", "1234"),
        ("JU", "1234"),
        ("BL", "1234"),
        ("KJ", "1234"),
        ("TR", "1234"),
        ("MAGAZYN", "1234"),
        ("EK", "1234"),
    ]

    for u, p in users:
        try:
            c.execute("INSERT INTO users (login, haslo) VALUES (?,?)", (u, p))
        except:
            pass

    conn.commit()
    conn.close()

create_users()

# ================= SLOTY =================

def get_days_and_slots():
    today = now_pl().replace(hour=0, minute=0, second=0, microsecond=0)

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

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("SELECT id,firma,status,data_godzina,typ_ladunku,waga_ladunku,komentarz FROM awizacje")

    for id_, f, s, dt, typ, waga, kom in c.fetchall():
        try:
            base = datetime.strptime(dt, "%Y-%m-%dT%H:%M")
        except:
            continue

        for i in range(-3, 4):
            key = (base + timedelta(minutes=15*i)).strftime("%Y-%m-%dT%H:%M")

            zajete[key] = {
                "id": id_,
                "firma": f,
                "status": s,
                "typ_ladunku": typ,
                "waga": waga,
                "komentarz": kom,
                "main": (i == 0),
                "future_block": (i > 0)
            }

    conn.close()
    return dni, godziny, zajete

# ================= FORM =================

@app.route("/")
def index():
    dni, godziny, zajete = get_days_and_slots()
    return render_template("form.html",
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        dane={},
        error=None
    )

@app.route("/zapisz", methods=["POST"])
def zapisz():
    dane = request.form.to_dict()

    slot = datetime.strptime(dane["data_godzina"], "%Y-%m-%dT%H:%M")

    # ❗ FIX: blokada przeszłości (PL TIME)
    if slot <= now_pl():
        return render_template("form.html", error="Nie można awizować przeszłości")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""INSERT INTO awizacje
        (firma,rejestracja,kierowca,email,telefon,data_godzina,typ_ladunku,waga_ladunku,komentarz)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (dane["firma"],dane["rejestracja"],dane["kierowca"],
         dane["email"],dane["telefon"],dane["data_godzina"],
         dane["typ_ladunku"],dane["waga_ladunku"],dane.get("komentarz",""))
    )

    conn.commit()
    conn.close()

    log_action("FORM", f"NOWA AWIZACJA {dane['firma']}")

    return render_template("success.html")

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
    if session.get("user"):
        log_action(session["user"], "LOGOUT")
    session.clear()
    return redirect("/login")

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

    return render_template("admin.html",
        awizacje=awizacje,
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        perms=(1,1,0,1,1,1,1)
    )

# ================= STATUS =================

@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):
    if not session.get("logged_in"):
        return redirect("/login")

    status = request.form["status"]

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

    log_action(session["user"], f"STATUS ID {id} -> {status}")

    return redirect("/admin")

# ================= EDIT =================

@app.route("/admin/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        f = request.form

        c.execute("""UPDATE awizacje SET
            firma=?, rejestracja=?, kierowca=?, email=?, telefon=?,
            data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?
            WHERE id=?""",
            (f["firma"],f["rejestracja"],f["kierowca"],
             f["email"],f["telefon"],f["data_godzina"],
             f["typ_ladunku"],f["waga_ladunku"],f["komentarz"],id)
        )

        conn.commit()
        conn.close()

        log_action(session["user"], f"EDYCJA ID {id}")
        return redirect("/admin")

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    awizacja = c.fetchone()
    conn.close()

    return render_template("edit.html", awizacja=awizacja)

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

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

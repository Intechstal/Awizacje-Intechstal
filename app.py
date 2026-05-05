from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ================= TIME =================

def now_pl():
    return datetime.utcnow() + timedelta(hours=2)

# ================= DB INIT =================

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

# ================= LOGS =================

def log_action(user, akcja):
    try:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
            (user if user else "UNKNOWN",
             akcja,
             now_pl().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except:
        pass

# ================= SLOTY (NAPRAWIONE – KLUCZOWE) =================

def get_days_and_slots():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    dni = []
    d = today
    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    godziny = []
    for s, e in [("07:30","09:30"),("11:00","13:15"),("14:15","20:00")]:
        t = datetime.strptime(s, "%H:%M")
        end = datetime.strptime(e, "%H:%M")

        while t < end:
            godziny.append(t.strftime("%H:%M"))
            t += timedelta(minutes=15)

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje")
    rows = c.fetchall()
    conn.close()

    zajete = {}

    for r in rows:
        try:
            base = datetime.strptime(r[6], "%Y-%m-%dT%H:%M")
        except:
            continue

        typ = r[7] if r[7] else "default"
        zakres = 3

        for i in range(-zakres, zakres + 1):
            key = (base + timedelta(minutes=15*i)).strftime("%Y-%m-%dT%H:%M")

            zajete[key] = {
                "firma": r[1],
                "status": r[10],
                "typ_ladunku": r[7],
                "waga": r[8],
                "komentarz": r[9],
                "main": (i == 0),
                "future_block": (i > 0)
            }

    return dni, godziny, zajete

# ================= FORM =================

@app.route("/")
def index():
    dane = {
        "firma": "",
        "rejestracja": "",
        "kierowca": "",
        "email": "",
        "telefon": ""
    }

    return render_template("form.html", dane=dane)

@app.route("/zapisz", methods=["POST"])
def zapisz():
    f = request.form

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

    log_action(session.get("user","FORM"), "NOWA AWIZACJA")

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
    log_action(session.get("user"), "LOGOUT")
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

    dni, godziny, zajete = get_days_and_slots()

    return render_template(
        "admin.html",
        awizacje=awizacje,
        dni=dni,
        godziny=godziny,
        zajete=zajete,
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
        (
            f["firma"],f["rejestracja"],f["kierowca"],f["email"],f["telefon"],
            f["data_godzina"],f["typ_ladunku"],f["waga_ladunku"],f["komentarz"],id
        ))

        conn.commit()
        conn.close()

        log_action(session.get("user"), f"EDIT ID {id}")
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

# ================= PERMISSIONS =================

@app.route("/admin/permissions", methods=["GET","POST"])
def permissions():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        login = request.form["login"]

        c.execute("""UPDATE permissions SET
        can_edit=?,can_status=?,calendar_only=?,show_logi=?,show_historia=?,show_permissions=?,show_slots=?
        WHERE login=?""",
        (
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

# ================= SLOTS =================

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

    if not data:
        data = [("złom",3),("dostawa",2),("materiał",4)]

    conn.close()

    return render_template("slots.html", settings=data)

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

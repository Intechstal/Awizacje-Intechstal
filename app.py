from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ================= TIME =================

def now_pl():
    return datetime.utcnow() + timedelta(hours=2)

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

    conn.commit()
    conn.close()

init_db()

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
    for s, e in [("07:30","09:30"),("11:00","13:15"),("14:15","20:00")]:
        t = datetime.strptime(s, "%H:%M")
        end = datetime.strptime(e, "%H:%M")

        while t < end:
            godziny.append(t.strftime("%H:%M"))
            t += timedelta(minutes=15)

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT data_godzina FROM awizacje")
    rows = c.fetchall()
    conn.close()

    zajete = {}

    for r in rows:
        try:
            base = datetime.strptime(r[0], "%Y-%m-%dT%H:%M")
        except:
            continue

        for i in range(-3, 4):
            key = (base + timedelta(minutes=15*i)).strftime("%Y-%m-%dT%H:%M")
            zajete[key] = True

    return dni, godziny, zajete

# ================= HOME =================

@app.route("/")
def index():
    dane = session.get("form_data", {
        "firma": "",
        "rejestracja": "",
        "kierowca": "",
        "email": "",
        "telefon": "",
        "waga_ladunku": "",
        "komentarz": ""
    })

    dni, godziny, zajete = get_days_and_slots()

    return render_template(
        "form.html",
        dane=dane,
        dni=dni,
        godziny=godziny,
        zajete=zajete
    )

# ================= SUCCESS =================

@app.route("/success")
def success():
    return render_template("success.html")

# ================= ZAPIS =================

@app.route("/zapisz", methods=["POST"])
def zapisz():
    f = request.form

    # ZACHOWAJ DANE JEŚLI BŁĄD
    session["form_data"] = dict(f)

    try:
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

        session.pop("form_data", None)

        return redirect("/success")

    except:
        return redirect("/")

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

    dni, godziny, zajete = get_days_and_slots()

    return render_template(
        "admin.html",
        awizacje=awizacje,
        dni=dni,
        godziny=godziny,
        zajete=zajete
    )

# ================= LOGI / HISTORIA =================

@app.route("/admin/logi")
def logi():
    return render_template("logi.html")

@app.route("/admin/historia")
def historia():
    return render_template("historia.html")

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

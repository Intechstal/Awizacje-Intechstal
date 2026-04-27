from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

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

# ================= USERS =================

def create_users():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    users = [
        ("admin1", "1234"),
        ("admin2", "1234"),
        ("admin3", "1234"),
        ("admin4", "1234"),
        ("admin5", "1234"),
    ]

    for u, p in users:
        try:
            c.execute("INSERT INTO users (login, haslo) VALUES (?,?)", (u, p))
        except:
            pass

    conn.commit()
    conn.close()

create_users()

# ================= LOGS =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
        (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

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

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""SELECT firma,status,data_godzina,typ_ladunku,waga_ladunku,komentarz 
                 FROM awizacje WHERE status!='odrzucona'""")

    for f, s, dt, typ, waga, kom in c.fetchall():
        base = datetime.strptime(dt, "%Y-%m-%dT%H:%M")

        for i in range(-3, 4):
            key = (base + timedelta(minutes=15*i)).strftime("%Y-%m-%dT%H:%M")

            zajete[key] = {
                "firma": f,
                "status": s,
                "typ_ladunku": typ,
                "waga": waga,
                "komentarz": kom,
                "main": (i == 0),
                "future_block": (i > 0),
                "past_block": (i < 0)
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
                           error=None)

@app.route("/zapisz", methods=["POST"])
def zapisz():
    dane = request.form.to_dict()

    # ================= WALIDACJA =================

    if not dane["telefon"].isdigit():
        dni, godziny, zajete = get_days_and_slots()
        return render_template("form.html",
                               dni=dni,
                               godziny=godziny,
                               zajete=zajete,
                               dane=dane,
                               error="Telefon tylko cyfry")

    if "@" not in dane["email"]:
        dni, godziny, zajete = get_days_and_slots()
        return render_template("form.html",
                               dni=dni,
                               godziny=godziny,
                               zajete=zajete,
                               dane=dane,
                               error="Błędny email")

    # ================= 🔥 FIX PRZESZŁOŚCI =================

    slot = datetime.strptime(dane["data_godzina"], "%Y-%m-%dT%H:%M")
    now = datetime.now()

    if slot <= now:
        dni, godziny, zajete = get_days_and_slots()
        return render_template(
            "form.html",
            dni=dni,
            godziny=godziny,
            zajete=zajete,
            dane=dane,
            error="Nie można awizować dat z przeszłości"
        )

    # ================= INSERT =================

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""INSERT INTO awizacje
        (firma,rejestracja,kierowca,email,telefon,data_godzina,
         typ_ladunku,waga_ladunku,komentarz)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (dane["firma"],dane["rejestracja"],dane["kierowca"],
         dane["email"],dane["telefon"],dane["data_godzina"],
         dane["typ_ladunku"],dane["waga_ladunku"],dane.get("komentarz",""))
    )

    conn.commit()
    conn.close()

    return render_template("success.html")

# ================= ADMIN =================

@app.route("/admin")
def admin():
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
                           zajete=zajete)

# ================= STATUS =================

@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):
    status = request.form["status"]

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

    return redirect("/admin")

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

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
    for start, end in [("07:30","09:30"),("11:00","13:15"),("14:15","20:00")]:
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        while s < e:
            godziny.append(s.strftime("%H:%M"))
            s += timedelta(minutes=15)

    zajete = {}
    return dni, godziny, zajete

# ================= FORM =================

@app.route("/")
def index():
    dni, godziny, zajete = get_days_and_slots()
    return render_template("form.html", dni=dni, godziny=godziny, zajete=zajete, dane={}, error=None)

@app.route("/zapisz", methods=["POST"])
def zapisz():
    dane = request.form.to_dict()

    # ================= RODO CHECK =================
    if "rodo" not in request.form:
        dni, godziny, zajete = get_days_and_slots()
        return render_template(
            "form.html",
            dni=dni,
            godziny=godziny,
            zajete=zajete,
            dane=dane,
            error="Musisz zaakceptować RODO"
        )

    # ================= VALIDACJE =================
    if not dane["telefon"].isdigit():
        dni, godziny, zajete = get_days_and_slots()
        return render_template("form.html", dni=dni, godziny=godziny, zajete=zajete, dane=dane, error="Telefon tylko cyfry")

    if "@" not in dane["email"]:
        dni, godziny, zajete = get_days_and_slots()
        return render_template("form.html", dni=dni, godziny=godziny, zajete=zajete, dane=dane, error="Błędny email")

    slot = datetime.strptime(dane["data_godzina"], "%Y-%m-%dT%H:%M")

    if slot <= datetime.now():
        dni, godziny, zajete = get_days_and_slots()
        return render_template("form.html", dni=dni, godziny=godziny, zajete=zajete, dane=dane, error="Nie można awizować dat z przeszłości")

    # ================= INSERT =================
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""INSERT INTO awizacje
        (firma,rejestracja,kierowca,email,telefon,data_godzina,typ_ladunku,waga_ladunku,komentarz)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (dane["firma"], dane["rejestracja"], dane["kierowca"],
         dane["email"], dane["telefon"], dane["data_godzina"],
         dane["typ_ladunku"], dane["waga_ladunku"], dane.get("komentarz",""))
    )

    conn.commit()
    conn.close()

    return render_template("success.html")

# ================= RUN =================

aplication = app

if __name__ == "__main__":
    app.run()

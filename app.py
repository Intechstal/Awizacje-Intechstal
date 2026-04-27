from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ---------------- DB ----------------

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

# ---------------- AUTH ----------------

def is_logged():
    return session.get("logged_in")

# ---------------- SLOTY ----------------

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
    c.execute("SELECT firma,status,data_godzina,typ_ladunku,waga_ladunku,komentarz FROM awizacje WHERE status!='odrzucona'")

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

# ---------------- FORM (HOME) ----------------

@app.route("/")
def index():
    dni, godziny, zajete = get_days_and_slots()
    return render_template("form.html",
                           dni=dni,
                           godziny=godziny,
                           zajete=zajete,
                           dane={},
                           error=None)

# ---------------- ZAPIS ----------------

@app.route("/zapisz", methods=["POST"])
def zapisz():
    dane = request.form.to_dict()

    try:
        dt = datetime.strptime(dane["data_godzina"], "%Y-%m-%dT%H:%M")
    except:
        return redirect("/")

    if dt < datetime.now():
        dni, godziny, zajete = get_days_and_slots()
        return render_template("form.html",
                               dni=dni,
                               godziny=godziny,
                               zajete=zajete,
                               dane=dane,
                               error="Nie można wybrać przeszłości")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("SELECT data_godzina FROM awizacje WHERE status!='odrzucona'")
    rows = c.fetchall()

    zajete_set = set()

    for (d,) in rows:
        base = datetime.strptime(d, "%Y-%m-%dT%H:%M")
        for i in range(-3, 4):
            zajete_set.add((base + timedelta(minutes=15*i)).strftime("%Y-%m-%dT%H:%M"))

    if dane["data_godzina"] in zajete_set:
        dni, godziny, zajete = get_days_and_slots()
        return render_template("form.html",
                               dni=dni,
                               godziny=godziny,
                               zajete=zajete,
                               dane=dane,
                               error="Termin zajęty")

    c.execute('''INSERT INTO awizacje
        (firma,rejestracja,kierowca,email,telefon,data_godzina,typ_ladunku,waga_ladunku,komentarz)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (dane["firma"], dane["rejestracja"], dane["kierowca"],
         dane["email"], dane["telefon"], dane["data_godzina"],
         dane["typ_ladunku"], dane["waga_ladunku"], dane.get("komentarz",""))
    )

    conn.commit()
    conn.close()

    return render_template("success.html")

# ---------------- ADMIN ----------------

@app.route("/admin")
def admin():
    if not is_logged():
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
                           zajete=zajete)

# ---------------- STATUS ----------------

@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):
    if not is_logged():
        return redirect("/login")

    status = request.form["status"]

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

    return redirect("/admin")

# ---------------- EDIT ----------------

@app.route("/admin/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    if not is_logged():
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    a = c.fetchone()

    if request.method == "POST":
        f = request.form

        c.execute('''UPDATE awizacje SET
            firma=?, rejestracja=?, kierowca=?, email=?, telefon=?,
            data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?
            WHERE id=?''',
            (f["firma"], f["rejestracja"], f["kierowca"],
             f["email"], f["telefon"], f["data_godzina"],
             f["typ_ladunku"], f["waga_ladunku"], f["komentarz"], id)
        )

        conn.commit()
        conn.close()
        return redirect("/admin")

    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    return render_template("edit.html",
                           awizacja=a,
                           dni=dni,
                           godziny=godziny,
                           zajete=zajete)

# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)

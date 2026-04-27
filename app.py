from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersekretnyklucz123"  # zmień na coś swojego

# --- dane logowania ---
ADMIN_LOGIN = "admin"
ADMIN_HASLO = "1234"  # zmień!

# --- sprawdzanie logowania ---
def is_logged():
    return session.get("logged_in")

# --- baza ---
def init_db():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS awizacje (
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
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- dni i sloty ---
def get_days_and_slots():
    today = datetime.now().replace(hour=0, minute=0)
    dni = []
    d = today

    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    godziny = []
    for start, end in [("07:30", "09:30"), ("11:00", "13:15"), ("14:15", "20:00")]:
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        while s < e:
            godziny.append(s.strftime('%H:%M'))
            s += timedelta(minutes=15)

    zajete = {}
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina, firma, status FROM awizacje WHERE status != 'odrzucona'")
    rows = c.fetchall()
    conn.close()

    for data_godzina, firma, status in rows:
        dt = datetime.strptime(data_godzina, '%Y-%m-%dT%H:%M')
        for i in range(-3, 4):
            blok = dt + timedelta(minutes=15*i)
            zajete[blok.strftime('%Y-%m-%dT%H:%M')] = {"firma": firma, "status": status}

    return dni, godziny, zajete

# ------------------- LOGIN -------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        login = request.form['login']
        haslo = request.form['haslo']

        if login == ADMIN_LOGIN and haslo == ADMIN_HASLO:
            session['logged_in'] = True
            return redirect('/admin')
        else:
            error = "Nieprawidłowe dane"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ------------------- FORM -------------------

@app.route('/')
def index():
    dni, godziny, zajete = get_days_and_slots()
    return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane={}, error=None)

@app.route('/zapisz', methods=['POST'])
def zapisz():
    dane = request.form.to_dict()
    data_godzina = dane.get("data_godzina")

    dt = datetime.strptime(data_godzina, "%Y-%m-%dT%H:%M")

    if dt < datetime.now():
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=dane,
                               error="Nie można w przeszłość")

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina FROM awizacje WHERE status != 'odrzucona'")
    rows = c.fetchall()
    conn.close()

    zajete_set = set()
    for (d,) in rows:
        base = datetime.strptime(d, '%Y-%m-%dT%H:%M')
        for i in range(-3, 4):
            zajete_set.add((base + timedelta(minutes=15*i)).strftime('%Y-%m-%dT%H:%M'))

    if data_godzina in zajete_set:
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=dane,
                               error="Termin zajęty")

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon, data_godzina,
        typ_ladunku, waga_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        dane['firma'], dane['rejestracja'], dane['kierowca'],
        dane['email'], dane['telefon'], data_godzina,
        dane['typ_ladunku'], dane['waga_ladunku'], dane.get('komentarz','')
    ))
    conn.commit()
    conn.close()

    return render_template('success.html')

# ------------------- ADMIN -------------------

@app.route('/admin')
def admin():
    if not is_logged():
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status != 'odrzucona'")
    awizacje = c.fetchall()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()

    return render_template("admin.html", awizacje=awizacje, dni=dni, godziny=godziny, zajete=zajete)

@app.route('/admin/update_status/<int:id>', methods=['POST'])
def update_status(id):
    if not is_logged():
        return redirect('/login')

    status = request.form['status']
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/edit/<int:id>', methods=['GET','POST'])
def edit_awizacja(id):
    if not is_logged():
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()

    if request.method == 'POST':
        dane = request.form.to_dict()
        c.execute('''
            UPDATE awizacje SET firma=?, rejestracja=?, kierowca=?, email=?, telefon=?,
            data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?
            WHERE id=?
        ''', (
            dane['firma'], dane['rejestracja'], dane['kierowca'],
            dane['email'], dane['telefon'], dane['data_godzina'],
            dane['typ_ladunku'], dane['waga_ladunku'], dane.get('komentarz',''), id
        ))
        conn.commit()
        conn.close()
        return redirect('/admin')

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    awizacja = c.fetchone()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    return render_template("edit.html", awizacja=awizacja, dni=dni, godziny=godziny, zajete=zajete)

@app.route('/admin/historia')
def historia():
    if not is_logged():
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status='odrzucona'")
    dane = c.fetchall()
    conn.close()

    return render_template("historia.html", awizacje=dane)

if __name__ == '__main__':
    app.run(debug=True)

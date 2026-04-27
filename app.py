from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ------------------ DB ------------------

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

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE,
            haslo TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS logi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            akcja TEXT,
            data TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# ------------------ USERS ------------------

def create_users():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()

    users = [
        ("admin1", "1234"),
        ("admin2", "1234"),
        ("admin3", "1234"),
        ("admin4", "1234")
    ]

    for u in users:
        try:
            c.execute("INSERT INTO users (login, haslo) VALUES (?, ?)", u)
        except:
            pass

    conn.commit()
    conn.close()

create_users()

# ------------------ LOGI ------------------

def log_action(user, akcja):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("INSERT INTO logi (user, akcja, data) VALUES (?, ?, ?)",
              (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# ------------------ LOGIN ------------------

def is_logged():
    return session.get("logged_in")

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        login = request.form['login']
        haslo = request.form['haslo']

        conn = sqlite3.connect('awizacje.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND haslo=?", (login, haslo))
        user = c.fetchone()
        conn.close()

        if user:
            session['logged_in'] = True
            session['user'] = login
            log_action(login, "Zalogował się")
            return redirect('/admin')
        else:
            error = "Błędne dane"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    if session.get('user'):
        log_action(session['user'], "Wylogował się")
    session.clear()
    return redirect('/login')

# ------------------ SLOTY ------------------

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
    c.execute("SELECT data_godzina, firma, status FROM awizacje WHERE status!='odrzucona'")
    for d, f, s in c.fetchall():
        dt = datetime.strptime(d, '%Y-%m-%dT%H:%M')
        for i in range(-3,4):
            zajete[(dt + timedelta(minutes=15*i)).strftime('%Y-%m-%dT%H:%M')] = {
                "firma": f,
                "status": s
            }
    conn.close()

    return dni, godziny, zajete

# ------------------ FORM ------------------

@app.route('/')
def index():
    dni, godziny, zajete = get_days_and_slots()
    return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane={}, error=None)

@app.route('/zapisz', methods=['POST'])
def zapisz():
    dane = request.form.to_dict()

    dt = datetime.strptime(dane['data_godzina'], "%Y-%m-%dT%H:%M")

    if dt < datetime.now():
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete,
                               dane=dane, error="Nie można w przeszłość")

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina FROM awizacje WHERE status!='odrzucona'")
    rows = c.fetchall()
    conn.close()

    zajete_set = set()
    for (d,) in rows:
        base = datetime.strptime(d, '%Y-%m-%dT%H:%M')
        for i in range(-3,4):
            zajete_set.add((base + timedelta(minutes=15*i)).strftime('%Y-%m-%dT%H:%M'))

    if dane['data_godzina'] in zajete_set:
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete,
                               dane=dane, error="Termin zajęty")

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon, data_godzina,
        typ_ladunku, waga_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        dane['firma'], dane['rejestracja'], dane['kierowca'],
        dane['email'], dane['telefon'], dane['data_godzina'],
        dane['typ_ladunku'], dane['waga_ladunku'], dane.get('komentarz','')
    ))
    conn.commit()
    conn.close()

    return render_template('success.html')

# ------------------ ADMIN ------------------

@app.route('/admin')
def admin():
    if not is_logged():
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status!='odrzucona'")
    dane = c.fetchall()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    return render_template("admin.html", awizacje=dane, dni=dni, godziny=godziny, zajete=zajete)

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

    log_action(session['user'], f"Zmiana statusu ID {id} → {status}")

    return redirect('/admin')

@app.route('/admin/edit/<int:id>', methods=['GET','POST'])
def edit(id):
    if not is_logged():
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    old = c.fetchone()

    if request.method == 'POST':
        new = request.form.to_dict()

        fields = ["firma","rejestracja","kierowca","email","telefon","data_godzina","typ_ladunku","waga_ladunku","komentarz"]
        changes = []

        for i, field in enumerate(fields, start=1):
            if str(old[i]) != new[field]:
                changes.append(f"{field}: {old[i]} → {new[field]}")

        if changes:
            log_action(session['user'], f"Edycja ID {id}: " + " | ".join(changes))

        c.execute('''
            UPDATE awizacje SET firma=?, rejestracja=?, kierowca=?, email=?, telefon=?,
            data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?
            WHERE id=?
        ''', (
            new['firma'], new['rejestracja'], new['kierowca'],
            new['email'], new['telefon'], new['data_godzina'],
            new['typ_ladunku'], new['waga_ladunku'], new['komentarz'], id
        ))

        conn.commit()
        conn.close()
        return redirect('/admin')

    conn.close()
    dni, godziny, zajete = get_days_and_slots()
    return render_template("edit.html", awizacja=old, dni=dni, godziny=godziny, zajete=zajete)

@app.route('/admin/historia')
def historia():
    if not is_logged():
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY data_godzina DESC")
    dane = c.fetchall()
    conn.close()

    return render_template("historia.html", awizacje=dane)

@app.route('/admin/logi')
def logi():
    if not is_logged():
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM logi ORDER BY id DESC")
    dane = c.fetchall()
    conn.close()

    return render_template("logi.html", logi=dane)

if __name__ == '__main__':
    app.run(debug=True)

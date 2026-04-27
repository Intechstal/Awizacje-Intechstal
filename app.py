from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# =======================
# UPLOAD FOLDER
# =======================
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
            zdjecie TEXT,
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
    c.execute(
        "INSERT INTO logi (user, akcja, data) VALUES (?, ?, ?)",
        (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

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
        for i in range(-3, 4):
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

    # ------------------ UPLOAD JPG ------------------
    file = request.files.get("zdjecie")
    filename = None

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    # ------------------ INSERT ------------------
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()

    c.execute('''
        INSERT INTO awizacje (
            firma, rejestracja, kierowca, email, telefon,
            data_godzina, typ_ladunku, waga_ladunku, komentarz, zdjecie
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        dane['firma'], dane['rejestracja'], dane['kierowca'],
        dane['email'], dane['telefon'], dane['data_godzina'],
        dane['typ_ladunku'], dane['waga_ladunku'],
        dane.get('komentarz', ''),
        filename
    ))

    conn.commit()
    conn.close()

    return render_template('success.html')

# ------------------ ADMIN ------------------

@app.route('/admin')
def admin():
    if not session.get("logged_in"):
        return redirect('/login')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status!='odrzucona'")
    dane = c.fetchall()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    return render_template("admin.html", awizacje=dane, dni=dni, godziny=godziny, zajete=zajete)

# ------------------ STATUS ------------------

@app.route('/admin/update_status/<int:id>', methods=['POST'])
def update_status(id):
    if not session.get("logged_in"):
        return redirect('/login')

    status = request.form['status']

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

    return redirect('/admin')

# ------------------ LOGIN ------------------

@app.route('/login', methods=['GET', 'POST'])
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
            return redirect('/admin')
        else:
            error = "Błędne dane"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ------------------ 🔥 TO JEST NAJWAŻNIEJSZE ------------------
# 📷 SERWOWANIE ZDJĘĆ (TO MUSI BYĆ TU NA DOLE)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ------------------ RUN ------------------

if __name__ == '__main__':
    app.run(debug=True)

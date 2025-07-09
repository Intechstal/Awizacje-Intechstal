from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("twojehaslo")  # Zmień na swoje
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

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

@app.route('/')
def index():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina, status FROM awizacje")
    rekordy = c.fetchall()
    conn.close()

    zajete = set()
    for data, status in rekordy:
        if status != "odrzucona":
            dt = datetime.strptime(data, '%Y-%m-%dT%H:%M')
            for i in range(4):
                zajete.add((dt + timedelta(minutes=15 * i)).strftime('%Y-%m-%dT%H:%M'))

    today = datetime.now().replace(hour=0, minute=0)
    dni = []
    d = today
    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    sloty_dostepne = []
    for dzien in dni:
        for start, end in [("07:30", "09:30"), ("11:00", "13:15"), ("14:30", "20:00")]:
            start_dt = datetime.combine(dzien.date(), datetime.strptime(start, "%H:%M").time())
            end_dt = datetime.combine(dzien.date(), datetime.strptime(end, "%H:%M").time())
            while start_dt < end_dt:
                blok = [(start_dt + timedelta(minutes=15 * i)).strftime('%Y-%m-%dT%H:%M') for i in range(4)]
                if all(b not in zajete for b in blok):
                    sloty_dostepne.append(start_dt.strftime('%Y-%m-%dT%H:%M'))
                start_dt += timedelta(minutes=15)

    return render_template('form.html', sloty=sloty_dostepne)

@app.route('/zapisz', methods=['POST'])
def zapisz():
    firma = request.form['firma']
    rejestracja = request.form['rejestracja']
    kierowca = request.form['kierowca']
    email = request.form['email']
    telefon = request.form['telefon']
    data_godzina = request.form['data_godzina']
    typ_ladunku = request.form['typ_ladunku']
    waga_ladunku = request.form['waga_ladunku']
    komentarz = request.form.get('komentarz', '')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina FROM awizacje WHERE status != 'odrzucona'")
    zajete = [r[0] for r in c.fetchall()]
    start_dt = datetime.strptime(data_godzina, '%Y-%m-%dT%H:%M')
    blok = [(start_dt + timedelta(minutes=15 * i)).strftime('%Y-%m-%dT%H:%M') for i in range(4)]

    if any(slot in zajete for slot in blok):
        conn.close()
        return render_template('error.html', komunikat="Ten termin jest już zajęty. Wybierz inny.", dane=request.form)

    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon, data_godzina,
                              typ_ladunku, waga_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (firma, rejestracja, kierowca, email, telefon, data_godzina,
          typ_ladunku, waga_ladunku, komentarz))
    conn.commit()
    conn.close()

    return render_template('success.html')

@app.route('/admin')
@auth.login_required
def admin():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY data_godzina ASC")
    awizacje = c.fetchall()
    conn.close()

    today = datetime.now().replace(hour=0, minute=0)
    dni = []
    d = today
    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    sloty = []
    for start, end in [("07:30", "09:30"), ("11:00", "13:15"), ("14:30", "20:00")]:
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        while s < e:
            sloty.append(s.strftime('%H:%M'))
            s += timedelta(minutes=15)

    zajete = {}
    for a in awizacje:
        dt = datetime.strptime(a[6], '%Y-%m-%dT%H:%M')
        firma = a[1]
        status = a[10]

        if status != "odrzucona":
            for i in range(4):
                blok = dt + timedelta(minutes=15 * i)
                slot = blok.strftime('%Y-%m-%dT%H:%M')
                zajete[slot] = {"firma": firma, "status": status}

    return render_template("admin.html", awizacje=awizacje, dni=dni, godziny=sloty, zajete=zajete)

@app.route('/admin/update_status/<int:id>', methods=['POST'])
@auth.login_required
def update_status(id):
    status = request.form['status']
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()

    if status == "odrzucona":
        c.execute("DELETE FROM awizacje WHERE id=?", (id,))
    else:
        c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))

    conn.commit()
    conn.close()
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("twojehaslo")
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
    return render_template('form.html')

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
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon, data_godzina, typ_ladunku, waga_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (firma, rejestracja, kierowca, email, telefon, data_godzina, typ_ladunku, waga_ladunku, komentarz))
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

    today = datetime.now()
    dni = []
    d = today
    while len(dni) < 6:
        if d.weekday() < 5:  # tylko dni robocze
            dni.append(d)
        d += timedelta(days=1)

    sloty = []
    przedzialy = [
        ("07:30", "09:30"),
        ("11:00", "13:15"),
        ("14:15", "20:00"),
    ]
    for start, end in przedzialy:
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        while s < e:
            sloty.append(s)
            s += timedelta(minutes=15)

    zajete = {}
    for a in awizacje:
        start_dt = datetime.strptime(a[6], "%Y-%m-%dT%H:%M")
        firma = a[1]
        status = a[10]

        if status in ("zaakceptowana", "oczekująca"):
            for i in range(4):  # blok 1h (4 sloty po 15min)
                blok = start_dt + timedelta(minutes=15*i)
                slot = blok.strftime('%Y-%m-%dT%H:%M')
                zajete[slot] = {"firma": firma, "status": status}

    return render_template("admin.html", awizacje=awizacje, dni=dni, godziny=sloty, zajete=zajete)

@app.route('/admin/accept/<int:id>')
@auth.login_required
def accept_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status='zaakceptowana' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/reject/<int:id>')
@auth.login_required
def reject_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("DELETE FROM awizacje WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/edit/<int:id>', methods=['POST'])
@auth.login_required
def edit_awizacja(id):
    firma = request.form['firma']
    rejestracja = request.form['rejestracja']
    kierowca = request.form['kierowca']
    email = request.form['email']
    telefon = request.form['telefon']
    data_godzina = request.form['data_godzina']
    typ_ladunku = request.form['typ_ladunku']
    waga_ladunku = request.form['waga_ladunku']
    komentarz = request.form.get('komentarz', '')
    status = request.form.get('status', 'oczekująca')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        UPDATE awizacje SET firma=?, rejestracja=?, kierowca=?, email=?, telefon=?, data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?, status=?
        WHERE id=?
    ''', (firma, rejestracja, kierowca, email, telefon, data_godzina, typ_ladunku, waga_ladunku, komentarz, status, id))
    conn.commit()
    conn.close()

    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("twojehaslo")  # Zmień hasło
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

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina FROM awizacje WHERE status != 'odrzucona'")
    records = c.fetchall()
    conn.close()

    zajete = {}
    for r in records:
        dt = datetime.strptime(r[0], "%Y-%m-%dT%H:%M")
        for i in range(4):
            blok = dt + timedelta(minutes=15 * i)
            zajete[blok.strftime('%Y-%m-%dT%H:%M')] = True

    return dni, godziny, zajete

@app.route('/')
def index():
    dni, godziny, zajete = get_days_and_slots()
    return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=None, error=None)

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
    existing = c.fetchall()
    conn.close()

    blokowane = set()
    for r in existing:
        dt = datetime.strptime(r[0], "%Y-%m-%dT%H:%M")
        for i in range(4):
            blok = dt + timedelta(minutes=15 * i)
            blokowane.add(blok.strftime('%Y-%m-%dT%H:%M'))

    if data_godzina in blokowane:
        dni, godziny, zajete = get_days_and_slots()
        dane = {
            'firma': firma,
            'rejestracja': rejestracja,
            'kierowca': kierowca,
            'email': email,
            'telefon': telefon,
            'typ_ladunku': typ_ladunku,
            'waga_ladunku': waga_ladunku,
            'komentarz': komentarz,
            'data_godzina': data_godzina
        }
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=dane,
                               error="Wybrany termin jest już zajęty. Wybierz inny.")

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
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
    c.execute("SELECT * FROM awizacje WHERE status != 'odrzucona' ORDER BY data_godzina ASC")
    awizacje = c.fetchall()
    conn.close()

    dni, godziny, _ = get_days_and_slots()

    zajete = {}
    for a in awizacje:
        dt = datetime.strptime(a[6], '%Y-%m-%dT%H:%M')
        firma = a[1]
        status = a[10]
        for i in range(4):
            blok = dt + timedelta(minutes=15 * i)
            zajete[blok.strftime('%Y-%m-%dT%H:%M')] = {"firma": firma, "status": status}

    return render_template("admin.html", awizacje=awizacje, dni=dni, godziny=godziny, zajete=zajete)

@app.route('/admin/update_status/<int:id>', methods=['POST'])
@auth.login_required
def update_status(id):
    status = request.form['status']
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    if status == "odrzucona":
        c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    else:
        c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@auth.login_required
def edit_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()

    if request.method == 'POST':
        firma = request.form['firma']
        rejestracja = request.form['rejestracja']
        kierowca = request.form['kierowca']
        email = request.form['email']
        telefon = request.form['telefon']
        data_godzina = request.form['data_godzina']
        typ_ladunku = request.form['typ_ladunku']
        waga_ladunku = request.form['waga_ladunku']
        komentarz = request.form['komentarz']

        c.execute('''
            UPDATE awizacje SET
                firma=?, rejestracja=?, kierowca=?, email=?, telefon=?,
                data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?
            WHERE id=?
        ''', (firma, rejestracja, kierowca, email, telefon, data_godzina,
              typ_ladunku, waga_ladunku, komentarz, id))
        conn.commit()
        conn.close()
        return redirect('/admin')

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    awizacja = c.fetchone()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    return render_template('edit.html', awizacja=awizacja, dni=dni, godziny=godziny, zajete=zajete)

@app.route('/admin/historia')
@auth.login_required
def historia():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status = 'odrzucona' ORDER BY data_godzina DESC")
    awizacje = c.fetchall()
    conn.close()
    return render_template("historia.html", awizacje=awizacje)

if __name__ == '__main__':
    app.run(debug=True)

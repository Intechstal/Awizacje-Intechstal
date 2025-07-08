efrom flask import Flask, render_template, request, redirect
import sqlite3
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import locale

# Ustawienia języka na polski dla dni tygodnia
try:
    locale.setlocale(locale.LC_TIME, 'pl_PL.UTF-8')
except:
    pass  # Render może nie obsługiwać

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("twojehaslo")  # ← Zmień hasło
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
            telefon_do_kierowcy TEXT,
            data_godzina TEXT,
            typ_ladunku TEXT,
            waga_ładunku TEXT,
            komentarz TEXT,
            status TEXT DEFAULT 'oczekująca'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    dane = {
        'firma': request.args.get('firma', ''),
        'rejestracja': request.args.get('rejestracja', ''),
        'kierowca': request.args.get('kierowca', ''),
        'email': request.args.get('email', ''),
        'telefon_kierowcy': request.args.get('telefon_kierowcy', ''),
        'data_godzina': request.args.get('data_godzina', ''),
        'typ_ladunku': request.args.get('typ_ladunku', ''),
        'waga_ladunku': request.args.get('waga_ladunku', ''),
        'komentarz': request.args.get('komentarz', '')
    }
    return render_template('form.html', dane=dane)

@app.route('/zapisz', methods=['POST'])
def zapisz():
    firma = request.form['firma']
    rejestracja = request.form['rejestracja']
    kierowca = request.form['kierowca']
    email = request.form['email']
    telefon = request.form['telefon_kierowcy']
    data_godzina = request.form['data_godzina']
    typ = request.form['typ_ladunku']
    waga = request.form['waga_ladunku']
    komentarz = request.form.get('komentarz', '')

    dane = {
        'firma': firma,
        'rejestracja': rejestracja,
        'kierowca': kierowca,
        'email': email,
        'telefon_kierowcy': telefon,
        'data_godzina': data_godzina,
        'typ_ladunku': typ,
        'waga_ladunku': waga,
        'komentarz': komentarz
    }

    try:
        dt = datetime.strptime(data_godzina, '%Y-%m-%dT%H:%M')
        if dt.weekday() >= 5:
            return render_template("error.html", message="Awizacje tylko pon–pt.", dane=dane)

        start_min = dt.hour * 60 + dt.minute
        end_min = start_min + 60
        przedzialy = [
            (450, 630),   # 07:30–10:30
            (660, 825),   # 11:00–13:45
            (855, 1200)   # 14:15–20:00
        ]
        if not any(start_min >= p1 and end_min <= p2 for (p1, p2) in przedzialy):
            return render_template("error.html", message="Dozwolone 1-godzinne bloki: 07:30–10:30, 11:00–13:45, 14:15–20:00", dane=dane)

        conn = sqlite3.connect('awizacje.db')
        c = conn.cursor()
        c.execute('SELECT data_godzina FROM awizacje')
        kolizje = c.fetchall()
        conn.close()

        for [czas] in kolizje:
            istnieje = datetime.strptime(czas, '%Y-%m-%dT%H:%M')
            różnica = abs((dt - istnieje).total_seconds()) / 60
            if różnica < 60:
                return render_template("error.html", message=f"Kolizja z awizacją o {istnieje.strftime('%H:%M')}. Zachowaj odstęp 1h.", dane=dane)

    except Exception as e:
        return render_template("error.html", message=f"Błąd: {e}", dane=dane)

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon_do_kierowcy,
                              data_godzina, typ_ladunku, waga_ładunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (firma, rejestracja, kierowca, email, telefon, data_godzina, typ, waga, komentarz))
    conn.commit()
    conn.close()

    return render_template('success.html')

@app.route('/admin')
@auth.login_required
def admin():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('SELECT * FROM awizacje ORDER BY data_godzina ASC')
    dane = c.fetchall()
    conn.close()

    zajete = { row[6]: row[1] for row in dane }  # data_godzina : firma

    dni = []
    dzien = datetime.now().replace(hour=0, minute=0)
    while len(dni) < 6:
        if dzien.weekday() < 5:
            dni.append(dzien)
        dzien += timedelta(days=1)

    godziny = [datetime.strptime(f'{h}:{m:02d}', '%H:%M')
               for h in range(7, 20)
               for m in (30,)]

    return render_template('admin.html', awizacje=dane, dni=dni, godziny=godziny, zajete=zajete)

@app.route('/admin/accept/<int:id>')
@auth.login_required
def accept_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status = 'zaakceptowana' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/reject/<int:id>')
@auth.login_required
def reject_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status = 'odrzucona' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@auth.login_required
def edit_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    if request.method == 'POST':
        dane = (
            request.form['firma'],
            request.form['rejestracja'],
            request.form['kierowca'],
            request.form['email'],
            request.form['telefon_kierowcy'],
            request.form['data_godzina'],
            request.form['typ_ladunku'],
            request.form['waga_ladunku'],
            request.form['komentarz'],
            request.form['status'],
            id
        )
        c.execute('''
            UPDATE awizacje SET
                firma=?, rejestracja=?, kierowca=?, email=?, telefon_do_kierowcy=?,
                data_godzina=?, typ_ladunku=?, waga_ładunku=?, komentarz=?, status=?
            WHERE id=?
        ''', dane)
        conn.commit()
        conn.close()
        return redirect('/admin')
    else:
        c.execute('SELECT * FROM awizacje WHERE id = ?', (id,))
        awizacja = c.fetchone()
        conn.close()
        return render_template('edit.html', awizacja=awizacja)

if __name__ == '__main__':
    app.run(debug=True)

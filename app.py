from flask import Flask, render_template, request, redirect
import sqlite3
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, time
import locale

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("twojehaslo")  # ← zmień hasło!
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

# Inicjalizacja bazy danych
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
            telefon_kierowcy TEXT,
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
    # Jeśli są dane z przekierowania (np. po błędzie), pobierz je
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
    telefon_kierowcy = request.form['telefon_kierowcy']
    data_godzina = request.form['data_godzina']
    typ_ladunku = request.form['typ_ladunku']
    waga_ladunku = request.form['waga_ladunku']
    komentarz = request.form.get('komentarz', '')

    # Sprawdzenie kolizji: blokujemy 1h = 4 sloty
    start_dt = datetime.strptime(data_godzina, "%Y-%m-%dT%H:%M")
    blokowane = [(start_dt + timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(4)]

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina FROM awizacje")
    zajete = [row[0] for row in c.fetchall()]
    conn.close()

    for blok in blokowane:
        if blok in zajete:
            # Przekieruj z powrotem z informacją o błędzie
            params = {
                "firma": firma,
                "rejestracja": rejestracja,
                "kierowca": kierowca,
                "email": email,
                "telefon_kierowcy": telefon_kierowcy,
                "data_godzina": data_godzina,
                "typ_ladunku": typ_ladunku,
                "waga_ladunku": waga_ladunku,
                "komentarz": komentarz
            }
            return render_template("error.html", message="Termin jest już zajęty!", dane=params)

    # Zapisz do bazy
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon_kierowcy, data_godzina, typ_ladunku, waga_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (firma, rejestracja, kierowca, email, telefon_kierowcy, data_godzina, typ_ladunku, waga_ladunku, komentarz))
    conn.commit()
    conn.close()

    return render_template('success.html')

@app.route('/admin')
@auth.login_required
def admin():
    locale.setlocale(locale.LC_TIME, 'pl_PL.UTF-8')

    # Pobierz awizacje
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('SELECT * FROM awizacje ORDER BY data_godzina ASC')
    awizacje = c.fetchall()
    conn.close()

    # Tworzenie slotów co 15 min tylko w określonych godzinach
    def generuj_sloty(start, end):
        sloty = []
        obecna = datetime.combine(datetime.today(), start)
        koniec = datetime.combine(datetime.today(), end)
        while obecna <= koniec:
            sloty.append(obecna.time())
            obecna += timedelta(minutes=15)
        return sloty

    godziny = (
        generuj_sloty(time(7, 30), time(9, 30)) +
        generuj_sloty(time(11, 0), time(13, 15)) +
        generuj_sloty(time(14, 30), time(20, 0))
    )

    # Dni robocze: dziś + 5 kolejnych dni roboczych
    dni = []
    dzien = datetime.today()
    while len(dni) < 6:
        if dzien.weekday() < 5:
            dni.append(dzien)
        dzien += timedelta(days=1)

    # Blokowanie slotów z zajętością 1 godziny
    zajete = {}
    for a in awizacje:
        start_dt = datetime.strptime(a[6], "%Y-%m-%dT%H:%M")
        firma = a[1]
        for i in range(4):  # 4x15 min = 1h blokady
            blok = start_dt + timedelta(minutes=15*i)
            slot = blok.strftime('%Y-%m-%dT%H:%M')
            zajete[slot] = firma

    return render_template("admin.html", awizacje=awizacje, dni=dni, godziny=godziny, zajete=zajete)

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
    c.execute("UPDATE awizacje SET status='odrzucona' WHERE id=?", (id,))
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
            request.form.get('komentarz', ''),
            request.form.get('status', 'oczekująca'),
            id
        )
        c.execute('''
            UPDATE awizacje
            SET firma=?, rejestracja=?, kierowca=?, email=?, telefon_kierowcy=?, data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?, status=?
            WHERE id=?
        ''', dane)
        conn.commit()
        conn.close()
        return redirect('/admin')
    else:
        c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
        awizacja = c.fetchone()
        conn.close()
        return render_template('edit.html', awizacja=awizacja)

if __name__ == '__main__':
    app.run(debug=True)

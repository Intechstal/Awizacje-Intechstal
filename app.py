from flask import Flask, render_template, request, redirect
import sqlite3
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
auth = HTTPBasicAuth()

# Dane logowania
users = {
    "admin": generate_password_hash("twojehaslo")  # Zmień hasło!
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users[username], password):
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
    return render_template('form.html')

@app.route('/zapisz', methods=['POST'])
def zapisz():
    firma = request.form['firma']
    rejestracja = request.form['rejestracja']
    kierowca = request.form['kierowca']
    email = request.form['email_kierowcy']
    telefon = request.form['telefon_kierowcy']
    data_godzina = request.form['data_godzina']
    typ = request.form['typ_ladunku']
    waga = request.form['waga_ladunku']
    komentarz = request.form.get('komentarz', '')

    try:
        dt = datetime.strptime(data_godzina, '%Y-%m-%dT%H:%M')

        if dt.weekday() >= 5:
            return "Awizacje możliwe tylko w dni robocze (pon–pt)", 400

        start_min = dt.hour * 60 + dt.minute
        end_min = start_min + 60  # Blok 1h

        przedzialy = [
            (450, 630),   # 07:30–10:30
            (660, 825),   # 11:00–13:45
            (855, 1200)   # 14:15–20:00
        ]

        valid = False
        for p_start, p_end in przedzialy:
            if start_min >= p_start and end_min <= p_end:
                valid = True
                break
        if not valid:
            return "Blok 1h musi mieścić się w jednym z dozwolonych przedziałów.", 400

        # Sprawdź kolizje ±60 min
        conn = sqlite3.connect('awizacje.db')
        c = conn.cursor()
        c.execute('SELECT data_godzina FROM awizacje')
        kolizje = c.fetchall()
        conn.close()

        for [czas] in kolizje:
            istnieje = datetime.strptime(czas, '%Y-%m-%dT%H:%M')
            różnica = abs((dt - istnieje).total_seconds()) / 60
            if różnica < 60:
                return f"Kolizja z inną awizacją o {istnieje.strftime('%H:%M')}. Odstęp min. 1h.", 400

    except Exception as e:
        return f"Błąd daty: {e}", 400

    # Zapis do bazy
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
    return render_template('admin.html', awizacje=dane)

if __name__ == '__main__':
    app.run(debug=True)

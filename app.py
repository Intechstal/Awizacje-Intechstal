from flask import Flask, render_template, request, redirect
import sqlite3
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
auth = HTTPBasicAuth()

# Użytkownicy admina (prosty auth)
users = {
    "sk": generate_password_hash("123")  # Zmień hasło!
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

    # Walidacja godzin i dni roboczych
    try:
        dt = datetime.strptime(data_godzina, '%Y-%m-%dT%H:%M')
        if dt.weekday() >= 5:
            return "Awizacje możliwe tylko w dni robocze (pon–pt)", 400

        minuta = dt.hour * 60 + dt.minute
        przedzialy = [(450, 630), (660, 825), (855, 1200)]

        if not any(start <= minuta <= end for start, end in przedzialy):
            return "Godzina poza dozwolonymi przedziałami.", 400
    except Exception as e:
        return f"Błąd daty: {e}", 400

    # Zapis do bazy
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon_do_kierowcy, data_godzina, typ_ladunku, waga_ładunku, komentarz)
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

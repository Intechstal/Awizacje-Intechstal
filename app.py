from flask import Flask, render_template, request, redirect
import sqlite3
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("twojehaslo")  # ← Zmień hasło na swoje
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
            email_kierowcy TEXT,
            telefon_kierowcy TEXT,
            data_godzina TEXT,
            typ_ladunku TEXT,
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
    email_kierowcy = request.form['email_kierowcy']
    telefon_kierowcy = request.form['telefon_kierowcy']
    data_godzina = request.form['data_godzina']
    typ_ladunku = request.form['typ_ladunku']
    komentarz = request.form.get('komentarz', '')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email_kierowcy, telefon_kierowcy, data_godzina, typ_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (firma, rejestracja, kierowca, email_kierowcy, telefon_kierowcy, data_godzina, typ_ladunku, komentarz))
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

@app.route('/admin/edit/<int:id>', methods=['GET'])
@auth.login_required
def edit_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('SELECT * FROM awizacje WHERE id = ?', (id,))
    awizacja = c.fetchone()
    conn.close()
    if awizacja:
        return render_template('edit.html', awizacja=awizacja)
    else:
        return "Awizacja nie znaleziona", 404

@app.route('/admin/edit/<int:id>', methods=['POST'])
@auth.login_required
def update_awizacja(id):
    firma = request.form['firma']
    rejestracja = request.form['rejestracja']
    kierowca = request.form['kierowca']
    email_kierowcy = request.form['email_kierowcy']
    telefon_kierowcy = request.form['telefon_kierowcy']
    data_godzina = request.form['data_godzina']
    typ_ladunku = request.form['typ_ladunku']
    komentarz = request.form.get('komentarz', '')
    status = request.form.get('status', 'oczekująca')

    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        UPDATE awizacje
        SET firma = ?, rejestracja = ?, kierowca = ?, email_kierowcy = ?, telefon_kierowcy = ?, data_godzina = ?, typ_ladunku = ?, komentarz = ?, status = ?
        WHERE id = ?
    ''', (firma, rejestracja, kierowca, email_kierowcy, telefon_kierowcy, data_godzina, typ_ladunku, komentarz, status, id))
    conn.commit()
    conn.close()
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)

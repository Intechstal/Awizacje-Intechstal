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

    # Przygotowanie listy 6 dni roboczych od dziś
    today = datetime.now()
    dni = []
    d = today
    while len(dni) < 6:
        if d.weekday() < 5:  # 0-4 to dni robocze
            dni.append(d)
        d += timedelta(days=1)

    # Przygotowanie slotów czasowych co 15 minut wg podanych przedziałów
    sloty = []
    przedzialy = [
        ("07:30", "09:30"),
        ("11:00", "13:15"),
        ("14:30", "20:00"),
    ]
    for dzien in dni:
        for start, end in przedzialy:
            start_time = datetime.strptime(start, "%H:%M").time()
            end_time = datetime.strptime(end, "%H:%M").time()
            current = datetime.combine(dzien.date(), start_time)
            end_dt = datetime.combine(dzien.date(), end_time)
            while current < end_dt:
                sloty.append(current)
                current += timedelta(minutes=15)

    # Zajęte sloty: klucz to 'YYYY-MM-DDTHH:MM', wartość to dict z firmą i statusem
    zajete = {}

    # Funkcja blokująca 1h (4 sloty po 15min) dla awizacji
    def blokuj_sloty(start_dt, firma, status):
        for i in range(4):  # 1 godzina, 4 sloty po 15 min
            blok = start_dt + timedelta(minutes=15*i)
            key = blok.strftime('%Y-%m-%dT%H:%M')
            zajete[key] = {"firma": firma, "status": status}

    for a in awizacje:
        id_, firma, rejestracja, kierowca, email, telefon, data_godzina, typ_ladunku, waga_ladunku, komentarz, status = a
        start_dt = datetime.strptime(data_godzina, "%Y-%m-%dT%H:%M")
        blokuj_sloty(start_dt, firma, status)

    return render_template("admin.html", dni=dni, godziny=sloty, zajete=zajete, awizacje=awizacje)

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

if __name__ == "__main__":
    app.run(debug=True)

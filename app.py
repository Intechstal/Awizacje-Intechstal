from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
auth = HTTPBasicAuth()

# -- Ustawienia użytkowników admina (zmień hasło) --
users = {
    "admin": generate_password_hash("twojehaslo")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

# -- Inicjalizacja bazy --
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

# -- Pomocniczka: dni robocze (dziś + 5 dni roboczych) i sloty godzinowe --
def get_days_and_slots():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    dni = []
    d = today
    # chcemy 5 dni roboczych (dziś + kolejne tak wiele, pomijając weekendy)
    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    # sloty co 15 minut w przedziałach:
    godziny = []
    przedzialy = [("07:30", "09:30"), ("11:00", "13:15"), ("14:15", "20:00")]
    for start, end in przedzialy:
        s = datetime.strptime(start, "%H:%M")
        e = datetime.strptime(end, "%H:%M")
        while s < e:
            godziny.append(s.strftime('%H:%M'))
            s += timedelta(minutes=15)

    # zajete słownik: klucz = 'YYYY-MM-DDTHH:MM' -> {"firma":..., "status":...}
    zajete = {}
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina, firma, status FROM awizacje WHERE status != 'odrzucona'")
    rows = c.fetchall()
    conn.close()

    # dla klienta traktujemy, że każdy zapis blokuje 3 sloty przed i 3 po (czyli admin decided: block -3..+3)
    for data_godzina, firma, status in rows:
        try:
            dt = datetime.strptime(data_godzina, '%Y-%m-%dT%H:%M')
        except Exception:
            continue
        for i in range(-3, 4):  # -3, -2, -1, 0, 1, 2, 3
            blok = dt + timedelta(minutes=15 * i)
            key = blok.strftime('%Y-%m-%dT%H:%M')
            zajete[key] = {"firma": firma, "status": status}
    return dni, godziny, zajete

# ------------------ Strony ------------------

# formularz główny - tylko dostępne sloty (klient)
@app.route('/')
def index():
    dni, godziny, zajete = get_days_and_slots()
    # przekaż też aktualne dane (puste) i brak błędu
    return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane={}, error=None)

# zapis awizacji (klient)
@app.route('/zapisz', methods=['POST'])
def zapisz():
    firma = request.form.get('firma', '').strip()
    rejestracja = request.form.get('rejestracja', '').strip()
    kierowca = request.form.get('kierowca', '').strip()
    email = request.form.get('email', '').strip()
    telefon = request.form.get('telefon', '').strip()
    data_godzina = request.form.get('data_godzina', '').strip()
    typ_ladunku = request.form.get('typ_ladunku', '').strip()
    waga_ladunku = request.form.get('waga_ladunku', '').strip()
    komentarz = request.form.get('komentarz', '').strip()

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

    # walidacja podstawowa
    if not firma or not rejestracja or not kierowca or not telefon or not data_godzina or not email or not typ ladunku or not waga ladunku:
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=dane,
                               error="Wypełnij wszystkie wymagane pola.")

    # nie można wstecz
    try:
        wybrany = datetime.strptime(data_godzina, "%Y-%m-%dT%H:%M")
    except Exception:
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=dane,
                               error="Nieprawidłowy format daty/godziny.")
    if wybrany < datetime.now():
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=dane,
                               error="Nie można awizować w przeszłość.")

    # sprawdź kolizje: blok -3..+3 względem istniejących (klienci nie mogą zarezerwować jeśli jakikolwiek z tych bloków zajęty)
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT data_godzina FROM awizacje WHERE status != 'odrzucona'")
    rows = c.fetchall()
    conn.close()

    zajete_set = set()
    for (d_str,) in rows:
        try:
            dt = datetime.strptime(d_str, '%Y-%m-%dT%H:%M')
        except Exception:
            continue
        for i in range(-3, 4):
            blok = dt + timedelta(minutes=15 * i)
            zajete_set.add(blok.strftime('%Y-%m-%dT%H:%M'))

    if data_godzina in zajete_set:
        dni, godziny, zajete = get_days_and_slots()
        return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, dane=dane,
                               error="Wybrany termin jest już zajęty lub zablokowany. Wybierz inny.")

    # zapis do bazy
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO awizacje (firma, rejestracja, kierowca, email, telefon, data_godzina,
                              typ_ladunku, waga_ladunku, komentarz)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (firma, rejestracja, kierowca, email, telefon, data_godzina, typ_ladunku, waga_ladunku, komentarz))
    conn.commit()
    conn.close()

    return render_template('success.html')

# panel admina (lista + kalendarz). nie pokazujemy odrzuconych w głównej liście
@app.route('/admin')
@auth.login_required
def admin():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status != 'odrzucona' ORDER BY data_godzina ASC")
    awizacje = c.fetchall()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    # zajete już zawiera -3..+3 blokowanie i statusy
    return render_template('admin.html', awizacje=awizacje, dni=dni, godziny=godziny, zajete=zajete)

# aktualizacja statusu (akceptuj/odrzuć/oczekująca)
@app.route('/admin/update_status/<int:id>', methods=['POST'])
@auth.login_required
def update_status(id):
    status = request.form.get('status')
    if status not in ('oczekująca', 'zaakceptowana', 'odrzucona'):
        return redirect('/admin')
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()
    return redirect('/admin')

# edycja awizacji (admin) — ADMIN MOŻE ZMIENIĆ WSZYSTKIE POLA (BEZ BLOKAD)
@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@auth.login_required
def edit_awizacja(id):
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    if request.method == 'POST':
        firma = request.form.get('firma', '').strip()
        rejestracja = request.form.get('rejestracja', '').strip()
        kierowca = request.form.get('kierowca', '').strip()
        email = request.form.get('email', '').strip()
        telefon = request.form.get('telefon', '').strip()
        data_godzina = request.form.get('data_godzina', '').strip()
        typ_ladunku = request.form.get('typ_ladunku', '').strip()
        waga_ladunku = request.form.get('waga_ladunku', '').strip()
        komentarz = request.form.get('komentarz', '').strip()

        c.execute('''
            UPDATE awizacje
            SET firma=?, rejestracja=?, kierowca=?, email=?, telefon=?, data_godzina=?,
                typ_ladunku=?, waga_ladunku=?, komentarz=?
            WHERE id=?
        ''', (firma, rejestracja, kierowca, email, telefon, data_godzina, typ_ladunku, waga_ladunku, komentarz, id))
        conn.commit()
        conn.close()
        return redirect('/admin')
    else:
        c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
        awizacja = c.fetchone()
        conn.close()
        dni, godziny, zajete = get_days_and_slots()
        # przy edycji admin widzi wszystkie sloty (zajęte oznaczone), ale może wybrać dowolny
        return render_template('edit.html', awizacja=awizacja, dni=dni, godziny=godziny, zajete=zajete)

# historia odrzuconych
@app.route('/admin/historia')
@auth.login_required
def historia():
    conn = sqlite3.connect('awizacje.db')
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status = 'odrzucona' ORDER BY data_godzina DESC")
    awizacje = c.fetchall()
    conn.close()
    return render_template('historia.html', awizacje=awizacje)

if __name__ == '__main__':
    app.run(debug=True)

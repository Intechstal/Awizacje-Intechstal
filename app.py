from flask import Flask, render_template, request
from datetime import datetime, timedelta
from database import init_db, dodaj_awizacje, pobierz_awizacje_aktualne

app = Flask(__name__)
init_db()

def generate_next_workdays(n):
    from datetime import date
    days = []
    current = date.today()
    while len(days) < n:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days

def generate_hours():
    godziny = []
    start = datetime.strptime("08:00", "%H:%M")
    for i in range(32):
        godziny.append((start + timedelta(minutes=15 * i)).strftime("%H:%M"))
    return godziny

def generate_zajete(awizacje):
    zajete = {}
    for a in awizacje:
        dt = datetime.strptime(a[6], '%Y-%m-%dT%H:%M')
        for i in range(4):  # 3x15min back + 0min
            blok = dt - timedelta(minutes=15 * i)
            zajete[blok.strftime('%Y-%m-%dT%H:%M')] = {'firma': a[1], 'status': a[10]}
    return zajete

@app.route('/')
def form():
    dni = generate_next_workdays(5)
    godziny = generate_hours()
    awizacje = pobierz_awizacje_aktualne()
    zajete = generate_zajete(awizacje)
    return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, error=None, dane=None)

@app.route('/zapisz', methods=['POST'])
def zapisz():
    dane = request.form
    data_godzina = dane['data_godzina']
    awizacje = pobierz_awizacje_aktualne()
    zajete = generate_zajete(awizacje)

    dt = datetime.strptime(data_godzina, '%Y-%m-%dT%H:%M')
    for i in range(4):
        slot = (dt - timedelta(minutes=15 * i)).strftime('%Y-%m-%dT%H:%M')
        if slot in zajete:
            dni = generate_next_workdays(5)
            godziny = generate_hours()
            return render_template('form.html', dni=dni, godziny=godziny, zajete=zajete, error=f"Wybrany termin koliduje z innym zgłoszeniem ({slot})", dane=dane)

    dodaj_awizacje(
        dane['firma'], dane['rejestracja'], dane['kierowca'],
        dane['email'], dane['telefon'], data_godzina,
        dane['typ_ladunku'], dane['waga_ladunku'], dane['komentarz']
    )
    return render_template('success.html')

@app.route('/admin')
def admin():
    dni = generate_next_workdays(5)
    godziny = generate_hours()
    awizacje = pobierz_awizacje_aktualne()
    zajete = generate_zajete(awizacje)
    return render_template('admin.html', dni=dni, godziny=godziny, zajete=zajete)

if __name__ == '__main__':
    app.run(debug=True)

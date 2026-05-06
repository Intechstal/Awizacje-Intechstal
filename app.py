from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta
import smtplib
import ssl
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "sekretnyklucz"


# ================= MAIL TEMPLATES =================

def get_mail_template(typ):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT subject, body FROM mail_templates WHERE typ=?", (typ,))
    row = c.fetchone()
    conn.close()
    return row if row else ("Awizacja", "")


def get_time_window(data_godzina, typ_ladunku):
    """Zwraca okno czasowe: od godziny awizacji do końca blokady"""
    try:
        base = datetime.strptime(data_godzina, "%Y-%m-%dT%H:%M")
        blokada = get_slot_blocks().get(typ_ladunku, 1)
        end = base + timedelta(minutes=15 * blokada)
        return base.strftime("%H:%M"), end.strftime("%H:%M"), base.strftime("%d.%m.%Y")
    except:
        return "–", "–", "–"

# ================= MAIL CONFIG =================

MAIL_HOST = "s47.cyber-folks.pl"
MAIL_PORT = 465
MAIL_USER = "info@awizacje-intechstal.pl"
MAIL_PASS = "--0bO8YLba^A0JQq"

def _send_mail_worker(to, subject, body):
    import sys
    print(f"[MAIL] Próba wysyłki do: {to}", flush=True)
    try:
        msg = MIMEMultipart()
        msg["From"] = MAIL_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        print(f"[MAIL] Łączenie z {MAIL_HOST}:{MAIL_PORT}", flush=True)
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT, context=context) as server:
            print(f"[MAIL] Logowanie...", flush=True)
            server.login(MAIL_USER, MAIL_PASS)
            print(f"[MAIL] Wysyłanie...", flush=True)
            server.sendmail(MAIL_USER, to, msg.as_string())
            print(f"[MAIL] Wysłano do: {to}", flush=True)
    except Exception as e:
        print(f"[MAIL ERROR] {type(e).__name__}: {e}", flush=True)

def send_mail(to, subject, body):
    print(f"[MAIL] Tworzenie wątku dla: {to}", flush=True)
    t = threading.Thread(target=_send_mail_worker, args=(to, subject, body))
    t.daemon = True
    t.start()
    print(f"[MAIL] Wątek uruchomiony", flush=True)



# ================= SLOT CONFIG =================

def get_slot_blocks():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT typ, blokada FROM slot_blocks")
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

# ================= DB =================

def init_db():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS awizacje (
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
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login TEXT UNIQUE,
        haslo TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS logi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        akcja TEXT,
        data TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS permissions (
        login TEXT PRIMARY KEY,
        can_edit INTEGER DEFAULT 1,
        can_status INTEGER DEFAULT 1,
        calendar_only INTEGER DEFAULT 0,
        show_logi INTEGER DEFAULT 1,
        show_historia INTEGER DEFAULT 1,
        show_permissions INTEGER DEFAULT 1,
        auto_refresh INTEGER DEFAULT 0,
        auto_refresh_interval INTEGER DEFAULT 60,
        show_maile INTEGER DEFAULT 1
    )''')

    # Migracja dla istniejących baz danych
    try:
        c.execute("ALTER TABLE permissions ADD COLUMN auto_refresh INTEGER DEFAULT 0")
    except:
        pass
    try:
        c.execute("ALTER TABLE permissions ADD COLUMN auto_refresh_interval INTEGER DEFAULT 60")
    except:
        pass
    try:
        c.execute("ALTER TABLE permissions ADD COLUMN show_maile INTEGER DEFAULT 1")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS slot_blocks (
        typ TEXT PRIMARY KEY,
        blokada INTEGER DEFAULT 1
    )''')

    # Domyślne wartości jeśli tabela pusta
    defaults = [
        ("Odbiór złomu", 2),
        ("Odbiór zamówienia", 1),
        ("Dostawa materiału", 3),
    ]
    for typ, blokada in defaults:
        c.execute("INSERT OR IGNORE INTO slot_blocks VALUES (?,?)", (typ, blokada))

    c.execute('''CREATE TABLE IF NOT EXISTS mail_templates (
        typ TEXT PRIMARY KEY,
        subject TEXT,
        body TEXT
    )''')

    defaults = [
        (
            "zaakceptowana",
            "Potwierdzenie awizacji – INTECHSTAL",
            """<p>Szanowni Państwo,</p>
<p>potwierdzamy przyjęcie awizacji.</p>
<p><strong>Szczegóły awizacji:</strong><br>
Kontrahent: {firma}<br>
Data dostawy/załadunku: {termin}<br>
Okno czasowe: {godz_od} – {godz_do}<br>
Rodzaj operacji: {typ_ladunku}<br>
Numer rejestracyjny pojazdu: {rejestracja}</p>
<p>Prosimy o przybycie w wyznaczonym oknie czasowym. W przypadku opóźnienia awizacja może zostać przesunięta lub wymagać ponownego umówienia.</p>
<p>W razie potrzeby zmiany terminu prosimy o kontakt poprzez system awizacji.</p>
<p><em>Uwaga: Ta wiadomość została wygenerowana automatycznie. Prosimy na nią nie odpowiadać.</em></p>
<p>Z poważaniem,<br>System Awizacji<br>Intechstal Sp. z o.o.</p>"""
        ),
        (
            "odrzucona",
            "Odrzucenie awizacji – INTECHSTAL",
            """<p>Szanowni Państwo,</p>
<p>informujemy, że awizacja została odrzucona.</p>
<p><strong>Powód odrzucenia:</strong><br>{powod}</p>
<p><strong>Szczegóły awizacji:</strong><br>
Kontrahent: {firma}<br>
Planowana data: {termin}<br>
Okno czasowe: {godz_od} – {godz_do}</p>
<p>Prosimy o ponowne przesłanie awizacji z poprawnymi danymi lub wybór innego dostępnego terminu.</p>
<p><em>Uwaga: Ta wiadomość została wygenerowana automatycznie. Prosimy na nią nie odpowiadać.</em></p>
<p>Z poważaniem,<br>System Awizacji<br>Intechstal Sp. z o.o.</p>"""
        ),
        (
            "edycja",
            "Aktualizacja awizacji – INTECHSTAL",
            """<p>Szanowni Państwo,</p>
<p>informujemy, że awizacja została zaktualizowana przez administratora systemu.</p>
<p><strong>Zaktualizowane dane awizacji:</strong><br>
Kontrahent: {firma}<br>
Data operacji: {termin}<br>
Okno czasowe: {godz_od} – {godz_do}<br>
Rodzaj operacji: {typ_ladunku}<br>
Numer rejestracyjny pojazdu: {rejestracja}</p>
<p><strong>Zmiany wprowadzone w awizacji:</strong><br>{opis_zmian}</p>
<p>Prosimy o uwzględnienie zaktualizowanych informacji podczas realizacji dostawy/załadunku.</p>
<p><em>Uwaga: Ta wiadomość została wygenerowana automatycznie. Prosimy na nią nie odpowiadać.</em></p>
<p>Z poważaniem,<br>System Awizacji<br>Intechstal Sp. z o.o.</p>"""
        ),
    ]
    for typ, subject, body in defaults:
        c.execute("INSERT OR IGNORE INTO mail_templates VALUES (?,?,?)", (typ, subject, body))

    conn.commit()
    conn.close()

init_db()

# ================= USERS =================

def create_users():
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    users = [
        ("SK","1234"),
        ("JU","1234"),
        ("BL","1234"),
        ("KJ","1234"),
        ("TR","1234"),
        ("MAGAZYN","1234"),
        ("EK","1234"),
    ]

    for u,p in users:
        c.execute("INSERT OR IGNORE INTO users VALUES (NULL,?,?)", (u,p))

        c.execute("""
            INSERT OR IGNORE INTO permissions
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (u,1,1,0,1,1,1,0,60,1))

    conn.commit()
    conn.close()

create_users()

# ================= LOG =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("INSERT INTO logi VALUES (NULL,?,?,?)",
              (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# ================= PERMISSIONS =================

def get_perms(login):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""
        SELECT can_edit, can_status, calendar_only,
               show_logi, show_historia, show_permissions, auto_refresh, auto_refresh_interval, show_maile
        FROM permissions WHERE login=?
    """, (login,))

    row = c.fetchone()
    conn.close()

    return row if row else (1,1,0,1,1,1,0,60,1)

# ================= SLOTY =================

def get_days_and_slots():
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    dni = []
    d = today
    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)
        d += timedelta(days=1)

    godziny = []
    for s, e in [("07:30", "09:30"), ("11:00", "13:15"), ("14:15", "20:00")]:
        t = datetime.strptime(s, "%H:%M")
        e = datetime.strptime(e, "%H:%M")
        while t < e:
            godziny.append(t.strftime("%H:%M"))
            t += timedelta(minutes=15)

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT id, firma, data_godzina, typ_ladunku, waga_ladunku, komentarz, status FROM awizacje WHERE status != 'odrzucona'")
    rows = c.fetchall()
    conn.close()

    zajete = {}

    for r in rows:
        try:
            aid, firma, data, typ, waga, komentarz, status = r
            base = datetime.strptime(data, "%Y-%m-%dT%H:%M")
            blokada = get_slot_blocks().get(typ, 1)

            for i in range(-blokada, blokada + 1):
                slot_time = base + timedelta(minutes=15 * i)
                key = slot_time.strftime("%Y-%m-%dT%H:%M")

                zajete[key] = {
                    "main": i == 0,
                    "future_block": i != 0,
                    "is_before": i < 0,
                    "firma": firma,
                    "typ_ladunku": typ,
                    "komentarz": komentarz,
                    "status": status,
                    "is_past": slot_time < now
                }

        except:
            continue

    return dni, godziny, zajete

# ================= FORM =================

@app.route("/")
def index():
    dni, godziny, zajete = get_days_and_slots()

    return render_template("form.html",
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        dane={},
        error=None
    )

# ================= ZAPIS =================

@app.route("/zapisz", methods=["POST"])
def zapisz():
    f = request.form

    # Blokada przeszłych slotów
    try:
        wybrana = datetime.strptime(f["data_godzina"], "%Y-%m-%dT%H:%M")
        if wybrana < datetime.now():
            dni, godziny, zajete = get_days_and_slots()
            return render_template("form.html",
                dni=dni, godziny=godziny, zajete=zajete,
                dane=f, error="Nie można awizować się na termin w przeszłości."
            )
    except:
        pass

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""INSERT INTO awizacje VALUES (NULL,?,?,?,?,?,?,?,?,?,?)""",
    (
        f["firma"], f["rejestracja"], f["kierowca"],
        f["email"], f["telefon"], f["data_godzina"],
        f["typ_ladunku"], f["waga_ladunku"], f["komentarz"],
        "oczekująca"
    ))

    conn.commit()
    conn.close()

    return render_template("success.html")

# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        haslo = request.form["haslo"]

        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND haslo=?", (login,haslo))
        user = c.fetchone()
        conn.close()

        if user:
            session["logged_in"] = True
            session["user"] = login
            log_action(login,"LOGIN")
            return redirect("/admin")

    return render_template("login.html")

@app.route("/logout")
def logout():
    log_action(session.get("user"), "LOGOUT")
    session.clear()
    return redirect("/login")

# ================= ADMIN =================

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje WHERE status != 'odrzucona' ORDER BY id DESC")
    awizacje = c.fetchall()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()
    perms = get_perms(session.get("user"))

    return render_template("admin.html",
        awizacje=awizacje,
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        perms=perms
    )

# ================= STATUS =================

@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):
    if not session.get("logged_in"):
        return redirect("/login")

    status = request.form.get("status")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    # Pobierz firmę do loga
    c.execute("SELECT firma FROM awizacje WHERE id=?", (id,))
    row = c.fetchone()
    firma = row[0] if row else f"ID:{id}"

    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))

    conn.commit()
    conn.close()

    log_action(session.get("user"), f"ZMIANA STATUSU: {firma} → {status}")

    # Pobierz email klienta
    conn2 = sqlite3.connect("awizacje.db")
    c2 = conn2.cursor()
    c2.execute("SELECT email, firma, data_godzina, typ_ladunku, rejestracja FROM awizacje WHERE id=?", (id,))
    row2 = c2.fetchone()
    conn2.close()

    if row2:
        email_klienta, firma2, data2, typ2, rejestracja2 = row2
        if status in ("zaakceptowana", "odrzucona"):
            godz_od, godz_do, data_fmt = get_time_window(data2, typ2)
            subject, body = get_mail_template(status)
            powod = request.form.get("powod_odrzucenia", "")
            body = body.format(
                firma=firma2,
                termin=data_fmt,
                typ_ladunku=typ2,
                godz_od=godz_od,
                godz_do=godz_do,
                rejestracja=rejestracja2,
                powod=powod
            )
            send_mail(email_klienta, subject, body)

    return redirect("/admin")

# ================= EDIT =================

@app.route("/admin/edit/<int:id>", methods=["GET","POST"])
def edit(id):
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        f = request.form

        c.execute("""UPDATE awizacje SET
            firma=?,rejestracja=?,kierowca=?,email=?,telefon=?,
            data_godzina=?,typ_ladunku=?,waga_ladunku=?,komentarz=?
            WHERE id=?""",
        (
            f["firma"],f["rejestracja"],f["kierowca"],
            f["email"],f["telefon"],f["data_godzina"],
            f["typ_ladunku"],f["waga_ladunku"],f["komentarz"],id
        ))

        conn.commit()
        conn.close()

        log_action(session.get("user"), f"EDYCJA AWIZACJI: ID:{id} firma:{f['firma']}")

        godz_od, godz_do, data_fmt = get_time_window(f["data_godzina"], f["typ_ladunku"])
        opis_zmian = request.form.get("opis_zmian", "")
        subject, body = get_mail_template("edycja")
        body = body.format(
            firma=f["firma"],
            termin=data_fmt,
            typ_ladunku=f["typ_ladunku"],
            godz_od=godz_od,
            godz_do=godz_do,
            rejestracja=f["rejestracja"],
            opis_zmian=opis_zmian
        )
        send_mail(f["email"], subject, body)

        return redirect("/admin")

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    awizacja = c.fetchone()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()

    return render_template(
        "edit.html",
        awizacja=awizacja,
        dni=dni,
        godziny=godziny,
        zajete=zajete
    )

# ================= LOGI =================

@app.route("/admin/logi")
def logi():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM logi ORDER BY id DESC")
    logi = c.fetchall()
    conn.close()

    return render_template("logi.html", logi=logi)

# ================= HISTORIA =================

@app.route("/admin/historia")
def historia():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY data_godzina DESC")
    dane = c.fetchall()
    conn.close()

    return render_template("historia.html", awizacje=dane)

# ================= PERMISSIONS =================

@app.route("/admin/permissions", methods=["GET","POST"])
def permissions():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        login = request.form["login"]

        c.execute("""UPDATE permissions SET
            can_edit=?,can_status=?,calendar_only=?,
            show_logi=?,show_historia=?,show_permissions=?,auto_refresh=?,auto_refresh_interval=?,show_maile=?
            WHERE login=?""",
        (
            int("can_edit" in request.form),
            int("can_status" in request.form),
            int("calendar_only" in request.form),
            int("show_logi" in request.form),
            int("show_historia" in request.form),
            int("show_permissions" in request.form),
            int("auto_refresh" in request.form),
            int(request.form.get("auto_refresh_interval", 60)),
            int("show_maile" in request.form),
            login
        ))

        conn.commit()

        log_action(session.get("user"), f"ZMIANA UPRAWNIEŃ: {login}")

    c.execute("SELECT * FROM permissions")
    users = c.fetchall()
    conn.close()

    slot_blocks = get_slot_blocks()
    return render_template("permissions.html", users=users, slot_blocks=slot_blocks)

# ================= SLOT BLOCKS EDIT =================

@app.route("/admin/slot_blocks", methods=["POST"])
def update_slot_blocks():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    for key, val in request.form.items():
        if key.startswith("blokada_"):
            typ = key[len("blokada_"):]
            try:
                blokada = int(val)
                c.execute("UPDATE slot_blocks SET blokada=? WHERE typ=?", (blokada, typ))
            except:
                pass

    conn.commit()
    conn.close()

    log_action(session.get("user"), "ZMIANA SLOT BLOCKS")
    return redirect("/admin/permissions")


# ================= USER MANAGEMENT =================

@app.route("/admin/add_user", methods=["POST"])
def add_user():
    if not session.get("logged_in"):
        return redirect("/login")

    login = request.form.get("login", "").strip()
    haslo = request.form.get("haslo", "").strip()

    if login and haslo:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users VALUES (NULL,?,?)", (login, haslo))
        c.execute("INSERT OR IGNORE INTO permissions VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (login, 1, 1, 0, 1, 1, 1, 0, 60, 1))
        conn.commit()
        conn.close()
        log_action(session.get("user"), f"DODANIE UŻYTKOWNIKA: {login}")

    return redirect("/admin/permissions")

@app.route("/admin/edit_user", methods=["POST"])
def edit_user():
    if not session.get("logged_in"):
        return redirect("/login")

    login = request.form.get("login", "").strip()
    haslo = request.form.get("haslo", "").strip()

    if login and haslo:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("UPDATE users SET haslo=? WHERE login=?", (haslo, login))
        conn.commit()
        conn.close()
        log_action(session.get("user"), f"ZMIANA HASŁA: {login}")

    return redirect("/admin/permissions")

@app.route("/admin/delete_user", methods=["POST"])
def delete_user():
    if not session.get("logged_in"):
        return redirect("/login")

    login = request.form.get("login", "").strip()

    if login:
        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE login=?", (login,))
        c.execute("DELETE FROM permissions WHERE login=?", (login,))
        conn.commit()
        conn.close()
        log_action(session.get("user"), f"USUNIĘCIE UŻYTKOWNIKA: {login}")

    return redirect("/admin/permissions")


# ================= MAIL TEMPLATES EDIT =================

@app.route("/admin/maile", methods=["GET","POST"])
def maile():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    if request.method == "POST":
        for typ in ["zaakceptowana", "odrzucona", "edycja"]:
            subject = request.form.get(f"subject_{typ}", "")
            body = request.form.get(f"body_{typ}", "")
            c.execute("UPDATE mail_templates SET subject=?, body=? WHERE typ=?", (subject, body, typ))
        conn.commit()
        log_action(session.get("user"), "EDYCJA SZABLONÓW MAILI")

    c.execute("SELECT typ, subject, body FROM mail_templates")
    templates = {r[0]: {"subject": r[1], "body": r[2]} for r in c.fetchall()}
    conn.close()

    return render_template("maile.html", templates=templates)

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

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
        auto_refresh_interval INTEGER DEFAULT 60
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
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (u,1,1,0,1,1,1,0,60))

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
               show_logi, show_historia, show_permissions, auto_refresh, auto_refresh_interval
        FROM permissions WHERE login=?
    """, (login,))

    row = c.fetchone()
    conn.close()

    return row if row else (1,1,0,1,1,1,0,60)

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
            show_logi=?,show_historia=?,show_permissions=?,auto_refresh=?,auto_refresh_interval=?
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
        c.execute("INSERT OR IGNORE INTO permissions VALUES (?,?,?,?,?,?,?,?,?)",
                  (login, 1, 1, 0, 1, 1, 1, 0, 60))
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

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

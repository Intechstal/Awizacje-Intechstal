from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

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
        show_permissions INTEGER DEFAULT 1
    )''')

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
        try:
            c.execute("INSERT INTO users (login, haslo) VALUES (?,?)", (u,p))

            c.execute("""
                INSERT OR IGNORE INTO permissions
                (login, can_edit, can_status, calendar_only, show_logi, show_historia, show_permissions)
                VALUES (?,?,?,?,?,?,?)
            """, (u,1,1,0,1,1,1))

        except:
            pass

    conn.commit()
    conn.close()

create_users()

# ================= LOG =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
              (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# ================= PERMISSIONS =================

def get_perms(user_login):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("""
        SELECT can_edit, can_status, calendar_only,
               show_logi, show_historia, show_permissions
        FROM permissions WHERE login=?
    """, (user_login,))
    row = c.fetchone()
    conn.close()

    return row if row else (1,1,0,1,1,1)

# ================= SLOTY =================

def get_days_and_slots():
    today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)

    dni=[]
    d=today
    while len(dni)<5:
        if d.weekday()<5:
            dni.append(d)
        d += timedelta(days=1)

    godziny=[]
    for s,e in [("07:30","09:30"),("11:00","13:15"),("14:15","20:00")]:
        t=datetime.strptime(s,"%H:%M")
        e=datetime.strptime(e,"%H:%M")
        while t<e:
            godziny.append(t.strftime("%H:%M"))
            t += timedelta(minutes=15)

    return dni,godziny,{}

# ================= FORM =================

@app.route("/")
def index():
    dni, godziny, zajete = get_days_and_slots()

    return render_template(
        "form.html",
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        dane={},
        error=None
    )

# ================= ZAPIS =================

@app.route("/zapisz", methods=["POST"])
def zapisz():
    dane = request.form.to_dict()

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""INSERT INTO awizacje
        (firma,rejestracja,kierowca,email,telefon,data_godzina,typ_ladunku,waga_ladunku,komentarz)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (dane["firma"],dane["rejestracja"],dane["kierowca"],
         dane["email"],dane["telefon"],dane["data_godzina"],
         dane["typ_ladunku"],dane["waga_ladunku"],dane.get("komentarz",""))
    )

    conn.commit()
    conn.close()

    return render_template("success.html")

# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user_login = request.form["login"]
        haslo = request.form["haslo"]

        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND haslo=?", (user_login, haslo))
        user = c.fetchone()
        conn.close()

        if user:
            session["logged_in"] = True
            session["user"] = user_login
            log_action(user_login, "LOGIN")
            return redirect("/admin")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= ADMIN =================

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect("/login")

    user_login = session.get("user")
    perms = get_perms(user_login)

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY id DESC")
    awizacje = c.fetchall()
    conn.close()

    dni, godziny, zajete = get_days_and_slots()

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

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (request.form["status"], id))
    conn.commit()
    conn.close()

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
            firma=?, rejestracja=?, kierowca=?, email=?, telefon=?,
            data_godzina=?, typ_ladunku=?, waga_ladunku=?, komentarz=?
            WHERE id=?""",
            (f["firma"],f["rejestracja"],f["kierowca"],
             f["email"],f["telefon"],f["data_godzina"],
             f["typ_ladunku"],f["waga_ladunku"],f["komentarz"],id))
        conn.commit()
        conn.close()
        return redirect("/admin")

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    awizacja = c.fetchone()
    conn.close()

    return render_template("edit.html", awizacja=awizacja)

# ================= LOGI =================

@app.route("/admin/logi")
def logi():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM logi ORDER BY id DESC")
    logi_list = c.fetchall()
    conn.close()

    return render_template("logi.html", logi=logi_list)

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
        user_login = request.form["login"]

        c.execute("""
            UPDATE permissions SET
            can_edit=?,
            can_status=?,
            calendar_only=?,
            show_logi=?,
            show_historia=?,
            show_permissions=?
            WHERE login=?
        """, (
            int("can_edit" in request.form),
            int("can_status" in request.form),
            int("calendar_only" in request.form),
            int("show_logi" in request.form),
            int("show_historia" in request.form),
            int("show_permissions" in request.form),
            user_login
        ))
        conn.commit()

    c.execute("SELECT * FROM permissions")
    users = c.fetchall()
    conn.close()

    return render_template("permissions.html", users=users)

# ================= RUN =================

aplication = app

if __name__ == "__main__":
    app.run()

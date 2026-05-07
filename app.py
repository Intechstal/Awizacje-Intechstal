from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import smtplib
import ssl
import threading
import zipfile
import io
import os
import shutil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "sekretnyklucz"


# ================= TIMEZONE =================

TZ = ZoneInfo("Europe/Warsaw")

def now_pl():
    return datetime.now(TZ)

def parse_local_datetime(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=TZ)


# ================= MAIL TEMPLATES =================

def get_mail_template(typ):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT subject, body FROM mail_templates WHERE typ=?", (typ,))
    row = c.fetchone()
    conn.close()
    return row if row else ("Awizacja", "")


def get_time_window(data_godzina, typ_ladunku):
    try:
        base = parse_local_datetime(data_godzina)
        blokada = get_slot_blocks().get(typ_ladunku, 1)

        end = base + timedelta(minutes=15 * blokada)

        return (
            base.strftime("%H:%M"),
            end.strftime("%H:%M"),
            base.strftime("%d.%m.%Y")
        )

    except:
        return "–", "–", "–"


# ================= MAIL CONFIG =================

MAIL_HOST = "s47.cyber-folks.pl"
MAIL_PORT = 465
MAIL_USER = "info@awizacje-intechstal.pl"
MAIL_PASS = "--0bO8YLba^A0JQq"


def _send_mail_worker(to, subject, body):
    print(f"[MAIL] Próba wysyłki do: {to}", flush=True)

    try:
        msg = MIMEMultipart()
        msg["From"] = MAIL_USER
        msg["To"] = to
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html", "utf-8"))

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT, context=context) as server:
            server.login(MAIL_USER, MAIL_PASS)
            server.sendmail(MAIL_USER, to, msg.as_string())

        print(f"[MAIL] Wysłano do: {to}", flush=True)

    except Exception as e:
        print(f"[MAIL ERROR] {type(e).__name__}: {e}", flush=True)


def send_mail(to, subject, body):
    t = threading.Thread(
        target=_send_mail_worker,
        args=(to, subject, body)
    )

    t.daemon = True
    t.start()


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

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE,
            haslo TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS logi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            akcja TEXT,
            data TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
            login TEXT PRIMARY KEY,
            can_edit INTEGER DEFAULT 1,
            can_status INTEGER DEFAULT 1,
            calendar_only INTEGER DEFAULT 0,
            show_logi INTEGER DEFAULT 1,
            show_historia INTEGER DEFAULT 1,
            show_permissions INTEGER DEFAULT 1,
            auto_refresh INTEGER DEFAULT 0,
            auto_refresh_interval INTEGER DEFAULT 60,
            show_maile INTEGER DEFAULT 1,
            show_backup INTEGER DEFAULT 1
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS slot_blocks (
            typ TEXT PRIMARY KEY,
            blokada INTEGER DEFAULT 1
        )
    ''')

    defaults = [
        ("Odbiór złomu", 2),
        ("Odbiór zamówienia", 1),
        ("Dostawa materiału", 3),
    ]

    for typ, blokada in defaults:
        c.execute(
            "INSERT OR IGNORE INTO slot_blocks VALUES (?,?)",
            (typ, blokada)
        )

    c.execute('''
        CREATE TABLE IF NOT EXISTS mail_templates (
            typ TEXT PRIMARY KEY,
            subject TEXT,
            body TEXT
        )
    ''')

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
        c.execute(
            "INSERT OR IGNORE INTO users VALUES (NULL,?,?)",
            (u,p)
        )

        c.execute("""
            INSERT OR IGNORE INTO permissions
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (u,1,1,0,1,1,1,0,60,1,1))

    conn.commit()
    conn.close()


create_users()


# ================= LOG =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute(
        "INSERT INTO logi VALUES (NULL,?,?,?)",
        (
            user,
            akcja,
            now_pl().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()


# ================= PERMISSIONS =================

def get_perms(login):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""
        SELECT can_edit, can_status, calendar_only,
               show_logi, show_historia, show_permissions,
               auto_refresh, auto_refresh_interval,
               show_maile, show_backup
        FROM permissions
        WHERE login=?
    """, (login,))

    row = c.fetchone()

    conn.close()

    return row if row else (1,1,0,1,1,1,0,60,1,1)


# ================= SLOTY =================

def get_days_and_slots():

    now = now_pl()

    today = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    dni = []

    d = today

    while len(dni) < 5:
        if d.weekday() < 5:
            dni.append(d)

        d += timedelta(days=1)

    godziny = []

    for s, e in [
        ("07:30", "09:30"),
        ("11:00", "13:15"),
        ("14:15", "20:00")
    ]:

        t = datetime.strptime(s, "%H:%M")
        e = datetime.strptime(e, "%H:%M")

        while t < e:
            godziny.append(t.strftime("%H:%M"))
            t += timedelta(minutes=15)

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""
        SELECT id, firma, data_godzina,
               typ_ladunku, waga_ladunku,
               komentarz, status
        FROM awizacje
        WHERE status != 'odrzucona'
    """)

    rows = c.fetchall()

    conn.close()

    zajete = {}

    # BLOKADA 1.5H
    min_advance = now + timedelta(minutes=90)

    for g in godziny:
        for d in dni:

            slot_str = d.strftime("%Y-%m-%d") + "T" + g

            slot_time = parse_local_datetime(slot_str)

            if slot_time <= min_advance:

                zajete[slot_str] = {
                    "main": False,
                    "future_block": False,
                    "is_before": False,
                    "is_past": True,
                    "firma": "",
                    "typ_ladunku": "",
                    "komentarz": "",
                    "status": ""
                }

    for r in rows:

        try:
            aid, firma, data, typ, waga, komentarz, status = r

            base = parse_local_datetime(data)

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

        except Exception as e:
            print("BŁĄD SLOT:", e)

    return dni, godziny, zajete


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

    f = request.form

    try:
        wybrana = parse_local_datetime(f["data_godzina"])

        now = now_pl()

        if wybrana < now:

            dni, godziny, zajete = get_days_and_slots()

            return render_template(
                "form.html",
                dni=dni,
                godziny=godziny,
                zajete=zajete,
                dane=f,
                error="Nie można awizować się na termin w przeszłości."
            )

        if (wybrana - now).total_seconds() < 90 * 60:

            dni, godziny, zajete = get_days_and_slots()

            return render_template(
                "form.html",
                dni=dni,
                godziny=godziny,
                zajete=zajete,
                dane=f,
                error="Awizacja wymaga co najmniej 1,5 godziny wyprzedzenia."
            )

    except Exception as e:
        print("BŁĄD DATY:", e)

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()

    c.execute("""
        INSERT INTO awizacje
        VALUES (NULL,?,?,?,?,?,?,?,?,?,?)
    """,
    (
        f["firma"],
        f["rejestracja"],
        f["kierowca"],
        f["email"],
        f["telefon"],
        f["data_godzina"],
        f["typ_ladunku"],
        f["waga_ladunku"],
        f["komentarz"],
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

        c.execute(
            "SELECT * FROM users WHERE login=? AND haslo=?",
            (login,haslo)
        )

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

    c.execute("""
        SELECT *
        FROM awizacje
        WHERE status != 'odrzucona'
        ORDER BY id DESC
    """)

    awizacje = c.fetchall()

    conn.close()

    dni, godziny, zajete = get_days_and_slots()

    perms = get_perms(session.get("user"))

    return render_template(
        "admin.html",
        awizacje=awizacje,
        dni=dni,
        godziny=godziny,
        zajete=zajete,
        perms=perms
    )


# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True)

# DLA CYBER_FOLKS / PASSENGER
aplication = app

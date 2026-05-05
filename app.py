from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sekretnyklucz"

# ================= LOGS =================

def log_action(user, akcja):
    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO logi (user, akcja, data) VALUES (?,?,?)",
        (user, akcja, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

# ================= LOGIN =================

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        haslo = request.form["haslo"]

        conn = sqlite3.connect("awizacje.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND haslo=?", (login, haslo))
        user = c.fetchone()
        conn.close()

        if user:
            session["logged_in"] = True
            session["user"] = login

            log_action(login, "LOGIN")

            return redirect("/admin")

    return render_template("login.html")

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    if session.get("user"):
        log_action(session["user"], "LOGOUT")

    session.clear()
    return redirect("/login")

# ================= FORM =================

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

    log_action("FORM", f"NOWA AWIZACJA {dane['firma']}")

    return render_template("success.html")

# ================= ADMIN STATUS =================

@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):
    if not session.get("logged_in"):
        return redirect("/login")

    status = request.form["status"]

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("UPDATE awizacje SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

    log_action(session["user"], f"STATUS ID {id} -> {status}")

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
             f["typ_ladunku"],f["waga_ladunku"],f["komentarz"],id)
        )

        conn.commit()
        conn.close()

        log_action(session["user"], f"EDYCJA ID {id}")

        return redirect("/admin")

    c.execute("SELECT * FROM awizacje WHERE id=?", (id,))
    awizacja = c.fetchone()
    conn.close()

    return render_template("edit.html", awizacja=awizacja)

# ================= LOGS VIEW =================

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

# ================= MAIN ADMIN =================

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect("/login")

    conn = sqlite3.connect("awizacje.db")
    c = conn.cursor()
    c.execute("SELECT * FROM awizacje ORDER BY id DESC")
    awizacje = c.fetchall()
    conn.close()

    return render_template("admin.html", awizacje=awizacje)

# ================= INIT =================

if __name__ == "__main__":
    app.run(debug=True)

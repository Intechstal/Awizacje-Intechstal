from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secret"

# ================= USERS + ROLE =================
users = [
    ("SK", "1234", "admin"),
    ("JU", "1234", "admin"),
    ("BL", "1234", "admin"),
    ("KJ", "1234", "admin"),
    ("TR", "1234", "admin"),
    ("MAGAZYN", "1234", "magazyn"),
    ("EK", "1234", "admin"),
]

# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        haslo = request.form["haslo"]

        user = next((u for u in users if u[0] == login and u[1] == haslo), None)

        if user:
            session["logged_in"] = True
            session["user"] = user[0]
            session["role"] = user[2]

            if user[2] == "magazyn":
                return redirect("/magazyn")
            else:
                return redirect("/admin")

        return render_template("login.html", error="Błędne dane")

    return render_template("login.html")


# ================= ADMIN =================
@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect("/login")
    return render_template("admin.html")


# ================= MAGAZYN =================
@app.route("/magazyn")
def magazyn():
    if not session.get("logged_in"):
        return redirect("/login")

    dni, godziny, zajete = get_days_and_slots()

    return render_template(
        "magazyn.html",
        dni=dni,
        godziny=godziny,
        zajete=zajete
    )


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ================= EDIT (BLOKADA MAGAZYN) =================
@app.route("/admin/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if not session.get("logged_in"):
        return redirect("/login")

    if session.get("role") == "magazyn":
        return redirect("/magazyn")

    return "EDIT FORM"


# ================= UPDATE STATUS (BLOKADA MAGAZYN) =================
@app.route("/admin/update_status/<int:id>", methods=["POST"])
def update_status(id):
    if not session.get("logged_in"):
        return redirect("/login")

    if session.get("role") == "magazyn":
        return redirect("/magazyn")

    return redirect("/admin")


# ================= MOCK DATA =================
def get_days_and_slots():
    today = datetime.now().date()
    dni = [today + timedelta(days=i) for i in range(5)]
    godziny = ["08:00", "10:00", "12:00", "14:00"]

    zajete = {}

    return dni, godziny, zajete


if __name__ == "__main__":
    app.run(debug=True)

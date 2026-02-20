from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from flask_bcrypt import Bcrypt
from email_validator import validate_email, EmailNotValidError
from datetime import timedelta
import sqlite3
import os
import re
import pdfplumber

from config import Config
from data.auth import create_user, validate_user, init_db
from ml.readiness import calculate_readiness


# ---------------- APP INIT ----------------
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)

bcrypt = Bcrypt(app)

os.makedirs(Config.UPLOAD_DIR, exist_ok=True)

init_db()


# ---------------- PASSWORD POLICY ----------------
def strong_password(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"[0-9]", password) and
        re.search(r"[!@#$%^&*]", password)
    )


# ---------------- ROOT ----------------
@app.route("/")
def home():
    return redirect(url_for("login"))


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        try:
            validate_email(email)
        except EmailNotValidError:
            flash("Invalid email format")
            return redirect(url_for("register"))

        if not strong_password(password):
            flash("Password too weak")
            return redirect(url_for("register"))

        if create_user(email, password):
            flash("Account created successfully")
            return redirect(url_for("login"))
        else:
            flash("Email already exists")

    return render_template("auth/register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        result = validate_user(email, password)

        if result == "LOCKED":
            flash("Account locked due to multiple failed attempts")
            return redirect(url_for("login"))

        if result:
            session.clear()
            session["user_id"] = result["id"]
            session["role"] = result["role"]
            session.permanent = True

            if result["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("student_dashboard"))

        flash("Invalid credentials")

    return render_template("auth/login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- STUDENT DASHBOARD ----------------
@app.route("/student/dashboard")
def student_dashboard():
    if "user_id" not in session or session["role"] != "student":
        return redirect(url_for("login"))

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?",
              (session["user_id"],))
    skill, resume = c.fetchone()
    conn.close()

    interview, readiness = calculate_readiness(skill, resume)

    return render_template(
        "student/dashboard.html",
        skill=skill,
        resume=resume,
        interview=interview,
        readiness=readiness
    )


@app.route("/tasks")
def tasks():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    return render_template("student/tasks.html")


@app.route("/readiness")
def readiness_page():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?",
              (session["user_id"],))
    row = c.fetchone()
    conn.close()

    if row:
        skill, resume = row
    else:
        skill = resume = 0

    interview, readiness = calculate_readiness(skill, resume)
    return render_template("student/readiness.html", readiness=readiness, interview=interview)


@app.route("/skills")
def skills_page():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    skill = row[0] if row else 0
    return render_template("student/skills.html", skill=skill)


@app.route("/resume")
def resume_page():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT resume_score FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    resume = row[0] if row else 0
    return render_template("student/resume.html", resume=resume)


@app.route("/interview")
def interview_page():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?",
              (session["user_id"],))
    row = c.fetchone()
    conn.close()
    skill, resume = (row if row else (0, 0))
    interview, readiness = calculate_readiness(skill, resume)
    return render_template("student/interview.html", interview=interview)


@app.route("/metrics")
def metrics():
    if "user_id" not in session or session.get("role") != "student":
        return jsonify({"error": "unauthorized"}), 401

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?",
              (session["user_id"],))
    row = c.fetchone()
    conn.close()

    if row:
        skill, resume = row
    else:
        skill = resume = 0

    interview, readiness = calculate_readiness(skill, resume)
    return jsonify({"skill": skill, "resume": resume, "interview": interview, "readiness": readiness})


# ---------------- UPDATE SKILL SCORE ----------------
@app.route("/update_skills", methods=["POST"])
def update_skills():
    if "user_id" not in session:
        return redirect(url_for("login"))

    skill_score = int(request.form["skill_score"])

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET skill_score=? WHERE id=?",
              (skill_score, session["user_id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("student_dashboard"))


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "user_id" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, email, skill_score, resume_score FROM users WHERE role='student'")
    students = c.fetchall()
    conn.close()

    return render_template("admin/dashboard.html", students=students)


# ---------------- RESUME UPLOAD ----------------
@app.route("/upload_resume", methods=["GET", "POST"])
def upload_resume():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # GET: render a simple upload form so links can navigate here
    if request.method == "GET":
        return render_template("student/upload_resume.html")

    # POST: process uploaded PDF and compute resume score
    file = request.files.get("resume")
    if not file or not file.filename.lower().endswith(".pdf"):
        return redirect(url_for("student_dashboard"))

    file_path = os.path.join(Config.UPLOAD_DIR, file.filename)
    file.save(file_path)

    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            if page.extract_text():
                text += page.extract_text().lower()

    keywords = ["python", "machine learning", "flask", "sql"]
    found = [k for k in keywords if k in text]
    resume_score = min(100, len(found) * 20)

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET resume_score=? WHERE id=?",
              (resume_score, session["user_id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("student_dashboard"))


if __name__ == "__main__":
    app.run(debug=True)

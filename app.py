from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
import os
import pdfplumber
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "users.db")

SKILLS = [
    "python", "java", "sql",
    "machine learning", "data science",
    "deep learning", "flask", "opencv"
]

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        skill_score INTEGER DEFAULT 60,
        resume_score INTEGER DEFAULT 50
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- AUTH ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, password FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            return redirect(url_for("dashboard"))

        flash("Invalid credentials")

    return render_template("auth/login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        try:
            c.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, password)
            )
            conn.commit()
            flash("Registration successful")
            return redirect(url_for("login"))
        except:
            flash("Email already exists")

        conn.close()

    return render_template("auth/register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- SCORE CALCULATION ----------------
def get_scores(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT skill_score, resume_score
        FROM users WHERE id=?
    """, (user_id,))
    skill, resume = c.fetchone()
    conn.close()

    # Auto interview score
    interview = int((skill + resume) / 2)

    # Readiness formula
    readiness = int(0.5 * skill + 0.3 * resume + 0.2 * interview)

    return skill, resume, interview, readiness


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    skill, resume, interview, readiness = get_scores(session["user_id"])

    return render_template(
        "student/dashboard.html",
        skill=skill,
        resume=resume,
        interview=interview,
        readiness=readiness
    )


# ---------------- RESUME UPLOAD ----------------
@app.route("/upload_resume", methods=["POST"])
def upload_resume():
    if "user_id" not in session:
        return redirect(url_for("login"))

    file = request.files["resume"]

    if file:
        path = os.path.join(UPLOAD_DIR, file.filename)
        file.save(path)

        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    text += page.extract_text().lower()

        found = [s for s in SKILLS if s in text]
        resume_score = min(100, len(found) * 15)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE users SET resume_score=? WHERE id=?",
            (resume_score, session["user_id"])
        )
        conn.commit()
        conn.close()

    return redirect(url_for("dashboard"))


# ---------------- SKILL UPDATE ----------------
@app.route("/update_skills", methods=["POST"])
def update_skills():
    if "user_id" not in session:
        return redirect(url_for("login"))

    skill_score = int(request.form["skill_score"])

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET skill_score=? WHERE id=?",
        (skill_score, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# ---------------- METRIC PAGES ----------------
@app.route("/readiness")
def readiness_page():
    skill, resume, interview, readiness = get_scores(session["user_id"])
    return render_template("student/readiness.html", readiness=readiness)

@app.route("/skills")
def skills_page():
    skill, resume, interview, readiness = get_scores(session["user_id"])
    return render_template("student/skills.html", skill=skill)

@app.route("/resume")
def resume_page():
    skill, resume, interview, readiness = get_scores(session["user_id"])
    return render_template("student/resume.html", resume=resume)

@app.route("/interview")
def interview_page():
    skill, resume, interview, readiness = get_scores(session["user_id"])
    return render_template("student/interview.html", interview=interview)

@app.route("/tasks")
def tasks_page():
    return render_template("student/tasks.html")


if __name__ == "__main__":
    app.run()


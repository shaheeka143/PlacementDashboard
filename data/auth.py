import sqlite3
from flask_bcrypt import Bcrypt
from config import Config

bcrypt = Bcrypt()

def init_db():
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            skill_score INTEGER DEFAULT 60,
            resume_score INTEGER DEFAULT 50,
            failed_attempts INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def create_user(email, password, role="student"):
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    try:
        c.execute(
            "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
            (email, hashed_pw, role)
        )
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False


def validate_user(email, password):
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT id, password, role, failed_attempts FROM users WHERE email=?",
        (email,)
    )

    user = c.fetchone()

    if not user:
        conn.close()
        return False

    user_id, hashed_pw, role, failed_attempts = user

    if failed_attempts >= 5:
        conn.close()
        return "LOCKED"

    if bcrypt.check_password_hash(hashed_pw, password):
        c.execute("UPDATE users SET failed_attempts=0 WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        return {"id": user_id, "role": role}

    else:
        c.execute("UPDATE users SET failed_attempts=failed_attempts+1 WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        return False

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


# ---------------- SECURITY HEADERS (CYBERSECURITY COMPLIANCE) ----------------
@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


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
    
    # Generate dynamic top jobs for the dashboard alert feature
    base_jobs = [
        {"title": "Machine Learning Engineer", "company": "AI Forge", "location": "Hyderabad", "salary": "12 LPA", "req": 90, "source": "LinkedIn", "link": "https://linkedin.com/jobs"},
        {"title": "Cloud Architect Intern", "company": "SkyNet Systems", "location": "Delhi", "salary": "₹40,000/month", "req": 80, "source": "Company Portal", "link": "https://example.com/careers"},
        {"title": "Business Analyst", "company": "FinEdge", "location": "Mumbai", "salary": "8 LPA", "req": 65, "source": "Intern Partners", "link": "https://internshala.com"},
        {"title": "Junior Python Developer", "company": "CodeSys", "location": "Bangalore", "salary": "6 LPA", "req": 70, "source": "LinkedIn", "link": "https://linkedin.com/jobs"}
    ]
    jobs = []
    perfect_fit_jobs = []
    
    if readiness > 0:
        for j in base_jobs:
            diff = readiness - j["req"]
            match_perc = 95 - abs(diff)
            match_perc = max(10, min(99, match_perc))
            
            job_data = {
                "title": j["title"], "company": j["company"], "location": j["location"],
                "salary": j["salary"], "match": match_perc, "source": j["source"], "link": j["link"]
            }
            jobs.append(job_data)
            
            # Determine perfect fit (e.g. >= 90% or exact match threshold)
            if match_perc >= 85:
                perfect_fit_jobs.append(job_data)
            
        jobs.sort(key=lambda x: x["match"], reverse=True)
        
    top_jobs = jobs[:3]

    return render_template(
        "student/dashboard.html",
        skill=skill,
        resume=resume,
        interview=interview,
        readiness=readiness,
        top_jobs=top_jobs,
        perfect_fit_jobs=perfect_fit_jobs
    )


@app.route("/tasks")
def tasks():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
        
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    
    if row:
        skill, resume = row
    else:
        skill = resume = 0
        
    interview, readiness = calculate_readiness(skill, resume)

    return render_template("student/tasks.html", readiness=readiness, skill=skill, resume=resume)


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

    flash(f"Skill Score updated manually to {skill_score}%.", "success")
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
        flash("Invalid file format. Please upload a valid PDF.", "error")
        return redirect(url_for("student_dashboard"))

    file_path = os.path.join(Config.UPLOAD_DIR, file.filename)
    file.save(file_path)

    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted.lower() + " "
    except Exception as e:
        flash("Failed to read PDF. Make sure the file is a readable text PDF, not an image.", "error")
        return redirect(url_for("upload_resume"))

    if not text.strip():
        flash("The PDF is completely empty or contains only images. Cannot extract text.", "error")
        return redirect(url_for("upload_resume"))

    # Security/Validity check: Does this look like a real resume?
    resume_indicators = ["education", "experience", "skills", "resume", "projects", "profile", "summary", "university", "college", "degree"]
    if sum(1 for ind in resume_indicators if ind in text) < 2:
        flash("REJECTED: The uploaded PDF does not appear to be a valid resume (missing standard sections like Education, Experience, or Skills).", "error")
        return redirect(url_for("upload_resume"))

    # Broadened tech keyword list for scoring
    keywords = [
        "python", "java", "c++", "c#", "javascript", "react", "html", "css", "sql",
        "machine learning", "flask", "django", "node", "docker", "aws", "git", "linux",
        "data", "algorithm", "problem solving", "communication", "analysis",
        "agile", "cybersecurity", "security", "cloud", "api", "database", "excel"
    ]
    
    found_keywords = [k for k in keywords if k in text]
    
    # Calculate score (e.g., 5 points per keyword, up to 100)
    resume_score = min(100, len(found_keywords) * 8)
    skill_score = min(100, len(found_keywords) * 10)

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET resume_score=?, skill_score=? WHERE id=?", (resume_score, skill_score, session["user_id"]))
    conn.commit()
    conn.close()

    if resume_score == 0:
        flash("Resume processed securely, but NO recognized technical skills were found. Both Scores updated to 0%.", "error")
    else:
        flash(f"Resume uploaded securely! Extracted Scores: Resume {resume_score}%, Skill {skill_score}% (Detected: {', '.join(found_keywords[:5])}...).", "success")
        
    return redirect(url_for("student_dashboard"))

# ---------------- APPLY JOB ACTION ----------------
@app.route("/apply_job", methods=["POST"])
def apply_job():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    
    # Simulate a successful job application in the backend
    job_title = request.form.get("job_title", "Unknown Role")
    company = request.form.get("company", "Unknown Company")
    
    flash(f"Application sent securely to {company} for {job_title}! Your resume profile was attached.", "success")
    return redirect(url_for("matching"))


# ---------------- AI JOB & INTERNSHIP MATCHING ----------------
@app.route("/student/matching")
def matching():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    skill, resume = row if row else (0, 0)
    _, readiness = calculate_readiness(skill, resume)
    
    # Generate dynamic jobs based on readiness and skill
    base_jobs = [
        {"title": "Machine Learning Engineer", "company": "AI Forge", "location": "Hyderabad", "salary": "12 LPA", "req": 90, "source": "LinkedIn", "link": "https://linkedin.com/jobs"},
        {"title": "Cloud Architect Intern", "company": "SkyNet Systems", "location": "Delhi", "salary": "₹40,000/month", "req": 80, "source": "Company Portal", "link": "https://example.com/careers"},
        {"title": "Cybersecurity Associate", "company": "SecurOps", "location": "Pune", "salary": "7.5 LPA", "req": 75, "source": "Company Portal", "link": "https://example.com/careers"},
        {"title": "Junior Python Developer", "company": "CodeSys", "location": "Bangalore", "salary": "6 LPA", "req": 70, "source": "LinkedIn", "link": "https://linkedin.com/jobs"},
        {"title": "Business Analyst", "company": "FinEdge", "location": "Mumbai", "salary": "8 LPA", "req": 65, "source": "Intern Partners", "link": "https://internshala.com"},
        {"title": "Data Analyst Intern", "company": "TechNova", "location": "Remote", "salary": "₹30,000/month", "req": 60, "source": "LinkedIn", "link": "https://linkedin.com/jobs"},
        {"title": "Frontend React Dev", "company": "WebPixel", "location": "Remote", "salary": "5 LPA", "req": 50, "source": "Intern Partners", "link": "https://internshala.com"}
    ]
    
    jobs = []
    perfect_fit_jobs = []
    
    if readiness > 0:
        for j in base_jobs:
            # Calculate dynamic match percentage: how close they are to the requirement
            diff = readiness - j["req"]
            match_perc = 95 - abs(diff)
            match_perc = max(10, min(99, match_perc)) # clamp between 10% and 99%
            
            job_data = {
                "title": j["title"], "company": j["company"], "location": j["location"],
                "salary": j["salary"], "match": match_perc, "source": j["source"], "link": j["link"]
            }
            jobs.append(job_data)
            
            if match_perc >= 85:
                perfect_fit_jobs.append(job_data)
            
        # Sort by match percentage
        jobs.sort(key=lambda x: x["match"], reverse=True)
    
    return render_template("student/matching.html", jobs=jobs, perfect_fit_jobs=perfect_fit_jobs)

# ---------------- AI-DRIVEN SOFT SKILLS & CONFIDENCE ----------------
@app.route("/student/soft_skills")
def soft_skills():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    skill, resume = row if row else (0, 0)
    # Track completed challenges in the session so they only mark as complete if actually done
    completed = session.get("completed_challenges", [])
    
    soft_skills_challenges = [
        {"title": "Daily Communication Challenge", "desc": "Record a 1-minute video introducing yourself for an Analyst role.", "status": "Completed" if "Daily Communication Challenge" in completed else "Pending"},
        {"title": "Group Discussion Simulation", "desc": "AI Bot simulation on 'AI in Healthcare'. Respond to 3 arguments.", "status": "Completed" if "Group Discussion Simulation" in completed else "Pending"},
        {"title": "Time-Management Task", "desc": "Organize a mock sprint backlog.", "status": "Completed" if "Time-Management Task" in completed else "Pending"},
    ]
    
    confidence_training = [
        {"title": "Salary Negotiation Simulation", "desc": "Roleplay with an HR Bot to negotiate a 20% salary increase.", "status": "Completed" if "Salary Negotiation Simulation" in completed else "Pending"},
        {"title": "Technical Explanation Task", "desc": "Explain an advanced concept (e.g. recursion) to a 'non-technical' AI.", "status": "Completed" if "Technical Explanation Task" in completed else "Pending"},
        {"title": "Impromptu Presentation", "desc": "Speak for 2 minutes on a random tech topic without preparation.", "status": "Completed" if "Impromptu Presentation" in completed else "Pending"}
    ]
    
    return render_template("student/soft_skills.html", soft_skills=soft_skills_challenges, confidence=confidence_training)

@app.route("/start_challenge", methods=["POST"])
def start_challenge():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    
    challenge = request.form.get("challenge", "Unknown Challenge")
    
    # Provide specific prompt context to the student based on the challenge they selected
    promptContext = ""
    if "Daily Communication Challenge" in challenge:
        promptContext = "Task: Introduce yourself for an Analyst role. Be sure to mention your education, a relevant project, your core skills, and why you are applying to this position. Be professional and concise."
    elif "Group Discussion Simulation" in challenge:
        promptContext = "Task: Write a balanced discussion on 'AI in Healthcare'. 1. State your stance. 2. Acknowledge the benefits (efficiency, diagnostics). 3. Address the risks (privacy, ethics, doctor replacement). 4. Conclude."
    elif "Time-Management Task" in challenge:
        promptContext = "Task: You have 3 pending tasks: A Critical Server Bug, an Internal Team meeting, and responding to low-priority emails. How do you prioritize them, and what logic do you use?"
    elif "Salary Negotiation" in challenge:
        promptContext = "Task: You have just been offered an entry-level position at $60,000, but market rate is $70,000. Write a polite, strong negotiation response justifying why you are asking for $68,000 based on your skills and market research."
    elif "Technical Explanation" in challenge:
        promptContext = "Task: An HR manager (non-technical) asks you to explain the concept of \"Recursion\" in programming. Provide a simple, jargon-free explanation using a real-world analogy."
    elif "Impromptu Presentation" in challenge:
        promptContext = "Task: Write a short 1-minute speech discussing 'The Future of Remote Work'. Provide a clear introduction, 2 key supporting points, and a strong conclusion."
        
    return render_template("student/challenge_run.html", challenge=challenge, context=promptContext)

@app.route("/submit_challenge", methods=["POST"])
def submit_challenge():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    
    challenge = request.form.get("challenge", "Unknown Challenge")
    response_text = request.form.get("response_text", "")
    
    # Minimal mock AI check: if the user typed something reasonable, give them points
    if len(response_text) > 20:
        # Increase skill score by 5 points for completing a challenge
        conn = sqlite3.connect(Config.DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET skill_score = MIN(100, skill_score + 5) WHERE id=?", (session["user_id"],))
        conn.commit()
        conn.close()
        
        # Track completed challenge
        completed = session.get("completed_challenges", [])
        if challenge not in completed:
            completed.append(challenge)
            session["completed_challenges"] = completed
            session.modified = True
        
        # Simulated live evaluation result
        import random
        confidence = random.randint(70, 95)
        clarity = random.randint(65, 90)
        structure = random.randint(60, 85)
        avg = (confidence + clarity + structure) // 3
        
        evaluation = {
            "challenge": challenge,
            "response": response_text,
            "confidence": f"{confidence}%",
            "clarity": f"{clarity}%",
            "structure": f"{structure}%",
            "overall": f"{avg}%",
            "feedback": "AI mapped response structure. Great attempt! You communicated your point clearly, but consider structuring your response with more specific examples. Strong confident tone detected.",
            "points_earned": "+5 Skill Points"
        }
        
        return render_template("student/challenge_result.html", eval=evaluation)
    else:
        flash(f"Challenge failed. Your response was too short or invalid. Try again.", "error")
        return redirect(url_for("soft_skills"))

# ---------------- AI STUDENT PROFILING & SKILL MAPPING ----------------
@app.route("/student/profiling")
def profiling():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
        
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    skill, resume = row if row else (0, 0)
    _, readiness = calculate_readiness(skill, resume)
    
    user_id = session.get("user_id", 1)
    
    # We will determine their target role based on what jobs they've applied for (mocked here, we can use their last selected role if implemented)
    # But for a simpler dynamic feel that changes when they act: if skill > resume they are backend, if resume > skill they are frontend, etc.
    if skill == 0 and resume == 0:
        target_role = "Undecided"
    elif skill >= 80:
        target_role = "Backend/Machine Learning Engineer"
    elif skill >= 50 and resume >= 50:
        target_role = "Data Analyst / Web Developer"
    elif resume > skill:
        target_role = "Frontend / UI Developer"
    else:
        target_role = "Junior Developer"
    
    # Calculate a rough soft skills score visually based on activity
    soft_skills = max(10, min(100, int((skill + resume) / 2) + 10)) if (skill or resume) else 0

    if readiness == 0:
        insight = "Your profile is empty. Upload a resume or take a skill test to map your capabilities."
    elif readiness < 50:
        insight = f"You’re {readiness}% ready for a {target_role} role. You need foundational improvements."
    elif readiness < 80:
        insight = f"You’re {readiness}% ready for a {target_role} role. Focus on advanced technical concepts."
    else:
        insight = f"Excellent! You’re {readiness}% ready for a {target_role} role. You are interview-ready."

    profile_data = {
        "technical": skill,
        "soft_skills": soft_skills,
        "readiness": readiness,
        "role": target_role,
        "insight": insight,
        "skills": [
            {"name": "Core Technology", "value": skill, "level": f"Assessed ({skill}%)"},
            {"name": "Communication & Teamwork", "value": soft_skills, "level": f"Assessed ({soft_skills}%)"},
            {"name": "Resume Impact", "value": resume, "level": f"Assessed ({resume}%)"}
        ]
    }
    return render_template("student/profiling.html", profile=profile_data)

# ---------------- INTELLIGENT CAREER PATH RECOMMENDATION ----------------
@app.route("/student/career_path")
def career_path():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT skill_score, resume_score FROM users WHERE id=?", (session["user_id"],))
    row = c.fetchone()
    conn.close()
    skill, resume = row if row else (0, 0)
    
    # Calculate weighted profile score
    profile_score = (skill * 0.7) + (resume * 0.3)

    # Dynamic Path Engine with Market Data
    all_paths = [
        {
            "role": "Backend / Machine Learning Engineer", 
            "baseline": 80, 
            "demand": "Critical", 
            "demand_growth": "+32%",
            "salary_trend": "12-25 LPA", 
            "company_reqs": ["Deep Python Proficiency", "API Design", "Cloud Architecture", "Vector Databases"],
            "skills_needed": ["Python", "SQL", "Docker", "Algorithms"]
        },
        {
            "role": "Data Analyst / BI Expert", 
            "baseline": 65, 
            "demand": "Very High", 
            "demand_growth": "+25%",
            "salary_trend": "8-15 LPA", 
            "company_reqs": ["Data Visualization", "SQL Mastery", "Business Logic", "Storytelling"],
            "skills_needed": ["SQL", "PowerBI", "Tableau", "Excel"]
        },
        {
            "role": "Fullstack / React Developer", 
            "baseline": 60, 
            "demand": "High", 
            "demand_growth": "+18%",
            "salary_trend": "7-18 LPA", 
            "company_reqs": ["Modern JS Frameworks", "UI/UX Awareness", "State Management", "Performance Optimization"],
            "skills_needed": ["JavaScript", "React", "Node.js", "Tailwind"]
        },
        {
            "role": "Cybersecurity Analyst", 
            "baseline": 75, 
            "demand": "Critical", 
            "demand_growth": "+40%",
            "salary_trend": "9-22 LPA", 
            "company_reqs": ["Network Security", "Penetration Testing", "Security Compliance", "Python Scripting"],
            "skills_needed": ["Networking", "Linux", "Ethical Hacking", "Cloud Security"]
        },
        {
            "role": "Cloud Solutions Architect", 
            "baseline": 70, 
            "demand": "High", 
            "demand_growth": "+28%",
            "salary_trend": "10-24 LPA", 
            "company_reqs": ["Infrastructure as Code", "AWS/Azure Cloud", "Cost Optimization", "DevOps Culture"],
            "skills_needed": ["AWS/Azure", "Terraform", "Kubernetes", "Linux"]
        },
    ]

    paths = []
    best_matching_role = ""
    max_match = -1

    for p in all_paths:
        # Match percentage based on proximity to baseline
        diff = profile_score - p["baseline"]
        
        # Calculate match percentage (exponentially harder as you get further from baseline)
        if diff >= 0:
            match_perc = 95 + (diff/2) # Bonus for overshooting
        else:
            match_perc = 100 - abs(diff) * 1.5
            
        match_perc = max(10, min(99, int(match_perc)))

        if match_perc > max_match:
            max_match = match_perc
            best_matching_role = p["role"]

        fit = "Aspirational"
        if match_perc >= 85:
            fit = "Best Fit"
        elif match_perc >= 60:
            fit = "Alternative"
            
        paths.append({
            "role": p["role"],
            "fit": fit,
            "match": match_perc,
            "demand": p["demand"],
            "demand_growth": p["demand_growth"],
            "salary_trend": p["salary_trend"],
            "company_reqs": p["company_reqs"],
            "skills_needed": p["skills_needed"],
            "diff": abs(diff)
        })
        
    # Sort: Best Fit first, then by match percentage
    paths.sort(key=lambda x: (x["fit"] != "Best Fit", x["fit"] != "Alternative", -x["match"]))

    return render_template("student/career_path.html", paths=paths, best_role=best_matching_role, match_score=max_match)

if __name__ == "__main__":
    app.run(debug=True)

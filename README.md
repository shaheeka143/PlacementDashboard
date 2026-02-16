
Placement Readiness Dashboard

Overview
This project is a web-based placement readiness dashboard designed to help students track their skills, resume quality, interview preparation, and overall placement readiness. The system integrates basic machine learning logic to estimate readiness scores and provides a structured interface for students and administrators.

Core Features
- Student registration and login
- Resume upload and management
- Skills and task tracking
- Interview preparation modules
- Readiness score prediction using a lightweight ML model
- Admin dashboard for monitoring student progress

Technology Stack
Backend: Python, Flask
Frontend: HTML, CSS, JavaScript
Database: SQLite
Machine Learning: Custom readiness scoring module (Python)
Deployment: Compatible with Render, local servers, or cloud platforms

Project Structure
placement_dashboard/
 ├── app.py                Main Flask application
 ├── config.py             Configuration settings
 ├── requirements.txt      Python dependencies
 ├── runtime.txt           Python runtime version
 ├── data/                 Database files
 ├── ml/                   Readiness prediction module
 ├── static/               CSS, JS, and images
 ├── templates/            HTML templates
 └── uploads/              Uploaded resumes

Installation
1. Clone the repository:
   git clone <repository_url>
   cd placement_dashboard

2. Create a virtual environment:
   python -m venv venv
   source venv/bin/activate      (Linux/Mac)
   venv\Scripts\activate       (Windows)

3. Install dependencies:
   pip install -r requirements.txt

4. Run the application:
   python app.py

5. Open the browser:
   http://127.0.0.1:5000

Usage
Students can register, upload resumes, track skills, and view their readiness score. Administrators can monitor student progress through the admin dashboard.

Machine Learning Module
The ML component calculates a readiness score based on user inputs such as skills, completed tasks, and interview preparation. The module is implemented in:
ml/readiness.py

Future Improvements
- Integration with real job APIs
- Advanced resume parsing using NLP
- Deep learning–based skill recommendation
- Real-time analytics dashboard

License
This project is for academic and educational purposes.

from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from groq import Groq

from io import BytesIO
import os
import json
import traceback
import pymupdf

import numpy as np

from pypdf import PdfReader
from docx import Document


ocr_reader = None

def get_ocr_reader():
    global ocr_reader

    if ocr_reader is None:
        import easyocr
        ocr_reader = easyocr.Reader(['en'], gpu=False)

    return ocr_reader

app = Flask(__name__)

app.secret_key = "quizsphere_ai_secret_key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"

db = SQLAlchemy(app)


# ==================================================
# CREATE UPLOAD FOLDER
# ==================================================

if not os.path.exists("static/uploads"):
    os.makedirs("static/uploads")


# ==================================================
# USER
# ==================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False
    )

    roll_no = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    contact = db.Column(db.String(15))
    address = db.Column(db.String(200))

    profile_pic = db.Column(
        db.String(200),
        default="default.png"
    )

    language = db.Column(db.String(50))
    bio = db.Column(db.Text)
    skills = db.Column(db.String(200))
    course = db.Column(db.String(100))
    year = db.Column(db.String(50))
    subject = db.Column(db.String(100))
    experience = db.Column(db.String(100))
    qualification = db.Column(db.String(200))


# ==================================================
# QUIZ
# ==================================================

class Quiz(db.Model):

    __tablename__ = "quiz"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    title = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    subject = db.Column(
        db.String(100)
    )

    total_questions = db.Column(
        db.Integer,
        default=0
    )

    duration = db.Column(
        db.Integer,
        default=30
    )

    difficulty = db.Column(
        db.String(20),
        default="Medium"
    )

    question_type = db.Column(
        db.String(30),
        default="MCQ"
    )

    number_of_questions = db.Column(
        db.Integer,
        default=10
    )

    passing_marks = db.Column(
        db.Integer,
        default=40
    )

    published = db.Column(
        db.Boolean,
        default=False
    )

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    teacher = db.relationship(
        "User",
        foreign_keys=[teacher_id]
    )

    questions = db.relationship(
        "Question",
        backref="quiz",
        cascade="all, delete-orphan"
    )


# ==================================================
# QUESTION
# ==================================================

class Question(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    quiz_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz.id"),
        nullable=False
    )

    question = db.Column(
        db.Text,
        nullable=False
    )

    option_a = db.Column(
        db.String(500),
        nullable=False
    )

    option_b = db.Column(
        db.String(500),
        nullable=False
    )

    option_c = db.Column(
        db.String(500),
        nullable=False
    )

    option_d = db.Column(
        db.String(500),
        nullable=False
    )

    answer = db.Column(
        db.String(1),
        nullable=False
    )

    correct_answer = db.Column(
        db.String(1),
        nullable=True
    )

    explanation = db.Column(
        db.Text
    )

    marks = db.Column(
        db.Integer,
        default=1
    )


# ==================================================
# RESULT
# ==================================================

class Result(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    quiz_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz.id")
    )

    score = db.Column(
        db.Integer
    )

    total = db.Column(
        db.Integer
    )

    student = db.relationship(
        "User"
    )

    quiz = db.relationship(
        "Quiz"
    )

    @property
    def percentage(self):

        if self.total == 0:
            return 0

        return int(
            (self.score / self.total) * 100
        )


# ==================================================
# HOME
# ==================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ==================================================
# REGISTER
# ==================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get(
            "confirm_password"
        )
        role = request.form.get("role")

        if (
            not name
            or not email
            or not password
            or not confirm_password
        ):
            return "Please fill all required fields."

        if password != confirm_password:
            return "Passwords do not match."

        if role not in [
            "student",
            "teacher"
        ]:
            return "Select valid role."

        if User.query.filter_by(
            email=email
        ).first():

            return "Email already exists."

        hashed_password = generate_password_hash(
            password
        )

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            role=role
        )

        db.session.add(new_user)

        db.session.commit()

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ==================================================
# LOGIN PAGE
# ==================================================

@app.route("/login")
def login():

    return render_template(
        "login.html"
    )


# ==================================================
# STUDENT LOGIN
# ==================================================

@app.route(
    "/student/login",
    methods=["GET", "POST"]
)
def student_login():

    if request.method == "POST":

        email = request.form.get(
            "email"
        )

        password = request.form.get(
            "password"
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if (
            user
            and check_password_hash(
                user.password,
                password
            )
        ):

            if user.role != "student":
                return "Not a student account."

            session["user_id"] = user.id
            session["user_name"] = user.name
            session["role"] = user.role

            return redirect(
                url_for(
                    "student_dashboard"
                )
            )

        return "Invalid login"

    return render_template(
        "student_login.html"
    )


# ==================================================
# TEACHER LOGIN
# ==================================================

@app.route(
    "/teacher/login",
    methods=["GET", "POST"]
)
def teacher_login():

    if request.method == "POST":

        email = request.form.get(
            "email"
        )

        password = request.form.get(
            "password"
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if (
            user
            and check_password_hash(
                user.password,
                password
            )
        ):

            if user.role != "teacher":
                return "Not a teacher account."

            session["user_id"] = user.id
            session["user_name"] = user.name
            session["role"] = user.role

            return redirect(
                url_for(
                    "teacher_dashboard"
                )
            )

        return "Invalid login"

    return render_template(
        "teacher_login.html"
    )


# ==================================================
# STUDENT DASHBOARD
# ==================================================

@app.route("/student/dashboard")
def student_dashboard():
    print("DASHBOARD SESSION:", dict(session))
    print("STUDENT ROLE:", session.get("role"))

    # CHECK STUDENT LOGIN

    if session.get("role") != "student":
        return redirect(
            url_for("login")
        )

    # GET STUDENT ID

    student_id = session.get("user_id")

    # GET STUDENT DETAILS

    student = db.session.get(
        User,
        student_id
    )

    if not student:
        return redirect(
            url_for("login")
        )

    # GET AVAILABLE QUIZZES

    quizzes = Quiz.query.filter_by(
        published=True
    ).order_by(
        Quiz.id.desc()
    ).all()

    # GET STUDENT RESULTS

    results = Result.query.filter_by(
        student_id=student_id
    ).order_by(
        Result.id.desc()
    ).all()

    # GET SAVED AI QUESTIONS

    saved_questions = SavedQuestion.query.filter_by(
        student_id=student_id
    ).order_by(
        SavedQuestion.id.desc()
    ).all()

    # TOTAL QUIZZES

    total_quizzes = len(
        quizzes
    )

    # COMPLETED QUIZZES

    completed = len(
        results
    )

    # AVERAGE SCORE

    avg_score = 0

    if results:

        avg_score = round(
            sum(
                r.percentage
                for r in results
            ) / len(results)
        )

    # RECENT RESULTS

    recent_results = results[:3]

    # RENDER STUDENT DASHBOARD

    return render_template(
        "student/dashboard.html",
        student=student,
        quizzes=quizzes,
        recent_results=recent_results,
        results=results,
        total_quizzes=total_quizzes,
        completed=completed,
        avg_score=avg_score,
        saved_questions=saved_questions
    )


# ==================================================
# STUDENT DOCUMENT UPLOAD
# ==================================================

@app.route(
    "/student/upload_document",
    methods=["POST"]
)
def student_upload_document():

    if session.get("role") != "student":
        return redirect(
            url_for("login")
        )

    if "document" not in request.files:

        return """
        <h2>Document Upload Error</h2>

        <p>
            Please select a document.
        </p>

        <a href="/student/dashboard">
            ← Back to Student Dashboard
        </a>
        """

    document = request.files["document"]

    if document.filename == "":

        return """
        <h2>Document Upload Error</h2>

        <p>
            Please select a document.
        </p>

        <a href="/student/dashboard">
            ← Back to Student Dashboard
        </a>
        """

    allowed_extensions = {
        "pdf",
        "docx",
        "txt"
    }

    filename = document.filename

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    if extension not in allowed_extensions:

        return """
        <h2>Invalid Document</h2>

        <p>
            Only PDF, DOCX and TXT files are allowed.
        </p>

        <a href="/student/dashboard">
            ← Back to Student Dashboard
        </a>
        """

    # ==================================================
    # SAFE FILENAME
    # ==================================================

    safe_name = os.path.basename(
        filename
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        safe_name
    )

    try:

        document.save(
            filepath
        )

        session["student_document"] = {

            "filename": safe_name,

            "filepath": filepath

        }

        session.modified = True

        return f"""
        <h2>Document Uploaded Successfully ✅</h2>

        <p>
            <strong>File:</strong>
            {safe_name}
        </p>

        <p>
            Your document has been uploaded successfully.
        </p>

        <a href="/student/dashboard">
            ← Back to Student Dashboard
        </a>
        """

    except Exception as e:

        print(
            "STUDENT DOCUMENT UPLOAD ERROR:",
            repr(e)
        )

        return f"""
        <h2>Document Upload Failed</h2>

        <p>
            Unable to upload the document.
        </p>

        <pre>{e}</pre>

        <a href="/student/dashboard">
            ← Back to Student Dashboard
        </a>
        """


# ==================================================
# STUDENT QUIZZES
# ==================================================

@app.route("/student/quizzes")
def student_quizzes():

    if session.get("role") != "student":
        return redirect(
            url_for("login")
        )

    quizzes = Quiz.query.filter_by(
        published=True
    ).order_by(
        Quiz.id.desc()
    ).all()

    return render_template(
        "student/quizzes.html",
        quizzes=quizzes
    )


# ==================================================
# START QUIZ
# ==================================================

@app.route(
    "/student/start_quiz/<int:quiz_id>"
)
def start_quiz(quiz_id):

    if session.get("role") != "student":
        return redirect(
            url_for("login")
        )

    quiz = Quiz.query.get_or_404(
        quiz_id
    )

    if not quiz.published:

        return """
        <h2>Quiz Not Available</h2>

        <p>
            This quiz is not published yet.
        </p>

        <a href="/student/quizzes">
            ← Back to Quizzes
        </a>
        """

    questions = Question.query.filter_by(
        quiz_id=quiz.id
    ).order_by(
        Question.id.asc()
    ).all()

    if not questions:

        return """
        <h2>Quiz Error</h2>

        <p>
            This quiz has no questions yet.
        </p>

        <a href="/student/quizzes">
            ← Back to Quizzes
        </a>
        """

    return render_template(
        "student/start_quiz.html",
        quiz=quiz,
        questions=questions,
        current_question=0
    )


# ==================================================
# SUBMIT NORMAL QUIZ
# ==================================================

@app.route(
    "/student/submit_quiz/<int:quiz_id>",
    methods=["POST"]
)
def submit_quiz(quiz_id):

    if session.get("role") != "student":
        return redirect(
            url_for("login")
        )

    quiz = Quiz.query.get_or_404(
        quiz_id
    )

    if not quiz.published:

        return """
        <h2>Quiz Not Available</h2>

        <p>
            This quiz is not published.
        </p>

        <a href="/student/dashboard">
            ← Back to Student Dashboard
        </a>
        """

    questions = Question.query.filter_by(
        quiz_id=quiz.id
    ).order_by(
        Question.id.asc()
    ).all()

    if not questions:

        return """
        <h2>Quiz Error</h2>

        <p>
            No questions were found.
        </p>

        <a href="/student/dashboard">
            ← Back to Student Dashboard
        </a>
        """

    score = 0

    total = 0

    student_answers = {}

    for question in questions:

        selected_answer = request.form.get(
            f"question_{question.id}"
        )

        student_answers[
            question.id
        ] = selected_answer

        marks = question.marks or 1

        total += marks

        if (
            selected_answer
            and
            selected_answer.strip().upper()
            ==
            str(
                question.correct_answer
            ).strip().upper()
        ):

            score += marks

    result = Result(

        student_id=session.get(
            "user_id"
        ),

        quiz_id=quiz.id,

        score=score,

        total=total

    )

    db.session.add(
        result
    )

    db.session.commit()

    return render_template(
        "student/result.html",
        quiz=quiz,
        result=result,
        score=score,
        total=total,
        questions=questions,
        student_answers=student_answers
    )



# ==================================================
# RESULTS HISTORY
# ==================================================

@app.route("/student/results")
def results_history():

    if session.get("role") != "student":
        return redirect(
            url_for("login")
        )

    results = Result.query.filter_by(
        student_id=session.get("user_id")
    ).order_by(
        Result.id.desc()
    ).all()

    return render_template(
        "student/results_history.html",
        results=results
    )

# ==================================================
# VIEW RESULT
# ==================================================

@app.route(
    "/student/result/<int:result_id>"
)
def view_result(result_id):

    if session.get("role") != "student":
        return redirect(
            url_for("login")
        )

    result = Result.query.get_or_404(
        result_id
    )

    # ==================================================
    # SECURITY CHECK
    # ==================================================

    if result.student_id != session.get(
        "user_id"
    ):

        return redirect(
            url_for("student_dashboard")
        )

    quiz = result.quiz

    questions = Question.query.filter_by(
        quiz_id=quiz.id
    ).order_by(
        Question.id.asc()
    ).all()

    return render_template(
        "student/result.html",
        quiz=quiz,
        result=result,
        score=result.score,
        total=result.total,
        questions=questions,
        student_answers={}
    )
    


# ==================================================
# AI QUIZ DRAFT
# ==================================================

class AIQuizDraft(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    topic = db.Column(
        db.String(200),
        nullable=False
    )

    difficulty = db.Column(
        db.String(20),
        default="Medium"
    )

    questions_json = db.Column(
        db.Text,
        nullable=False
    )


# ==================================================
# SAVED QUESTIONS
# ==================================================

class SavedQuestion(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    topic = db.Column(
        db.String(200),
        nullable=False
    )

    difficulty = db.Column(
        db.String(20),
        default="Medium"
    )

    questions_json = db.Column(
        db.Text,
        nullable=False
    )

    saved_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )

    student = db.relationship(
        "User",
        backref="saved_ai_questions"
    )




@app.route("/student/generate-quiz", methods=["GET"])
def generate_quiz_page():

    user_id = session.get("user_id")
    role = str(session.get("role", "")).strip().lower()

    if not user_id or role != "student":
        return redirect(url_for("login"))

    # Read selected AI Quiz Center panel
    mode = request.args.get("mode", "topic").strip().lower()

    if mode not in ["topic", "smart", "document"]:
        mode = "topic"

    return render_template(
        "student/ai_quiz.html",
        mode=mode
    )


# ==================================================
# AI QUIZ GENERATION - 3 AI QUIZ CENTER PANELS
# ==================================================

@app.route("/student/generate_ai_quiz", methods=["POST"])
def student_generate_ai_quiz():

    if (
        not session.get("user_id")
        or str(session.get("role", "")).lower() != "student"
    ):
        return redirect(url_for("login"))

    # --------------------------------------------------
    # PANEL MODE
    # --------------------------------------------------

    creation_mode = (
        request.form.get("creation_mode", "topic")
        .strip()
        .lower()
    )

    if creation_mode not in ["topic", "smart", "document"]:
        creation_mode = "topic"

    # --------------------------------------------------
    # BASIC FORM DATA
    # --------------------------------------------------

    topic = (
        request.form.get("topic")
        or request.form.get("subject")
        or ""
    ).strip()

    difficulty = request.form.get(
        "difficulty", "Medium"
    ).strip().capitalize()

    number = (
        request.form.get("number")
        or request.form.get("number_of_questions")
        or request.form.get("num_questions")
        or request.form.get("question_count")
        or "10"
    )

    # AI Quiz Generator always uses Practice Mode.
    if creation_mode == "topic":
        quiz_mode = "practice"
    else:
        quiz_mode = request.form.get(
            "quiz_mode", "practice"
        ).strip().lower()

    if quiz_mode not in ["practice", "test"]:
        quiz_mode = "practice"

    # --------------------------------------------------
    # QUESTION TYPES
    # --------------------------------------------------

    question_types = (
        request.form.getlist("question_types")
        or request.form.getlist("question_type")
        or ["MCQ"]
    )

    type_mapping = {
        "mcq": "MCQ",
        "multiple choice": "MCQ",
        "multiple-choice": "MCQ",

        "true/false": "True/False",
        "true_false": "True/False",
        "true false": "True/False",

        "fill in the blanks": "Fill in the Blanks",
        "fill in blanks": "Fill in the Blanks",
        "fill_blank": "Fill in the Blanks",
        "fill in blank": "Fill in the Blanks",
        "fill-in-the-blanks": "Fill in the Blanks"
    }

    all_types = [
        "MCQ",
        "True/False",
        "Fill in the Blanks"
    ]

    selected_types = []

    for q_type in question_types:

        normalized_input = str(q_type).strip().lower()

        if normalized_input == "mixed":
            selected_types = all_types.copy()
            break

        normalized = type_mapping.get(normalized_input)

        if normalized and normalized not in selected_types:
            selected_types.append(normalized)

    if not selected_types:
        return "Please select a valid question type."

    # --------------------------------------------------
    # QUESTION COUNT AND DIFFICULTY
    # --------------------------------------------------

    try:
        number = int(number)

    except (ValueError, TypeError):
        return "Invalid number of questions."

    if number < 1 or number > 20:
        return "Select between 1 and 20 questions."

    if difficulty not in ["Easy", "Medium", "Hard"]:
        difficulty = "Medium"

    

    # --------------------------------------------------
    # DOCUMENT EXTRACTION
    # --------------------------------------------------

    uploaded_file = request.files.get("document")

    document_text = ""
    document_filename = ""

    if uploaded_file and uploaded_file.filename:

        document_filename = secure_filename(
            uploaded_file.filename
        )

        extension = (
            document_filename.rsplit(".", 1)[-1].lower()
            if "." in document_filename
            else ""
        )

        allowed_extensions = ["pdf", "docx", "txt"]

        if extension not in allowed_extensions:
            return """
            <h2>Invalid Document</h2>
            <p>Please upload PDF, DOCX or TXT files only.</p>
            <a href="/student/generate-quiz">Go Back</a>
            """

        try:

            file_bytes = uploaded_file.read(
                8 * 1024 * 1024 + 1
            )

            if not file_bytes:
                return "The uploaded document is empty."

            if len(file_bytes) > 8 * 1024 * 1024:
                return """
                <h2>File Too Large</h2>
                <p>Please upload a document smaller than 8 MB.</p>
                <a href="/student/generate-quiz">Go Back</a>
                """

            # PDF - TEXT EXTRACTION + OCR
            if extension == "pdf":

                pdf = pymupdf.open(
                    stream=file_bytes,
                    filetype="pdf"
                )

                try:

                    if pdf.is_encrypted:
                        return """
                        <h2>Password Protected PDF</h2>
                        <p>Please upload an unlocked PDF.</p>
                        <a href="/student/generate-quiz">Go Back</a>
                        """

                    extracted_pages = []

                    for page in pdf:

                        page_text = page.get_text("text") or ""

                        # OCR scanned pages or pages with little text
                        if len(page_text.strip()) < 30:

                            pix = page.get_pixmap(
                                matrix=pymupdf.Matrix(2, 2),
                                alpha=False
                            )

                            image = np.frombuffer(
                                pix.samples,
                                dtype=np.uint8
                            ).reshape(
                                pix.height,
                                pix.width,
                                pix.n
                            )

                            ocr_results = ocr_reader.readtext(
                                image,
                                detail=0,
                                paragraph=True
                            )

                            ocr_text = "\n".join(ocr_results)

                            if len(ocr_text.strip()) > len(page_text.strip()):
                                page_text = ocr_text

                        if page_text.strip():
                            extracted_pages.append(page_text)

                    document_text = "\n".join(extracted_pages)

                finally:
                    pdf.close()

            # DOCX
            elif extension == "docx":

                doc = Document(BytesIO(file_bytes))

                paragraphs = [
                    paragraph.text.strip()
                    for paragraph in doc.paragraphs
                    if paragraph.text.strip()
                ]

                document_text = "\n".join(paragraphs)

                # Extract tables also
                for table in doc.tables:

                    for row in table.rows:

                        row_text = " | ".join(
                            cell.text.strip()
                            for cell in row.cells
                            if cell.text.strip()
                        )

                        if row_text:
                            document_text += "\n" + row_text

            # TXT
            elif extension == "txt":

                try:
                    document_text = file_bytes.decode(
                        "utf-8-sig"
                    )

                except UnicodeDecodeError:
                    document_text = file_bytes.decode(
                        "cp1252",
                        errors="replace"
                    )

            document_text = document_text.strip()

            if not document_text:
                return """
                <h2>No Readable Text Found</h2>
                <p>No readable text was found in this document.</p>
                <a href="/student/generate-quiz">Go Back</a>
                """

            print("DOCUMENT:", document_filename)
            print("EXTRACTED TEXT LENGTH:", len(document_text))

        except Exception as e:

            print("DOCUMENT EXTRACTION ERROR:", repr(e))
            traceback.print_exc()

            return """
            <h2>Document Reading Failed</h2>
            <p>Unable to read the uploaded document.</p>
            <a href="/student/generate-quiz">Try Again</a>
            """


    #----------------------------------
    # PANEL-WISE VALIDATION
    # --------------------------------------------------

    if creation_mode == "topic" and not topic:
        return """
        <h2>Topic Required</h2>
        <p>Please enter a topic to generate your AI quiz.</p>
        <a href="/student/generate-quiz?mode=topic">Go Back</a>
        """

    if creation_mode == "smart" and not topic:
        return """
        <h2>Topic Required</h2>
        <p>Please enter a topic for Smart Quiz Creation.</p>
        <a href="/student/generate-quiz?mode=smart">Go Back</a>
        """

    if creation_mode == "document" and not document_text:
        return """
        <h2>Document Required</h2>
        <p>Please upload a readable PDF, DOCX or TXT document.</p>
        <a href="/student/generate-quiz?mode=document">Go Back</a>
        """

    if not topic and not document_text:
        return """
        <h2>Missing Study Material</h2>
        <p>Please enter a topic or upload a study document.</p>
        <a href="/student/generate-quiz">Go Back</a>
        """

    # --------------------------------------------------
    # AI SOURCE INSTRUCTIONS
    # --------------------------------------------------

    if document_text:

        # Limit document text to reduce API token usage.
        source_text = document_text[:8000]

        quiz_topic = topic if topic else document_filename

        source_instruction = f"""
STUDY DOCUMENT CONTENT:

{source_text}

DOCUMENT RULES:
- Generate questions using the uploaded document.
- Use only information supported by the document.
- Do not introduce unrelated topics.
- Do not invent facts that are not present in the document.
"""

    else:

        quiz_topic = topic

        source_instruction = f"""
QUIZ TOPIC:

{topic}

Generate questions using established educational knowledge
about this topic.
"""

    # --------------------------------------------------
    # GROQ API
    # --------------------------------------------------

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
       return """
        <h2>Groq API Key Missing</h2>
        <p>Please configure your GROQ_API_KEY.</p>
        <a href="/student/generate-quiz">Go Back</a>
        """

    try:
        client = Groq(api_key=api_key)

        # --------------------------------------------------
        # AI PROMPT
        # --------------------------------------------------

        prompt = f"""
You are an expert educational quiz generator.

Generate EXACTLY {number} questions.

{source_instruction}

Difficulty: {difficulty}

Selected question types:
{", ".join(selected_types)}

IMPORTANT INSTRUCTIONS:

1. Generate exactly {number} questions.
2. Distribute selected question types as evenly as possible.
3. Do not repeat questions.
4. Match the selected difficulty.
5. Every question must have a correct answer and explanation.
6. Use only the selected question types.
7. Return all questions in a valid JSON array.

JSON FORMAT:

[
    {{
        "type": "MCQ",
        "question": "Question text",
        "option_a": "Option A",
        "option_b": "Option B",
        "option_c": "Option C",
        "option_d": "Option D",
        "correct_answer": "A",
        "explanation": "Explanation"
    }}
]

MCQ RULES:

- type = MCQ
- Provide four meaningful options.
- correct_answer must be A, B, C or D.

TRUE/FALSE RULES:

- type = True/False
- option_a = True
- option_b = False
- option_c = ""
- option_d = ""
- correct_answer = A or B.

FILL IN THE BLANKS RULES:

- type = Fill in the Blanks
- Question must contain _____.
- All options must be empty.
- correct_answer must contain the missing word.

Every question must include an explanation.

Generate exactly {number} questions.

Return valid JSON only.
Do not include markdown or additional text.
"""

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.2,
            max_tokens=8000
        )

        ai_text = (
            response.choices[0].message.content or ""
        ).strip()

        # --------------------------------------------------
        # CLEAN AI RESPONSE
        # --------------------------------------------------

        if ai_text.startswith("```"):

            ai_text = ai_text.replace("```json", "")
            ai_text = ai_text.replace("```", "").strip()

        decoder = json.JSONDecoder()

        json_start = -1

        for index, character in enumerate(ai_text):

            if character in "[{":
                json_start = index
                break

        if json_start == -1:
            raise json.JSONDecodeError(
                "JSON not found",
                ai_text,
                0
            )

        data, _ = decoder.raw_decode(
            ai_text[json_start:]
        )

        if isinstance(data, dict):

            questions = data.get(
                "questions",
                data.get("quiz", [])
            )

        else:
            questions = data

        if not isinstance(questions, list):
            raise ValueError("Invalid question format.")

        # --------------------------------------------------
        # VALIDATE QUESTIONS
        # --------------------------------------------------

        clean_questions = []

        for q in questions:

            if not isinstance(q, dict):
                continue

            q_type = str(
                q.get("type", "MCQ")
            ).strip()

            q_type = type_mapping.get(
                q_type.lower(),
                q_type
            )

            question = str(
                q.get("question", "")
            ).strip()

            answer = str(
                q.get("correct_answer", "")
            ).strip()

            explanation = str(
                q.get("explanation", "")
            ).strip()

            item = {
                "type": q_type,
                "question": question,

                "option_a": str(
                    q.get("option_a", "")
                ).strip(),

                "option_b": str(
                    q.get("option_b", "")
                ).strip(),

                "option_c": str(
                    q.get("option_c", "")
                ).strip(),

                "option_d": str(
                    q.get("option_d", "")
                ).strip(),

                "correct_answer": answer,
                "explanation": explanation
            }

            if not question or not explanation:
                continue

            if q_type not in selected_types:
                continue

            # MCQ
            if q_type == "MCQ":

                item["correct_answer"] = answer.upper()

                if (
                    item["option_a"]
                    and item["option_b"]
                    and item["option_c"]
                    and item["option_d"]
                    and item["correct_answer"] in ["A", "B", "C", "D"]
                ):
                    clean_questions.append(item)

            # TRUE/FALSE
            elif q_type == "True/False":

                answer = answer.upper()

                if answer == "TRUE":
                    answer = "A"

                elif answer == "FALSE":
                    answer = "B"

                item["option_a"] = "True"
                item["option_b"] = "False"
                item["option_c"] = ""
                item["option_d"] = ""

                item["correct_answer"] = answer

                if answer in ["A", "B"]:
                    clean_questions.append(item)

            # FILL IN THE BLANKS
            elif q_type == "Fill in the Blanks":

                if "_____" in question and answer:

                    item["option_a"] = ""
                    item["option_b"] = ""
                    item["option_c"] = ""
                    item["option_d"] = ""

                    clean_questions.append(item)

        clean_questions = clean_questions[:number]

        # --------------------------------------------------
        # CHECK QUESTION COUNT
        # --------------------------------------------------

        if len(clean_questions) != number:

            return f"""
            <h2>Quiz Generation Incomplete</h2>

            <p>Requested: {number}</p>

            <p>Generated: {len(clean_questions)}</p>

            <p>Please try again with a smaller question count.</p>

            <a href="/student/generate-quiz?mode={creation_mode}">
                Try Again
            </a>
            """

                # --------------------------------------------------
        # SAVE QUIZ - DOCUMENT PANEL USES DATABASE
        # --------------------------------------------------

        if creation_mode == "document":

            try:
                draft = AIQuizDraft(
                    student_id=session.get("user_id"),
                    topic=quiz_topic,
                    difficulty=difficulty,
                    questions_json=json.dumps(clean_questions)
                )

                db.session.add(draft)
                db.session.commit()

                # Store only small metadata in session.
                session["student_ai_quiz"] = {
                    "topic": quiz_topic,
                    "difficulty": difficulty,
                    "quiz_mode": quiz_mode,
                    "creation_mode": "document",
                    "question_types": selected_types,
                    "document_filename": document_filename,
                    "draft_id": draft.id
                }

                session.modified = True

            except Exception:
                db.session.rollback()
                raise

        else:

            # Existing Topic and Smart Quiz workflow unchanged.
            session["student_ai_quiz"] = {
                "topic": quiz_topic,
                "difficulty": difficulty,
                "quiz_mode": quiz_mode,
                "creation_mode": creation_mode,
                "question_types": selected_types,
                "document_filename": document_filename,
                "questions": clean_questions
            }
                
            session.modified = True

        

        if quiz_mode == "test":
            return render_template(
                "student/ai_test_quiz.html",
                topic=quiz_topic,
                difficulty=difficulty,
                questions=clean_questions,
                total=len(clean_questions)
            )
        else:
            return render_template(
                "student/ai_generated_quiz.html",
                topic=quiz_topic,
                difficulty=difficulty,
                questions=clean_questions,
                total=len(clean_questions)
            )
    

    except json.JSONDecodeError:

        return """
        <h2>AI Response Error</h2>
        <p>AI returned invalid JSON. Please try again.</p>
        <a href="/student/generate-quiz">Go Back</a>
        """

    except Exception as e:

        print("STUDENT AI QUIZ ERROR:", repr(e))
        traceback.print_exc()

        return f"""
        <h2>AI Quiz Generation Failed</h2>
        <p>{str(e)}</p>
        <a href="/student/generate-quiz">Go Back</a>
        """
# ==================================================    
# STUDENT SAVED QUESTIONS
# ==================================================

@app.route("/student/saved-questions")
def student_saved_questions():

    if not session.get("user_id") or str(
        session.get("role", "")
    ).lower() != "student":
        return redirect(url_for("login"))

    saved_questions = SavedQuestion.query.filter_by(
        student_id=session.get("user_id")
    ).order_by(
        SavedQuestion.id.desc()
    ).all()

    for item in saved_questions:

        try:
            item.questions_list = json.loads(
                item.questions_json or "[]"
            )

        except (TypeError, json.JSONDecodeError):
            item.questions_list = []

    return render_template(
        "student/saved_questions.html",
        saved_questions=saved_questions
    )

# ==================================================
# SAVE AI GENERATED QUESTIONS
# ==================================================

@app.route("/student/save-ai-questions", methods=["POST"])
def student_save_ai_questions():

    if not session.get("user_id") or str(
        session.get("role", "")
    ).lower() != "student":
        return redirect(url_for("login"))

    ai_quiz = session.get("student_ai_quiz")

    if not ai_quiz:
        return redirect(url_for("generate_quiz_page"))

    if ai_quiz.get("creation_mode") == "document":

        draft = AIQuizDraft.query.filter_by(
            id=ai_quiz.get("draft_id"),
            student_id=session.get("user_id")
        ).first()

        if not draft:
            return redirect(
                url_for("generate_quiz_page", mode="document")
            )

        try:
            questions_data = json.loads(
                draft.questions_json or "[]"
            )
        except (TypeError, json.JSONDecodeError):
            questions_data = []

    else:
        questions_data = ai_quiz.get("questions", [])

    if not questions_data:
        return redirect(url_for("generate_quiz_page"))

    try:
        saved = SavedQuestion(
            student_id=session.get("user_id"),
            topic=ai_quiz.get("topic", "AI Quiz"),
            difficulty=ai_quiz.get("difficulty", "Medium"),
            questions_json=json.dumps(questions_data)
        )

        db.session.add(saved)
        db.session.commit()

        return redirect(url_for("student_saved_questions"))

    except Exception as e:
        db.session.rollback()
        print("SAVE AI QUESTIONS ERROR:", e)

        return "Unable to save questions. Please try again."
# ==================================================
# RESTART AI TEST
# ==================================================

@app.route("/student/restart-ai-test")
def student_restart_ai_test():

    if (
        not session.get("user_id")
        or str(session.get("role", "")).strip().lower() != "student"
    ):
        return redirect(url_for("login"))

    quiz_data = session.get("student_ai_quiz")

    if not quiz_data:
        return redirect(
            url_for("generate_quiz_page")
        )

    if quiz_data.get("creation_mode") == "document":

        draft = AIQuizDraft.query.filter_by(
            id=quiz_data.get("draft_id"),
            student_id=session.get("user_id")
        ).first()

        if not draft:
            return redirect(
                url_for("generate_quiz_page", mode="document")
            )

        try:
            questions = json.loads(
                draft.questions_json or "[]"
            )
        except (TypeError, json.JSONDecodeError):
            questions = []

    else:
        questions = quiz_data.get("questions", [])

    if not questions:
        return redirect(
            url_for("generate_quiz_page")
        )

    # Hide correct answers from the test page.
    display_questions = []

    for question in questions:

        display_questions.append({
            "type": question.get("type", "MCQ"),
            "question": question.get("question", ""),
            "option_a": question.get("option_a", ""),
            "option_b": question.get("option_b", ""),
            "option_c": question.get("option_c", ""),
            "option_d": question.get("option_d", "")
        })

    return render_template(
        "student/ai_test_quiz.html",
        topic=quiz_data.get("topic", "AI Quiz"),
        difficulty=quiz_data.get("difficulty", "Medium"),
        questions=display_questions,
        total=len(display_questions)
    )

@app.route("/student/submit-ai-test", methods=["POST"])
def student_submit_ai_test():

    if (
        not session.get("user_id")
        or str(session.get("role", "")).strip().lower() != "student"
    ):
        return redirect(url_for("login"))

    quiz_data = session.get("student_ai_quiz")

    if not quiz_data:
        return redirect(url_for("generate_quiz_page"))

    if quiz_data.get("creation_mode") == "document":

        draft = AIQuizDraft.query.filter_by(
            id=quiz_data.get("draft_id"),
            student_id=session.get("user_id")
        ).first()

        if not draft:
            return redirect(
                url_for("generate_quiz_page", mode="document")
            )

        try:
            questions = json.loads(
                draft.questions_json or "[]"
            )
        except (TypeError, json.JSONDecodeError):
            questions = []

    else:
        questions = quiz_data.get("questions", [])

    if not questions:
        return redirect(url_for("generate_quiz_page"))
    
    def normalize(value):
        """Normalize answers for comparison."""
        return " ".join(
            str(value or "").strip().casefold().split()
        )

    results = []
    score = 0

    for index, question in enumerate(questions):

        selected = str(
            request.form.get(f"answer_{index}", "")
        ).strip()

        correct = str(
            question.get("correct_answer", "")
        ).strip()

        q_type = str(
            question.get("type", "MCQ")
        ).strip().lower()

        option_map = {
            "A": str(question.get("option_a", "")).strip(),
            "B": str(question.get("option_b", "")).strip(),
            "C": str(question.get("option_c", "")).strip(),
            "D": str(question.get("option_d", "")).strip()
        }

        selected_upper = selected.upper()
        correct_upper = correct.upper()

        selected_display = selected
        correct_display = correct

        # ==========================================
        # FILL IN THE BLANKS
        # ==========================================

        if q_type in [
            "fill in the blanks",
            "fill in the blank",
            "fill in blank",
            "fill_blank",
            "fill_blanks"
        ]:

            accepted_answers = [correct]

            # Optional alternative answers
            alternatives = question.get(
                "alternative_answers", []
            )

            if isinstance(alternatives, str):
                alternatives = [alternatives]

            if isinstance(alternatives, list):
                accepted_answers.extend(alternatives)

            is_correct = (
                bool(selected)
                and normalize(selected) in [
                    normalize(answer)
                    for answer in accepted_answers
                    if str(answer).strip()
                ]
            )

            selected_display = selected
            correct_display = correct

        # ==========================================
        # TRUE / FALSE
        # ==========================================

        elif q_type in [
            "true/false",
            "true or false",
            "true_false",
            "true false"
        ]:

            # Frontend sends A for True and B for False.
            if correct_upper in ["TRUE", "A", "OPTION A"]:
                correct_letter = "A"
                correct_display = "True"

            elif correct_upper in ["FALSE", "B", "OPTION B"]:
                correct_letter = "B"
                correct_display = "False"

            else:
                correct_letter = correct_upper

            if selected_upper == "A":
                selected_display = "True"

            elif selected_upper == "B":
                selected_display = "False"

            else:
                selected_display = selected

            is_correct = (
                bool(selected)
                and selected_upper == correct_letter
            )

        # ==========================================
        # MCQ
        # ==========================================

        else:

            # Accept A, B, C, D or Option A formats.
            if correct_upper.startswith("OPTION "):
                correct_upper = correct_upper.replace(
                    "OPTION ", "", 1
                ).strip()

            if correct_upper in option_map:
                correct_letter = correct_upper

            else:
                # Also match the actual option text.
                correct_letter = ""

                for letter, option_text in option_map.items():
                    if (
                        normalize(correct) == normalize(option_text)
                        and option_text
                    ):
                        correct_letter = letter
                        break

            # Handle selected option.
            if selected_upper.startswith("OPTION "):
                selected_upper = selected_upper.replace(
                    "OPTION ", "", 1
                ).strip()

            if selected_upper in option_map:
                selected_letter = selected_upper
                selected_display = (
                    f"{selected_letter}. "
                    f"{option_map[selected_letter]}"
                )

            else:
                selected_letter = ""

                for letter, option_text in option_map.items():
                    if (
                        normalize(selected) == normalize(option_text)
                        and option_text
                    ):
                        selected_letter = letter
                        selected_display = (
                            f"{letter}. {option_text}"
                        )
                        break

            if correct_letter in option_map:
                correct_display = (
                    f"{correct_letter}. "
                    f"{option_map[correct_letter]}"
                )

            is_correct = (
                bool(selected)
                and bool(correct_letter)
                and selected_letter == correct_letter
            )

        # ==========================================
        # CALCULATE SCORE
        # ==========================================

        if is_correct:
            score += 1

        results.append({
            "question": question.get("question", ""),
            "type": question.get("type", "MCQ"),

            "selected_answer": selected_display,
            "correct_answer": correct_display,

            "selected_answer_text": selected_display,
            "correct_answer_text": correct_display,

            "option_a": option_map["A"],
            "option_b": option_map["B"],
            "option_c": option_map["C"],
            "option_d": option_map["D"],

            "explanation": question.get("explanation", ""),
            "is_correct": is_correct
        })

    # ==========================================
    # FINAL RESULT
    # ==========================================

    total = len(questions)

    percentage = round(
        (score / total) * 100, 2
    ) if total else 0

    print("========== AI TEST RESULT ==========")
    print("Total Questions:", total)
    print("Correct Answers:", score)
    print("Incorrect Answers:", total - score)
    print("Percentage:", percentage)
    print("====================================")

    return render_template(
        "student/ai_test_result.html",
        topic=quiz_data.get("topic", "AI Quiz"),
        difficulty=quiz_data.get("difficulty", "Medium"),
        results=results,
        score=score,
        total=total,
        percentage=percentage
    )
# ==================================================
# TEACHER DASHBOARD
# ==================================================

@app.route("/teacher/dashboard")
def teacher_dashboard():

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    if not user:
        return redirect(
            url_for("login")
        )

    quizzes = Quiz.query.filter_by(
        teacher_id=user.id
    ).all()

    quiz_ids = [
        q.id
        for q in quizzes
    ]

    if quiz_ids:

        results = Result.query.filter(
            Result.quiz_id.in_(quiz_ids)
        ).all()

    else:

        results = []

    student_ids = list(
        set(
            r.student_id
            for r in results
        )
    )

    if student_ids:

        students = User.query.filter(
            User.id.in_(student_ids)
        ).all()

    else:

        students = []

    total_quizzes = len(
        quizzes
    )

    total_students = len(
        students
    )

    total_attempts = len(
        results
    )

    avg_score = 0
    highest = 0
    lowest = 0

    if results:

        scores = [
            r.percentage
            for r in results
            if r.percentage is not None
        ]

        if scores:

            avg_score = round(
                sum(scores)
                / len(scores),
                2
            )

            highest = max(scores)

            lowest = min(scores)

    return render_template(
        "teacher/dashboard.html",
        user=user,
        quizzes=quizzes,
        results=results,
        total_quizzes=total_quizzes,
        total_students=total_students,
        total_attempts=total_attempts,
        avg_score=avg_score,
        highest=highest,
        lowest=lowest
    )


# ==================================================
# MY QUIZZES
# ==================================================

@app.route("/teacher/my_quizzes")
def my_quizzes():

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    quizzes = Quiz.query.filter_by(
        teacher_id=session.get(
            "user_id"
        )
    ).order_by(
        Quiz.id.desc()
    ).all()

    return render_template(
        "teacher/my_quizzes.html",
        quizzes=quizzes
    )


# ==================================================
# DELETE QUIZ
# ==================================================

@app.route(
    "/teacher/delete_quiz/<int:quiz_id>"
)
def delete_quiz(quiz_id):

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    quiz = Quiz.query.get_or_404(
        quiz_id
    )

    if quiz.teacher_id != session.get(
        "user_id"
    ):
        return "Unauthorized access."

    db.session.delete(
        quiz
    )

    db.session.commit()

    return redirect(
        url_for("my_quizzes")
    )


# ==================================================
# AI QUIZ CENTER
# ==================================================

@app.route("/teacher/ai_quiz")
def ai_quiz():

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session.get("user_id")
    )

    if not user:
        return redirect(
            url_for("login")
        )

    return render_template(
        "teacher/ai_quiz.html",
        user=user
    )


# ==================================================
# UPLOAD DOCUMENT
# ==================================================

@app.route(
    "/teacher/upload_document",
    methods=["POST"]
)
def upload_document():

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    file = request.files.get(
        "document"
    )

    if not file:
        return "Please select a document."

    if file.filename == "":
        return "Please select a document."

    allowed_extensions = {
        "pdf",
        "docx",
        "txt"
    }

    extension = file.filename.rsplit(
        ".",
        1
    )[-1].lower()

    if extension not in allowed_extensions:
        return (
            "Only PDF, DOCX and TXT files are allowed."
        )

    upload_folder = os.path.join(
        "static",
        "uploads",
        "documents"
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    from werkzeug.utils import secure_filename

    filename = secure_filename(
        file.filename
    )

    filepath = os.path.join(
        upload_folder,
        filename
    )

    file.save(
        filepath
    )

    return redirect(
        url_for("ai_quiz")
    )


# ==================================================
# TEACHER AI QUIZ GENERATOR
# ==================================================

@app.route(
    "/teacher/generate_ai_quiz",
    methods=["POST"]
)
def generate_ai_quiz():

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    topic = request.form.get(
        "topic",
        ""
    ).strip()

    difficulty = request.form.get(
        "difficulty",
        "Medium"
    )

    number_of_questions = request.form.get(
        "number_of_questions",
        "10"
    )

    if not topic:
        return "Please enter a topic."

    try:

        number_of_questions = int(
            number_of_questions
        )

    except (
        ValueError,
        TypeError
    ):

        return "Invalid number of questions."

    if number_of_questions < 1:
        return "Number of questions must be at least 1."

    if number_of_questions > 20:
        return (
            "Maximum 20 questions allowed per generation."
        )

    # ==================================================
    # GROQ API KEY
    # ==================================================

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        return """
        <h2>Groq API Key Not Found</h2>

        <p>
            GROQ_API_KEY is not available.
        </p>

        <a href="/teacher/ai_quiz">
            ← Back to AI Quiz Center
        </a>
        """

    # ==================================================
    # GROQ CLIENT
    # ==================================================

    try:

        client = Groq(
            api_key=api_key
        )

    except Exception as e:

        return f"""
        <h2>Groq Client Error</h2>

        <p>
            {str(e)}
        </p>

        <a href="/teacher/ai_quiz">
            ← Back to AI Quiz Center
        </a>
        """

    # ==================================================
    # AI PROMPT
    # ==================================================

    prompt = f"""
Generate exactly {number_of_questions}
multiple choice questions about "{topic}".

Difficulty: {difficulty}

Return valid JSON only. No markdown.

Each question must contain:

question
option_a
option_b
option_c
option_d
correct_answer
explanation

correct_answer must be exactly A, B, C, or D.

No markdown.
No ```json.
No text before or after the JSON.

Keep questions and explanations concise.

Return exactly {number_of_questions} complete questions.
"""

    # ==================================================
    # CALL GROQ
    # ==================================================

    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.2,

            max_tokens=8000
        )

        # ==================================================
        # GET AI RESPONSE
        # ==================================================

        ai_text = ai_text = (
    response.choices[0].message.content or ""
).strip()
        print("GROQ RAW AI RESPONSE:", repr(ai_text[:3000]))

        # ==================================================
        # REMOVE MARKDOWN
        # ==================================================

        if ai_text.startswith("```"):

            ai_text = ai_text.replace(
                "```json",
                ""
            )

            ai_text = ai_text.replace(
                "```",
                ""
            )

            ai_text = ai_text.strip()

        # ==================================================
        # PARSE JSON
        # ==================================================

        try:

            data = json.loads(
                ai_text
            )

        except json.JSONDecodeError as e:

            return f"""
            <h2>AI Generation Error</h2>

            <p>
                AI returned incomplete or invalid JSON.
            </p>

            <p>
                Error: {str(e)}
            </p>

            <p>
                Please try generating again.
            </p>

            <a href="{url_for('ai_quiz')}">
                ← Back to AI Quiz Center
            </a>
            """

        # ==================================================
        # GET QUESTIONS
        # ==================================================

        if isinstance(
            data,
            dict
        ):

            if "questions" in data:

                questions = data[
                    "questions"
                ]

            elif "quiz" in data:

                questions = data[
                    "quiz"
                ]

            else:

                return """
                <h2>AI Generation Error</h2>

                <p>
                    JSON received but questions
                    were not found.
                </p>

                <a href="/teacher/ai_quiz">
                    ← Back to AI Quiz Center
                </a>
                """

        elif isinstance(
            data,
            list
        ):

            questions = data

        else:

            return """
            <h2>AI Generation Error</h2>

            <p>
                AI returned invalid data.
            </p>

            <a href="/teacher/ai_quiz">
                ← Back to AI Quiz Center
            </a>
            """

        # ==================================================
        # VALIDATE QUESTIONS
        # ==================================================

        clean_questions = []

        for q in questions:

            if not isinstance(
                q,
                dict
            ):
                continue

            question_text = str(
                q.get(
                    "question",
                    ""
                )
            ).strip()

            option_a = str(
                q.get(
                    "option_a",
                    ""
                )
            ).strip()

            option_b = str(
                q.get(
                    "option_b",
                    ""
                )
            ).strip()

            option_c = str(
                q.get(
                    "option_c",
                    ""
                )
            ).strip()

            option_d = str(
                q.get(
                    "option_d",
                    ""
                )
            ).strip()

            correct_answer = str(
                q.get(
                    "correct_answer",
                    ""
                )
            ).strip().upper()

            explanation = str(
                q.get(
                    "explanation",
                    ""
                )
            ).strip()

            if not question_text:
                continue

            if not option_a:
                continue

            if not option_b:
                continue

            if not option_c:
                continue

            if not option_d:
                continue

            if correct_answer not in [
                "A",
                "B",
                "C",
                "D"
            ]:
                continue

            clean_questions.append({

                "question": question_text,

                "option_a": option_a,

                "option_b": option_b,

                "option_c": option_c,

                "option_d": option_d,

                "correct_answer": correct_answer,

                "explanation": explanation

            })

        # ==================================================
        # CHECK QUESTIONS
        # ==================================================

        if not clean_questions:

            return """
            <h2>AI Generation Error</h2>

            <p>
                No valid questions were generated.
            </p>

            <a href="/teacher/ai_quiz">
                ← Back to AI Quiz Center
            </a>
            """

        # ==================================================
        # LIMIT QUESTIONS
        # ==================================================

        clean_questions = clean_questions[
            :number_of_questions
        ]

        # ==================================================
        # SAVE IN SESSION
        # ==================================================

        session[
            "ai_quiz_questions"
        ] = clean_questions

        session[
            "ai_quiz_topic"
        ] = topic

        session[
            "ai_quiz_difficulty"
        ] = difficulty

        session.modified = True

        # ==================================================
        # DISPLAY QUESTIONS
        # ==================================================

        return render_template(

            "teacher/ai_generated_quiz.html",

            topic=topic,

            difficulty=difficulty,

            questions=clean_questions

        )

    except Exception as e:

        return f"""
        <h2>AI Generation Error</h2>

        <p>
            {str(e)}
        </p>

        <br>

        <a href="{url_for('ai_quiz')}">
            ← Back to AI Quiz Center
        </a>
        """


# ==================================================
# SAVE TEACHER AI GENERATED QUIZ
# ==================================================

@app.route(
    "/teacher/save_ai_quiz",
    methods=["POST"]
)
def save_ai_quiz():

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    questions = session.get(
        "ai_quiz_questions"
    )

    topic = session.get(
        "ai_quiz_topic",
        "AI Generated Quiz"
    )

    difficulty = session.get(
        "ai_quiz_difficulty",
        "Medium"
    )

    if not questions:

        return """
        <h2>Save Quiz Error</h2>

        <p>
            No AI generated questions found.
        </p>

        <a href="/teacher/ai_quiz">
            ← Back to AI Quiz Center
        </a>
        """

    if not isinstance(
        questions,
        list
    ):

        return """
        <h2>Save Quiz Error</h2>

        <p>
            Invalid AI question format.
        </p>

        <a href="/teacher/ai_quiz">
            ← Back to AI Quiz Center
        </a>
        """

    try:

        quiz = Quiz(

            title=f"AI Quiz - {topic}",

            description=(
                f"AI generated quiz about {topic}"
            ),

            subject=topic,

            difficulty=difficulty,

            question_type="MCQ",

            number_of_questions=len(
                questions
            ),

            total_questions=len(
                questions
            ),

            passing_marks=(
                len(questions) // 2
            ) + 1,

            duration=30,

            published=False,

            teacher_id=session.get(
                "user_id"
            )

        )

        db.session.add(
            quiz
        )

        db.session.flush()

        for q in questions:

            correct_answer = str(
                q.get(
                    "correct_answer",
                    ""
                )
            ).strip().upper()

            new_question = Question(

                quiz_id=quiz.id,

                question=str(
                    q.get(
                        "question",
                        ""
                    )
                ).strip(),

                option_a=str(
                    q.get(
                        "option_a",
                        ""
                    )
                ).strip(),

                option_b=str(
                    q.get(
                        "option_b",
                        ""
                    )
                ).strip(),

                option_c=str(
                    q.get(
                        "option_c",
                        ""
                    )
                ).strip(),

                option_d=str(
                    q.get(
                        "option_d",
                        ""
                    )
                ).strip(),

                answer=correct_answer,

                correct_answer=correct_answer,

                explanation=str(
                    q.get(
                        "explanation",
                        ""
                    )
                ).strip(),

                marks=1

            )

            db.session.add(
                new_question
            )

        db.session.commit()

        session.pop(
            "ai_quiz_questions",
            None
        )

        session.pop(
            "ai_quiz_topic",
            None
        )

        session.pop(
            "ai_quiz_difficulty",
            None
        )

        session.modified = True

        return redirect(
            url_for("my_quizzes")
        )

    except Exception as e:

        db.session.rollback()

        print(
            "SAVE TEACHER AI QUIZ ERROR:",
            repr(e)
        )

        return f"""
        <h2>Unable to Save AI Quiz</h2>

        <p>
            An error occurred while saving
            the AI quiz.
        </p>

        <pre>{e}</pre>

        <a href="/teacher/ai_quiz">
            ← Back to AI Quiz Center
        </a>
        """


# ==================================================
# CREATE QUIZ
# ==================================================

@app.route(
    "/teacher/create_quiz",
    methods=["GET", "POST"]
)
def create_quiz():

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        title = request.form.get(
            "title"
        )

        description = request.form.get(
            "description"
        )

        subject = request.form.get(
            "subject"
        )

        duration = request.form.get(
            "duration"
        )

        difficulty = request.form.get(
            "difficulty"
        )

        published = request.form.get(
            "published"
        )

        total_questions = request.form.get(
            "total_questions"
        )

        if (
            not title
            or not subject
            or not duration
            or not total_questions
        ):

            return (
                "Please fill all required fields."
            )

        try:

            duration = int(
                duration
            )

            total_questions = int(
                total_questions
            )

        except (
            ValueError,
            TypeError
        ):

            return (
                "Duration and number of questions "
                "must be numbers."
            )

        if duration <= 0:
            return (
                "Duration must be greater than 0."
            )

        if total_questions <= 0:
            return (
                "Number of questions "
                "must be greater than 0."
            )

        passing_marks = (
            total_questions // 2
        ) + 1

        is_published = (
            published == "1"
        )

        quiz = Quiz(

            title=title,

            description=description,

            subject=subject,

            duration=duration,

            difficulty=difficulty,

            total_questions=total_questions,

            passing_marks=passing_marks,

            published=is_published,

            teacher_id=session.get(
                "user_id"
            )

        )

        db.session.add(
            quiz
        )

        db.session.commit()

        return redirect(
            url_for(
                "add_questions",
                quiz_id=quiz.id
            )
        )

    return render_template(
        "teacher/create_quiz.html"
    )


# ==================================================
# EDIT QUIZ
# ==================================================

@app.route(
    "/teacher/edit_quiz/<int:quiz_id>",
    methods=["GET", "POST"]
)
def edit_quiz(quiz_id):

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    quiz = Quiz.query.get_or_404(
        quiz_id
    )

    if quiz.teacher_id != session.get(
        "user_id"
    ):

        return "Unauthorized access."

    if request.method == "POST":

        quiz.title = request.form.get(
            "title"
        )

        quiz.description = request.form.get(
            "description"
        )

        quiz.subject = request.form.get(
            "subject"
        )

        quiz.duration = int(
            request.form.get(
                "duration"
            )
        )

        quiz.difficulty = request.form.get(
            "difficulty"
        )

        quiz.question_type = request.form.get(
            "question_type"
        )

        quiz.number_of_questions = int(
            request.form.get(
                "number_of_questions"
            )
        )

        quiz.passing_marks = int(
            request.form.get(
                "passing_marks"
            )
        )

        db.session.commit()

        return redirect(
            url_for("my_quizzes")
        )

    return render_template(
        "teacher/edit_quiz.html",
        quiz=quiz
    )


# ==================================================
# ADD QUESTIONS
# ==================================================

@app.route(
    "/teacher/add_questions/<int:quiz_id>",
    methods=["GET", "POST"]
)
def add_questions(quiz_id):

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    quiz = Quiz.query.get_or_404(
        quiz_id
    )

    if quiz.teacher_id != session.get(
        "user_id"
    ):

        return "Unauthorized access."

    questions = Question.query.filter_by(
        quiz_id=quiz.id
    ).all()

    if request.method == "POST":

        question_text = request.form.get(
            "question"
        )

        option_a = request.form.get(
            "option_a"
        )

        option_b = request.form.get(
            "option_b"
        )

        option_c = request.form.get(
            "option_c"
        )

        option_d = request.form.get(
            "option_d"
        )

        correct_answer = request.form.get(
            "correct_answer"
        )

        explanation = request.form.get(
            "explanation"
        )

        marks = request.form.get(
            "marks"
        )

        if (
            not question_text
            or not option_a
            or not option_b
            or not option_c
            or not option_d
            or not correct_answer
        ):

            return (
                "Please fill all required fields."
            )

        try:

            marks = int(
                marks
            )

        except (
            ValueError,
            TypeError
        ):

            marks = 1

        new_question = Question(

            quiz_id=quiz.id,

            question=question_text,

            option_a=option_a,

            option_b=option_b,

            option_c=option_c,

            option_d=option_d,

            answer=correct_answer,

            correct_answer=correct_answer,

            explanation=explanation,

            marks=marks

        )

        db.session.add(
            new_question
        )

        db.session.flush()

        quiz.total_questions = (
            Question.query.filter_by(
                quiz_id=quiz.id
            ).count()
        )

        db.session.commit()

        return redirect(
            url_for(
                "add_questions",
                quiz_id=quiz.id
            )
        )

    return render_template(
        "teacher/add_questions.html",
        quiz=quiz,
        questions=questions
    )


# ==================================================
# PREVIEW QUIZ
# ==================================================

@app.route(
    "/teacher/preview_quiz/<int:quiz_id>"
)
def preview_quiz(quiz_id):

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    quiz = Quiz.query.get_or_404(
        quiz_id
    )

    if quiz.teacher_id != session.get(
        "user_id"
    ):

        return "Unauthorized access."

    questions = Question.query.filter_by(
        quiz_id=quiz.id
    ).all()

    return render_template(
        "teacher/preview_quiz.html",
        quiz=quiz,
        questions=questions
    )


# ==================================================
# PUBLISH QUIZ
# ==================================================

@app.route(
    "/teacher/publish_quiz/<int:quiz_id>",
    methods=["POST"]
)
def publish_quiz(quiz_id):

    if session.get("role") != "teacher":
        return redirect(
            url_for("login")
        )

    quiz = Quiz.query.get_or_404(
        quiz_id
    )

    if quiz.teacher_id != session.get(
        "user_id"
    ):

        return "Unauthorized access."

    question_count = Question.query.filter_by(
        quiz_id=quiz.id
    ).count()

    if question_count == 0:

        return (
            "Please add at least one question "
            "before publishing."
        )

    quiz.published = True

    quiz.total_questions = question_count

    db.session.commit()

    return redirect(
        url_for("my_quizzes")
    )


# ==================================================
# PROFILE
# ==================================================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect(
            url_for("login")
        )

    user = db.session.get(
        User,
        session["user_id"]
    )

    if not user:
        return redirect(
            url_for("login")
        )

    total_quizzes = 0
    completed = 0
    avg_score = 0

    total_students = 0
    total_attempts = 0

    # ==================================================
    # STUDENT
    # ==================================================

    if user.role == "student":

        total_quizzes = Quiz.query.filter_by(
            published=True
        ).count()

        student_results = Result.query.filter_by(
            student_id=user.id
        ).all()

        completed = len(
            student_results
        )

        if student_results:

            percentages = [
                r.percentage
                for r in student_results
                if r.total
                and r.total > 0
            ]

            if percentages:

                avg_score = round(
                    sum(percentages)
                    / len(percentages)
                )

    # ==================================================
    # TEACHER
    # ==================================================

    elif user.role == "teacher":

        teacher_quizzes = Quiz.query.filter_by(
            teacher_id=user.id
        ).all()

        total_quizzes = len(
            teacher_quizzes
        )

        quiz_ids = [
            quiz.id
            for quiz in teacher_quizzes
        ]

        if quiz_ids:

            teacher_results = Result.query.filter(
                Result.quiz_id.in_(quiz_ids)
            ).all()

            total_attempts = len(
                teacher_results
            )

            student_ids = set(
                r.student_id
                for r in teacher_results
                if r.student_id
            )

            total_students = len(
                student_ids
            )

    return render_template(
        "profile/profile.html",
        user=user,
        total_quizzes=total_quizzes,
        completed=completed,
        avg_score=avg_score,
        total_students=total_students,
        total_attempts=total_attempts
    )


# ==================================================
# EDIT PROFILE
# ==================================================

@app.route(
    "/edit_profile",
    methods=["GET", "POST"]
)
def edit_profile():

    if "user_id" not in session:
        return redirect(
            url_for("login")
        )

    user = User.query.get(
        session["user_id"]
    )

    if not user:
        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        user.name = request.form.get(
            "name"
        )

        user.language = request.form.get(
            "language"
        )

        user.bio = request.form.get(
            "bio"
        )

        if user.role == "student":

            user.roll_no = request.form.get(
                "roll_no"
            )

            user.course = request.form.get(
                "course"
            )

            user.year = request.form.get(
                "year"
            )

            user.skills = request.form.get(
                "skills"
            )

        if user.role == "teacher":

            user.subject = request.form.get(
                "subject"
            )

            user.experience = request.form.get(
                "experience"
            )

            user.qualification = request.form.get(
                "qualification"
            )

        # ==================================================
        # PROFILE PICTURE
        # ==================================================

        file = request.files.get(
            "profile_pic"
        )

        if file and file.filename:

            extension = os.path.splitext(
                file.filename
            )[1].lower()

            allowed_extensions = [
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".webp"
            ]

            if extension not in allowed_extensions:

                return (
                    "Only JPG, JPEG, PNG, GIF "
                    "and WEBP images are allowed."
                )

            filename = (
                f"user_{user.id}{extension}"
            )

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            file.save(
                filepath
            )

            user.profile_pic = filename

        db.session.commit()

        return redirect(
            url_for("edit_profile")
        )

    return render_template(
        "profile/edit_profile.html",
        user=user
    )


# ==================================================
# CHANGE PASSWORD
# ==================================================

@app.route(
    "/change_password",
        methods=["GET", "POST"]
)
def change_password():

    if "user_id" not in session:
        return redirect(
            url_for("login")
        )

    user = User.query.get(
        session["user_id"]
    )

    if not user:
        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        current_password = request.form.get(
            "current_password"
        )

        new_password = request.form.get(
            "new_password"
        )

        confirm_password = request.form.get(
            "confirm_password"
        )

        if not check_password_hash(
            user.password,
            current_password
        ):

            return (
                "Current password is incorrect."
            )

        if new_password != confirm_password:

            return (
                "New passwords do not match."
            )

        user.password = generate_password_hash(
            new_password
        )

        db.session.commit()

        return redirect(
            url_for("profile")
        )

    return render_template(
        "profile/change_password.html",
        user=user
    )


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ==================================================
# DATABASE
# ==================================================

from sqlalchemy import inspect

with app.app_context():

    db.create_all()

    try:

        inspector = inspect(
            db.engine
        )

        columns = inspector.get_columns(
            "question"
        )

        print(
            "\n===== QUESTION TABLE COLUMNS ====="
        )

        for column in columns:

            print(
                column["name"]
            )

        print(
            "=================================\n"
        )

    except Exception as e:

        print(
            "DATABASE INSPECTION ERROR:",
            e
        )



# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(
        debug=True
    )

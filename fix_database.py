import sqlite3
import os

# Flask-SQLAlchemy usually stores this here
db_path = os.path.join("instance", "database.db")

# If database.db exists in current folder, use that instead
if not os.path.exists(db_path):
    db_path = "database.db"

print("Database:", os.path.abspath(db_path))

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Disable foreign-key checking temporarily
cursor.execute("PRAGMA foreign_keys=OFF")

print("\nChecking quiz table...")

# Get current quiz table structure
cursor.execute("PRAGMA table_info(quiz)")
columns = cursor.fetchall()

if not columns:
    print("quiz table does not exist.")
    conn.close()
    exit()

for column in columns:
    print(column)

# Check teacher_id nullability
teacher_column = None

for column in columns:
    # column format:
    # cid, name, type, notnull, default, pk
    if column[1] == "teacher_id":
        teacher_column = column
        break

if teacher_column is None:
    print("\nteacher_id column not found.")
    conn.close()
    exit()

print("\nCurrent teacher_id NOT NULL value:", teacher_column[3])

if teacher_column[3] == 0:
    print("\nteacher_id is already nullable.")
    print("No migration required.")
    conn.close()
    exit()

print("\nMigrating quiz table...")
print("Making teacher_id nullable...")

# Create new quiz table with teacher_id nullable
cursor.execute("""
CREATE TABLE quiz_new (
    id INTEGER NOT NULL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    subject VARCHAR(100),
    total_questions INTEGER,
    duration INTEGER,
    difficulty VARCHAR(20),
    question_type VARCHAR(30),
    number_of_questions INTEGER,
    passing_marks INTEGER,
    published BOOLEAN,
    teacher_id INTEGER,
    FOREIGN KEY(teacher_id) REFERENCES user(id)
)
""")

# Copy existing quiz data
cursor.execute("""
INSERT INTO quiz_new (
    id,
    title,
    description,
    subject,
    total_questions,
    duration,
    difficulty,
    question_type,
    number_of_questions,
    passing_marks,
    published,
    teacher_id
)
SELECT
    id,
    title,
    description,
    subject,
    total_questions,
    duration,
    difficulty,
    question_type,
    number_of_questions,
    passing_marks,
    published,
    teacher_id
FROM quiz
""")

# Remove old table
cursor.execute("""
DROP TABLE quiz
""")

# Rename new table
cursor.execute("""
ALTER TABLE quiz_new
RENAME TO quiz
""")

conn.commit()

cursor.execute("PRAGMA foreign_keys=ON")

print("\n====================================")
print("DATABASE MIGRATION SUCCESSFUL")
print("====================================")

# Verify
cursor.execute("PRAGMA table_info(quiz)")
new_columns = cursor.fetchall()

print("\nUpdated quiz table:")

for column in new_columns:
    print(
        f"{column[1]} | "
        f"{column[2]} | "
        f"NOT NULL = {column[3]}"
    )

conn.close()

print("\nYou can now run:")
print("python app.py")
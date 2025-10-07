"""
Core non-GUI logic for Security+ Study App.
This module contains database helpers and pure logic functions so the GUI
can remain focused on interface code.

Functions include:
- Database initialization and connection
- Adding and importing questions
- Retrieving questions and domains
- Recording attempts and calculating statistics
- Simple spaced repetition scheduling for flashcards
"""

# Import necessary modules
import sqlite3
import csv
import json
import datetime
from pathlib import Path

#Make a database file in a new directory in the user's home directory
APP_DIR = Path.home() / ".security_plus_study_app"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "study.db"

# database connection helper
def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

# Initialize the database with necessary tables
def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # questions table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            domain TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT,
            qtype TEXT DEFAULT 'free',
            metadata TEXT
        )
        """
    )
    
    # attempts table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY,
            question_id INTEGER,
            correct INTEGER,
            timestamp TEXT,
            FOREIGN KEY(question_id) REFERENCES questions(id)
        )
        """
    )
    
    # flashcards table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY,
            question_id INTEGER UNIQUE,
            interval INTEGER DEFAULT 1,
            ease REAL DEFAULT 2.5,
            next_review TEXT,
            FOREIGN KEY(question_id) REFERENCES questions(id)
        )
        """
    )
    conn.commit()
    conn.close()

# Add a single question to the database
def add_question(domain, question, answer, qtype='free', metadata=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO questions (domain,question,answer,qtype,metadata) VALUES (?,?,?,?,?)",
        (domain, question, answer, qtype, json.dumps(metadata) if metadata else None)
    )
    qid = c.lastrowid
    conn.commit()
    conn.close()
    return qid

# Import questions from CSV or JSON file
def import_csv(path):
    added = 0
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain') or row.get('Domain') or 'General'
            q = row.get('question') or row.get('Question')
            a = row.get('answer') or row.get('Answer') or ''
            t = row.get('type') or row.get('Type') or 'free'
            if q:
                add_question(domain, q, a, t, None)
                added += 1
    return added

def import_json(path):
    added = 0
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for item in data:
            domain = item.get('domain', 'General')
            q = item.get('question')
            a = item.get('answer', '')
            t = item.get('type', 'free')
            if q:
                add_question(domain, q, a, t, item.get('metadata'))
                added += 1
    return added

# Retrieve distinct domains
def list_domains():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT domain FROM questions ORDER BY domain")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

# Retrieve questions, optionally filtered by domain and limited in number
def get_questions(domain=None, limit=None):
    conn = get_conn()
    c = conn.cursor()
    if domain and domain != 'All':
        c.execute("SELECT * FROM questions WHERE domain=? ORDER BY id", (domain,))
    else:
        c.execute("SELECT * FROM questions ORDER BY id")
    rows = c.fetchall()
    conn.close()
    if limit:
        return rows[:limit]
    return rows

# Record an attempt at answering a question
def record_attempt(question_id, correct):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO attempts (question_id, correct, timestamp) VALUES (?,?,?)",
        (question_id, 1 if correct else 0, datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

# Calculate statistics per domain
def stats_per_domain():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT q.domain,
          COUNT(a.id) as attempts,
          SUM(a.correct) as correct
        FROM questions q
        LEFT JOIN attempts a ON a.question_id = q.id
        GROUP BY q.domain
        ORDER BY attempts DESC
        """
    )
    rows = c.fetchall()
    conn.close()
    stats = []
    for r in rows:
        attempts = r['attempts'] or 0
        correct = r['correct'] or 0
        pct = (correct / attempts * 100) if attempts > 0 else 0
        stats.append({'domain': r['domain'], 'attempts': attempts, 'correct': correct, 'pct': pct})
    return stats

# --- Simple flashcard SRS update (SM-2 simplified) ---
def schedule_update(question_id, quality):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id,interval,ease FROM flashcards WHERE question_id=?", (question_id,))
    row = c.fetchone()
    if not row:
        interval = 1
        ease = 2.5
        next_review = (datetime.date.today() + datetime.timedelta(days=interval)).isoformat()
        c.execute(
            "INSERT OR REPLACE INTO flashcards (question_id,interval,ease,next_review) VALUES (?,?,?,?)",
            (question_id, interval, ease, next_review)
        )
    else:
        interval = row[1]
        ease = row[2]
        if quality < 3:
            interval = 1
        else:
            interval = int(round(interval * ease))
            ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        next_review = (datetime.date.today() + datetime.timedelta(days=interval)).isoformat()
        c.execute(
            "UPDATE flashcards SET interval=?, ease=?, next_review=? WHERE question_id=?",
            (interval, ease, next_review, question_id)
        )
    conn.commit()
    conn.close()


def due_flashcards():
    conn = get_conn()
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute(
        "SELECT f.id as fid, q.* FROM flashcards f JOIN questions q ON f.question_id=q.id WHERE f.next_review<=? ORDER BY f.next_review",
        (today,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

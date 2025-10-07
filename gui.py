"""
GUI module for Security+ Study App.
Contains the MainWindow class and GUI wiring. Keeps UI code separate from core logic in app_core.py.
"""
import json
import random
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QTextEdit, QLineEdit, QFileDialog, QMessageBox,
    QTabWidget, QFormLayout, QSpinBox, QComboBox, QTableWidget, QTableWidgetItem,
    QInputDialog, QApplication
)

from app_core import (
    get_conn, add_question, import_csv, import_json,
    list_domains, get_questions, record_attempt, stats_per_domain,
    schedule_update, due_flashcards
)

# Optional: progress chart
try:
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


class MainWindow(QMainWindow):
    # Main window with tabs
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Security+ Study App")
        self.resize(1000, 700)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab()
        self.flashcards_tab()
        self.bank_tab()
        self.quiz_tab()
        self.import_tab()
        self.settings_tab()

    # dashboard tab with stats
    def dashboard_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        w.setLayout(layout)

        h = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()
        h.addLayout(left, 2)
        h.addLayout(right, 1)

        left.addWidget(QLabel("<h2>Overview</h2>"))
        self.progress_table = QTableWidget(0, 3)
        self.progress_table.setHorizontalHeaderLabels(["Domain", "Attempts", "% Correct"])
        left.addWidget(self.progress_table)

        if MATPLOTLIB_AVAILABLE:
            self.fig = Figure(figsize=(4, 2))
            self.canvas = FigureCanvas(self.fig)
            left.addWidget(self.canvas)

        reload_btn = QPushButton("Refresh Stats")
        reload_btn.clicked.connect(self.load_stats)
        left.addWidget(reload_btn)

        right.addWidget(QLabel("<h3>Quick Actions</h3>"))
        btn_flash = QPushButton("Study Due Flashcards")
        btn_flash.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        right.addWidget(btn_flash)

        btn_quiz = QPushButton("Start Quick Quiz")
        btn_quiz.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        right.addWidget(btn_quiz)

        btn_import = QPushButton("Import Questions")
        btn_import.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        right.addWidget(btn_import)

        layout.addLayout(h)
        self.tabs.addTab(w, "Dashboard")
        self.load_stats()

    # Load and display stats
    def load_stats(self):
        stats = stats_per_domain()
        self.progress_table.setRowCount(len(stats))
        domains = []
        pct = []
        for i, s in enumerate(stats):
            self.progress_table.setItem(i, 0, QTableWidgetItem(s['domain']))
            self.progress_table.setItem(i, 1, QTableWidgetItem(str(s['attempts'])))
            self.progress_table.setItem(i, 2, QTableWidgetItem(f"{s['pct']:.1f}%"))
            domains.append(s['domain'])
            pct.append(s['pct'])

        if MATPLOTLIB_AVAILABLE:
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            ax.bar(domains, pct)
            ax.set_ylabel("% Correct")
            ax.set_title("Accuracy by Domain")
            ax.set_ylim(0, 100)
            self.canvas.draw()

    # Flashcards tab with SRS
    def flashcards_tab(self):
        w = QWidget()
        layout = QHBoxLayout()
        w.setLayout(layout)

        left = QVBoxLayout()
        right = QVBoxLayout()
        layout.addLayout(left, 3)
        layout.addLayout(right, 2)

        left.addWidget(QLabel("<h2>Flashcards (Due)</h2>"))
        self.fc_list = QListWidget()
        left.addWidget(self.fc_list)
        self.load_due_flashcards()
        self.fc_list.currentRowChanged.connect(self.show_flashcard)

        right.addWidget(QLabel("<h3>Card</h3>"))
        self.card_q = QTextEdit()
        self.card_q.setReadOnly(True)
        right.addWidget(self.card_q)

        self.card_a = QTextEdit()
        self.card_a.setReadOnly(True)
        self.card_a.hide()
        right.addWidget(self.card_a)

        show_ans_btn = QPushButton("Show Answer")
        show_ans_btn.clicked.connect(self.card_a.show)
        right.addWidget(show_ans_btn)

        grades_layout = QHBoxLayout()
        for label, score in [("Again", 0), ("Hard", 3), ("Good", 4), ("Easy", 5)]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, sc=score: self.grade_card(sc))
            grades_layout.addWidget(btn)
        right.addLayout(grades_layout)

        refresh = QPushButton("Refresh Due List")
        refresh.clicked.connect(self.load_due_flashcards)
        right.addWidget(refresh)

        self.tabs.addTab(w, "Flashcards")

    # Load and display due flashcards
    def load_due_flashcards(self):
        self.fc_list.clear()
        for r in due_flashcards():
            display = f"[{r['domain']}] {r['question'][:120]}"
            # 'id' is always present from the questions table in the query result
            self.fc_list.addItem(f"{r['id']}: {display}")

    # Display selected flashcard
    def show_flashcard(self, idx):
        if idx < 0:
            return
        item = self.fc_list.item(idx).text()
        qid = int(item.split(":", 1)[0])
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM questions WHERE id=?", (qid,))
        r = c.fetchone()
        conn.close()
        if r:
            self.current_card_id = r['id']
            self.card_q.setPlainText(r['question'])
            self.card_a.setPlainText(r['answer'] or "<no answer provided>")
            self.card_a.hide()

    # Grade the card and update SRS
    def grade_card(self, quality):
        if not hasattr(self, "current_card_id"):
            QMessageBox.warning(self, "No card", "Select a card first")
            return
        qid = self.current_card_id
        schedule_update(qid, quality)
        record_attempt(qid, quality >= 4)
        QMessageBox.information(self, "Saved", "Your answer and scheduling updated.")
        self.load_due_flashcards()

    # Question bank tab
    def bank_tab(self):
        w = QWidget()
        layout = QHBoxLayout()
        w.setLayout(layout)

        left = QVBoxLayout()
        right = QVBoxLayout()
        layout.addLayout(left, 3)
        layout.addLayout(right, 2)

        left.addWidget(QLabel("<h2>Question Bank</h2>"))
        self.domain_filter = QComboBox()
        self.domain_filter.addItem("All")
        self.domain_filter.addItems(list_domains())
        self.domain_filter.currentTextChanged.connect(self.load_bank)
        left.addWidget(self.domain_filter)

        self.bank_list = QListWidget()
        left.addWidget(self.bank_list)
        self.bank_list.currentRowChanged.connect(self.show_bank_question)

        right.addWidget(QLabel("<h3>Question</h3>"))
        self.bank_q = QTextEdit()
        self.bank_q.setReadOnly(True)
        right.addWidget(self.bank_q)
        self.bank_a = QTextEdit()
        self.bank_a.setReadOnly(True)
        right.addWidget(self.bank_a)

        del_btn = QPushButton("Delete Question")
        del_btn.clicked.connect(self.delete_question)
        right.addWidget(del_btn)

        refresh = QPushButton("Refresh Domains")
        refresh.clicked.connect(self.reload_domains)
        right.addWidget(refresh)

        self.tabs.addTab(w, "Question Bank")
        self.load_bank()

    # Reload domains and refresh bank list
    def reload_domains(self):
        self.domain_filter.clear()
        self.domain_filter.addItem("All")
        self.domain_filter.addItems(list_domains())
        self.load_bank()

    def load_bank(self):
        domain = self.domain_filter.currentText()
        self.bank_list.clear()
        for r in get_questions(domain if domain != "All" else None):
            self.bank_list.addItem(f"{r['id']}: [{r['domain']}] {r['question'][:80]}")

    def show_bank_question(self, idx):
        if idx < 0:
            return
        text = self.bank_list.item(idx).text()
        qid = int(text.split(":", 1)[0])
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM questions WHERE id=?", (qid,))
        r = c.fetchone()
        conn.close()
        if r:
            self.bank_q.setPlainText(r['question'])
            self.bank_a.setPlainText(r['answer'] or "")

    def delete_question(self):
        idx = self.bank_list.currentRow()
        if idx < 0:
            return
        text = self.bank_list.item(idx).text()
        qid = int(text.split(":", 1)[0])
        conn = get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM questions WHERE id=?", (qid,))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Deleted", "Question removed")
        self.load_bank()

    def quiz_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        w.setLayout(layout)

        form = QFormLayout()
        self.quiz_domain = QComboBox()
        self.quiz_domain.addItem("All")
        self.quiz_domain.addItems(list_domains())
        self.quiz_count = QSpinBox()
        self.quiz_count.setRange(1, 200)
        self.quiz_count.setValue(20)
        form.addRow("Domain", self.quiz_domain)
        form.addRow("Number of Questions", self.quiz_count)
        layout.addLayout(form)

        start = QPushButton("Start Quiz")
        start.clicked.connect(self.start_quiz)
        layout.addWidget(start)

        self.quiz_area = QListWidget()
        layout.addWidget(self.quiz_area)

        self.tabs.addTab(w, "Quiz")

    def start_quiz(self):
        domain = self.quiz_domain.currentText()
        count = self.quiz_count.value()
        qs = get_questions(domain if domain != "All" else None)
        if len(qs) == 0:
            QMessageBox.warning(self, "No questions", "No questions in chosen domain")
            return
        self.quiz_questions = random.sample(qs, min(count, len(qs)))
        self.quiz_index = 0
        self.quiz_score = 0
        self.show_quiz_question()

    def show_quiz_question(self):
        self.quiz_area.clear()
        if self.quiz_index >= len(self.quiz_questions):
            QMessageBox.information(self, "Finished", f"Quiz finished. Score: {self.quiz_score}/{len(self.quiz_questions)}")
            self.load_stats()
            return
        q = self.quiz_questions[self.quiz_index]
        self.current_quiz_qid = q['id']
        self.quiz_area.addItem(f"Q{self.quiz_index+1}: {q['question']}")
        # open a simple dialog for answer entry
        ans, ok = QInputDialog.getText(self, "Answer", q['question'])
        if ok:
            user = ans.strip()
            correct = False
            if q['answer'] and user:
                # Use strict equality for answer checking
                correct = user.lower() == q['answer'].lower()
            else:
                resp = QMessageBox.question(self, "Self grade", "Did you answer correctly?", QMessageBox.Yes | QMessageBox.No)
                correct = (resp == QMessageBox.Yes)
            if correct:
                self.quiz_score += 1
            record_attempt(q['id'], correct)
            self.quiz_index += 1
            self.show_quiz_question()
        else:
            # user canceled; do nothing
            return

    def import_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        w.setLayout(layout)

        layout.addWidget(QLabel("<h2>Import Questions</h2>"))

        btn_csv = QPushButton("Import CSV...")
        btn_csv.clicked.connect(self.on_import_csv)
        layout.addWidget(btn_csv)

        btn_json = QPushButton("Import JSON...")
        btn_json.clicked.connect(self.on_import_json)
        layout.addWidget(btn_json)

        layout.addWidget(QLabel("CSV format: header row with columns domain,question,answer,type"))
        layout.addWidget(QLabel("JSON format: list of objects with keys domain,question,answer,type"))
        self.tabs.addTab(w, "Import")

    def on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", str(Path.home()), "CSV files (*.csv)")
        if not path:
            return
        added = import_csv(path)
        QMessageBox.information(self, "Imported", f"Imported {added} questions")
        self.reload_domains()
        self.load_stats()

    def on_import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open JSON", str(Path.home()), "JSON files (*.json)")
        if not path:
            return
        added = import_json(path)
        QMessageBox.information(self, "Imported", f"Imported {added} questions")
        self.reload_domains()
        self.load_stats()

    def settings_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        w.setLayout(layout)

        layout.addWidget(QLabel("<h2>Settings & Export</h2>"))

        export_btn = QPushButton("Export Question Bank (JSON)")
        export_btn.clicked.connect(self.export_bank)
        layout.addWidget(export_btn)

        reset_btn = QPushButton("Reset Database (delete all)")
        reset_btn.clicked.connect(self.reset_db)
        layout.addWidget(reset_btn)

        self.tabs.addTab(w, "Settings")

    # Export question bank to JSON
    def export_bank(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON", str(Path.home() / "questions_export.json"), "JSON files (*.json)")
        if not path:
            return
        qs = get_questions(None)
        out = []
        for q in qs:
            out.append({
                "domain": q["domain"],
                "question": q["question"],
                "answer": q["answer"],
                "type": q["qtype"]
            })
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Exported", f"Exported {len(out)} questions to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    # reset database
    def reset_db(self):
        reply = QMessageBox.question(
            self,
            "Are you sure?",
            "This will delete ALL questions, flashcards, attempts, and progress. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            conn = get_conn()
            c = conn.cursor()
            c.execute("DELETE FROM attempts")
            c.execute("DELETE FROM flashcards")
            c.execute("DELETE FROM questions")
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Reset", "Database reset")
            self.reload_domains()
            self.load_stats()

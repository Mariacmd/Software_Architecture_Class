# password_recovery.py
# Forgot password for DriveShare. Uses the Chain of Responsibility pattern.
#
# Why Chain of Responsibility: recovering a password has to get past 3 checks in a row
# (the user's 3 security questions). Each check is its own handler object, linked to the next:
#
#     Question 1  ->  Question 2  ->  Question 3  ->  password can be reset
#
# Each handler only knows about its own question. If its answer is right, it passes the
# request down the chain. If it's wrong, the chain stops right there and nothing gets reset.
# Adding a 4th check later (ex. an email code) just means linking one more handler on the end.
#
# 3 parts:
# 1. RecoveryHandler          = the shared "shape", every handler has handle() and set_next()
# 2. SecurityQuestionHandler  = checks the answer to ONE security question
# 3. build_chain()            = links question 1 -> 2 -> 3 together

from abc import ABC, abstractmethod
from main import get_connection
from login_gui import hash_text
from notifications import send_notification


# ------------------------------------------------------------
# 1. RecoveryHandler: what every link in the chain has to have
# ------------------------------------------------------------
class RecoveryHandler(ABC):
    def __init__(self):
        self.next_handler = None   # the next link in the chain (None = this is the last one)

    def set_next(self, handler):
        # Links the next handler. Returns it so we can chain: a.set_next(b).set_next(c)
        self.next_handler = handler
        return handler

    def handle(self, user_id, answers):
        # Checks this link. If it passes, hands it to the next link.
        # Returns True only if EVERY link in the chain passed.
        if not self.check(user_id, answers):
            return False                # wrong answer, the chain stops here
        if self.next_handler is None:
            return True                 # last link passed, all checks are done
        return self.next_handler.handle(user_id, answers)

    @abstractmethod
    def check(self, user_id, answers):
        pass


# ------------------------------------------------------------
# 2. SecurityQuestionHandler: checks one security question
# ------------------------------------------------------------
class SecurityQuestionHandler(RecoveryHandler):
    def __init__(self, question_order):
        super().__init__()
        self.question_order = question_order   # 1, 2 or 3

    def check(self, user_id, answers):
        conn = get_connection()
        row = conn.execute(
            "SELECT answer_hash FROM security_questions WHERE user_id = ? AND question_order = ?",
            (user_id, self.question_order),
        ).fetchone()
        conn.close()

        if row is None:
            return False

        # Answers were saved lowercased and hashed at sign up, so do the same here
        typed = answers[self.question_order - 1]
        return hash_text(typed.strip().lower()) == row["answer_hash"]


# ------------------------------------------------------------
# 3. Build the chain: question 1 -> question 2 -> question 3
# ------------------------------------------------------------
def build_chain():
    first = SecurityQuestionHandler(1)
    first.set_next(SecurityQuestionHandler(2)).set_next(SecurityQuestionHandler(3))
    return first


# ------------------------------------------------------------
# Functions the GUI uses
# ------------------------------------------------------------
def get_security_questions(email):
    # Step 1 of recovery: user types their email, we show them their 3 questions.
    # Returns (user_id, [question 1, question 2, question 3]).
    conn = get_connection()
    user = conn.execute("SELECT user_id FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if user is None:
        conn.close()
        raise ValueError("No account with that email")

    rows = conn.execute(
        "SELECT question_text FROM security_questions WHERE user_id = ? ORDER BY question_order",
        (user["user_id"],),
    ).fetchall()
    conn.close()

    if len(rows) != 3:
        raise ValueError("This account doesn't have 3 security questions set up")
    return user["user_id"], [r["question_text"] for r in rows]


def recover_password(email, answers, new_password):
    # Step 2 of recovery: run the answers through the chain. Only if all 3 pass does the password change.
    # Raises ValueError with a message the GUI can show if something is wrong.
    if len(new_password) < 6:
        raise ValueError("password must be at least 6 characters")

    user_id, questions = get_security_questions(email)

    # Don't say WHICH answer was wrong, that would help someone guessing
    if not build_chain().handle(user_id, answers):
        raise ValueError("One or more answers are wrong")

    conn = get_connection()
    conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (hash_text(new_password), user_id))
    # Heads up in case it wasn't really them
    send_notification(user_id, "account", "Your password was reset using your security questions", conn)
    conn.commit()
    conn.close()

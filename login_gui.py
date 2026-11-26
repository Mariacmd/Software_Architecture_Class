import sqlite3
from main import get_connection

import tkinter as tk
from tkinter import messagebox
from abc import ABC, abstractmethod
from notifications import get_notifications

#extra funcs
import hashlib
def hash_text(text):
    return hashlib.sha256(text.encode()).hexdigest()

#singleton pattern
class Session:
    _instance = None

    def __new__(sess):
        if sess._instance is None:
            sess._instance = super().__new__(sess)
            sess._instance.user = None
        return sess._instance

    def login(self, user):
        self.user = user

    def logout(self):
        self.user = None

    def is_logged_in(self):
        return self.user is not None

    def user_id(self):
        return self.user["user_id"]


# imported here, after hash_text and Session exist, because these files import them from login_gui
from password_recovery import get_security_questions, recover_password
from screens import FindCarScreen, ListCarScreen, InboxScreen, PaymentsScreen, HistoryScreen

    
#gui has the register functions

security_questions = [
    "What was the name of your first pet?",
    "What city were you born in?",
    "What was your first car?",
    "What is your mother's maiden name?",
    "What was the name of your elementary school?",
    "What is your favorite food?",
]

def register_user(full_name, email, password, questions):
    if not full_name or not email or not password:
        raise ValueError("gimme all valus")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")

    for question, answer in questions:
        if not question or not answer.strip():
            raise ValueError("answer all the questions")


    #questions user picked
    picked = []
    for question, answer in questions:
        if question in picked:
            raise ValueError("pick 3 different security questions")
        picked.append(question)

    conn = get_connection()

    try:
        cursor = conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES (?,?,?)",
                              (email.lower(), hash_text(password), full_name))
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("an account with that email already exists")

    user_id = cursor.lastrowid

    for order, (question, answer) in enumerate(questions, start=1):
        conn.execute("INSERT INTO security_questions (user_id, question_order, question_text, answer_hash) VALUES (?, ?, ?, ?)",
                     (user_id, order, question, hash_text(answer.strip().lower())),)
    conn.commit()
    conn.close()

    return user_id
  


# Login functs

def login_user(email,password):
    conn = get_connection()
    user = conn.execute( "SELECT * FROM users WHERE email = ? AND password_hash = ?", (email.lower(), hash_text(password)),).fetchone()
    conn.close()

    if user is None:
        return False
    else:
        Session().login(user)
        return True


# mediator 

#parent
class Mediator(ABC):
    @abstractmethod
    def notify(self, sender, event, data = None):
        pass

#driveshare mediator inherits from the mediator

class DriveShareMediator(Mediator):
    def __init__(self,app):
        self.app = app
        self.nav_bar = None

    def register_nav_bar(self, nav_bar):
        self.nav_bar = nav_bar
        self.update_inbox_count()

    def notify(self, sender, event, data = None):
        if event == "go_to":
            self.show(data)
        elif event == "logged_in":
            self.show("findcar")
        elif event == "logged_out":
            Session().logout()
            self.show("login")
        elif event in ("registered", "password_reset", "recovery_locked"):
            self.show("login")
        elif event == "message_owner":
            self.show("inbox", contact_id = data["owner_id"], car_id = data["car_id"])
        elif event == "booking_made":
            self.app.screen.search()
        elif event in ("car_listed", "listing_changed", "booking_answered"):
            self.show("listcar")
        elif event in ("booking_changed", "review_left"):
            self.show("history")
        elif event == "watch_removed":
            self.show("inbox")
        elif event in ("payment_made", "notifications_read"):
            self.update_inbox_count()
        else:
            raise ValueError("help")

    def show(self, screen_name, **options):
        self.app.show(screen_name, **options)

    def update_inbox_count(self):
        if self.nav_bar is None or not Session().is_logged_in():
            return
        unread = len(get_notifications(Session().user_id(), unread_only = True))

        self.nav_bar.set_inbox_count(unread)


#gui or the tkinter  and nothing gets shown without the mediator

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DriveShare App")
        self.geometry("900x650")
        self.screen = None
        self.mediator = DriveShareMediator(self)
        self.show("login")
  
    protected_screens = ["findcar", "listcar", "inbox", "payments", "history"]

    #function only gets called by the mediator
    def show(self, nameofscreen, **options):
        if nameofscreen in self.protected_screens and not Session().is_logged_in():
            messagebox.showwarning("Not logged in","log in first")
            nameofscreen = "login"
            options = {}

        if self.screen is not None:
            self.screen.destroy()
        self.mediator.nav_bar = None

        #these are all the ids and the screens for the mediator
        screens = {
            "login": LoginScreen,
            "register": RegisterScreen,
            "recover": RecoverScreen,   
            "findcar": FindCarScreen,    
            "listcar": ListCarScreen,
            "inbox": InboxScreen,
            "payments": PaymentsScreen,
            "history": HistoryScreen,
        }

        self.screen = screens[nameofscreen](self, **options)
        self.screen.pack(fill = "both", expand = True, padx = 20, pady = 20)


# screens definitions
class LoginScreen(tk.Frame):
    def __init__(self, app):
            super().__init__(app)
            self.mediator = app.mediator
    
            tk.Label(self, text="Drive Share App", font=("Arial", 18, "bold")).pack(pady=15)
            tk.Label(self, text="Email").pack()
    
            self.email = tk.Entry(self, width=35)
            self.email.pack(pady=5)
    
            tk.Label(self, text="Password").pack()
            self.password = tk.Entry(self, width=35, show="*")
            self.password.pack(pady=5)
    
            tk.Button(self, text="Submit", width=25, command=self.submit).pack(pady=15)
    
            link = tk.Label(self, text="No Account? Create!", fg="blue", cursor="hand2")
            link.pack()
            link.bind("<Button-1>", lambda event: self.mediator.notify(self, "go_to", "register"))
    
            # forgot password goes to the recovery screen which triggers the chain of responsibility
            forgot = tk.Label(self, text="Forgot Password?", fg="blue", cursor="hand2")
            forgot.pack(pady=5)
            forgot.bind("<Button-1>", lambda event: self.mediator.notify(self, "go_to", "recover"))

    #what happens when hitting the submit/login button
    def submit(self):
        if login_user(self.email.get().strip(), self.password.get()):
            self.mediator.notify(self, "logged_in")
        else:
            messagebox.showerror("Login failed", "Wrong email or password")

class RegisterScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.mediator = app.mediator

        tk.Label(self, text="Drive Share App", font=("Arial", 18, "bold")).grid(row=0, column=0, columnspan=4, pady=13)
    
        # Name, Email, Password, Confirm Password boxes
        self.name = self.add_field("Name:", 1, 0)
        self.email = self.add_field("Email:", 1, 2)
        self.password = self.add_field("Password:", 2, 0, hidden=True)
        self.confirm = self.add_field("Confirm Password:", 2, 2, hidden=True)

        self.picked = []  
        self.answers = [] 
        q_frame = tk.Frame(self)
        q_frame.grid(row=3, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=(10, 0))

        for i in range(3):
            tk.Label(q_frame, text=f"Security Question {i + 1}").grid(row=i, column=0, sticky="w", pady=2)

            choice = tk.StringVar(value=security_questions[i])
            tk.OptionMenu(q_frame, choice, *security_questions).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            self.picked.append(choice)

            box = tk.Entry(q_frame, width=20)
            box.grid(row=i, column=2, sticky="w", padx=(5, 0), pady=2)

            self.answers.append(box)

        tk.Button(self, text="Submit", width=20, command=self.submit).grid(row=6, column=0, columnspan=4, pady=(30, 10))
        tk.Button(self, text="Exit", width=20, command=lambda: self.mediator.notify(self, "go_to", "login")).grid(row=7, column=0, columnspan=4)

    def add_field(self, text, row, column, hidden=False):
        tk.Label(self, text=text).grid(row=row, column=column, sticky="e", padx=(0, 5), pady=8)
        if hidden:
            box = tk.Entry(self, width=15, show="*")
        else:
            box = tk.Entry(self, width=15)
        box.grid(row=row, column=column + 1, sticky="w", padx=(0, 15), pady=4)
        return box

    def submit(self):
        if self.password.get() != self.confirm.get():
            messagebox.showerror("Error", "Passwords do not match")
            return
        questions = []

        for i in range(3):
            questions.append((self.picked[i].get(), self.answers[i].get()))

        try:
            register_user(self.name.get().strip(), self.email.get().strip(), self.password.get(), questions)
        except ValueError as error:
            messagebox.showerror("Error", str(error))
            return
       
        messagebox.showinfo("Success", "Account created! You can log in now.")
        self.mediator.notify(self, "registered")



class RecoverScreen(tk.Frame):
    max_tries = 3 

    def __init__(self, app):
        super().__init__(app)
        self.mediator = app.mediator
        self.tries = 0

        tk.Label(self, text="Drive Share App", font=("Arial", 18, "bold")).pack(pady=15)
        tk.Label(self, text="Forgot Password", font=("Arial", 12, "bold")).pack()

         # step 1
        tk.Label(self, text="Email").pack(pady=(10, 0))
        self.email = tk.Entry(self, width=35)
        self.email.pack(pady=5)
        self.next_button = tk.Button(self, text="Next", width=25, command=self.show_questions)
        self.next_button.pack(pady=10)

        # step 2 then questions to show
        self.step2 = tk.Frame(self)
        self.step2.pack()

        tk.Button(self, text="Back to Login", width=25, command=lambda: self.mediator.notify(self, "go_to", "login")).pack(pady=10)

    def show_questions(self):
        try:
            user_id, questions = get_security_questions(self.email.get())
        except ValueError as error:
            messagebox.showerror("Error", str(error))
            return

        # lock email
        self.email.config(state="disabled")
        self.next_button.destroy()

        self.answers = []
        for i, question in enumerate(questions):
            tk.Label(self.step2, text=question).grid(row=i, column=0, sticky="e", padx=(0, 5), pady=4)
            box = tk.Entry(self.step2, width=20)
            box.grid(row=i, column=1, sticky="w", pady=4)
            self.answers.append(box)

        tk.Label(self.step2, text="New Password:").grid(row=3, column=0, sticky="e", padx=(0, 5), pady=(15, 4))
        self.password = tk.Entry(self.step2, width=20, show="*")
        self.password.grid(row=3, column=1, sticky="w", pady=(15, 4))

        tk.Label(self.step2, text="Confirm Password:").grid(row=4, column=0, sticky="e", padx=(0, 5), pady=4)
        self.confirm = tk.Entry(self.step2, width=20, show="*")
        self.confirm.grid(row=4, column=1, sticky="w", pady=4)

        tk.Button(self.step2, text="Reset Password", width=25, command=self.submit).grid(row=5, column=0, columnspan=2, pady=15)


    # checks if everything is valid and limits the user after all steps completed
    def submit(self):
        if self.password.get() != self.confirm.get():
            messagebox.showerror("Error", "Passwords do not match")
            return

        typed_answers = []
        for box in self.answers:
            typed_answers.append(box.get())

        try:
            recover_password(self.email.get(), typed_answers, self.password.get())
        except ValueError as error:
            if "answers are wrong" in str(error):
                self.tries += 1
                if self.tries >= self.max_tries:
                    messagebox.showerror("Error", "Too many wrong answers. Try again later.")
                    self.mediator.notify(self, "recovery_locked")
                    return
                left = self.max_tries - self.tries
                
                if left == 1:
                    messagebox.showerror("Error", f"{error}. 1 try left.")
                else:
                    messagebox.showerror("Error", f"{error}. {left} tries left.")
           
            else:
                messagebox.showerror("Error", str(error))
            return

        messagebox.showinfo("Success", "Password reset! You can log in with your new password.")
        self.mediator.notify(self, "password_reset")    
# login_gui.py
# Registration, login, and the Login / Create Account screens for DriveShare.
# Started from main.py


import hashlib
import sqlite3
import tkinter as tk
from tkinter import messagebox
from database import get_connection

#Singleton pattern here
class Session:
    _instance = None   

    def __new__(cls):
        # checks the instance if the instance is none start the session it's not the same as login
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.user = None 
        return cls._instance

    def login(self, user):
        self.user = user   

    def logout(self):
        self.user = None

    def is_logged_in(self):
       #checks if logged in if user is == None then they ain't logged in
        return self.user is not None



# we can remove if we get issues
def hash_text(text):
    # quick hash function before password gets sent to db it's hashed and when logging in check the hash
    return hashlib.sha256(text.encode()).hexdigest()


#Register
SECURITY_QUESTIONS = [
    "secret question #1",
    "secret question #2",
    "secret question #3",
]

def register_user(full_name, email, password, questions):
    #value error if condition not met. Need name, email and password
    if not full_name or not email or not password:
        raise ValueError("fill all values")
    if "@" not in email:
        raise ValueError("email is not valid")
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")

    for question, answer in questions:
        if not question or not answer.strip():
            raise ValueError("answer all the questions")


    #SQL part
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)",
            (email.lower(), hash_text(password), full_name),
        )
        user_id = cursor.lastrowid

        # will save questions in order of what was picked and will convert answers to lower case
        for order, (question, answer) in enumerate(questions, start=1):
            conn.execute(
                """INSERT INTO security_questions (user_id, question_order, question_text, answer_hash)
                   VALUES (?, ?, ?, ?)""",
                (user_id, order, question, hash_text(answer.strip().lower())),
            )
        conn.commit()
        #new user id cause they are registered
        return user_id
    except sqlite3.IntegrityError:
        # email column is UNIQUE, so this means the email is already used
        raise ValueError("an account with that email already exists")

    finally:
        conn.close()


#Login
#this is for logging in after account is registered and created
def login_user(email, password):
    # if email and user match in the DB go to the session
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ? AND password_hash = ?",
        (email.lower(), hash_text(password)),
    ).fetchone()
    conn.close()

    if user is None:
        return False
    else:
        Session().login(user)
        return True



#Mediator pattern

# App and this main screen/default
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DriveShare App")
        self.geometry("520x520")
        self.screen = None
        self.show("login")

    # screens that need a logged in user right now there is just the home
    protected_screens = {"home"}


    ############# if you have questions lemme know but this is where we get our screens to appear
    def show(self, nameofscreen):
        # if screen is protected send them to log in if they aren't logged in

        if nameofscreen in self.protected_screens and not Session().is_logged_in():
            messagebox.showwarning("Not logged in", "Please log in first")
            nameofscreen = "login"

        # Removes the current screen and shows the one asked for
        if self.screen is not None:
            self.screen.destroy()


        screens = {"login": LoginScreen, "register": RegisterScreen, "home": HomeScreen}

        self.screen = screens[nameofscreen](self)
        self.screen.pack(fill="both", expand=True, padx=20, pady=20)
    ########

# Login screen

class LoginScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        tk.Label(self, text="Drive Share App", font=("Arial", 18, "bold")).pack(pady=15)

        tk.Label(self, text="Email").pack()
        self.email = tk.Entry(self, width=35)
        self.email.pack(pady=5)

        tk.Label(self, text="Password").pack()
        self.password = tk.Entry(self, width=35, show="*")   # show="*" hides the password
        self.password.pack(pady=5)

        tk.Button(self, text="Submit", width=25, command=self.submit).pack(pady=15)


        link = tk.Label(self, text="No Account? Create!", fg="blue", cursor="hand2")
        link.pack()

        #show the register
        link.bind("<Button-1>", lambda event: app.show("register"))

    def submit(self):
        #if login user returns true then go home else 
        if login_user(self.email.get().strip(), self.password.get()):
            self.app.show("home")   
        else:
            messagebox.showerror("Login failed", "Wrong email or password")


# Register GUI
class RegisterScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
 
        # grid
        tk.Label(self, text="Drive Share App", font=("Arial", 18, "bold")).grid(row=0, column=0, columnspan=4, pady=13)


        # label and box
        self.name = self.add_field("Name:", 1, 0)
        self.email = self.add_field("Email:", 1, 2)
        self.password = self.add_field("Password:", 2, 0, hidden=True)
        self.confirm = self.add_field("Confirm Password:", 2, 2, hidden=True)
 
        
        self.answers = []
        q_frame = tk.Frame(self)
        q_frame.grid(row=3, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=(10, 0))

        for i, question in enumerate(SECURITY_QUESTIONS):
            tk.Label(q_frame, text=question).grid(row=i, column=0, sticky="w", pady=2)

            box = tk.Entry(q_frame, width=20)
            box.grid(row=i, column=1, sticky="w", padx=(5, 0), pady=2)

            self.answers.append(box)
       
 
        tk.Button(self, text="Submit", width=20, command=self.submit).grid(row=6, column=0, columnspan=4, pady=(30, 10))
        tk.Button(self, text="Exit", width=20, command=lambda: app.show("login")).grid(row=7, column=0, columnspan=4)
 
    def add_field(self, text, row, column, hidden=False):
            # Makes one label and textbox pair
            tk.Label(self, text=text).grid(row=row, column=column, sticky="e", padx=(0, 5), pady=8)
            box = tk.Entry(self, width=15, show="*" if hidden else "")
            box.grid(row=row, column=column + 1, sticky="w", padx=(0, 15), pady=4)
            return box
 
    def submit(self):
        if self.password.get() != self.confirm.get():
            messagebox.showerror("Error", "Passwords do not match")
            return
 
        # pair question to the answer
        questions = [(q, box.get()) for q, box in zip(SECURITY_QUESTIONS, self.answers)]
 
        try:
            register_user(self.name.get().strip(), self.email.get().strip(), self.password.get(), questions)

        except ValueError as error:
            messagebox.showerror("Error", str(error))
            return
 
        messagebox.showinfo("Success", "Account created! You can log in now.")
        self.app.show("login")


# Reachable through Login only
class HomeScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.app = app

        tk.Label(self, text="Welcome to the homepage", font=("Arial", 18, "bold")).pack(pady=15)

        tk.Button(self, text="Log out", width=20, command=self.logout).pack(pady=10)

    def logout(self):
        Session().logout()
        self.app.show("login")
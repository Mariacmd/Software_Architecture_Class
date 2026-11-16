# main.py
# The main place we run the code. Starts DriveShare.
# Run with: python main.py

from database import create_tables
from login_gui import App

if __name__ == "__main__":
    create_tables()     # makes sure the database tables exist
    App().mainloop()    # opens the window, starting on the login screen

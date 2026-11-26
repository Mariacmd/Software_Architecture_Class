#datpicker for picking the dates since it's hard for users to put in correct format

import tkinter as tk
from tkinter import ttk
from datetime import datetime

# Show the current year and the next two years
current_year = datetime.now().year
years = [""] + [str(year) for year in range(current_year, current_year + 3)]
times = [f"{hour:02d}:00" for hour in range(24)]
months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun","Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
days = [""] + [str(day) for day in range(1, 32)]


class DatePicker(tk.Frame):

    def __init__(self, parent, default_time="10:00"):
        super().__init__(parent)

       #dropdowns 
        self.month = ttk.Combobox(self, values=months, width=4, state="readonly")
        self.day = ttk.Combobox(self, values=days, width=3, state="readonly")
        self.year = ttk.Combobox(self, values=years, width=5, state="readonly")
        self.time = ttk.Combobox(self, values=times, width=6, state="readonly")
        self.time.set(default_time)

        # Place the dropdown menus next to each other
        self.month.pack(side="left")
        self.day.pack(side="left", padx=2)
        self.year.pack(side="left")

        tk.Label(self, text="at").pack(side="left", padx=4)
        self.time.pack(side="left")


    def get(self):
        # Get the values selected by the user
        month = self.month.get()
        day = self.day.get()
        year = self.year.get()

        if not month and not day and not year:
            return None

        if not month or not day or not year:
            raise ValueError("Please select a month, day, and year")

        date = datetime(int(year), months.index(month), int(day))


        return date.strftime("%Y-%m-%d") + " " + self.time.get()


    def set(self, value):
        if value is None:
            # Clear the date fields
            self.month.set("")
            self.day.set("")
            self.year.set("")
            return

        date = datetime.strptime(value, "%Y-%m-%d %H:%M")

        # Put the date values into their dropdown menus
        self.month.set(months[date.month])
        self.day.set(str(date.day))
        self.year.set(str(date.year))
        self.time.set(date.strftime("%H:%M"))


    def clear(self):
        # Clear the selected date
        self.set(None)

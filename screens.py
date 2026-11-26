# screens.py
# The screens you see after logging in. Follows the drawings in the gui/ folder.
#
#   Find a Car  = search for cars, View More, Book Now, Add Watchlist   (gui/watchlist_findcar.jpg)
#   List a Car  = your listings with Edit, add a new listing             (gui/history.jpg, top)
#   Inbox       = contacts, chat with owners/renters, notifications     (gui/history.jpg, bottom)
#   Payments    = pay for confirmed bookings (Proxy pattern, payment.py) and add funds
#   History     = rental history for renters and owners, cancel/complete, reviews
#
# Every screen has the same bar at the top (NavBar) with buttons to switch screens.
# Mediator pattern (mediator.py): screens, popups and the NavBar never call each other.
# They just tell the mediator what happened, ex. self.mediator.notify(self, "booking_made"),
# and the mediator decides what the rest of the app should do about it.
#
# Dates are picked with dropdowns (DatePicker in date_picker.py), no typing needed.
#
# Tkinter tip you'll see a lot below:
#   command=lambda c=car: self.view_more(c)
# The "c=car" part saves THIS car for THIS button. Without it, every button made
# in the loop would end up using the last car in the list.

import tkinter as tk
from tkinter import messagebox, simpledialog

from login_gui import Session
from car import (CarBuilder, save_car, get_cars_by_owner, search_cars, update_price,
                 add_car_availability, remove_car_availability, get_car_availability, set_car_active)
from booking import (calculate_price, create_booking, confirm_booking, cancel_booking, complete_booking,
                     get_owner_history, get_renter_history)
from reviews import leave_review, can_review, get_reviews_for_user, get_average_rating
from notifications import get_notifications, mark_all_read, watch_car, unwatch_car, get_watchlist
from messaging import send_message, get_conversation, get_contacts, get_user_name
from payment import PaymentScreen
from date_picker import DatePicker


# ------------------------------------------------------------
# Small helpers the screens use
# ------------------------------------------------------------
def show_blank(value):
    # Shows "-" for optional car info the owner left empty
    if value is None or value == "":
        return "-"
    return value


def rating_text(user_id):
    # ex. "4.5 stars (2 reviews)" or "No reviews yet"
    average = get_average_rating(user_id)
    if average is None:
        return "No reviews yet"
    how_many = len(get_reviews_for_user(user_id))
    return f"{average} stars ({how_many} reviews)"


# ------------------------------------------------------------
# Top bar: "Drive Share App" + buttons to switch screens
# ------------------------------------------------------------
class NavBar(tk.Frame):
    def __init__(self, parent, mediator):
        super().__init__(parent)

        tk.Label(self, text="Drive Share App", font=("Arial", 16, "bold")).pack(side="left", padx=(0, 30))

        # Each button just tells the mediator where the user wants to go
        tk.Button(self, text="Find a Car", command=lambda: mediator.notify(self, "go_to", "findcar")).pack(side="left", padx=5)
        tk.Button(self, text="List a Car", command=lambda: mediator.notify(self, "go_to", "listcar")).pack(side="left", padx=5)
        self.inbox_button = tk.Button(self, text="Inbox", command=lambda: mediator.notify(self, "go_to", "inbox"))
        self.inbox_button.pack(side="left", padx=5)
        tk.Button(self, text="Payments", command=lambda: mediator.notify(self, "go_to", "payments")).pack(side="left", padx=5)
        tk.Button(self, text="History", command=lambda: mediator.notify(self, "go_to", "history")).pack(side="left", padx=5)
        tk.Button(self, text="Log out", command=lambda: mediator.notify(self, "logged_out")).pack(side="right", padx=5)

        # Sign up with the mediator so other screens can update our Inbox count
        mediator.register_nav_bar(self)

    def set_inbox_count(self, unread):
        # Called by the mediator. Shows "Inbox (2)" when there are unread notifications.
        self.inbox_button.config(text=f"Inbox ({unread})" if unread else "Inbox")


# ------------------------------------------------------------
# Find a Car (landing page)
# ------------------------------------------------------------
class FindCarScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.mediator = app.mediator
        NavBar(self, self.mediator).pack(fill="x", pady=(0, 15))

        # Filter box at the top
        filters = tk.LabelFrame(self, text="Filter Car", padx=10, pady=10)
        filters.pack(fill="x")

        tk.Label(filters, text="Location:").grid(row=0, column=0, sticky="e")
        self.location = tk.Entry(filters, width=15)
        self.location.grid(row=0, column=1, padx=5)

        tk.Label(filters, text="Model:").grid(row=0, column=2, sticky="e")
        self.model = tk.Entry(filters, width=15)
        self.model.grid(row=0, column=3, padx=5)

        tk.Label(filters, text="From:").grid(row=1, column=0, sticky="e", pady=5)
        self.start = DatePicker(filters)
        self.start.grid(row=1, column=1, padx=5)

        tk.Label(filters, text="To:").grid(row=1, column=2, sticky="e")
        self.end = DatePicker(filters)
        self.end.grid(row=1, column=3, padx=5)

        tk.Button(filters, text="Search", width=10, command=self.search).grid(row=0, column=4, rowspan=2, padx=15)
        tk.Button(filters, text="Clear Dates", command=self.clear_dates).grid(row=2, column=4, padx=15)
        tk.Label(filters, text="Dates are optional", fg="gray").grid(row=2, column=0, columnspan=4, sticky="w")

        # The car boxes go in here
        self.results = tk.Frame(self)
        self.results.pack(fill="both", expand=True, pady=15)

        self.search()   # show every car when the page first opens

    def clear_dates(self):
        self.start.clear()
        self.end.clear()
        self.search()

    def search(self):
        # Location and model words both get searched (see search_cars in car.py)
        text = self.location.get() + " " + self.model.get()
        try:
            cars = search_cars(text, self.start.get(), self.end.get())
        except ValueError as e:
            messagebox.showerror("Search", str(e))
            return

        # Clear old results
        for widget in self.results.winfo_children():
            widget.destroy()

        if not cars:
            tk.Label(self.results, text="No cars found").pack()
            return

        # 3 car boxes per row, like the drawing
        row = 0
        column = 0
        for car in cars:
            box = tk.LabelFrame(self.results, text="Car", padx=10, pady=5)
            box.grid(row=row, column=column, padx=5, pady=5, sticky="nsew")

            tk.Label(box, text=f"{car['year']} {car['make']} {car['model']}").pack(anchor="w")
            tk.Label(box, text=f"{car['pickup_location']}, {car['mileage']} miles, ${car['daily_price']:.2f}/day").pack(anchor="w")
            tk.Button(box, text="View More", command=lambda c=car: self.view_more(c)).pack(anchor="w", pady=2)
            tk.Button(box, text="Add Watchlist", command=lambda c=car: self.add_watchlist(c)).pack(anchor="w")

            # move to the next spot, and start a new row after 3
            column += 1
            if column == 3:
                column = 0
                row += 1

    def view_more(self, car):
        # Small popup with the car's details, Book Now and Add Watchlist
        popup = tk.Toplevel(self)
        popup.title("Car")

        details = [
            f"{car['year']} {car['make']} {car['model']}",
            f"Location: {car['pickup_location']}",
            f"Miles: {car['mileage']}",
            f"Price: ${car['daily_price']:.2f}/day",
            f"Color: {show_blank(car['color'])}    Seats: {show_blank(car['seats'])}",
            f"Description: {show_blank(car['description'])}",
            f"Owner rating: {rating_text(car['owner_id'])}",
        ]
        for line in details:
            tk.Label(popup, text=line).pack(anchor="w", padx=15, pady=2)

        tk.Label(popup, text="Available:").pack(anchor="w", padx=15, pady=(8, 0))
        dates = get_car_availability(car["car_id"])
        if not dates:
            tk.Label(popup, text="  Any time").pack(anchor="w", padx=15)
        for d in dates:
            tk.Label(popup, text=f"  {d['available_from']} to {d['available_to']}").pack(anchor="w", padx=15)

        # Pick the rental dates right here. Starts with whatever dates were in the filter.
        dates_box = tk.LabelFrame(popup, text="Rent it", padx=10, pady=5)
        dates_box.pack(fill="x", padx=15, pady=(10, 0))
        tk.Label(dates_box, text="From:").grid(row=0, column=0, sticky="e")
        popup.start = DatePicker(dates_box)
        popup.start.grid(row=0, column=1, pady=2)
        tk.Label(dates_box, text="To:").grid(row=1, column=0, sticky="e")
        popup.end = DatePicker(dates_box)
        popup.end.grid(row=1, column=1, pady=2)
        try:
            popup.start.set(self.start.get())
            popup.end.set(self.end.get())
        except ValueError:
            pass   # filter dates were only half picked, just leave these blank

        tk.Button(popup, text="Book Now", width=15, command=lambda: self.book(car, popup)).pack(pady=(10, 3))
        tk.Button(popup, text="Add Watchlist", width=15, command=lambda: self.add_watchlist(car)).pack(pady=3)

        # Ask the owner something before booking. Not shown on your own car.
        if car["owner_id"] != Session().user_id():
            tk.Button(popup, text="Message Owner", width=15,
                      command=lambda: self.message_owner(car, popup)).pack(pady=(3, 10))

    def message_owner(self, car, popup):
        # Opens the Inbox with a chat to this car's owner already picked
        popup.destroy()
        self.mediator.notify(self, "message_owner", {"owner_id": car["owner_id"], "car_id": car["car_id"]})

    def book(self, car, popup):
        # Books the car for the dates picked in the popup
        try:
            start = popup.start.get()
            end = popup.end.get()
            if start is None or end is None:
                raise ValueError("Pick a From and To date")
            create_booking(car["car_id"], Session().user_id(), start, end)
        except ValueError as e:
            messagebox.showerror("Book", str(e), parent=popup)
            return
        total = calculate_price(car["daily_price"], start, end)
        messagebox.showinfo("Book", f"Booking request sent for ${total:.2f}! "
                                    "Once the owner confirms, pay on the Payments page.", parent=popup)
        popup.destroy()
        self.mediator.notify(self, "booking_made")   # mediator refreshes the search results

    def add_watchlist(self, car):
        # Observer pattern: renter gets a notification when the car hits their price (and dates, if typed)
        max_price = simpledialog.askfloat("Watchlist", "Tell me when the price per day is at or below:", parent=self)
        if max_price is None:
            return   # they hit cancel
        try:
            # if dates are picked in the filter, also wait for the car to be free then
            watch_car(Session().user_id(), car["car_id"], max_price, self.start.get(), self.end.get())
        except ValueError as e:
            messagebox.showerror("Watchlist", str(e))
            return
        messagebox.showinfo("Watchlist", "Added! You'll get a notification in your Inbox.")


# ------------------------------------------------------------
# List a Car: your listings on the left, add a new one on the right
# ------------------------------------------------------------
class ListCarScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.mediator = app.mediator
        NavBar(self, self.mediator).pack(fill="x", pady=(0, 15))

        body = tk.Frame(self)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        self.build_listings(left)
        self.build_requests(left)

        self.build_add_form(body)

    def build_listings(self, parent):
        # "Your Listings" table with an Edit button on each row
        box = tk.LabelFrame(parent, text="Your Listings:", padx=10, pady=10)
        box.pack(fill="x")

        headers = ["Car", "Price", "Location", "Status", ""]
        for col, text in enumerate(headers):
            tk.Label(box, text=text, font=("Arial", 10, "bold")).grid(row=0, column=col, sticky="w", padx=5)

        cars = get_cars_by_owner(Session().user_id())
        if not cars:
            tk.Label(box, text="You haven't listed a car yet").grid(row=1, column=0, columnspan=5, sticky="w")

        for row, car in enumerate(cars, start=1):
            status = "Listed" if car["is_active"] else "Hidden"
            values = [f"{car['year']} {car['make']} {car['model']}", f"${car['daily_price']:.2f}",
                      car["pickup_location"], status]
            for col, text in enumerate(values):
                tk.Label(box, text=text).grid(row=row, column=col, sticky="w", padx=5)
            tk.Button(box, text="Edit", command=lambda c=car: EditCarPopup(self, c, self.mediator)).grid(row=row, column=4, padx=5, pady=2)

    def build_requests(self, parent):
        # Booking requests on your cars. Owner has to confirm before the renter can pay.
        box = tk.LabelFrame(parent, text="Booking Requests:", padx=10, pady=10)
        box.pack(fill="x", pady=(15, 0))

        pending = [b for b in get_owner_history(Session().user_id()) if b["status"] == "pending"]
        if not pending:
            tk.Label(box, text="No new requests").grid(row=0, column=0, sticky="w")

        for row, b in enumerate(pending):
            text = f"{b['renter_name']} - {b['make']} {b['model']} - {b['start_time']} to {b['end_time']} - ${b['total_price']:.2f}"
            tk.Label(box, text=text).grid(row=row, column=0, sticky="w")
            tk.Button(box, text="Confirm", command=lambda i=b["booking_id"]: self.answer(i, True)).grid(row=row, column=1, padx=5, pady=2)
            tk.Button(box, text="Decline", command=lambda i=b["booking_id"]: self.answer(i, False)).grid(row=row, column=2, pady=2)

    def answer(self, booking_id, accept):
        # Confirm or decline a request. The renter gets a notification either way.
        try:
            if accept:
                confirm_booking(booking_id, Session().user_id())
            else:
                cancel_booking(booking_id, Session().user_id())
        except ValueError as e:
            messagebox.showerror("Booking", str(e))
        self.mediator.notify(self, "booking_answered")

    def build_add_form(self, parent):
        # "Add New Listing" form. Uses CarBuilder (Builder pattern) to make the car.
        box = tk.LabelFrame(parent, text="Add New Listing", padx=10, pady=10)
        box.pack(side="right", fill="y", padx=(15, 0))

        self.fields = {}
        labels = ["Make", "Model", "Year", "Mileage", "Location", "Price", "Color", "Seats"]
        for row, name in enumerate(labels):
            tk.Label(box, text=name).grid(row=row, column=0, sticky="w", pady=2)
            entry = tk.Entry(box, width=18)
            entry.grid(row=row, column=1, sticky="w", pady=2)
            self.fields[name] = entry

        # Availability uses dropdowns. Whole days by default (midnight to 11pm).
        row = len(labels)
        tk.Label(box, text="Available From").grid(row=row, column=0, sticky="w", pady=2)
        self.available_from = DatePicker(box, default_time="00:00")
        self.available_from.grid(row=row, column=1, sticky="w", pady=2)
        tk.Label(box, text="Available To").grid(row=row + 1, column=0, sticky="w", pady=2)
        self.available_to = DatePicker(box, default_time="23:00")
        self.available_to.grid(row=row + 1, column=1, sticky="w", pady=2)

        tk.Label(box, text="Color, Seats and dates are optional.\nNo dates = available any time.", fg="gray").grid(row=row + 2, column=0, columnspan=2, pady=(5, 0))
        tk.Button(box, text="Submit", width=15, command=self.add_car).grid(row=row + 3, column=0, columnspan=2, pady=10)

    def add_car(self):
        # Read every box, ex. f["Make"] = "Honda"
        f = {}
        for name in self.fields:
            f[name] = self.fields[name].get().strip()

        # Turn the number boxes into numbers first
        try:
            year = int(f["Year"])
            mileage = int(f["Mileage"])
            price = float(f["Price"])
            seats = None
            if f["Seats"]:
                seats = int(f["Seats"])
        except ValueError:
            messagebox.showerror("Add Listing", "Year, Mileage, Price and Seats have to be numbers")
            return

        try:
            # Required info goes in the builder, optional info is added only if filled in
            builder = CarBuilder(Session().user_id(), f["Make"], f["Model"], year, mileage, price, f["Location"])
            if f["Color"]:
                builder.set_color(f["Color"])
            if seats:
                builder.set_seats(seats)

            start = self.available_from.get()
            end = self.available_to.get()
            if start is None and end is not None:
                raise ValueError("Pick both an Available From and To date, or neither")
            if start is not None and end is None:
                raise ValueError("Pick both an Available From and To date, or neither")
            if start is not None:
                builder.add_availability(start, end)

            save_car(builder.build())
        except ValueError as e:
            # build() checks the info and tells us what's wrong
            messagebox.showerror("Add Listing", str(e))
            return
        messagebox.showinfo("Add Listing", "Car listed!")
        self.mediator.notify(self, "car_listed")


class EditCarPopup(tk.Toplevel):
    # Popup from the Edit button: change price, add/remove dates, hide/show the listing.
    # Price drops and new dates notify watchers (Observer pattern, in car.py).
    def __init__(self, parent, car, mediator):
        super().__init__(parent)
        self.mediator = mediator   # the popup doesn't know about the List a Car screen, only the mediator
        self.car = car
        self.title(f"Edit {car['make']} {car['model']}")

        # Price
        tk.Label(self, text="Price per day:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.price = tk.Entry(self, width=12)
        self.price.insert(0, str(car["daily_price"]))
        self.price.grid(row=0, column=1, padx=5)
        tk.Button(self, text="Save Price", command=self.save_price).grid(row=0, column=2, padx=10)

        # Availability dates
        tk.Label(self, text="Available dates:").grid(row=1, column=0, sticky="w", padx=10, pady=(10, 0))
        self.dates = tk.Listbox(self, width=45, height=5)
        self.dates.grid(row=2, column=0, columnspan=2, padx=10)
        tk.Button(self, text="Remove Selected", command=self.remove_dates).grid(row=2, column=2, padx=10)

        tk.Label(self, text="From:").grid(row=3, column=0, sticky="w", padx=10, pady=(10, 0))
        self.start = DatePicker(self, default_time="00:00")
        self.start.grid(row=3, column=1, sticky="w", pady=(10, 0))
        tk.Label(self, text="To:").grid(row=4, column=0, sticky="w", padx=10)
        self.end = DatePicker(self, default_time="23:00")
        self.end.grid(row=4, column=1, sticky="w")
        tk.Button(self, text="Add Dates", command=self.add_dates).grid(row=4, column=2, padx=10)

        # Hide / show in search
        if car["is_active"]:
            hide_text = "Hide Listing"
        else:
            hide_text = "Show Listing"
        tk.Button(self, text=hide_text, command=self.toggle_active).grid(row=6, column=0, columnspan=3, pady=15)

        self.load_dates()

    def load_dates(self):
        self.dates.delete(0, tk.END)
        self.date_ids = []   # availability_id for each line, so we know which one to remove
        for d in get_car_availability(self.car["car_id"]):
            self.dates.insert(tk.END, f"{d['available_from']} to {d['available_to']}")
            self.date_ids.append(d["availability_id"])

    def save_price(self):
        try:
            update_price(self.car["car_id"], Session().user_id(), float(self.price.get()))
        except ValueError as e:
            messagebox.showerror("Edit", str(e), parent=self)
            return
        messagebox.showinfo("Edit", "Price saved", parent=self)
        self.done()

    def add_dates(self):
        try:
            start = self.start.get()
            end = self.end.get()
            if start is None or end is None:
                raise ValueError("Pick a From and To date")
            add_car_availability(self.car["car_id"], Session().user_id(), start, end)
        except ValueError as e:
            messagebox.showerror("Edit", str(e), parent=self)
            return
        self.start.clear()
        self.end.clear()
        self.load_dates()

    def remove_dates(self):
        selected = self.dates.curselection()
        if not selected:
            return
        remove_car_availability(self.car["car_id"], Session().user_id(), self.date_ids[selected[0]])
        self.load_dates()

    def toggle_active(self):
        set_car_active(self.car["car_id"], Session().user_id(), not self.car["is_active"])
        self.done()

    def done(self):
        # Close the popup and let the mediator update whatever shows this listing
        self.destroy()
        self.mediator.notify(self, "listing_changed")


# ------------------------------------------------------------
# Inbox: chat with owners/renters, notifications, and your watchlist
# ------------------------------------------------------------
class InboxScreen(tk.Frame):
    # Laid out like the drawing: Contacts | chat with one person | Notifications
    # contact_id (optional) opens a chat with that person right away, ex. from "Message Owner".
    # car_id (optional) saves which car the messages are about.
    def __init__(self, app, contact_id=None, car_id=None):
        super().__init__(app)
        self.mediator = app.mediator
        self.car_id = car_id
        self.contact_id = None   # who we're chatting with right now
        NavBar(self, self.mediator).pack(fill="x", pady=(0, 15))

        top = tk.Frame(self)
        top.pack(fill="both", expand=True)

        # --- Contacts (left) ---
        contacts_box = tk.LabelFrame(top, text="Contacts:", padx=10, pady=10)
        contacts_box.pack(side="left", fill="y")
        self.contacts_list = tk.Listbox(contacts_box, width=20, height=15)
        self.contacts_list.pack(fill="y", expand=True)
        self.contacts_list.bind("<<ListboxSelect>>", self.pick_contact)

        # self.contacts is a list of (user_id, name), in the same order as the names in the Listbox
        self.contacts = []
        for c in get_contacts(Session().user_id()):
            self.contacts.append((c["user_id"], c["full_name"]))

        # "Message Owner" might open someone we've never talked to, so add them to the top of the list
        if contact_id is not None and not self.has_contact(contact_id):
            self.contacts.insert(0, (contact_id, get_user_name(contact_id)))

        for user_id, name in self.contacts:
            self.contacts_list.insert(tk.END, name)
        if not self.contacts:
            self.contacts_list.insert(tk.END, "(no contacts yet)")

        # --- Chat (middle) ---
        self.chat_box = tk.LabelFrame(top, text="Pick a contact", padx=10, pady=10)
        self.chat_box.pack(side="left", fill="both", expand=True, padx=10)

        # state="disabled" makes the chat read-only, we switch it on just to add text
        self.chat = tk.Text(self.chat_box, width=45, height=15, wrap="word", state="disabled")
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("me", justify="right")   # my messages on the right, like the drawing

        tk.Label(self.chat_box, text="Write Here:").pack(anchor="w", pady=(8, 0))
        self.write = tk.Entry(self.chat_box)
        self.write.pack(fill="x")
        self.write.bind("<Return>", lambda event: self.send())   # Enter key sends too
        tk.Button(self.chat_box, text="Send", width=10, command=self.send).pack(anchor="e", pady=5)

        # --- Notifications (right) ---
        notes_box = tk.LabelFrame(top, text="Notifications", padx=10, pady=10)
        notes_box.pack(side="left", fill="y")
        notes = tk.Text(notes_box, width=35, height=15, wrap="word")
        notes.pack(fill="y", expand=True)

        all_notes = get_notifications(Session().user_id())
        if not all_notes:
            notes.insert(tk.END, "No notifications yet")
        for n in all_notes:
            if n["is_read"]:
                notes.insert(tk.END, f"[{n['type']}] {n['message']}\n\n")
            else:
                notes.insert(tk.END, f"NEW [{n['type']}] {n['message']}\n\n")
        notes.config(state="disabled")   # read-only

        # They've seen them now, so the mediator can clear the count on the nav bar
        mark_all_read(Session().user_id())
        self.mediator.notify(self, "notifications_read")

        # Open the chat right away if we were sent here for a specific person
        if contact_id is not None:
            for index in range(len(self.contacts)):
                if self.contacts[index][0] == contact_id:
                    self.contacts_list.selection_set(index)
            self.open_chat(contact_id)

        # Cars you're watching (Observer pattern). Alerts for these show up in Notifications above.
        watch_box = tk.LabelFrame(self, text="My Watchlist", padx=10, pady=10)
        watch_box.pack(fill="x", pady=(15, 0))

        watches = get_watchlist(Session().user_id())
        if not watches:
            tk.Label(watch_box, text="You're not watching any cars. Use Add Watchlist on Find a Car.").grid(row=0, column=0, sticky="w")

        for row, w in enumerate(watches):
            text = f"{w['year']} {w['make']} {w['model']} - now ${w['daily_price']:.2f}/day"
            if w["max_price"] is not None:
                text += f" - tell me at ${w['max_price']:.2f} or less"
            if w["desired_from"] is not None:
                text += f" - free {w['desired_from']} to {w['desired_to']}"
            tk.Label(watch_box, text=text).grid(row=row, column=0, sticky="w")
            tk.Button(watch_box, text="Remove", command=lambda c=w["car_id"]: self.unwatch(c)).grid(row=row, column=1, padx=5, pady=2)

    def has_contact(self, user_id):
        # True if this person is already in the Contacts list
        for contact_user_id, name in self.contacts:
            if contact_user_id == user_id:
                return True
        return False

    def pick_contact(self, event):
        # Clicked a name in Contacts
        selected = self.contacts_list.curselection()
        if not selected or not self.contacts:
            return
        self.car_id = None   # switching people, so the message isn't about the earlier car anymore
        user_id, name = self.contacts[selected[0]]
        self.open_chat(user_id)

    def open_chat(self, contact_id):
        # Shows every message with this person, oldest at the top
        self.contact_id = contact_id
        self.chat_box.config(text=get_user_name(contact_id))   # person's name at the top, like the drawing

        self.chat.config(state="normal")
        self.chat.delete("1.0", tk.END)
        their_name = get_user_name(contact_id)
        for m in get_conversation(Session().user_id(), contact_id):
            if m["sender_id"] == Session().user_id():
                # "me" tag puts my messages on the right side
                self.chat.insert(tk.END, f"You: {m['body']}\n\n", "me")
            else:
                self.chat.insert(tk.END, f"{their_name}: {m['body']}\n\n")
        self.chat.config(state="disabled")
        self.chat.see(tk.END)   # scroll to the newest message

    def send(self):
        if self.contact_id is None:
            messagebox.showerror("Message", "Pick a contact first")
            return
        try:
            send_message(Session().user_id(), self.contact_id, self.write.get(), self.car_id)
        except ValueError as e:
            messagebox.showerror("Message", str(e))
            return
        self.write.delete(0, tk.END)
        self.open_chat(self.contact_id)   # reload so the new message shows

    def unwatch(self, car_id):
        unwatch_car(Session().user_id(), car_id)
        self.mediator.notify(self, "watch_removed")


# ------------------------------------------------------------
# Payments: Pay button for each confirmed booking (Proxy pattern, payment.py)
# ------------------------------------------------------------
class PaymentsScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.mediator = app.mediator
        NavBar(self, self.mediator).pack(fill="x", pady=(0, 15))

        # Reuses the payment screen from payment.py.
        # After paying or adding money, tell the mediator so the nav bar's Inbox count
        # picks up the new notification.
        PaymentScreen(self, Session().user_id(), on_change=self.balance_changed).pack(fill="both", expand=True)

    def balance_changed(self):
        self.mediator.notify(self, "payment_made")


# ------------------------------------------------------------
# History: rental history for both sides, plus cancel / complete / reviews
# ------------------------------------------------------------
class HistoryScreen(tk.Frame):
    def __init__(self, app):
        super().__init__(app)
        self.mediator = app.mediator
        user_id = Session().user_id()
        NavBar(self, self.mediator).pack(fill="x", pady=(0, 15))

        # Cars I rented
        rented = tk.LabelFrame(self, text="Cars I Rented", padx=10, pady=10)
        rented.pack(fill="x")
        self.table(rented, ["Car", "Dates", "Price", "Status", ""], get_renter_history(user_id), is_owner=False)

        # People who rented my cars
        mine = tk.LabelFrame(self, text="Rentals of My Cars", padx=10, pady=10)
        mine.pack(fill="x", pady=(15, 0))
        self.table(mine, ["Car", "Renter", "Dates", "Price", "Status", ""], get_owner_history(user_id), is_owner=True)

        # Reviews other people left about me
        reviews = tk.LabelFrame(self, text=f"My Reviews: {rating_text(user_id)}", padx=10, pady=10)
        reviews.pack(fill="x", pady=(15, 0))
        for r in get_reviews_for_user(user_id):
            comment = r["comment"]
            if comment is None:
                comment = ""
            tk.Label(reviews, text=f"{r['rating']} stars from {r['reviewer_name']}: {comment}").pack(anchor="w")

    def table(self, box, headers, bookings, is_owner):
        # One row per booking, with whatever buttons make sense for its status
        for col, text in enumerate(headers):
            tk.Label(box, text=text, font=("Arial", 10, "bold")).grid(row=0, column=col, sticky="w", padx=5)

        if not bookings:
            tk.Label(box, text="Nothing yet").grid(row=1, column=0, sticky="w", padx=5)

        for row, b in enumerate(bookings, start=1):
            values = [f"{b['year']} {b['make']} {b['model']}"]
            if is_owner:
                values.append(b["renter_name"])
            values += [f"{b['start_time']} to {b['end_time']}", f"${b['total_price']:.2f}", b["status"]]
            for col, text in enumerate(values):
                tk.Label(box, text=text).grid(row=row, column=col, sticky="w", padx=5)

            buttons = tk.Frame(box)
            buttons.grid(row=row, column=len(values), sticky="w", padx=5, pady=2)
            booking_id = b["booking_id"]

            # Either side can cancel before it's paid
            if b["status"] in ("pending", "confirmed"):
                tk.Button(buttons, text="Cancel", command=lambda i=booking_id: self.run(cancel_booking, i)).pack(side="left")
            # Owner marks it done once the car comes back, then both can review
            if is_owner and b["status"] == "paid":
                tk.Button(buttons, text="Complete", command=lambda i=booking_id: self.run(complete_booking, i)).pack(side="left")
            if can_review(booking_id, Session().user_id()):
                tk.Button(buttons, text="Review", command=lambda i=booking_id: self.review(i)).pack(side="left")

    def run(self, action, booking_id):
        # Runs cancel_booking or complete_booking and reloads the page
        try:
            action(booking_id, Session().user_id())
        except ValueError as e:
            messagebox.showerror("History", str(e))
        self.mediator.notify(self, "booking_changed")

    def review(self, booking_id):
        # Asks for 1-5 stars and an optional comment
        rating = simpledialog.askinteger("Review", "How many stars? (1-5)", minvalue=1, maxvalue=5, parent=self)
        if rating is None:
            return   # they hit cancel
        comment = simpledialog.askstring("Review", "Any comments? (optional)", parent=self)
        try:
            if comment == "":
                comment = None   # empty comment is saved as no comment
            leave_review(booking_id, Session().user_id(), rating, comment)
        except ValueError as e:
            messagebox.showerror("Review", str(e))
            return
        messagebox.showinfo("Review", "Thanks for the review!")
        self.mediator.notify(self, "review_left")

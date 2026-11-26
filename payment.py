# payment.py
# Fake payment for DriveShare. Uses the Proxy pattern.
#
# Why Proxy: the app never talks to the payment system directly. It talks to PaymentProxy,
# which looks exactly the same (same pay() method) but does security checks first.
# Only if everything checks out does the proxy pass the payment on to the real payment system.
# This is so a bad payment (wrong user, not enough money, paying twice) never reaches it.
#
# 3 parts:
# 1. PaymentService     = the shared "shape", both real and proxy have pay()
# 2. RealPaymentService = actually moves the money (renter balance down, owner balance up)
# 3. PaymentProxy       = the guard in front of it, the GUI only ever uses this one

import os
import tkinter as tk
from abc import ABC, abstractmethod
from main import get_connection
from notifications import send_notification, get_notifications
from booking import get_renter_history

# 1. PaymentService: what every payment system has to have
class PaymentService(ABC):
    @abstractmethod
    def pay(self, booking_id, user_id):
        pass


# 2. RealPaymentService: does the actual money moving
# Doesn't check anything, it trusts whoever calls it. That's why it's hidden behind the proxy.
class RealPaymentService(PaymentService):
    def pay(self, booking_id, user_id):
        # user_id isn't used here, the proxy already checked it. It's only here so
        # pay() looks the same in the real service and the proxy.
        conn = get_connection()
        b = get_booking_info(conn, booking_id)
        amount = b["total_price"]

        # Move the money, renter pays and owner gets paid
        conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, b["renter_id"]))
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, b["owner_id"]))

        # Save a record of the payment and mark the booking paid
        cursor = conn.execute(
            "INSERT INTO payments (booking_id, payer_id, payee_id, amount) VALUES (?, ?, ?, ?)",
            (booking_id, b["renter_id"], b["owner_id"], amount),
        )
        conn.execute("UPDATE bookings SET status = 'paid' WHERE booking_id = ?", (booking_id,))

        # Notify both people
        car_name = f"{b['make']} {b['model']}"
        send_notification(b["renter_id"], "payment", f"You paid ${amount:.2f} for the {car_name}", conn)
        send_notification(b["owner_id"], "payment", f"You received ${amount:.2f} for your {car_name}", conn)

        conn.commit()   # all of it saves together, or none of it does
        conn.close()
        return cursor.lastrowid


# 3. PaymentProxy: checks everything first, then passes it to the real service
class PaymentProxy(PaymentService):
    def __init__(self):
        self._real_service = RealPaymentService()

    def pay(self, booking_id, user_id):
        # Security checks. Raises ValueError with a message the GUI can show.
        conn = get_connection()
        b = get_booking_info(conn, booking_id)
        conn.close()

        if b is None:
            raise ValueError("Booking not found")

        # Check 1: only the renter on this booking can pay for it
        if b["renter_id"] != user_id:
            raise ValueError("You can only pay for your own booking")

        # Check 2: owner has to confirm first, and can't pay twice
        if b["status"] == "paid" or b["status"] == "completed":
            raise ValueError("This booking is already paid")
        if b["status"] != "confirmed":
            raise ValueError("Owner has to confirm the booking before you can pay")

        # Check 3: renter needs enough money
        balance = get_balance(user_id)
        if balance < b["total_price"]:
            raise ValueError(f"Not enough balance. Need ${b['total_price']:.2f}, have ${balance:.2f}")

        # Everything checks out, pass it on to the real payment system
        return self._real_service.pay(booking_id, user_id)


# Helpers
def get_booking_info(conn, booking_id):
    # Gets a booking with the car and owner info
    return conn.execute(
        """SELECT b.*, c.make, c.model, c.owner_id
           FROM bookings b JOIN cars c ON b.car_id = c.car_id
           WHERE b.booking_id = ?""",
        (booking_id,),
    ).fetchone()


def get_balance(user_id):
    # Gets a user's balance. Used to show it on the screen next to the pay button.
    conn = get_connection()
    row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["balance"]


def add_funds(user_id, amount):
    # Adds fake money to a user's balance (ex. the renter can't afford a booking yet).
    # Not a real payment, it just raises the number in the DB and sends a notification.
    # Raises ValueError with a message the GUI can show if the amount is bad.
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Amount has to be a number")
    if amount <= 0:
        raise ValueError("Amount has to be more than $0")
    if amount > 10000:
        raise ValueError("You can add at most $10,000 at a time")

    conn = get_connection()
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    send_notification(user_id, "payment", f"You added ${amount:.2f} to your balance", conn)
    conn.commit()
    conn.close()

# Payment screen: what the renter sees

class PaymentScreen(tk.Frame):

    def __init__(self, master, renter_id, on_change=None):
        super().__init__(master, padx=12, pady=12)
        self.renter_id = renter_id
        self.payment = PaymentProxy() 
        self.on_change = on_change 

        self.balance_label = tk.Label(self, font=("Arial", 14, "bold"))
        self.balance_label.pack(anchor="w")

        funds_row = tk.Frame(self)
        funds_row.pack(anchor="w", pady=(5, 0))
        tk.Label(funds_row, text="Add Funds: $").pack(side="left")
        self.funds_entry = tk.Entry(funds_row, width=10)
        self.funds_entry.pack(side="left")
        tk.Button(funds_row, text="Add", command=self.add_funds).pack(side="left", padx=5)

        tk.Label(self, text="Your bookings", font=("Arial", 12, "underline")).pack(anchor="w", pady=(10, 0))
        self.bookings_frame = tk.Frame(self)
        self.bookings_frame.pack(fill="x")

        self.status_label = tk.Label(self, text="", wraplength=420, justify="left")
        self.status_label.pack(anchor="w", pady=(10, 0))

        tk.Label(self, text="Payment notifications", font=("Arial", 12, "underline")).pack(anchor="w", pady=(10, 0))
        self.notifications_list = tk.Listbox(self, width=60, height=5)
        self.notifications_list.pack(fill="x")

        self.refresh()

    #rereads from the DB
    def refresh(self):
        self.balance_label.config(text=f"Balance: ${get_balance(self.renter_id):.2f}")


        for widget in self.bookings_frame.winfo_children():
            widget.destroy()
        bookings = []
        for b in get_renter_history(self.renter_id):
            if b["status"] == "confirmed" or b["status"] == "paid":
                bookings.append(b)
        if not bookings:
            tk.Label(self.bookings_frame, text="No bookings waiting for payment").pack(anchor="w")

        for b in bookings:
            row = tk.Frame(self.bookings_frame)
            row.pack(fill="x", pady=2)
            info = f"{b['year']} {b['make']} {b['model']}  |  {b['start_time']} to {b['end_time']}"
            tk.Label(row, text=info).pack(side="left")

            if b["status"] == "paid":
                tk.Label(row, text="Paid", fg="green").pack(side="right")
            else:
                # The button shows the amount, clicking it pays that booking
                tk.Button(row, text=f"Pay ${b['total_price']:.2f}",
                          command=lambda booking_id=b["booking_id"]: self.pay(booking_id)).pack(side="right")


        #send notifications
        self.notifications_list.delete(0, tk.END)
        for n in get_notifications(self.renter_id):
            if n["type"] == "payment":
                self.notifications_list.insert(tk.END, n["message"])

    def add_funds(self):
        # What the Add button does
        try:
            add_funds(self.renter_id, self.funds_entry.get().strip())
            self.status_label.config(text="Money added to your balance!", fg="green")
            self.funds_entry.delete(0, tk.END)
            if self.on_change:
                self.on_change()   # new notification, so the Inbox count updates
        except ValueError as e:
            self.status_label.config(text=f"Couldn't add money: {e}", fg="red")
        self.refresh()

    def pay(self, booking_id):
        # What the Pay button does.
        try:
            self.payment.pay(booking_id, self.renter_id)
            self.status_label.config(text="Payment done! The owner has been notified.", fg="green")
            if self.on_change:
                self.on_change()
        except ValueError as e:
            # Not confirmed, already paid, not enough balance, etc.
            self.status_label.config(text=f"Payment failed: {e}", fg="red")
        self.refresh()


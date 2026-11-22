# payment_screen.py
# The "Pay" screen for DriveShare (no real payment, just fake balances in the local DB).
#
# What the renter sees:
#   - their current balance
#   - every booking the owner has confirmed, each with a "Pay $amount" button
#   - their latest payment notifications
# Clicking "Pay $amount" goes through PaymentProxy (Proxy pattern, payment.py), which checks
# the payment and then moves the money: renter balance down, owner balance up,
# booking marked paid, and both people get a notification.
#
# The screen never touches RealPaymentService or the balances directly, it only uses the proxy.
#
# Run this file by itself to see a demo: python payment_screen.py
# (the demo uses its own test database, the real driveshare.db is never touched)

import os
import sys
import tkinter as tk

# database.py and car.py live in car-create/, so let Python find them from here
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "car-create"))

from payment import PaymentProxy, get_balance
from booking import get_renter_history
from notifications import get_notifications


class PaymentScreen(tk.Frame):
    # One screen for one renter. renter_id is whoever is logged in.

    def __init__(self, master, renter_id, on_paid=None):
        super().__init__(master, padx=12, pady=12)
        self.renter_id = renter_id
        self.payment = PaymentProxy()   # the only way this screen can pay
        self.on_paid = on_paid          # optional, lets other parts of the GUI refresh after a payment

        # Balance at the top
        self.balance_label = tk.Label(self, font=("Arial", 14, "bold"))
        self.balance_label.pack(anchor="w")

        # Bookings with pay buttons go in here (rebuilt every refresh)
        tk.Label(self, text="Your bookings", font=("Arial", 12, "underline")).pack(anchor="w", pady=(10, 0))
        self.bookings_frame = tk.Frame(self)
        self.bookings_frame.pack(fill="x")

        # Shows "Payment done" or the reason the proxy blocked it
        self.status_label = tk.Label(self, text="", wraplength=420, justify="left")
        self.status_label.pack(anchor="w", pady=(10, 0))

        # Latest payment notifications
        tk.Label(self, text="Payment notifications", font=("Arial", 12, "underline")).pack(anchor="w", pady=(10, 0))
        self.notifications_list = tk.Listbox(self, width=60, height=5)
        self.notifications_list.pack(fill="x")

        self.refresh()

    def refresh(self):
        # Re-reads everything from the database so the screen always matches it
        self.balance_label.config(text=f"Balance: ${get_balance(self.renter_id):.2f}")

        # Clear out the old booking rows
        for widget in self.bookings_frame.winfo_children():
            widget.destroy()

        # Only confirmed (ready to pay) and paid bookings belong on this screen
        bookings = [b for b in get_renter_history(self.renter_id) if b["status"] in ("confirmed", "paid")]
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

        # Show the newest payment notifications
        self.notifications_list.delete(0, tk.END)
        for n in get_notifications(self.renter_id):
            if n["type"] == "payment":
                self.notifications_list.insert(tk.END, n["message"])

    def pay(self, booking_id):
        # What the Pay button does. The proxy does all the checking.
        try:
            self.payment.pay(booking_id, self.renter_id)
            self.status_label.config(text="Payment done! The owner has been notified.", fg="green")
            if self.on_paid:
                self.on_paid()
        except ValueError as e:
            # Not confirmed, already paid, not enough balance, etc.
            self.status_label.config(text=f"Payment failed: {e}", fg="red")
        self.refresh()


# ------------------------------------------------------------
# Demo: makes a test database with one confirmed booking, then opens the screen.
# Also shows the owner's balance and notifications so you can see both sides change.
# ------------------------------------------------------------
if __name__ == "__main__":
    import database
    database.DB_FILE = os.path.join(database.FOLDER, "demo_payment_driveshare.db")
    if os.path.exists(database.DB_FILE):
        os.remove(database.DB_FILE)

    from database import create_tables, get_connection
    from car import CarBuilder, save_car
    from booking import create_booking, confirm_booking

    create_tables()
    conn = get_connection()
    conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('owner@test.com', 'x', 'Olivia Owner')")
    conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('renter@test.com', 'x', 'Ryan Renter')")
    conn.commit()
    conn.close()
    owner_id, renter_id = 1, 2

    car_id = save_car(CarBuilder(owner_id, "Honda", "Civic", 2020, 30000, 45.00, "Dearborn").build())
    confirm_booking(create_booking(car_id, renter_id, "2026-12-01 09:00", "2026-12-03 09:00"), owner_id)  # $90

    root = tk.Tk()
    root.title("DriveShare - Payment")

    # Owner side, so the demo shows the owner getting paid and notified too
    owner_label = tk.Label(root, padx=12, pady=8, justify="left", bg="#eef")

    def show_owner():
        messages = [n["message"] for n in get_notifications(owner_id) if n["type"] == "payment"]
        owner_label.config(text=f"Owner balance: ${get_balance(owner_id):.2f}\n" + "\n".join(messages))

    PaymentScreen(root, renter_id, on_paid=show_owner).pack(fill="both")
    owner_label.pack(fill="x")
    show_owner()

    root.mainloop()
    os.remove(database.DB_FILE)

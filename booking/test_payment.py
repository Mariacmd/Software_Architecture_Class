# test_payment.py
# Quick test for Payment (Proxy pattern). Run with: python test_payment.py

import os
import database
database.DB_FILE = os.path.join(database.FOLDER, "test_driveshare.db")
if os.path.exists(database.DB_FILE):
    os.remove(database.DB_FILE)

from database import create_tables, get_connection
from car import CarBuilder, save_car
from booking import create_booking, confirm_booking
from payment import PaymentProxy, get_balance
from notifications import get_notifications

create_tables()

# Owner, renter, and a broke renter with only $20
conn = get_connection()
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('owner@test.com', 'x', 'Olivia Owner')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('renter@test.com', 'x', 'Ryan Renter')")
conn.execute("INSERT INTO users (email, password_hash, full_name, balance) VALUES ('broke@test.com', 'x', 'Brooke Broke', 20)")
conn.commit()
conn.close()
owner_id, renter_id, broke_id = 1, 2, 3

car_id = save_car(CarBuilder(owner_id, "Honda", "Civic", 2020, 30000, 45.00, "Dearborn").build())
b1 = create_booking(car_id, renter_id, "2026-12-01 09:00", "2026-12-03 09:00")   # $90
b2 = create_booking(car_id, broke_id, "2026-12-05 09:00", "2026-12-06 09:00")    # $45

payment = PaymentProxy()   # GUI only ever uses the proxy


def check(label, func):
    try:
        func()
        print(f"OK      {label}")
    except ValueError as e:
        print(f"BLOCKED {label} -> {e}")


print(f"Start: renter ${get_balance(renter_id):.2f}, owner ${get_balance(owner_id):.2f}\n")

check("Pay before owner confirms", lambda: payment.pay(b1, renter_id))
confirm_booking(b1, owner_id)
confirm_booking(b2, owner_id)
check("Someone else pays renter's booking", lambda: payment.pay(b1, broke_id))
check("Broke renter pays $45 with $20", lambda: payment.pay(b2, broke_id))
check("Renter pays $90", lambda: payment.pay(b1, renter_id))
check("Renter pays again", lambda: payment.pay(b1, renter_id))

print(f"\nEnd: renter ${get_balance(renter_id):.2f}, owner ${get_balance(owner_id):.2f}")

print("\nPayment notifications:")
for uid in (renter_id, owner_id):
    for n in get_notifications(uid):
        if n["type"] == "payment":
            print("  -", n["message"])

os.remove(database.DB_FILE)

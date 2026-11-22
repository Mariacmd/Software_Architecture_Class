# test_watchlist.py
# Quick test for Edit Car + Watchlist (Observer pattern). Run with: python test_watchlist.py

import os
import database
database.DB_FILE = os.path.join(database.FOLDER, "test_driveshare.db")
if os.path.exists(database.DB_FILE):
    os.remove(database.DB_FILE)

from database import create_tables, get_connection
from car import CarBuilder, save_car, update_price, add_car_availability
from booking import create_booking, cancel_booking
from watchlist import watch_car, get_watchlist
from notifications import get_notifications

create_tables()

conn = get_connection()
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('owner@test.com', 'x', 'Olivia Owner')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('price@test.com', 'x', 'Paul Price')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('dates@test.com', 'x', 'Dana Dates')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('other@test.com', 'x', 'Oscar Other')")
conn.commit()
conn.close()
owner_id, paul, dana, oscar = 1, 2, 3, 4

# Car is $60/day, available Dec 1 to Dec 10
car_id = save_car(CarBuilder(owner_id, "Toyota", "RAV4", 2022, 15000, 60.00, "Ann Arbor")
                  .add_availability("2026-12-01 00:00", "2026-12-10 23:59").build())

# Oscar books Dec 5 to 7
oscar_booking = create_booking(car_id, oscar, "2026-12-05 09:00", "2026-12-07 09:00")


def check(label, func):
    try:
        func()
        print(f"OK      {label}")
    except ValueError as e:
        print(f"BLOCKED {label} -> {e}")


def show(label, user_id):
    # Prints watchlist notifications for a user
    msgs = [n["message"] for n in get_notifications(user_id) if n["type"] == "watchlist"]
    print(f"  {label} has {len(msgs)} watchlist alert(s)" + "".join(f"\n    - {m}" for m in msgs))


print("Setting up watchers:")
check("Paul watches for price $50 or less", lambda: watch_car(paul, car_id, max_price=50))
check("Dana watches for Dec 5-7 (booked by Oscar)", lambda: watch_car(dana, car_id, desired_from="2026-12-05 09:00", desired_to="2026-12-07 09:00"))
check("Paul watches same car again", lambda: watch_car(paul, car_id, max_price=40))
check("Owner watches own car", lambda: watch_car(owner_id, car_id, max_price=40))
check("Watch with nothing set", lambda: watch_car(oscar, car_id))

print("\nStep 1: Price drops $60 -> $55 (still above Paul's $50)")
update_price(car_id, owner_id, 55)
show("Paul", paul)

print("\nStep 2: Price drops $55 -> $48")
update_price(car_id, owner_id, 48)
show("Paul", paul)
show("Dana", dana)

print("\nStep 3: Oscar cancels, Dec 5-7 frees up")
cancel_booking(oscar_booking, oscar)
show("Dana", dana)

print("\nOther edit checks:")
check("Someone else edits the price", lambda: update_price(car_id, paul, 10))
check("Owner adds Dec 20-25 availability", lambda: add_car_availability(car_id, owner_id, "2026-12-20 00:00", "2026-12-25 23:59"))

print("\nPaul's watchlist:", [f"{w['make']} {w['model']} (max ${w['max_price']:.0f})" for w in get_watchlist(paul)])

os.remove(database.DB_FILE)

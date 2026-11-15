# test_booking.py
# Quick test for Booking. Run with: python test_booking.py
# Deletes and remakes the test database each time so results are the same.

import os
import database
database.DB_FILE = os.path.join(database.FOLDER, "test_driveshare.db")
if os.path.exists(database.DB_FILE):
    os.remove(database.DB_FILE)

from database import create_tables, get_connection
from car import CarBuilder, save_car
from booking import (create_booking, confirm_booking, cancel_booking,
                     get_renter_history, get_owner_history)
from notifications import get_notifications

create_tables()

# Make an owner and a renter (Maria's register code will do this for real)
conn = get_connection()
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('owner@test.com', 'x', 'Olivia Owner')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('renter@test.com', 'x', 'Ryan Renter')")
conn.commit()
conn.close()
owner_id, renter_id = 1, 2

# Owner lists a car available Dec 1 to Dec 20
car = (CarBuilder(owner_id, "Honda", "Civic", 2020, 30000, 45.00, "Dearborn")
       .add_availability("2026-12-01 00:00", "2026-12-20 23:59")
       .build())
car_id = save_car(car)


def check(label, func):
    # Runs a step and prints if it worked or what the error was
    try:
        result = func()
        print(f"OK      {label}" + (f" -> {result}" if result else ""))
    except ValueError as e:
        print(f"BLOCKED {label} -> {e}")


# Test 1: normal booking, Dec 1 9am to Dec 3 9am = 2 days x $45 = $90
check("Book Dec 1-3", lambda: create_booking(car_id, renter_id, "2026-12-01 09:00", "2026-12-03 09:00"))

# Test 2: overlapping dates should get blocked
check("Book Dec 2-4 (overlaps)", lambda: create_booking(car_id, renter_id, "2026-12-02 09:00", "2026-12-04 09:00"))

# Test 3: back to back is fine
check("Book Dec 3-4 (back to back)", lambda: create_booking(car_id, renter_id, "2026-12-03 09:00", "2026-12-04 09:00"))

# Test 4: outside the owner's availability
check("Book Dec 25-27 (not available)", lambda: create_booking(car_id, renter_id, "2026-12-25 09:00", "2026-12-27 09:00"))

# Test 5: owner can't rent their own car
check("Owner books own car", lambda: create_booking(car_id, owner_id, "2026-12-10 09:00", "2026-12-11 09:00"))

# Test 6: owner confirms booking 1, renter cancels booking 2
check("Owner confirms booking 1", lambda: confirm_booking(1, owner_id))
check("Renter cancels booking 2", lambda: cancel_booking(2, renter_id))

# Test 7: cancelled dates are free again
check("Book Dec 3-4 again after cancel", lambda: create_booking(car_id, renter_id, "2026-12-03 09:00", "2026-12-04 09:00"))

print("\nRenter history:")
for b in get_renter_history(renter_id):
    print(f"  #{b['booking_id']} {b['make']} {b['model']} {b['start_time']} to {b['end_time']} ${b['total_price']:.2f} [{b['status']}]")

print("\nOwner notifications:")
for n in get_notifications(owner_id):
    print("  -", n["message"])

print("\nRenter notifications:")
for n in get_notifications(renter_id):
    print("  -", n["message"])

os.remove(database.DB_FILE)

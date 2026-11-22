# test_reviews_search.py
# Quick test for Search and Reviews. Run with: python test_reviews_search.py

import os
import database
database.DB_FILE = os.path.join(database.FOLDER, "test_driveshare.db")
if os.path.exists(database.DB_FILE):
    os.remove(database.DB_FILE)

from database import create_tables, get_connection
from car import CarBuilder, save_car
from booking import create_booking, confirm_booking, complete_booking
from payment import PaymentProxy
from search import search_cars, get_car
from reviews import leave_review, get_reviews_for_user, get_average_rating, can_review

create_tables()

conn = get_connection()
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('owner@test.com', 'x', 'Olivia Owner')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('renter@test.com', 'x', 'Ryan Renter')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('other@test.com', 'x', 'Oscar Other')")
conn.commit()
conn.close()
owner_id, renter_id, oscar = 1, 2, 3

# 3 cars from the same owner
civic = save_car(CarBuilder(owner_id, "Honda", "Civic", 2020, 30000, 45.00, "Dearborn, MI").set_seats(5).build())
rav4 = save_car(CarBuilder(owner_id, "Toyota", "RAV4", 2022, 15000, 60.00, "Ann Arbor, MI").set_seats(5).build())
mini = save_car(CarBuilder(owner_id, "Mini", "Cooper", 2019, 50000, 35.00, "Dearborn, MI").set_seats(2).build())

# Oscar books the Civic Dec 5 to 7
create_booking(civic, oscar, "2026-12-05 09:00", "2026-12-07 09:00")


def names(cars):
    return [f"{c['make']} {c['model']} ${c['daily_price']:.0f}" for c in cars]


def check(label, func):
    try:
        result = func()
        print(f"OK      {label}" + (f" -> {result}" if result is not None else ""))
    except ValueError as e:
        print(f"BLOCKED {label} -> {e}")


print("SEARCH")
print("  All cars:             ", names(search_cars()))
print("  In Dearborn:          ", names(search_cars(location="dearborn")))
print("  Max $50/day:          ", names(search_cars(max_price=50)))
print("  At least 4 seats:     ", names(search_cars(min_seats=4)))
print("  Free Dec 5-7:         ", names(search_cars(start_time="2026-12-05 09:00", end_time="2026-12-07 09:00")))
print("  Dearborn + free Dec 5-7:", names(search_cars(location="Dearborn", start_time="2026-12-05 09:00", end_time="2026-12-07 09:00")))
print("  Owner searching (own cars hidden):", names(search_cars(renter_id=owner_id)))
print("  Car details:          ", get_car(rav4)["owner_name"], "owns the RAV4")

print("\nREVIEWS")
# Full rental: book, confirm, pay, complete
b = create_booking(rav4, renter_id, "2026-12-01 09:00", "2026-12-03 09:00")
check("Review before rental is done", lambda: leave_review(b, renter_id, 5))
confirm_booking(b, owner_id)
PaymentProxy().pay(b, renter_id)
complete_booking(b, owner_id)

print("  Renter can review?", can_review(b, renter_id))
check("Renter reviews owner (5 stars)", lambda: leave_review(b, renter_id, 5, "Clean car, easy pickup"))
check("Owner reviews renter (4 stars)", lambda: leave_review(b, owner_id, 4, "Returned a bit late"))
check("Renter reviews again", lambda: leave_review(b, renter_id, 1))
check("Stranger reviews", lambda: leave_review(b, oscar, 1))
check("6 star rating", lambda: leave_review(b, oscar, 6))
print("  Renter can review now?", can_review(b, renter_id))

print(f"\n  Owner rating: {get_average_rating(owner_id)} stars")
for r in get_reviews_for_user(owner_id):
    print(f"    - {r['rating']} stars from {r['reviewer_name']}: {r['comment']}")
print(f"  Renter rating: {get_average_rating(renter_id)} stars")
print(f"  Oscar rating: {get_average_rating(oscar)} (no reviews yet)")

os.remove(database.DB_FILE)

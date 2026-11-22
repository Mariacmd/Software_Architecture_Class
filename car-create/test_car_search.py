# test_car_search.py
# Tests for get_car, get_all_cars and search_cars. Run with: python test_car_search.py
# Deletes and remakes a separate test database each time so results are always the same
# (the real driveshare.db is never touched).

import os
import database
database.DB_FILE = os.path.join(database.FOLDER, "test_search_driveshare.db")
if os.path.exists(database.DB_FILE):
    os.remove(database.DB_FILE)

from database import create_tables, get_connection
from car import CarBuilder, save_car, get_car, get_all_cars, search_cars

create_tables()

# Make an owner and a renter (Maria's register code will do this for real)
conn = get_connection()
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('owner@test.com', 'x', 'Olivia Owner')")
conn.execute("INSERT INTO users (email, password_hash, full_name) VALUES ('renter@test.com', 'x', 'Ryan Renter')")
conn.commit()
conn.close()
owner_id, renter_id = 1, 2

# A few cars to search through
civic_id = save_car(CarBuilder(owner_id, "Honda", "Civic", 2020, 30000, 45.00, "Dearborn")
                    .set_color("Silver")
                    .add_availability("2026-12-01 00:00", "2026-12-20 23:59")
                    .build())
rav4_id = save_car(CarBuilder(owner_id, "Toyota", "RAV4", 2022, 15000, 60.00, "Ann Arbor")
                   .set_color("Blue")
                   .set_description("Clean, good on gas, 100% smoke free")
                   .build())                       # no availability set = always available
accord_id = save_car(CarBuilder(owner_id, "Honda", "Accord", 2018, 70000, 40.00, "Ann Arbor")
                     .build())
hidden_id = save_car(CarBuilder(owner_id, "Ford", "Focus", 2019, 40000, 30.00, "Dearborn")
                     .build())

# Owner hides the Focus, it shouldn't show up for renters
conn = get_connection()
conn.execute("UPDATE cars SET is_active = 0 WHERE car_id = ?", (hidden_id,))
# Someone already booked the RAV4 Dec 5-8
conn.execute("""INSERT INTO bookings (car_id, renter_id, start_time, end_time, total_price)
                VALUES (?, ?, '2026-12-05 10:00', '2026-12-08 10:00', 180)""", (rav4_id, renter_id))
conn.commit()
conn.close()


def ids(rows):
    # Just the car IDs from a list of rows, easier to compare
    return [r["car_id"] for r in rows]


passed = 0


def check(name, actual, expected):
    # Prints PASS/FAIL for each test and stops if something's wrong
    global passed
    assert actual == expected, f"FAIL {name}: expected {expected}, got {actual}"
    passed += 1
    print("PASS", name)


# ---- get_car ----
car = get_car(civic_id)
check("get_car returns the right car", (car["make"], car["model"], car["year"]), ("Honda", "Civic", 2020))
check("get_car returns None for a bad id", get_car(9999), None)
check("get_car still finds a hidden car (for the owner)", get_car(hidden_id)["model"], "Focus")

# ---- get_all_cars ----
check("get_all_cars skips hidden cars, cheapest first", ids(get_all_cars()), [accord_id, civic_id, rav4_id])

# ---- search_cars: text ----
check("search by make", ids(search_cars("honda")), [accord_id, civic_id])
check("search is not case sensitive", ids(search_cars("HoNdA")), [accord_id, civic_id])
check("search by partial model", ids(search_cars("civ")), [civic_id])
check("search by location", ids(search_cars("ann arbor")), [accord_id, rav4_id])
check("search by color", ids(search_cars("blue")), [rav4_id])
check("search by year", ids(search_cars("2022")), [rav4_id])
check("search by description", ids(search_cars("gas")), [rav4_id])
check("every word has to match", ids(search_cars("honda ann arbor")), [accord_id])
check("no matches gives empty list", ids(search_cars("tesla")), [])
check("empty search gives all active cars", ids(search_cars("")), ids(get_all_cars()))
check("blank spaces search gives all active cars", ids(search_cars("   ")), ids(get_all_cars()))
check("None search gives all active cars", ids(search_cars(None)), ids(get_all_cars()))
check("hidden car never shows in search", ids(search_cars("focus")), [])
check("% is searched as a real character", ids(search_cars("100%")), [rav4_id])
check("% alone isn't a wildcard", ids(search_cars("%")), [rav4_id])
check("_ isn't a wildcard", ids(search_cars("_")), [])

# ---- search_cars: dates ----
# Civic is only available Dec 1-20, RAV4 is booked Dec 5-8, Accord has no limits
check("dates inside Civic's range, during RAV4 booking",
      ids(search_cars("", "2026-12-06 09:00", "2026-12-07 09:00")), [accord_id, civic_id])
check("dates outside Civic's range",
      ids(search_cars("", "2027-01-05 09:00", "2027-01-06 09:00")), [accord_id, rav4_id])
check("dates partly outside Civic's range",
      ids(search_cars("civic", "2026-12-19 09:00", "2026-12-22 09:00")), [])
check("back to back with a booking is fine",
      ids(search_cars("rav4", "2026-12-08 10:00", "2026-12-09 10:00")), [rav4_id])
check("text and dates together",
      ids(search_cars("ann arbor", "2026-12-06 09:00", "2026-12-07 09:00")), [accord_id])

# Cancelled booking should free the RAV4 up again
conn = get_connection()
conn.execute("UPDATE bookings SET status = 'cancelled' WHERE car_id = ?", (rav4_id,))
conn.commit()
conn.close()
check("cancelled booking doesn't block dates",
      ids(search_cars("rav4", "2026-12-06 09:00", "2026-12-07 09:00")), [rav4_id])

# ---- search_cars: bad dates get rejected ----
for name, args in [("only a start date", ("", "2026-12-06 09:00", None)),
                   ("end before start", ("", "2026-12-07 09:00", "2026-12-06 09:00"))]:
    try:
        search_cars(*args)
        raise AssertionError(f"FAIL {name}: should have been rejected")
    except ValueError as e:
        passed += 1
        print("PASS", name, "rejected:", e)

print(f"\nAll {passed} tests passed")
os.remove(database.DB_FILE)

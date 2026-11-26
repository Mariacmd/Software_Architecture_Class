# booking.py
# Booking a car for DriveShare. Also covers Rental History.
#
# How a booking goes:
# 1. Renter picks a car and dates -> create_booking() (status = pending, owner gets notified)
# 2. Owner accepts -> confirm_booking() (status = confirmed, renter gets notified)
# 3. Renter pays (payment.py, Proxy pattern) -> status = paid
# 4. Rental is over -> complete_booking() (status = completed, now they can leave reviews)
# Either side can cancel before it's paid -> cancel_booking()
#
# Main rule: the same car can't be booked by 2 people for overlapping dates.
# Checked here first so we get a clear message, and the database trigger is a backup.
#
# The bottom of this file is Search: renters can search by any mix of these (all optional):
# - location    (ex. "Dearborn", matches part of the pickup location)
# - dates       (only shows cars that are available AND not booked for those dates)
# - max price   (per day)
# - min seats
# - make        (ex. "Honda")
# Results are sorted cheapest first.

import math
import sqlite3
from datetime import datetime
from main import get_connection
from notifications import send_notification

DATE_FORMAT = "%Y-%m-%d %H:%M"   # dates look like "2026-12-01 09:00"


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def calculate_price(daily_price, start_time, end_time):
    # Total price = number of days x daily price.
    # Any part of a day counts as a full day, ex. 25 hours = 2 days.
    start = datetime.strptime(start_time, DATE_FORMAT)
    end = datetime.strptime(end_time, DATE_FORMAT)
    hours = (end - start).total_seconds() / 3600
    days = math.ceil(hours / 24)
    return round(days * daily_price, 2)


def is_car_free(conn, car_id, start_time, end_time):
    # Checks if any active booking overlaps these dates.
    # Two bookings overlap when new start < old end AND new end > old start.
    # Back to back is fine (one ends at 10:00, next starts at 10:00).
    overlap = conn.execute(
        """SELECT 1 FROM bookings
           WHERE car_id = ? AND status <> 'cancelled'
             AND ? < end_time AND ? > start_time""",
        (car_id, start_time, end_time),
    ).fetchone()
    return overlap is None


def is_in_availability(conn, car_id, start_time, end_time):
    # Checks the dates fall inside one of the owner's availability ranges.
    # If the owner never set any ranges, the car is treated as always available.
    ranges = conn.execute(
        "SELECT available_from, available_to FROM car_availability WHERE car_id = ?",
        (car_id,),
    ).fetchall()

    if len(ranges) == 0:
        return True

    for r in ranges:
        if r["available_from"] <= start_time and end_time <= r["available_to"]:
            return True
    return False


# ------------------------------------------------------------
# Booking actions
# ------------------------------------------------------------
def create_booking(car_id, renter_id, start_time, end_time):
    # Renter requests a car for certain dates. Returns the new booking_id.
    # Raises ValueError with a message the GUI can show if something is wrong.
    if end_time <= start_time:
        raise ValueError("End date has to be after the start date")

    conn = get_connection()
    try:
        car = conn.execute("SELECT * FROM cars WHERE car_id = ?", (car_id,)).fetchone()

        if car is None or car["is_active"] == 0:
            raise ValueError("This car isn't available for rent")
        if car["owner_id"] == renter_id:
            raise ValueError("You can't rent your own car")
        if not is_in_availability(conn, car_id, start_time, end_time):
            raise ValueError("Owner hasn't made the car available for those dates")
        if not is_car_free(conn, car_id, start_time, end_time):
            raise ValueError("Car is already booked for those dates")

        total = calculate_price(car["daily_price"], start_time, end_time)

        cursor = conn.execute(
            """INSERT INTO bookings (car_id, renter_id, start_time, end_time, total_price)
               VALUES (?, ?, ?, ?, ?)""",
            (car_id, renter_id, start_time, end_time, total),
        )
        booking_id = cursor.lastrowid

        # Let the owner know someone wants their car
        send_notification(
            car["owner_id"], "booking",
            f"New booking request for your {car['make']} {car['model']} "
            f"({start_time} to {end_time}), ${total:.2f}",
            conn,
        )

        conn.commit()
        return booking_id

    except sqlite3.IntegrityError:
        # Backup in case the database trigger catches an overlap
        raise ValueError("Car is already booked for those dates")
    finally:
        conn.close()


def confirm_booking(booking_id, owner_id):
    # Owner accepts a pending booking. Renter gets notified.
    change_status(booking_id, owner_id, "pending", "confirmed")


def cancel_booking(booking_id, user_id):
    # Owner or renter cancels before payment. Other person gets notified.
    # Cancelled bookings free up the dates again.
    conn = get_connection()
    b = get_booking_with_car(conn, booking_id)
    conn.close()

    if b is None:
        raise ValueError("Booking not found")
    if user_id not in (b["renter_id"], b["owner_id"]):
        raise ValueError("This isn't your booking")
    if b["status"] not in ("pending", "confirmed"):
        raise ValueError("Only pending or confirmed bookings can be cancelled")

    conn = get_connection()
    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?", (booking_id,))

    # Notify whoever didn't cancel
    if user_id == b["renter_id"]:
        other_person = b["owner_id"]
    else:
        other_person = b["renter_id"]
    send_notification(other_person, "booking",
                      f"Booking #{booking_id} for the {b['make']} {b['model']} was cancelled", conn)
    conn.commit()
    conn.close()

    # Dates just freed up, so tell anyone watching this car (Observer pattern)
    from notifications import CarSubject   # imported here since notifications.py imports booking.py
    CarSubject(b["car_id"]).notify_watchers()


def complete_booking(booking_id, owner_id):
    # Owner marks the rental as finished once the car is returned.
    change_status(booking_id, owner_id, "paid", "completed")


def change_status(booking_id, owner_id, from_status, to_status):
    # Shared code for confirm and complete. Checks it's the owner and the status is right.
    conn = get_connection()
    b = get_booking_with_car(conn, booking_id)
    conn.close()

    if b is None:
        raise ValueError("Booking not found")
    if b["owner_id"] != owner_id:
        raise ValueError("Only the car owner can do this")
    if b["status"] != from_status:
        raise ValueError(f"Booking has to be {from_status} first")

    conn = get_connection()
    conn.execute("UPDATE bookings SET status = ? WHERE booking_id = ?", (to_status, booking_id))
    send_notification(b["renter_id"], "booking",
                      f"Your booking for the {b['make']} {b['model']} is now {to_status}", conn)
    conn.commit()
    conn.close()


def get_booking_with_car(conn, booking_id):
    # Gets a booking plus the car's info and owner in one go
    return conn.execute(
        """SELECT b.*, c.make, c.model, c.owner_id
           FROM bookings b JOIN cars c ON b.car_id = c.car_id
           WHERE b.booking_id = ?""",
        (booking_id,),
    ).fetchone()


# ------------------------------------------------------------
# Rental History
# ------------------------------------------------------------
def get_renter_history(renter_id):
    # All cars this user has rented, newest first
    conn = get_connection()
    rows = conn.execute(
        """SELECT b.*, c.make, c.model, c.year
           FROM bookings b JOIN cars c ON b.car_id = c.car_id
           WHERE b.renter_id = ?
           ORDER BY b.start_time DESC""",
        (renter_id,),
    ).fetchall()
    conn.close()
    return rows


def get_owner_history(owner_id):
    # All bookings on this user's cars, newest first
    conn = get_connection()
    rows = conn.execute(
        """SELECT b.*, c.make, c.model, c.year, u.full_name AS renter_name
           FROM bookings b
           JOIN cars c ON b.car_id = c.car_id
           JOIN users u ON b.renter_id = u.user_id
           WHERE c.owner_id = ?
           ORDER BY b.start_time DESC""",
        (owner_id,),
    ).fetchall()
    conn.close()
    return rows


# ------------------------------------------------------------
# Search (renter looking for a car by location, dates, price, seats or make)
# Uses is_car_free() and is_in_availability() from the top of this file.
# ------------------------------------------------------------
def search_cars(location=None, start_time=None, end_time=None, max_price=None,
                min_seats=None, make=None, renter_id=None):
    # Returns a list of matching cars.
    # renter_id is optional. If given, the renter's own cars are left out of the results.
    if start_time is None and end_time is not None:
        raise ValueError("Pick both a start and end date")
    if start_time is not None and end_time is None:
        raise ValueError("Pick both a start and end date")
    if start_time is not None and end_time <= start_time:
        raise ValueError("End date has to be after the start date")

    # Build the SQL one filter at a time, only adding the ones the renter filled in
    sql = "SELECT * FROM cars WHERE is_active = 1"
    values = []

    if location:
        sql += " AND pickup_location LIKE ?"
        values.append(f"%{location}%")      # % means "anything before or after"
    if max_price is not None:
        sql += " AND daily_price <= ?"
        values.append(max_price)
    if min_seats is not None:
        sql += " AND seats >= ?"
        values.append(min_seats)
    if make:
        sql += " AND make LIKE ?"
        values.append(f"%{make}%")
    if renter_id is not None:
        sql += " AND owner_id <> ?"
        values.append(renter_id)

    sql += " ORDER BY daily_price ASC"

    conn = get_connection()
    cars = conn.execute(sql, values).fetchall()

    # Date check can't be done in one simple query, so check each car after
    if start_time is not None:
        free_cars = []
        for car in cars:
            if is_in_availability(conn, car["car_id"], start_time, end_time) and is_car_free(conn, car["car_id"], start_time, end_time):
                free_cars.append(car)
        cars = free_cars

    conn.close()
    return cars


def get_car(car_id):
    # Gets one car's full info, for the car details page
    conn = get_connection()
    car = conn.execute(
        """SELECT c.*, u.full_name AS owner_name
           FROM cars c JOIN users u ON c.owner_id = u.user_id
           WHERE c.car_id = ?""",
        (car_id,),
    ).fetchone()
    conn.close()
    return car

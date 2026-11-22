# search.py
# Searching for cars to rent on DriveShare.
#
# Renter can search by any mix of these (all optional):
# - location    (ex. "Dearborn", matches part of the pickup location)
# - dates       (only shows cars that are available AND not booked for those dates)
# - max price   (per day)
# - min seats
# - make        (ex. "Honda")
# Results are sorted cheapest first.

from database import get_connection
from booking import is_car_free, is_in_availability


def search_cars(location=None, start_time=None, end_time=None, max_price=None,
                min_seats=None, make=None, renter_id=None):
    # Returns a list of matching cars.
    # renter_id is optional. If given, the renter's own cars are left out of the results.
    if (start_time is None) != (end_time is None):
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
        cars = [car for car in cars
                if is_in_availability(conn, car["car_id"], start_time, end_time)
                and is_car_free(conn, car["car_id"], start_time, end_time)]

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

# car.py
# Car listing for DriveShare. Uses the Builder pattern.
#
# Why Builder: a car has some info that's always required (make, model, year, etc.)
# and some that's optional (color, seats, description). Instead of one huge constructor
# with a bunch of None values, the owner sets only what they want, then calls build().
# Essentially build() checks everything is valid and hands back a finished Car.

from database import get_connection


# ------------------------------------------------------------
# Car: the finished product. Just holds the car's info.
# ------------------------------------------------------------
class Car:
    def __init__(self, builder):
        # Car only gets made through CarBuilder, so it copies everything from the builder
        self.car_id = None                      # set after it's saved to the database
        self.owner_id = builder.owner_id
        self.make = builder.make
        self.model = builder.model
        self.year = builder.year
        self.mileage = builder.mileage
        self.daily_price = builder.daily_price
        self.pickup_location = builder.pickup_location
        self.color = builder.color              # optional
        self.seats = builder.seats              # optional
        self.description = builder.description  # optional
        self.availability = builder.availability  # list of (from, to) date ranges

    def __str__(self):
        # How the car shows up when printed, ex. "2020 Honda Civic - $45.00/day (Dearborn)"
        return f"{self.year} {self.make} {self.model} - ${self.daily_price:.2f}/day ({self.pickup_location})"


# ------------------------------------------------------------
# CarBuilder: builds a Car step by step.
# Required info goes in the constructor, optional info uses set_ methods.
# Each set_ method returns self so they can be chained together.
# ------------------------------------------------------------
class CarBuilder:
    def __init__(self, owner_id, make, model, year, mileage, daily_price, pickup_location):
        # Required info
        self.owner_id = owner_id
        self.make = make
        self.model = model
        self.year = year
        self.mileage = mileage
        self.daily_price = daily_price
        self.pickup_location = pickup_location

        # Optional info starts empty
        self.color = None
        self.seats = None
        self.description = None
        self.availability = []

    def set_color(self, color):
        self.color = color
        return self

    def set_seats(self, seats):
        self.seats = seats
        return self

    def set_description(self, description):
        self.description = description
        return self

    def add_availability(self, available_from, available_to):
        # Adds a date range the car can be rented. Dates as "YYYY-MM-DD HH:MM"
        # Can be called more than once for more than one range.
        self.availability.append((available_from, available_to))
        return self

    def build(self):
        # Checks the info before making the car. This is so bad listings never get saved.
        if not self.make or not self.model:
            raise ValueError("Make and model are required")
        if self.year < 1950 or self.year > 2027:
            raise ValueError("Year is not valid")
        if self.mileage < 0:
            raise ValueError("Mileage can't be negative")
        if self.daily_price <= 0:
            raise ValueError("Price has to be more than 0")
        if not self.pickup_location:
            raise ValueError("Pickup location is required")
        for start, end in self.availability:
            if end <= start:
                raise ValueError("Availability end has to be after the start")

        return Car(self)


# ------------------------------------------------------------
# Database functions for cars
# ------------------------------------------------------------
def save_car(car):
    # Saves a new car and its availability to the database. Returns the new car_id.
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO cars (owner_id, make, model, year, mileage, daily_price,
                             pickup_location, color, seats, description)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (car.owner_id, car.make, car.model, car.year, car.mileage, car.daily_price,
         car.pickup_location, car.color, car.seats, car.description),
    )
    car.car_id = cursor.lastrowid

    # Save each availability range in the car_availability table
    for start, end in car.availability:
        conn.execute(
            "INSERT INTO car_availability (car_id, available_from, available_to) VALUES (?, ?, ?)",
            (car.car_id, start, end),
        )

    conn.commit()
    conn.close()
    return car.car_id


def get_cars_by_owner(owner_id):
    # Gets all cars listed by one owner. Used for the owner's "My Cars" page.
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cars WHERE owner_id = ?", (owner_id,)).fetchall()
    conn.close()
    return rows


# ------------------------------------------------------------
# Edit car (owner managing their listing)
# Price drops and new dates tell the watchers (Observer pattern, watchlist.py)
# ------------------------------------------------------------
def _check_owner(conn, car_id, owner_id):
    # Makes sure the car exists and belongs to this owner before editing
    car = conn.execute("SELECT * FROM cars WHERE car_id = ?", (car_id,)).fetchone()
    if car is None:
        raise ValueError("Car not found")
    if car["owner_id"] != owner_id:
        raise ValueError("You can only edit your own car")
    return car


def update_price(car_id, owner_id, new_price):
    # Owner changes the daily price. If it went down, watchers get checked.
    if new_price <= 0:
        raise ValueError("Price has to be more than 0")

    conn = get_connection()
    try:
        car = _check_owner(conn, car_id, owner_id)
        old_price = car["daily_price"]
        conn.execute("UPDATE cars SET daily_price = ? WHERE car_id = ?", (new_price, car_id))
        conn.commit()
    finally:
        conn.close()

    # Only a price drop can help a watcher, so only notify then
    if new_price < old_price:
        from watchlist import CarSubject   # imported here so car.py doesn't need watchlist to load
        CarSubject(car_id).notify_watchers()


def add_car_availability(car_id, owner_id, available_from, available_to):
    # Owner adds a new date range the car can be rented. Watchers get checked.
    if available_to <= available_from:
        raise ValueError("Availability end has to be after the start")

    conn = get_connection()
    try:
        _check_owner(conn, car_id, owner_id)
        conn.execute(
            "INSERT INTO car_availability (car_id, available_from, available_to) VALUES (?, ?, ?)",
            (car_id, available_from, available_to),
        )
        conn.commit()
    finally:
        conn.close()

    from watchlist import CarSubject
    CarSubject(car_id).notify_watchers()


def remove_car_availability(car_id, owner_id, availability_id):
    # Owner removes a date range
    conn = get_connection()
    try:
        _check_owner(conn, car_id, owner_id)
        conn.execute("DELETE FROM car_availability WHERE availability_id = ? AND car_id = ?",
                     (availability_id, car_id))
        conn.commit()
    finally:
        conn.close()


def get_car_availability(car_id):
    # All date ranges for a car, for the edit car page
    conn = get_connection()
    rows = conn.execute("SELECT * FROM car_availability WHERE car_id = ? ORDER BY available_from",
                        (car_id,)).fetchall()
    conn.close()
    return rows


def set_car_active(car_id, owner_id, active):
    # Owner hides (False) or shows (True) their listing in search
    conn = get_connection()
    try:
        _check_owner(conn, car_id, owner_id)
        conn.execute("UPDATE cars SET is_active = ? WHERE car_id = ?", (1 if active else 0, car_id))
        conn.commit()
    finally:
        conn.close()

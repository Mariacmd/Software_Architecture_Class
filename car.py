# car.py
#this file contains the car, carbuilder, and make a newe car listing, saving cars, reading them back from the db, ownder edit car, and renter search for car


from main import get_connection

class Car:
    def __init__(self, builder):
        self.car_id = None   # the database gives it an id when it's saved
        self.owner_id = builder.owner_id
        self.make = builder.make
        self.model = builder.model
        self.year = builder.year
        self.mileage = builder.mileage
        self.daily_price = builder.daily_price
        self.pickup_location = builder.pickup_location
        self.color = builder.color
        self.seats = builder.seats
        self.description = builder.description
        self.availability = builder.availability 

    def __str__(self):
        # what print(car) shows
        return f"{self.year} {self.make} {self.model} - ${self.daily_price:.2f}/day ({self.pickup_location})"

class CarBuilder:
    def __init__(self, owner_id, make, model, year, mileage, daily_price, pickup_location):
            # required info
            self.owner_id = owner_id
            self.make = make
            self.model = model
            self.year = year
            self.mileage = mileage
            self.daily_price = daily_price
            self.pickup_location = pickup_location

            # optional info starts empty
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
        # adds a date range the car can be rented, ex. "2026-12-01 00:00" to "2026-12-20 23:00"
        self.availability.append((available_from, available_to))
        return self

    def build(self):
        # Checks the info before making the car. Raises ValueError with a message the GUI can show.
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

def save_car(car):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO cars (owner_id, make, model, year, mileage, daily_price, pickup_location, color, seats, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    #stuff to go into it
    (car.owner_id, car.make, car.model, car.year, car.mileage, car.daily_price, car.pickup_location, car.color, car.seats, car.description),
    
    )


    car.car_id = cursor.lastrowid 

    #check availbility 
    for start, end in car.availability:
        conn.execute("INSERT INTO car_availability (car_id, available_from, available_to) VALUES(?,?,?)",
                    (car.car_id, start, end),
                    )

    conn.commit()
    conn.close()
    return car.car_id



# various get car functions

def get_car(car_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM cars WHERE car_id = ?", (car_id,)).fetchone()
    conn.close()
    return row

def get_all_cars():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cars WHERE is_active = 1 ORDER BY daily_price, car_id").fetchall()
    conn.close()
    return rows

def get_cars_by_owner(owner_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cars WHERE owner_id =?", (owner_id,)).fetchall()
    conn.close()
    return rows


#Edit cars and price functions

#check if you are hte owner
def check_owner(conn, car_id, owner_id):
    car = conn.execute("SELECT * FROM cars WHERE car_id = ?", (car_id,)).fetchone()

    if car is None:
        raise ValueError("Car not found")
    elif car["owner_id"] != owner_id:
        raise ValueError("You can only edit your own car")

    return car

def update_price(car_id, owner_id, new_price):
    if new_price <= 0:
        raise ValueError("price must be more than 0")

    conn = get_connection()
    try:
        car = check_owner(conn, car_id, owner_id)
        old_price = car["daily_price"]
        conn.execute("UPDATE cars SET daily_price = ? WHERE car_id = ?", (new_price, car_id))
        conn.commit()
    finally:
        conn.close()

    if new_price < old_price:
        from notifications import CarSubject
        CarSubject(car_id).notify_watchers()


def add_car_availability(car_id, owner_id, available_from, available_to):
    if available_to <= available_from:
        raise ValueError("Availability end has to be after the start")

    conn = get_connection()
    try:
        check_owner(conn, car_id, owner_id)
        conn.execute("INSERT INTO car_availability (car_id, available_from, available_to) VALUES (?, ?, ?)",
                     (car_id, available_from, available_to))
        conn.commit()
    finally:
        conn.close()

    from notifications import CarSubject
    CarSubject(car_id).notify_watchers()


def remove_car_availability(car_id, owner_id, availability_id):
     conn = get_connection()
     check_owner(conn, car_id, owner_id)
     conn.execute("DELETE FROM car_availability WHERE availability_id = ? AND car_id = ?", (availability_id, car_id))
     conn.commit()
     conn.close()

def get_car_availability(car_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM car_availability WHERE car_id = ? ORDER BY available_from", (car_id,)).fetchall()
    conn.close()
    return rows

def set_car_active(car_id, owner_id, active):
    conn = get_connection()
    check_owner(conn, car_id, owner_id)
    conn.execute("UPDATE cars SET is_active = ? WHERE car_id = ?", (1 if active else 0, car_id))
    conn.commit()
    conn.close()


#when searching search word through every column 
SEARCH_COLUMNS = ["make","model","pickup_location","color", "description", "CAST(year AS TEXT)"]

def search_cars(search_text, start_time = None, end_time = None):
    a = "SELECT * FROM cars WHERE is_active = 1"
    params = []

    if search_text is None:
        search_text = ""

    words = search_text.split()

    #clean up the words
    for word in words:
        safe_word = word.replace("\\", "\\\\")
        safe_word = safe_word.replace("%", "\\%")
        safe_word = safe_word.replace("_", "\\_")

        conditions =[] 
        for column in SEARCH_COLUMNS:
            conditions.append(f"{column} LIKE ? ESCAPE '\\'")
            params.append(f"%{safe_word}%")

        a += " AND(" +" OR ".join(conditions) + ")"

    if start_time is not None or end_time is not None:
        if start_time is None or end_time is None:
            raise ValueError("Pick a start and end date")

        if end_time <= start_time:
            raise ValueError("end date too early")
        
        a += " AND (NOT EXISTS( SELECT 1 FROM car_availability a WHERE a.car_id = cars.car_id) OR EXISTS(SELECT 1 FROM car_availability a WHERE a.car_id = cars.car_id AND a.available_from <= ? AND ? <= a.available_to))"

        params.append(start_time)
        params.append(end_time)

        a += " AND NOT EXISTS ( SELECT 1 FROM bookings b WHERE b.car_id = cars.car_id AND b.status <> 'cancelled' AND ? < b.end_time AND ? > b.start_time)"
        params.append(start_time)
        params.append(end_time)

    a += " ORDER BY daily_price, car_id"

    conn = get_connection()
    rows = conn.execute(a, params).fetchall()
    conn.close()
    
    return rows

# car.py
#this has the functions for creating the car and listing the car 

from database import get_connection


class Car:
    def __init__(self, builder):
        self.car_id = None 
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
        #how car gets printed in string format
        return f"{self.year} {self.make} {self.model} - ${self.daily_price:.2f}/day ({self.pickup_location})"


#car builder 

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

    # add a date range
    def add_availability(self, available_from, available_to):
        
        self.availability.append((available_from, available_to))
        return self

    def build(self):
        # Checks the info before making the car
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


#DB funcitons for the cars
def save_car(car):
    # save the car to the DB
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
        conn.execute("INSERT INTO car_availability (car_id, available_from, available_to) VALUES (?, ?, ?)",(car.car_id, start, end),)

    conn.commit()
    conn.close()
    return car.car_id



# get all cars listed by car
def get_cars_by_owner(owner_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cars WHERE owner_id = ?", (owner_id,)).fetchall()
    conn.close()
    return rows

# get car by id should be the whole row
def get_car(car_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM cars WHERE car_id = ?", (car_id,)).fetchone()
    conn.close()
    return row

#just gets the cars where the is_active is true/1 and should order them all by the price and id
def get_all_cars():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cars WHERE is_active = 1 ORDER BY daily_price, car_id").fetchall()
    conn.close()
    return rows


#the columns in the car database that the user gonna search 
SEARCH_COLUMNS = ["make", "model", "pickup_location", "color", "description", "CAST(year AS TEXT)"]


def search_cars(search_text, start_time=None, end_time=None):
   
    sql = "SELECT * FROM cars WHERE is_active = 1"
    params = []

    # cut the words up
    words = (search_text or "").split()

    for word in words:

        # remove the special chars
        safe_word = word.replace("\\", "\\\\")
        safe_word = safe_word.replace("%", "\\%")
        safe_word = safe_word.replace("_", "\\_")


        search_conditions = []
        for column in SEARCH_COLUMNS:
            condition = f"{column} LIKE ? ESCAPE '\\'"
            search_conditions.append(condition)


        sql += " AND (" + " OR ".join(search_conditions) + ")"

        for column in SEARCH_COLUMNS:
            params.append(f"%{safe_word}%")


    
    if start_time is not None or end_time is not None:

        if start_time is None or end_time is None:
            raise ValueError("Pick both a start and end date, or neither")

        if end_time <= start_time:
            raise ValueError("End date has to be after the start date")

        sql += """
            AND (
                -- If the car has no availability records, treat it as available
                NOT EXISTS (
                    SELECT 1
                    FROM car_availability a
                    WHERE a.car_id = cars.car_id
                )

                OR

                -- Otherwise, check if the requested dates fall within
                -- one of the car's availability periods
                EXISTS (
                    SELECT 1
                    FROM car_availability a
                    WHERE a.car_id = cars.car_id
                    AND a.available_from <= ?
                    AND ? <= a.available_to
                )
            )
        """
        params.append(start_time)
        params.append(end_time)

        sql += """
            AND NOT EXISTS (
                SELECT 1
                FROM bookings b
                WHERE b.car_id = cars.car_id
                AND b.status <> 'cancelled'

                -- Check if the requested dates overlap an existing booking
                AND ? < b.end_time
                AND ? > b.start_time
            )
        """

        params.append(start_time)
        params.append(end_time)

        sql += " ORDER BY daily_price, car_id"

        conn = get_connection()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return rows

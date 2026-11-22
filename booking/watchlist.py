# watchlist.py
# Watchlist for DriveShare. Uses the Observer pattern.
#
# Why Observer: renters want to know when a car they like gets cheaper or frees up.
# Instead of renters checking over and over, the car tells them when something changes.
#
# 3 parts:
# 1. Observer       = the shared "shape", every watcher has update()
# 2. RenterWatcher  = a renter watching one car, with their price and/or dates
# 3. CarSubject     = the car being watched. Keeps a list of watchers and calls
#                     update() on all of them when the car changes (notify_watchers)
#
# What triggers notify_watchers():
# - Owner lowers the price            (car.py, update_price)
# - Owner adds new available dates    (car.py, add_car_availability)
# - A booking gets cancelled          (booking.py, cancel_booking)
#
# Each watcher checks if the change matches what the renter wanted.
# Only then does the renter get a notification.

from abc import ABC, abstractmethod
from database import get_connection
from notifications import send_notification
from booking import is_car_free, is_in_availability


# ------------------------------------------------------------
# 1. Observer: what every watcher has to have
# ------------------------------------------------------------
class Observer(ABC):
    @abstractmethod
    def update(self, car, conn):
        pass


# ------------------------------------------------------------
# 2. RenterWatcher: one renter watching one car
# ------------------------------------------------------------
class RenterWatcher(Observer):
    def __init__(self, renter_id, max_price=None, desired_from=None, desired_to=None):
        self.renter_id = renter_id
        self.max_price = max_price          # notify if price is at or below this
        self.desired_from = desired_from    # notify if car is free for these dates
        self.desired_to = desired_to

    def update(self, car, conn):
        # Gets called by the car when it changes. Checks if the car now matches
        # what the renter wanted. If yes, sends a notification.
        if car["is_active"] == 0:
            return

        # Check price, if the renter set one
        price_ok = self.max_price is None or car["daily_price"] <= self.max_price

        # Check dates, if the renter set them. Car has to be available AND not booked.
        dates_ok = True
        if self.desired_from is not None:
            dates_ok = (is_in_availability(conn, car["car_id"], self.desired_from, self.desired_to)
                        and is_car_free(conn, car["car_id"], self.desired_from, self.desired_to))

        if price_ok and dates_ok:
            message = f"A car you're watching matches what you wanted: {car['year']} {car['make']} {car['model']}, ${car['daily_price']:.2f}/day"
            if self.desired_from is not None:
                message += f", free {self.desired_from} to {self.desired_to}"
            send_notification(self.renter_id, "watchlist", message, conn)


# ------------------------------------------------------------
# 3. CarSubject: the car being watched
# Watchers are saved in the watchlist table so they're still there after the app closes.
# ------------------------------------------------------------
class CarSubject:
    def __init__(self, car_id):
        self.car_id = car_id

    def attach(self, watcher):
        # Adds a watcher (saves it to the watchlist table)
        conn = get_connection()
        conn.execute(
            """INSERT INTO watchlist (renter_id, car_id, max_price, desired_from, desired_to)
               VALUES (?, ?, ?, ?, ?)""",
            (watcher.renter_id, self.car_id, watcher.max_price, watcher.desired_from, watcher.desired_to),
        )
        conn.commit()
        conn.close()

    def detach(self, renter_id):
        # Removes a watcher
        conn = get_connection()
        conn.execute("DELETE FROM watchlist WHERE car_id = ? AND renter_id = ?", (self.car_id, renter_id))
        conn.commit()
        conn.close()

    def get_watchers(self, conn):
        # Loads everyone watching this car from the database as RenterWatcher objects
        rows = conn.execute("SELECT * FROM watchlist WHERE car_id = ?", (self.car_id,)).fetchall()
        return [RenterWatcher(r["renter_id"], r["max_price"], r["desired_from"], r["desired_to"]) for r in rows]

    def notify_watchers(self):
        # Car changed, tell every watcher. Each one decides if it matters to them.
        conn = get_connection()
        car = conn.execute("SELECT * FROM cars WHERE car_id = ?", (self.car_id,)).fetchone()
        if car is not None:
            for watcher in self.get_watchers(conn):
                watcher.update(car, conn)
        conn.commit()
        conn.close()


# ------------------------------------------------------------
# Functions the GUI uses
# ------------------------------------------------------------
def watch_car(renter_id, car_id, max_price=None, desired_from=None, desired_to=None):
    # Renter starts watching a car. Needs at least a price or dates to watch for.
    if max_price is None and desired_from is None:
        raise ValueError("Set a max price or dates to watch for")
    if (desired_from is None) != (desired_to is None):
        raise ValueError("Set both a start and end date")
    if desired_from is not None and desired_to <= desired_from:
        raise ValueError("End date has to be after the start date")
    if max_price is not None and max_price <= 0:
        raise ValueError("Max price has to be more than 0")

    conn = get_connection()
    car = conn.execute("SELECT * FROM cars WHERE car_id = ?", (car_id,)).fetchone()
    already = conn.execute(
        "SELECT 1 FROM watchlist WHERE car_id = ? AND renter_id = ?", (car_id, renter_id)
    ).fetchone()
    conn.close()

    if car is None:
        raise ValueError("Car not found")
    if car["owner_id"] == renter_id:
        raise ValueError("You can't watch your own car")
    if already:
        raise ValueError("You're already watching this car")

    CarSubject(car_id).attach(RenterWatcher(renter_id, max_price, desired_from, desired_to))


def unwatch_car(renter_id, car_id):
    # Renter stops watching a car
    CarSubject(car_id).detach(renter_id)


def get_watchlist(renter_id):
    # All cars a renter is watching, for the "My Watchlist" page
    conn = get_connection()
    rows = conn.execute(
        """SELECT w.*, c.make, c.model, c.year, c.daily_price
           FROM watchlist w JOIN cars c ON w.car_id = c.car_id
           WHERE w.renter_id = ?""",
        (renter_id,),
    ).fetchall()
    conn.close()
    return rows

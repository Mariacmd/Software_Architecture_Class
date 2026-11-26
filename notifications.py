# notifications.py
# Saves in-app notifications for users. Booking, payment, and watchlist all use this.
# This is so every part of the app sends notifications the same way.


from abc import ABC, abstractmethod
from main import get_connection


def send_notification(user_id, type, message, conn=None):
    # Adds a notification for a user.
    # type is one of: booking, payment, watchlist, message, review
    # conn is optional. If the caller is already in the middle of saving something,

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    conn.execute(
        "INSERT INTO notifications (user_id, type, message) VALUES (?, ?, ?)",
        (user_id, type, message),
    )

    if own_conn:
        conn.commit()
        conn.close()


def get_notifications(user_id, unread_only=False):
    # Gets a user's notifications, newest first. Used for the notifications page.
    conn = get_connection()
    sql = "SELECT * FROM notifications WHERE user_id = ?"
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY notification_id DESC"
    rows = conn.execute(sql, (user_id,)).fetchall()
    conn.close()
    return rows


def mark_all_read(user_id):
    # Marks all of a user's notifications as read once they open the page.
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# observer what every watcher has
class Observer(ABC):
    @abstractmethod
    def update(self, car, conn):
        pass


# renter watcher
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
        price_ok = True
        if self.max_price is not None and car["daily_price"] > self.max_price:
            price_ok = False

        # Check dates, if the renter set them. Car has to be available AND not booked.
        dates_ok = True
        if self.desired_from is not None:
            # imported here since booking.py imports this file
            from booking import is_car_free, is_in_availability
            if not is_in_availability(conn, car["car_id"], self.desired_from, self.desired_to):
                dates_ok = False
            if not is_car_free(conn, car["car_id"], self.desired_from, self.desired_to):
                dates_ok = False

        if price_ok and dates_ok:
            message = f"A car you're watching matches what you wanted: {car['year']} {car['make']} {car['model']}, ${car['daily_price']:.2f}/day"
            if self.desired_from is not None:
                message += f", free {self.desired_from} to {self.desired_to}"
            send_notification(self.renter_id, "watchlist", message, conn)


#  car subject or the car being watched
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
        watchers = []
        for r in rows:
            watchers.append(RenterWatcher(r["renter_id"], r["max_price"], r["desired_from"], r["desired_to"]))
        return watchers

    def notify_watchers(self):
        # Car changed, tell every watcher. Each one decides if it matters to them.
        conn = get_connection()
        car = conn.execute("SELECT * FROM cars WHERE car_id = ?", (self.car_id,)).fetchone()
        if car is not None:
            for watcher in self.get_watchers(conn):
                watcher.update(car, conn)
        conn.commit()
        conn.close()


#functions the gui uses
def watch_car(renter_id, car_id, max_price=None, desired_from=None, desired_to=None):
    # Renter starts watching a car. Needs at least a price or dates to watch for.
    if max_price is None and desired_from is None:
        raise ValueError("Set a max price or dates to watch for")
    if desired_from is None and desired_to is not None:
        raise ValueError("Set both a start and end date")
    if desired_from is not None and desired_to is None:
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

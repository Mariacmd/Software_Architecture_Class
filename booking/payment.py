# payment.py
# Fake payment for DriveShare. Uses the Proxy pattern.
#
# Why Proxy: the app never talks to the payment system directly. It talks to PaymentProxy,
# which looks exactly the same (same pay() method) but does security checks first.
# Only if everything checks out does the proxy pass the payment on to the real payment system.
# This is so a bad payment (wrong user, not enough money, paying twice) never reaches it.
#
# 3 parts:
# 1. PaymentService     = the shared "shape", both real and proxy have pay()
# 2. RealPaymentService = actually moves the money (renter balance down, owner balance up)
# 3. PaymentProxy       = the guard in front of it, the GUI only ever uses this one

from abc import ABC, abstractmethod
from database import get_connection
from notifications import send_notification


# ------------------------------------------------------------
# 1. PaymentService: what every payment system has to have
# ------------------------------------------------------------
class PaymentService(ABC):
    @abstractmethod
    def pay(self, booking_id, user_id):
        pass


# ------------------------------------------------------------
# 2. RealPaymentService: does the actual money moving
# Doesn't check anything, it trusts whoever calls it. That's why it's hidden behind the proxy.
# ------------------------------------------------------------
class RealPaymentService(PaymentService):
    def pay(self, booking_id, user_id):
        conn = get_connection()
        b = _get_booking(conn, booking_id)
        amount = b["total_price"]

        # Move the money, renter pays and owner gets paid
        conn.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, b["renter_id"]))
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, b["owner_id"]))

        # Save a record of the payment and mark the booking paid
        cursor = conn.execute(
            "INSERT INTO payments (booking_id, payer_id, payee_id, amount) VALUES (?, ?, ?, ?)",
            (booking_id, b["renter_id"], b["owner_id"], amount),
        )
        conn.execute("UPDATE bookings SET status = 'paid' WHERE booking_id = ?", (booking_id,))

        # Notify both people
        car_name = f"{b['make']} {b['model']}"
        send_notification(b["renter_id"], "payment", f"You paid ${amount:.2f} for the {car_name}", conn)
        send_notification(b["owner_id"], "payment", f"You received ${amount:.2f} for your {car_name}", conn)

        conn.commit()   # all of it saves together, or none of it does
        conn.close()
        return cursor.lastrowid


# ------------------------------------------------------------
# 3. PaymentProxy: checks everything first, then passes it to the real service
# ------------------------------------------------------------
class PaymentProxy(PaymentService):
    def __init__(self):
        # Proxy holds the real service. Nobody else gets to touch it.
        self._real_service = RealPaymentService()

    def pay(self, booking_id, user_id):
        # Security checks. Raises ValueError with a message the GUI can show.
        conn = get_connection()
        b = _get_booking(conn, booking_id)

        if b is None:
            conn.close()
            raise ValueError("Booking not found")

        # Check 1: only the renter on this booking can pay for it
        if b["renter_id"] != user_id:
            conn.close()
            raise ValueError("You can only pay for your own booking")

        # Check 2: owner has to confirm first, and can't pay twice
        if b["status"] == "paid" or b["status"] == "completed":
            conn.close()
            raise ValueError("This booking is already paid")
        if b["status"] != "confirmed":
            conn.close()
            raise ValueError("Owner has to confirm the booking before you can pay")

        # Check 3: renter needs enough money
        balance = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()["balance"]
        conn.close()
        if balance < b["total_price"]:
            raise ValueError(f"Not enough balance. Need ${b['total_price']:.2f}, have ${balance:.2f}")

        # Everything checks out, pass it on to the real payment system
        return self._real_service.pay(booking_id, user_id)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _get_booking(conn, booking_id):
    # Gets a booking with the car and owner info
    return conn.execute(
        """SELECT b.*, c.make, c.model, c.owner_id
           FROM bookings b JOIN cars c ON b.car_id = c.car_id
           WHERE b.booking_id = ?""",
        (booking_id,),
    ).fetchone()


def get_balance(user_id):
    # Gets a user's balance. Used to show it on the screen next to the pay button.
    conn = get_connection()
    row = conn.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["balance"]

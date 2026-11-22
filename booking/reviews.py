# reviews.py
# Reviews and ratings for DriveShare.
#
# After a rental is completed, both sides can review each other:
# - renter reviews the owner (how was the car, pickup, communication)
# - owner reviews the renter (returned on time, took care of the car)
# Ratings are 1 to 5 stars, comment is optional.
# Each person can only review once per booking.

from database import get_connection
from notifications import send_notification


def leave_review(booking_id, reviewer_id, rating, comment=None):
    # Saves a review. Figures out who it's about from the booking.
    # Raises ValueError with a message the GUI can show if something is wrong.
    if rating < 1 or rating > 5:
        raise ValueError("Rating has to be 1 to 5 stars")

    conn = get_connection()
    try:
        b = conn.execute(
            """SELECT b.*, c.make, c.model, c.owner_id
               FROM bookings b JOIN cars c ON b.car_id = c.car_id
               WHERE b.booking_id = ?""",
            (booking_id,),
        ).fetchone()

        if b is None:
            raise ValueError("Booking not found")
        if b["status"] != "completed":
            raise ValueError("You can only review after the rental is completed")

        # Reviewer has to be on the booking. The other person is who it's about.
        if reviewer_id == b["renter_id"]:
            reviewee_id = b["owner_id"]
        elif reviewer_id == b["owner_id"]:
            reviewee_id = b["renter_id"]
        else:
            raise ValueError("You can only review your own rentals")

        already = conn.execute(
            "SELECT 1 FROM reviews WHERE booking_id = ? AND reviewer_id = ?",
            (booking_id, reviewer_id),
        ).fetchone()
        if already:
            raise ValueError("You already reviewed this rental")

        cursor = conn.execute(
            """INSERT INTO reviews (booking_id, reviewer_id, reviewee_id, rating, comment)
               VALUES (?, ?, ?, ?, ?)""",
            (booking_id, reviewer_id, reviewee_id, rating, comment),
        )

        # Let the other person know they got a review
        send_notification(reviewee_id, "review",
                          f"You got a {rating} star review for the {b['make']} {b['model']} rental", conn)

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_reviews_for_user(user_id):
    # All reviews written about a user, newest first. Shows on their profile.
    conn = get_connection()
    rows = conn.execute(
        """SELECT r.*, u.full_name AS reviewer_name
           FROM reviews r JOIN users u ON r.reviewer_id = u.user_id
           WHERE r.reviewee_id = ?
           ORDER BY r.review_id DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_average_rating(user_id):
    # Average star rating for a user, ex. 4.5. Returns None if they have no reviews yet.
    conn = get_connection()
    row = conn.execute(
        "SELECT AVG(rating) AS avg, COUNT(*) AS total FROM reviews WHERE reviewee_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()

    if row["total"] == 0:
        return None
    return round(row["avg"], 1)


def can_review(booking_id, user_id):
    # True if this user can still leave a review for this booking.
    # Used by the GUI to show or hide the "Leave Review" button.
    conn = get_connection()
    b = conn.execute(
        """SELECT b.status, b.renter_id, c.owner_id
           FROM bookings b JOIN cars c ON b.car_id = c.car_id
           WHERE b.booking_id = ?""",
        (booking_id,),
    ).fetchone()
    already = conn.execute(
        "SELECT 1 FROM reviews WHERE booking_id = ? AND reviewer_id = ?", (booking_id, user_id)
    ).fetchone()
    conn.close()

    if b is None or b["status"] != "completed" or already:
        return False
    return user_id in (b["renter_id"], b["owner_id"])

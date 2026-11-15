# notifications.py
# Saves in-app notifications for users. Booking, payment, and watchlist all use this.
# This is so every part of the app sends notifications the same way.

from database import get_connection


def send_notification(user_id, type, message, conn=None):
    # Adds a notification for a user.
    # type is one of: booking, payment, watchlist, message, review
    # conn is optional. If the caller is already in the middle of saving something,
    # they pass their connection so it all saves together.
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

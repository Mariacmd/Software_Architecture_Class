# messaging.py
# Messaging between car owners and renters on DriveShare.

from main import get_connection
from notifications import send_notification


def send_message(sender_id, receiver_id, body, car_id=None):
    # Saves a message. car_id is optional, it's for when the message is about a specific car.
    
    body = (body or "").strip()
    if not body:
        raise ValueError("Type a message first")
    if sender_id == receiver_id:
        raise ValueError("You can't message yourself")

    conn = get_connection()
    try:
        sender = conn.execute("SELECT full_name FROM users WHERE user_id = ?", (sender_id,)).fetchone()
        receiver = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (receiver_id,)).fetchone()
        if sender is None or receiver is None:
            raise ValueError("User not found")

        cursor = conn.execute(
            "INSERT INTO messages (sender_id, receiver_id, car_id, body) VALUES (?, ?, ?, ?)",
            (sender_id, receiver_id, car_id, body),
        )

        # Let them know they have a new message
        send_notification(receiver_id, "message", f"New message from {sender['full_name']}", conn)

        conn.commit()   # message and notification save together
        return cursor.lastrowid
    finally:
        conn.close()


def get_conversation(user_id, other_id):
    # All messages between 2 people, oldest first, so it reads top to bottom like a chat
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM messages
           WHERE (sender_id = ? AND receiver_id = ?)
              OR (sender_id = ? AND receiver_id = ?)
           ORDER BY message_id""",
        (user_id, other_id, other_id, user_id),
    ).fetchall()
    conn.close()
    return rows


def get_contacts(user_id):
    # Everyone this user can message: people they've already talked to,
    # plus owners/renters they have a booking with. Sorted by name.
    conn = get_connection()
    rows = conn.execute(
        """SELECT user_id, full_name FROM users WHERE user_id IN (
                             SELECT receiver_id FROM messages WHERE sender_id = ?
               UNION
               SELECT sender_id FROM messages WHERE receiver_id = ?
               UNION
               SELECT c.owner_id FROM bookings b JOIN cars c ON b.car_id = c.car_id WHERE b.renter_id = ?
               UNION
               SELECT b.renter_id FROM bookings b JOIN cars c ON b.car_id = c.car_id WHERE c.owner_id = ?
           )
           AND user_id <> ?
           ORDER BY full_name""",
        (user_id, user_id, user_id, user_id, user_id),
    ).fetchall()
    conn.close()
    return rows


def get_user_name(user_id):
    # Just the person's name, for the top of the chat box
    conn = get_connection()
    row = conn.execute("SELECT full_name FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["full_name"] if row else None

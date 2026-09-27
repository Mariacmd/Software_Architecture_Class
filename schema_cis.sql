-- DriveShare Database Schema using Turo as an example.
-- Each table is like spreadsheet tab: each line inside is a column

PRAGMA foreign_keys = ON;


-- Table 1: Users. Everyone who signs up goes here.(owners and renters)
-- Same account can list a car and rent a car.
CREATE TABLE users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID for each user
    email          TEXT NOT NULL UNIQUE,               -- login email, can't be used twice
    password_hash  TEXT NOT NULL,                      -- scrambled password, never the real one
    full_name      TEXT NOT NULL,                      -- user name
    balance        REAL NOT NULL DEFAULT 500.00        -- starting default fake money
);


-- Table 2: Security Questions. 
-- Order for password recovery (Chain of Responsibility).
--  all 3 correct = reset password.
CREATE TABLE security_questions (
    question_id    INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID for each question
    user_id        INTEGER NOT NULL REFERENCES users(user_id),  -- which user it belongs to
    question_order INTEGER NOT NULL,                   -- 1, 2 or 3 (order they get asked)
    question_text  TEXT NOT NULL,                      -- the question
    answer_hash    TEXT NOT NULL                       -- scrambled answer
);


-- Table 3: Cars that owners list for rent.
-- Required info can't be empty but optional info can be. 
-- owner only fills in what they want and the builder handles the rest.
CREATE TABLE cars (
    car_id           INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID for each car
    owner_id         INTEGER NOT NULL REFERENCES users(user_id),  -- who owns the car
    make             TEXT NOT NULL,                      -- brand. eg Honda
    model            TEXT NOT NULL,                      -- eg Civic
    year             INTEGER NOT NULL,                   -- eg 2020
    mileage          INTEGER NOT NULL,                   -- miles on the car
    daily_price      REAL NOT NULL,                      -- price per day
    pickup_location  TEXT NOT NULL,                      -- where renter picks it up
    color            TEXT,                               -- optional
    seats            INTEGER,                            -- optional
    description      TEXT,                               -- optional notes from owner
    is_active        INTEGER NOT NULL DEFAULT 1          -- 1 = shows in search, 0 = hidden
);


-- Table 4: Car Availability.
-- This is the availability calendar. Owner can update these anytime.
CREATE TABLE car_availability (
    availability_id  INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID
    car_id           INTEGER NOT NULL REFERENCES cars(car_id),  -- which car
    available_from   TEXT NOT NULL,                      -- start date or time
    available_to     TEXT NOT NULL                       -- end date or time
);


-- Table 5: Bookings. A renter reserving a car for certain dates.
-- covers Rental History, just pull up past bookings for that user. No extra table needed.
CREATE TABLE bookings (
    booking_id   INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID for each booking
    car_id       INTEGER NOT NULL REFERENCES cars(car_id),     -- which car
    renter_id    INTEGER NOT NULL REFERENCES users(user_id),   -- who is renting
    start_time   TEXT NOT NULL,                      -- rental start
    end_time     TEXT NOT NULL,                      -- rental end
    total_price  REAL NOT NULL,                      -- days x daily price
    status       TEXT NOT NULL DEFAULT 'pending'     -- pending, confirmed, paid, completed or cancelled
);

-- Double booking check. Stops the same car from being rented by 2 people on overlapping dates. No errors
-- If a new booking overlaps an old one, it gets rejected. Back to back bookings are fine.
CREATE TRIGGER prevent_double_booking
BEFORE INSERT ON bookings
BEGIN
    SELECT RAISE(ABORT, 'Car is already booked for those dates')
    WHERE EXISTS (
        SELECT 1 FROM bookings
        WHERE car_id = NEW.car_id
          AND status <> 'cancelled'
          AND NEW.start_time < end_time    -- new one starts before old one ends
          AND NEW.end_time > start_time    -- and new one ends after old one starts
    );
END;


-- Table 6: Payments. Record of each payment.
-- Payment goes through the Proxy first. Proxy checks it, then renter balance goes down,
-- owner balance goes up, and both get a notification.
CREATE TABLE payments (
    payment_id  INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID
    booking_id  INTEGER NOT NULL REFERENCES bookings(booking_id),  -- which booking got paid
    payer_id    INTEGER NOT NULL REFERENCES users(user_id),        -- renter money out
    payee_id    INTEGER NOT NULL REFERENCES users(user_id),        -- owner money in
    amount      REAL NOT NULL,                      -- how much
    paid_at     TEXT NOT NULL DEFAULT (datetime('now'))  -- when
);


-- Table 7: Watchlist. Renters watching a car (Observer pattern).
-- Renter sets a max price and or the dates they want. 
-- When price drops or it frees up and matches, renter gets notified.
CREATE TABLE watchlist (
    watch_id      INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID
    renter_id     INTEGER NOT NULL REFERENCES users(user_id),  -- who is watching
    car_id        INTEGER NOT NULL REFERENCES cars(car_id),    -- which car
    max_price     REAL,                               -- notify if price is at or below this
    desired_from  TEXT,                               -- notify if car is free starting here
    desired_to    TEXT                                -- and ending here
);


-- Table 8: Notifications. alerts.
-- Booking requests, confirmations, payments, watchlist alerts new messages.
CREATE TABLE notifications (
    notification_id  INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID
    user_id          INTEGER NOT NULL REFERENCES users(user_id),  -- who gets it
    type             TEXT NOT NULL,                      -- booking, payment, watchlist, message, etc.
    message          TEXT NOT NULL,                      -- text that shows up
    is_read          INTEGER NOT NULL DEFAULT 0,         -- 0 = unread, 1 = read
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))  -- when it was sent
);


-- Table 9: Messages. Chat between owners and renters.
CREATE TABLE messages (
    message_id   INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID
    sender_id    INTEGER NOT NULL REFERENCES users(user_id),  -- who sent it
    receiver_id  INTEGER NOT NULL REFERENCES users(user_id),  -- who gets it
    car_id       INTEGER REFERENCES cars(car_id),    
    body         TEXT NOT NULL,                      -- the message
    sent_at      TEXT NOT NULL DEFAULT (datetime('now'))  -- when sent
);


-- Table 10: Reviews. Ratings after a rental.
-- owner rates renter and renter rates owner.
CREATE TABLE reviews (
    review_id    INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique ID
    booking_id   INTEGER NOT NULL REFERENCES bookings(booking_id),  -- which rental
    reviewer_id  INTEGER NOT NULL REFERENCES users(user_id),        -- who wrote it
    reviewee_id  INTEGER NOT NULL REFERENCES users(user_id),        -- who its about
    rating       INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),   -- 1-5 stars
    comment      TEXT                                -- optional written review
);


-- Note: Logged in user (Singleton pattern) is kept in the program's memory, not the database.
-- So no table needed for it. Same for Mediator, that's all UI side.

-- Main concerns:
-- 1. Database type = Written for SQLite since it needs no setup. If we go with MySQL or Postgres
--    it only needs small changes. Decide once backend language is picked.
-- 2. Passwords = Need to hash passwords and security answers before saving. Answers should be
--    lowercased first so "Fluffy" and "fluffy" both work.
--  * Think of whether we want car photos, would just be one more column (image_url).

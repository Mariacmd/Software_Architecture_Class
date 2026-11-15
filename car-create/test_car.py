# test_car.py
# Quick test for Create Car. Run with: python test_car.py

from database import create_tables, get_connection
from car import CarBuilder, save_car, get_cars_by_owner

create_tables()

# Need a user to own the car (Maria's register code will do this for real)
conn = get_connection()
conn.execute("INSERT OR IGNORE INTO users (email, password_hash, full_name) VALUES ('owner@test.com', 'x', 'Test Owner')")
conn.commit()
owner_id = conn.execute("SELECT user_id FROM users WHERE email = 'owner@test.com'").fetchone()["user_id"]
conn.close()

# Test 1: build a car with only required info
car1 = CarBuilder(owner_id, "Honda", "Civic", 2020, 30000, 45.00, "Dearborn").build()
print("Built:", car1)

# Test 2: build a car with optional info chained on
car2 = (CarBuilder(owner_id, "Toyota", "RAV4", 2022, 15000, 60.00, "Ann Arbor")
        .set_color("Blue")
        .set_seats(5)
        .set_description("Clean, good on gas")
        .add_availability("2026-12-01 09:00", "2026-12-10 18:00")
        .build())
print("Built:", car2, "| color:", car2.color, "| seats:", car2.seats)

# Test 3: save both and read them back
save_car(car1)
save_car(car2)
print("Owner's cars:", [f'{r["make"]} {r["model"]}' for r in get_cars_by_owner(owner_id)])

# Test 4: bad info should get rejected
try:
    CarBuilder(owner_id, "Ford", "Focus", 2019, 40000, -5, "Detroit").build()
except ValueError as e:
    print("Rejected bad car:", e)

"""
Mealert - Step 2: the database.

Stores three things in a SQLite file (mealert.db):
    menu_items  - every dish served, by date, dining hall and meal
    users       - people who signed up for alerts
    favorites   - dishes (keywords) each user wants to be alerted about

To load a day's menus into the database:
    /usr/bin/python3 db.py menus_2026-10-05.json
"""

import json
import sqlite3
import sys

DB_FILE = "mealert.db"


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # lets us use row["name"] instead of row[0]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the tables if they don't exist yet."""
    with connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                location    TEXT NOT NULL,
                period      TEXT NOT NULL,
                dish_id     TEXT NOT NULL,
                name        TEXT NOT NULL,
                station     TEXT,
                description TEXT,
                diet_tags   TEXT,      -- JSON list, e.g. ["Vegan", "Vegetarian"]
                allergens   TEXT,      -- JSON list, e.g. ["Egg", "Milk"]
                calories    INTEGER,
                portion     TEXT,
                UNIQUE (date, location, period, dish_id)
            );

            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS favorites (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL,   -- e.g. "chicken tenders" or "biscuits"
                UNIQUE (user_id, keyword)
            );
        """)


# ---------- Menus ----------

def save_menus(menus):
    """
    Save the output of fetch_menus.py (a list of meals, each with dishes).
    Running it twice for the same day won't create duplicates.
    """
    count = 0
    with connect() as conn:
        for meal in menus:
            for dish in meal["dishes"]:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO menu_items
                        (date, location, period, dish_id, name, station,
                         description, diet_tags, allergens, calories, portion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meal["date"], meal["location"], meal["period"],
                        dish["id"], dish["name"], dish.get("station"),
                        dish.get("description"),
                        json.dumps(dish.get("diet_tags", [])),
                        json.dumps(dish.get("allergens", [])),
                        dish.get("calories"), dish.get("portion"),
                    ),
                )
                count += 1
    return count


def get_menu(date, location=None):
    """Get all dishes for a date, optionally for one dining hall."""
    query = "SELECT * FROM menu_items WHERE date = ?"
    params = [date]
    if location:
        query += " AND location = ?"
        params.append(location)
    query += " ORDER BY location, period, station, name"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dish(r) for r in rows]


def row_to_dish(row):
    dish = dict(row)
    dish["diet_tags"] = json.loads(dish["diet_tags"] or "[]")
    dish["allergens"] = json.loads(dish["allergens"] or "[]")
    return dish


# ---------- Users ----------

def add_user(name, email):
    """Add a user and return their id. If the email exists, return the existing id."""
    email = email.strip().lower()
    with connect() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return existing["id"]
        cur = conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name.strip(), email))
        return cur.lastrowid


def get_users():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]


def delete_user(user_id):
    with connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------- Favorites ----------

def add_favorite(user_id, keyword):
    """Save a favorite dish keyword for a user (stored in lowercase)."""
    keyword = keyword.strip().lower()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO favorites (user_id, keyword) VALUES (?, ?)",
            (user_id, keyword),
        )


def get_favorites(user_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT keyword FROM favorites WHERE user_id = ? ORDER BY keyword", (user_id,)
        ).fetchall()
    return [r["keyword"] for r in rows]


def remove_favorite(user_id, keyword):
    with connect() as conn:
        conn.execute(
            "DELETE FROM favorites WHERE user_id = ? AND keyword = ?",
            (user_id, keyword.strip().lower()),
        )


# ---------- Run directly to load a menus file ----------

def main():
    init_db()

    if len(sys.argv) < 2:
        print("Database is ready (mealert.db).")
        print("To load menus: /usr/bin/python3 db.py menus_2026-10-05.json")
        return

    with open(sys.argv[1]) as f:
        menus = json.load(f)
    count = save_menus(menus)
    print(f"Saved {count} dishes to {DB_FILE}")

    # Quick check: how many dishes per dining hall and meal
    date = menus[0]["date"] if menus else None
    if date:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT location, period, COUNT(*) AS dishes
                FROM menu_items WHERE date = ?
                GROUP BY location, period
                ORDER BY location, period
                """,
                (date,),
            ).fetchall()
        print(f"\nMenus in the database for {date}:")
        for r in rows:
            print(f"   {r['location']} - {r['period']}: {r['dishes']} dishes")


if __name__ == "__main__":
    main()

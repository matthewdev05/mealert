"""
Mealert - Step 3: match each day's dishes to users' favorites.

For every user, checks their favorite keywords (e.g. "biscuits", "chicken")
against the dishes in the database for a date, and lists what matches,
where, and at which meal.

To see today's matches:
    /usr/bin/python3 match.py
For a specific date:
    /usr/bin/python3 match.py 2026-10-05
"""

import re
import sys
from datetime import date

import db

# Show meals in this order instead of alphabetically
PERIOD_ORDER = ["Breakfast", "Brunch", "Lunch", "Dinner", "Late Night", "Everyday"]


def keyword_matches(keyword, dish_name):
    """
    True if the keyword appears in the dish name as a whole word.
    "egg" matches "Scrambled Eggs" but not "Eggplant Parmesan".
    """
    pattern = r"\b" + re.escape(keyword) + r"(s|es)?\b"
    return re.search(pattern, dish_name, re.IGNORECASE) is not None


def find_matches(favorites, dishes):
    """Return the dishes whose names match any of the user's favorites."""
    matches = []
    for dish in dishes:
        hits = [kw for kw in favorites if keyword_matches(kw, dish["name"])]
        if hits:
            matches.append({**dish, "matched": hits})
    return matches


def sort_key(dish):
    period = dish["period"]
    order = PERIOD_ORDER.index(period) if period in PERIOD_ORDER else len(PERIOD_ORDER)
    return (order, dish["location"], dish["name"])


def period_rank(period):
    return PERIOD_ORDER.index(period) if period in PERIOD_ORDER else len(PERIOD_ORDER)


def describe_times(times):
    """
    [("Breakfast", "Frank Dining Hall"), ("Lunch", "Frank Dining Hall"), ("Dinner", "The Coop")]
    -> "Breakfast and Lunch at Frank Dining Hall; Dinner at The Coop"
    """
    by_location = {}
    for period, location in times:
        by_location.setdefault(location, [])
        if period not in by_location[location]:
            by_location[location].append(period)
    parts = []
    for location, periods in by_location.items():
        periods.sort(key=period_rank)
        if "Everyday" in periods:  # served all day, so the other meals don't matter
            parts.append(f"All day at {location}")
            continue
        if len(periods) > 1:
            joined = ", ".join(periods[:-1]) + " and " + periods[-1]
        else:
            joined = periods[0]
        parts.append(f"{joined} at {location}")
    return "; ".join(parts)


def group_matches(matches):
    """
    Dine On Campus lists some dishes under several meals (e.g. Lunch and Dinner).
    Combine those into one entry per dish, keeping every time it's served.
    """
    grouped = {}
    for dish in sorted(matches, key=sort_key):
        key = dish["name"].strip().lower()
        if key not in grouped:
            grouped[key] = {**dish, "times": []}
        if (dish["period"], dish["location"]) not in grouped[key]["times"]:
            grouped[key]["times"].append((dish["period"], dish["location"]))
        for kw in dish["matched"]:
            if kw not in grouped[key]["matched"]:
                grouped[key]["matched"].append(kw)
    for dish in grouped.values():
        dish["when"] = describe_times(dish["times"])
    return list(grouped.values())


def matches_for_all_users(day_str):
    """Return a list of {user, matches} for everyone with at least one match."""
    dishes = db.get_menu(day_str)
    results = []
    for user in db.get_users():
        favorites = db.get_favorites(user["id"])
        if not favorites:
            continue
        matches = group_matches(find_matches(favorites, dishes))
        if matches:
            results.append({"user": user, "matches": matches})
    return results


def main():
    day_str = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    db.init_db()

    if not db.get_menu(day_str):
        print(f"No menus in the database for {day_str}.")
        print(f"Run: /usr/bin/python3 fetch_menus.py {day_str}")
        print(f"Then: /usr/bin/python3 db.py menus_{day_str}.json")
        return

    users = db.get_users()
    if not users:
        print("No users yet. Add one with:")
        print('   /usr/bin/python3 -c "import db; u = db.add_user(\'Your Name\', '
              '\'you@colgate.edu\'); db.add_favorite(u, \'biscuits\')"')
        return

    results = matches_for_all_users(day_str)
    matched_ids = {r["user"]["id"] for r in results}

    for r in results:
        user = r["user"]
        print(f"\n{user['name']} ({user['email']}) - {len(r['matches'])} matches on {day_str}")
        for dish in r["matches"]:
            print(f"   {dish['name']}: {dish['when']}"
                  f"  (matched: {', '.join(dish['matched'])})")

    for user in users:
        if user["id"] not in matched_ids:
            print(f"\n{user['name']}: no favorites on the menu for {day_str}")


if __name__ == "__main__":
    main()

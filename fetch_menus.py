"""
Mealert - Step 1: fetch Colgate's menus from Dine On Campus.

What it does:
    1. For each dining location that publishes menus (Frank Dining Hall, The Coop),
       gets the meal periods for a date (Breakfast, Lunch, Dinner, ...).
    2. Gets the menu for each period and pulls out every dish, with its
       station, diet tags, allergens, calories and portion size.
    3. Prints a summary and saves the dishes to menus_<date>.json.
       The raw API responses are saved in a raw/ folder, in case we need them.

Dine On Campus has no official public API. These are the URLs its website
calls in the background (found with Safari's Web Inspector), so they can change.
"""

import json
import os
import sys
import time
from datetime import date

# curl_cffi connects like a real browser, which gets past Cloudflare's bot check
from curl_cffi import requests

# ---- Settings (found in Safari's Web Inspector) ----
API_BASE = "https://apiv4.dineoncampus.com"

# The locations that publish menus (from the locations-public request)
LOCATIONS = {
    "Frank Dining Hall": "588230103191a2fac0d85d39",
    "The Coop": "588150c73191a2fadfd6f8fd",
}

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://dineoncampus.com",
    "Referer": "https://dineoncampus.com/",
}
TIMEOUT = 15
PAUSE_SECONDS = 2   # wait between requests so the site doesn't rate-limit us
RETRIES = 3         # how many times to retry when the site returns no meals


def get_json(path, params):
    time.sleep(PAUSE_SECONDS)
    resp = requests.get(
        f"{API_BASE}{path}",
        params=params,
        headers=HEADERS,
        timeout=TIMEOUT,
        impersonate="safari",
    )
    if resp.status_code != 200:
        raise RuntimeError(f"{resp.status_code} error for {resp.url}")
    return resp.json()


def save_raw(data, name):
    os.makedirs("raw", exist_ok=True)
    with open(os.path.join("raw", name), "w") as f:
        json.dump(data, f, indent=2)


def get_periods(location_id, day_str):
    """
    Get the meal periods for a location and date.
    The site sometimes returns an empty list when it's busy, so retry a few times.
    """
    for attempt in range(1, RETRIES + 1):
        data = get_json(f"/locations/{location_id}/periods/", {"date": day_str})
        if data.get("periods"):
            return data
        if attempt < RETRIES:
            print(f"   No meals returned, retrying ({attempt}/{RETRIES - 1})...")
            time.sleep(PAUSE_SECONDS * 2)
    return data


def parse_dishes(menu):
    """
    Pull the dishes out of a menu.
    Layout: menu -> period -> categories (stations) -> items (dishes)
    The same dish can be listed under several stations, so keep each one once.
    """
    period = (menu or {}).get("period") or {}
    dishes = []
    seen = set()

    for category in period.get("categories", []):
        station = category.get("name", "")
        for item in category.get("items", []):
            name = (item.get("name") or "").strip()
            if not name or item.get("id") in seen:
                continue
            seen.add(item.get("id"))

            filters = item.get("filters", [])
            dishes.append({
                "id": item.get("id"),
                "name": name,
                "station": station,
                "description": (item.get("desc") or "").strip(),
                # Labels with an icon are diet tags (Vegan, Vegetarian, ...)
                "diet_tags": [f["name"] for f in filters if f.get("icon")],
                # Labels without an icon are allergens/ingredients (Egg, Milk, ...)
                "allergens": [f["name"].rstrip("*") for f in filters if not f.get("icon")],
                "calories": item.get("calories"),
                "portion": item.get("portion"),
            })
    return dishes


def print_summary(period_name, dishes):
    print(f"   {period_name}: {len(dishes)} dishes")
    for dish in dishes[:5]:
        tags = f"  [{', '.join(dish['diet_tags'])}]" if dish["diet_tags"] else ""
        print(f"      - {dish['name']} ({dish['station']}){tags}")
    if len(dishes) > 5:
        print(f"      ...and {len(dishes) - 5} more")


def fetch_day(day):
    day_str = day.isoformat()  # e.g. 2026-10-05
    results = []

    for location_name, location_id in LOCATIONS.items():
        print(f"\n{location_name}")
        try:
            periods_data = get_periods(location_id, day_str)
        except Exception as e:
            print(f"   Could not get meal periods: {e}")
            continue
        save_raw(periods_data, f"periods_{location_id}_{day_str}.json")

        periods = periods_data.get("periods", [])
        if not periods:
            print("   No meals listed for this day.")
            continue

        # The periods response already includes the first meal's menu
        included_menu = periods_data.get("menu") or {}
        included_period_id = (included_menu.get("period") or {}).get("id")

        for period in periods:
            if period["id"] == included_period_id:
                menu = included_menu
            else:
                try:
                    menu_data = get_json(
                        f"/locations/{location_id}/menu",
                        {"date": day_str, "period": period["id"]},
                    )
                except Exception as e:
                    print(f"   {period['name']}: could not get menu ({e})")
                    continue
                save_raw(menu_data, f"menu_{location_id}_{period['id']}_{day_str}.json")
                menu = menu_data.get("menu") or menu_data

            dishes = parse_dishes(menu)
            print_summary(period["name"], dishes)
            results.append({
                "date": day_str,
                "location": location_name,
                "period": period["name"],
                "dishes": dishes,
            })

    return results


def main():
    # Run for today, or for a date you type after the file name, e.g. 2026-10-05
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    menus = fetch_day(day)

    if not menus:
        print("\nNo menus found for that day.")
        sys.exit(1)

    out_file = f"menus_{day.isoformat()}.json"
    with open(out_file, "w") as f:
        json.dump(menus, f, indent=2)
    total = sum(len(m["dishes"]) for m in menus)
    print(f"\nSaved {total} dishes to {out_file}")


if __name__ == "__main__":
    main()
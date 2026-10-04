"""
Mealert - the daily run: fetch today's menus, save them, email everyone.

Run it by hand:
    /usr/bin/python3 run_daily.py
Your Mac can also run it every morning automatically (see com.mealert.daily.plist).

It only emails once per day, even if it runs more than once.
"""

import os
from datetime import date, datetime

import db
from fetch_menus import fetch_day
from match import matches_for_all_users
from notify import build_email, load_env, send_email

SENT_MARKER = "last_sent.txt"  # remembers the last date emails went out


def already_sent(day_str):
    if not os.path.exists(SENT_MARKER):
        return False
    with open(SENT_MARKER) as f:
        return f.read().strip() == day_str


def mark_sent(day_str):
    with open(SENT_MARKER, "w") as f:
        f.write(day_str)


def main():
    # Run from the mealert folder, wherever it's started from
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    load_env()
    db.init_db()

    today = date.today()
    day_str = today.isoformat()
    print(f"\n=== Mealert daily run, {datetime.now():%Y-%m-%d %H:%M} ===")

    if already_sent(day_str):
        print("Emails already sent today. Nothing to do.")
        return

    # 1. Fetch and save today's menus
    menus = fetch_day(today)
    if not menus:
        print("No menus found for today, so no emails.")
        return
    count = db.save_menus(menus)
    print(f"Saved {count} dishes.")

    # 2. Match and email
    results = matches_for_all_users(day_str)
    if not results:
        print("No matches for anyone today.")
        mark_sent(day_str)
        return

    sent = 0
    for r in results:
        user = r["user"]
        subject, text, html_body, photos = build_email(user, r["matches"], day_str)
        try:
            send_email(user["email"], subject, text, html_body, photos)
            print(f"Sent to {user['email']}: {subject}")
            sent += 1
        except Exception as e:
            print(f"Could not send to {user['email']}: {e}")

    if sent:
        mark_sent(day_str)
    print(f"Done: {sent} of {len(results)} emails sent.")


if __name__ == "__main__":
    main()

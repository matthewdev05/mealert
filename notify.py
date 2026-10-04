"""
Mealert - Step 4: email each user their matches.

Preview the emails without sending (saves HTML files you can open):
    /usr/bin/python3 notify.py 2026-10-05 --preview
Send for real:
    /usr/bin/python3 notify.py 2026-10-05

Sending uses a Gmail account. Put its address and app password in a file
called .env in the mealert folder (never commit this file):
    MEALERT_EMAIL=yourname@gmail.com
    MEALERT_APP_PASSWORD=abcdabcdabcdabcd
"""

import html
import os
import smtplib
import sys
import urllib.parse
from datetime import date
from email.message import EmailMessage
from email.utils import make_msgid

import db

LOGO_PATH = "assets/mealert_app_icon.png"
FONT = "Poppins,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
from photos import find_photo, photo_index
from match import matches_for_all_users

# Food emoji: the first keyword found in a dish name wins
EMOJI = [
    ("pancake", "🥞"), ("waffle", "🧇"), ("egg", "🍳"), ("omelet", "🍳"),
    ("bacon", "🥓"), ("sausage", "🌭"), ("biscuit", "🥐"), ("bread", "🍞"),
    ("bagel", "🥯"), ("muffin", "🧁"), ("oatmeal", "🥣"), ("grits", "🥣"),
    ("pizza", "🍕"), ("burger", "🍔"), ("fries", "🍟"), ("taco", "🌮"),
    ("burrito", "🌯"), ("sandwich", "🥪"), ("wrap", "🌯"), ("soup", "🍲"),
    ("chicken", "🍗"), ("turkey", "🍗"), ("beef", "🥩"), ("steak", "🥩"),
    ("pork", "🥩"), ("ham", "🍖"), ("fish", "🐟"), ("salmon", "🐟"),
    ("shrimp", "🍤"), ("pasta", "🍝"), ("spaghetti", "🍝"), ("noodle", "🍜"),
    ("rice", "🍚"), ("curry", "🍛"), ("salad", "🥗"), ("broccoli", "🥦"),
    ("potato", "🥔"), ("hashbrown", "🥔"), ("corn", "🌽"), ("cheese", "🧀"),
    ("ice cream", "🍨"), ("cookie", "🍪"), ("cake", "🍰"), ("pie", "🥧"),
    ("brownie", "🍫"), ("fruit", "🍓"), ("strawberr", "🍓"), ("apple", "🍎"),
    ("banana", "🍌"), ("yogurt", "🥛"),
]
DEFAULT_EMOJI = "🍽️"


def emoji_for(dish_name):
    name = dish_name.lower()
    for word, emoji in EMOJI:
        if word in name:
            return emoji
    return DEFAULT_EMOJI


def load_env(path=".env"):
    """Read KEY=value lines from .env into environment variables."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def nice_date(day_str):
    d = date.fromisoformat(day_str)
    return d.strftime("%A, %B ") + str(d.day)  # e.g. Monday, October 5


def build_email(user, matches, day_str, preview=False):
    """
    Return (subject, plain_text, html_body, photos) for one user.
    photos is a list of (content_id, file_path) to attach inside the email.
    In preview mode, images point at the files directly so Safari can show them.
    """
    count = len(matches)
    halls = sorted({location for m in matches for _, location in m["times"]})
    first_name = user["name"].split()[0] if user["name"].strip() else "there"
    headline = f"{count} of your favorites {'is' if count == 1 else 'are'} on today"
    # e.g. "Matthew, 3 of your favorites are on today"
    subject = f"{first_name}, {headline[0].lower() + headline[1:]}" if first_name != "there" else headline
    when = f"{nice_date(day_str)} · {' and '.join(halls)}"

    # Plain text version (shown by email apps that don't display HTML)
    lines = [f"Good morning, {first_name}!", "", headline + ".", when, ""]
    for m in matches:
        lines.append(f"{emoji_for(m['name'])} {m['name']}")
        lines.append(f"   {m['when']} ({m['station']})")
        if m["allergens"]:
            lines.append(f"   Contains: {', '.join(m['allergens'])}")
        lines.append("")
    lines += ["while (hungry) { eat(); }", "- Mealert"]
    text = "\n".join(lines)

    # HTML version (styled like the preview's email screen)
    cards = []
    photos = []
    index = photo_index()
    for m in matches:
        e = html.escape
        details = e(m["station"] or "")
        if m["calories"]:
            details += f" · {m['calories']} cal"
        tags = "".join(
            f'<span style="display:inline-block;padding:3px 9px;margin:0 6px 6px 0;'
            f'border-radius:999px;background:#E8F0E3;color:#2C5221;font-size:12px">{e(t)}</span>'
            for t in m["diet_tags"]
        )
        allergens = (
            f'<div style="font-size:13px;color:#8A1C22;margin-top:4px">'
            f'Contains: {e(", ".join(m["allergens"]))}</div>'
            if m["allergens"] else ""
        )
        # Real photo from the photos/ folder, if we have one for this dish
        photo = ""
        path = find_photo(m["name"], index)
        if path:
            if preview:
                src = urllib.parse.quote(path)  # spaces in file names become %20
            else:
                cid = make_msgid(domain="mealert")[1:-1]  # strip the < >
                photos.append((cid, path))
                src = "cid:" + cid
            photo = (
                f'<img src="{e(src)}" alt="{e(m["name"])}" width="100%" '
                f'style="display:block;width:100%;height:180px;object-fit:cover;border-radius:12px;margin-bottom:12px">'
            )
        cards.append(f"""
        <div style="background:#ffffff;border:1px solid #E4E0DA;border-radius:16px;padding:16px;margin-bottom:12px">
          {photo}
          <div style="font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:#8A1C22">
            {e(m['when'])}</div>
          <div style="font-size:19px;font-weight:700;margin:6px 0">{emoji_for(m['name'])} {e(m['name'])}</div>
          <div style="font-size:14px;color:#4A4650;margin-bottom:8px">{details}</div>
          <div>{tags}</div>
          {allergens}
          <div style="font-size:13px;color:#5C5862;margin-top:6px">
            Matched your favorite: {e(", ".join(m['matched']))}</div>
        </div>""")

    # Logo for the signature, embedded like the dish photos
    logo = ""
    if os.path.exists(LOGO_PATH):
        if preview:
            logo_src = LOGO_PATH
        else:
            logo_cid = make_msgid(domain="mealert")[1:-1]
            photos.append((logo_cid, LOGO_PATH))
            logo_src = "cid:" + logo_cid
        logo = (f'<img src="{logo_src}" alt="Mealert" width="44" height="44" '
                f'style="display:block;width:44px;height:44px;border-radius:10px">')

    html_body = f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body style="margin:0;background:#F4F2EF;font-family:{FONT};color:#1C1B1F">
  <div style="max-width:480px;margin:0 auto;padding:20px">
    <div style="font-size:15px;font-weight:700;color:#8A1C22;margin-bottom:12px;letter-spacing:.02em">MEALERT</div>
    <div style="font-size:16px;color:#4A4650;margin-bottom:4px">Good morning, {html.escape(first_name)}!</div>
    <div style="font-size:24px;font-weight:700;line-height:1.2;letter-spacing:-.01em">{html.escape(headline)}</div>
    <div style="font-size:14px;color:#5C5862;margin:6px 0 16px">{html.escape(when)}</div>
    {''.join(cards)}

    <!-- Signature -->
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:24px;border-top:1px solid #E4E0DA;padding-top:18px;width:100%">
      <tr>
        <td style="width:56px;vertical-align:middle">{logo}</td>
        <td style="vertical-align:middle;font-family:{FONT}">
          <div style="display:inline-block;font-family:Menlo,Consolas,'Courier New',monospace;font-size:14px;background:#1C1B1F;color:#F4F2EF;padding:6px 10px;border-radius:8px;margin-bottom:6px">
            <span style="color:#F4B43C">while</span> (hungry) {{ <span style="color:#F4B43C">eat</span>(); }}</div>
          <div style="font-size:17px;font-weight:700;color:#8A1C22">&mdash; Mealert</div>
        </td>
      </tr>
    </table>

    <div style="font-size:12px;color:#5C5862;text-align:center;margin-top:20px;line-height:1.5">
      You get this because you follow {len(db.get_favorites(user['id']))} foods on Mealert.<br>
      Menus from Colgate Dining. A student project, not affiliated with Colgate Dining.</div>
  </div>
</body></html>"""
    return subject, text, html_body, photos


def send_email(to_address, subject, text, html_body, photos=()):
    sender = os.environ.get("MEALERT_EMAIL")
    password = os.environ.get("MEALERT_APP_PASSWORD")
    if not sender or not password:
        raise RuntimeError("Missing MEALERT_EMAIL or MEALERT_APP_PASSWORD in .env")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Mealert <{sender}>"
    msg["To"] = to_address
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    # Attach each photo inside the HTML part, so the email shows it without hosting
    html_part = msg.get_payload()[1]
    for cid, path in photos:
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        with open(path, "rb") as f:
            html_part.add_related(f.read(), maintype="image",
                                  subtype="jpeg" if ext in ("jpg", "jpeg") else ext,
                                  cid=f"<{cid}>")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    preview = "--preview" in sys.argv
    day_str = args[0] if args else date.today().isoformat()

    load_env()
    db.init_db()
    results = matches_for_all_users(day_str)

    if not results:
        print(f"No matches for anyone on {day_str}, so no emails to send.")
        return

    for r in results:
        user = r["user"]
        subject, text, html_body, photos = build_email(user, r["matches"], day_str, preview)
        if preview:
            filename = f"preview_{user['id']}_{day_str}.html"
            with open(filename, "w") as f:
                f.write(html_body)
            print(f"Saved preview for {user['email']}: {filename}  ({subject})")
        else:
            try:
                send_email(user["email"], subject, text, html_body, photos)
                print(f"Sent to {user['email']}: {subject}")
            except Exception as e:
                print(f"Could not send to {user['email']}: {e}")


if __name__ == "__main__":
    main()

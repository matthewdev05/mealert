"""
Mealert - real photos of Colgate dishes.

Save photos in the photos/ folder, named after the dish exactly as the menu
writes it (capital letters don't matter):
    photos/Biscuits and Country Gravy.jpg
    photos/Scrambled Eggs.heic

Get photos ready for email (converts iPhone HEIC to JPEG and shrinks them):
    /usr/bin/python3 photos.py prepare

See which of a day's dishes have photos, and which to shoot next:
    /usr/bin/python3 photos.py 2026-10-05
"""

import os
import re
import subprocess
import sys

PHOTO_DIR = "photos"
EMAIL_TYPES = {".jpg", ".jpeg", ".png"}
CONVERT_TYPES = {".heic", ".heif", ".webp", ".tiff"}
MAX_SIZE = 800  # longest side in pixels; keeps emails small


def normalize(name):
    """'Biscuits & Country-Gravy ' -> 'biscuits country gravy'"""
    words = re.findall(r"[a-z0-9]+", name.lower().replace("&", " and "))
    return " ".join(w for w in words if w != "and")


def photo_index():
    """Map each normalized dish name to its photo file."""
    index = {}
    if not os.path.isdir(PHOTO_DIR):
        return index
    for filename in os.listdir(PHOTO_DIR):
        stem, ext = os.path.splitext(filename)
        if ext.lower() in EMAIL_TYPES:
            index[normalize(stem)] = os.path.join(PHOTO_DIR, filename)
    return index


def find_photo(dish_name, index=None):
    """Return the path of a real photo for this dish, or None."""
    index = photo_index() if index is None else index
    return index.get(normalize(dish_name))


def prepare():
    """Convert HEIC and other formats to JPEG, and shrink large photos (uses macOS's sips tool)."""
    if not os.path.isdir(PHOTO_DIR):
        os.makedirs(PHOTO_DIR)
        print(f"Created the {PHOTO_DIR}/ folder. Add photos named after dishes, then run this again.")
        return

    for filename in sorted(os.listdir(PHOTO_DIR)):
        path = os.path.join(PHOTO_DIR, filename)
        stem, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext in CONVERT_TYPES:
            new_path = os.path.join(PHOTO_DIR, stem + ".jpg")
            subprocess.run(["sips", "-s", "format", "jpeg", "-Z", str(MAX_SIZE), path, "--out", new_path],
                           check=True, capture_output=True)
            os.remove(path)
            print(f"Converted {filename} -> {stem}.jpg")
        elif ext in EMAIL_TYPES:
            subprocess.run(["sips", "-Z", str(MAX_SIZE), path], check=True, capture_output=True)
            print(f"Ready: {filename}")


def report(day_str):
    """List the day's dishes that have photos, and the ones still missing."""
    import db
    index = photo_index()
    dishes = db.get_menu(day_str)
    if not dishes:
        print(f"No menus in the database for {day_str}.")
        return

    names = sorted({d["name"] for d in dishes})
    have = [n for n in names if find_photo(n, index)]
    missing = [n for n in names if not find_photo(n, index)]

    print(f"{len(have)} of {len(names)} dishes on {day_str} have real photos.\n")
    for n in have:
        print(f"   [photo] {n}")
    print("\nNo photo yet (save as photos/<name>.jpg):")
    for n in missing:
        print(f"   {n}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "prepare":
        prepare()
    elif len(sys.argv) > 1:
        report(sys.argv[1])
    else:
        print(__doc__)

import json
import os

BAN_FILE = os.path.join(os.path.dirname(__file__), "../../banned_users.json")
BAN_FILE = os.path.normpath(BAN_FILE)


def load_banned() -> set:
    try:
        with open(BAN_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_banned(banned: set) -> None:
    with open(BAN_FILE, "w") as f:
        json.dump(sorted(banned), f)


banned_users: set = load_banned()

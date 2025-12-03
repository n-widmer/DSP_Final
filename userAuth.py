import os
from typing import Optional, Dict, Any, Tuple, List

from flask import Flask, request, session, jsonify
from flask_mysqldb import MySQL


app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "dev-secret")

# In-memory user stores. Each entry is (username, password).
# For this non-production demo passwords are stored plaintext for simplicity.
groupH: List[Tuple[str, str]] = [
    ("alice", "alicepass"),
    ("henry", "henrypass"),
]

groupR: List[Tuple[str, str]] = [
    ("bob", "bobpass"),
    ("rachel", "rachelpass"),
]


def _local_authenticate(username: str, password: str) -> Optional[str]:
    """Check the in-memory groups and return 'H' or 'R' on success, otherwise None.

    This implementation uses plaintext comparison because this is a demo/non-production program.
    """
    for user, pw in groupH:
        if user == username and pw == password:
            return "H"
    for user, pw in groupR:
        if user == username and pw == password:
            return "R"
    return None


# --- Minimal MySQL wiring left in place; if MySQL env vars present we'll use DB auth, otherwise local auth is used.
MYSQL_HOST = os.environ.get("MYSQL_HOST")
MYSQL_USER = os.environ.get("MYSQL_USER")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
MYSQL_DB = os.environ.get("MYSQL_DB")

mysql: Optional[MySQL] = None
if MYSQL_HOST and MYSQL_USER and MYSQL_DB:
    app.config["MYSQL_HOST"] = MYSQL_HOST
    app.config["MYSQL_USER"] = MYSQL_USER
    app.config["MYSQL_PASSWORD"] = MYSQL_PASSWORD or ""
    app.config["MYSQL_DB"] = MYSQL_DB
    mysql = MySQL(app)


def _get_db_cursor():
    if mysql is None:
        return None
    return mysql.connection.cursor()


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate using only the local in-memory users and return user info with group.

    Returns a dict with keys `username` and `group` on success, otherwise None.
    """
    group = _local_authenticate(username, password)
    if group:
        return {"id": None, "username": username, "group": group}
    return None


def filter_record_for_group(record: Dict[str, Any], group: str) -> Dict[str, Any]:
    safe = dict(record)
    if group == "R":
        for fld in ("first_name", "last_name"):
            safe.pop(fld, None)
    return safe


@app.get("/")
def home():
    return jsonify({"message": "Hello — use POST /login or run the script directly for CLI authentication."})


@app.post("/login")
def login():
    data = request.get_json(silent=True) or request.form
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    user = authenticate_user(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401

    session["user_id"] = user.get("id")
    session["username"] = user.get("username")
    session["group"] = user.get("group")
    return jsonify({"message": "authenticated", "group": user.get("group")})


@app.get("/record/<int:record_id>")
def get_record(record_id: int):
    user_group = session.get("group")
    if not user_group:
        return jsonify({"error": "not authenticated"}), 401

    # If no DB present, return a demo record
    cur = _get_db_cursor()
    record = None
    if cur is not None:
        try:
            table = os.environ.get("RECORD_TABLE", "people")
            cur.execute(f"SELECT * FROM {table} WHERE id = %s", (record_id,))
            row = cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                record = dict(zip(cols, row))
        except Exception:
            record = None
        finally:
            try:
                cur.close()
            except Exception:
                pass

    if record is None:
        record = {
            "id": record_id,
            "first_name": "Demo",
            "last_name": "User",
            "email": "demo.user@example.com",
            "ssn": "000-00-0000",
        }

    filtered = filter_record_for_group(record, user_group)
    return jsonify({"record": filtered})


def run_cli():
    """Simple CLI flow: prompt for username/password, then show a demo record according to group."""
    print("Local authentication CLI — enter your credentials")
    username = input("Username: ")
    import getpass

    password = getpass.getpass("Password: ")
    user = authenticate_user(username, password)
    if user is None:
        print("Authentication failed.")
        return
    print(f"Authenticated as {user['username']} (group {user['group']})")
    try:
        rid = int(input("Enter record id to fetch (demo): "))
    except Exception:
        rid = 1
    # demo record
    record = {
        "id": rid,
        "first_name": "Demo",
        "last_name": "Person",
        "email": "demo.person@example.com",
        "ssn": "111-11-1111",
    }
    filtered = filter_record_for_group(record, user["group"])
    print("Record:")
    print(filtered)


if __name__ == "__main__":
    # If script is run directly, offer CLI auth; otherwise Flask app is served when executed as a module.
    run_cli()
import os
import json
from typing import Optional, Dict, Any, Tuple, List

from flask import Flask, request, session, jsonify
from flask_mysqldb import MySQL
from merkle import compute_row_hash, bytes_to_hex, hex_to_bytes, build_root_from_hashes, get_proof, verify_proof


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


# Local Merkle root storage (in-memory). In production, sign and publish this.
MERKLE_ROOT_FILE = "merkle_root.json"
merkle_root_cache = {
    "root": None,  # hex string
    "timestamp": None,
}


def _get_db_cursor():
    if mysql is None:
        return None
    return mysql.connection.cursor()


def compute_patient_row_hash(patient_data: Dict[str, Any]) -> str:
    """Compute SHA-256 row hash for a patient record (in deterministic field order).
    
    Fields ordered by: id, first_name, last_name, health_history, gender, age, weight, height.
    Returns the hash as a hex string suitable for storage in MySQL BINARY(32) column.
    """
    values = [
        patient_data.get("id"),
        patient_data.get("first_name"),
        patient_data.get("last_name"),
        patient_data.get("health_history"),
        patient_data.get("gender"),
        patient_data.get("age"),
        patient_data.get("weight"),
        patient_data.get("height"),
    ]
    row_hash_bytes = compute_row_hash(values)
    return bytes_to_hex(row_hash_bytes)


def insert_patient_with_hash(cursor, first_name: str, last_name: str, health_history: str, 
                               gender: str, age: int, weight: float, height: float) -> bool:
    """Insert a new patient and automatically compute + store row_hash.
    
    Returns True on success, False otherwise.
    """
    try:
        # Insert without id (auto-increment) and row_hash (computed after insert)
        insert_query = """
            INSERT INTO Patients (first_name, last_name, health_history, gender, age, weight, height)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (first_name, last_name, health_history, gender, age, weight, height))
        # Get the newly inserted id
        new_id = cursor.lastrowid
        
        # Build patient data dict and compute hash
        patient_data = {
            "id": new_id,
            "first_name": first_name,
            "last_name": last_name,
            "health_history": health_history,
            "gender": gender,
            "age": age,
            "weight": weight,
            "height": height,
        }
        row_hash_hex = compute_patient_row_hash(patient_data)
        
        # Update the row with computed hash
        update_query = "UPDATE Patients SET row_hash = UNHEX(%s) WHERE id = %s"
        cursor.execute(update_query, (row_hash_hex, new_id))
        
        return True
    except Exception as e:
        print(f"Error inserting patient with hash: {e}")
        return False


def update_patient_with_hash(cursor, patient_id: int, first_name: str, last_name: str, 
                              health_history: str, gender: str, age: int, weight: float, height: float) -> bool:
    """Update an existing patient and recompute + store row_hash.
    
    Returns True on success, False otherwise.
    """
    try:
        # Update patient data
        update_query = """
            UPDATE Patients 
            SET first_name = %s, last_name = %s, health_history = %s, gender = %s, 
                age = %s, weight = %s, height = %s
            WHERE id = %s
        """
        cursor.execute(update_query, (first_name, last_name, health_history, gender, age, weight, height, patient_id))
        
        # Build patient data dict and recompute hash
        patient_data = {
            "id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "health_history": health_history,
            "gender": gender,
            "age": age,
            "weight": weight,
            "height": height,
        }
        row_hash_hex = compute_patient_row_hash(patient_data)
        
        # Update the row hash
        update_hash_query = "UPDATE Patients SET row_hash = UNHEX(%s) WHERE id = %s"
        cursor.execute(update_hash_query, (row_hash_hex, patient_id))
        
        return True
    except Exception as e:
        print(f"Error updating patient with hash: {e}")
        return False


def compute_patients_merkle_root() -> Optional[str]:
    """Compute Merkle root from all Patients' row_hash values (ordered by id).
    
    Queries the database for all row_hashes, builds the tree, stores root locally,
    and returns the root as a hex string.
    Returns None if no cursor or query fails.
    """
    cur = _get_db_cursor()
    if cur is None:
        print("No database cursor available")
        return None
    
    try:
        # Fetch all row_hashes in order by id (deterministic ordering)
        cur.execute("SELECT id, row_hash FROM Patients ORDER BY id ASC")
        rows = cur.fetchall()
        
        if not rows:
            print("No patients in database; using empty root")
            # Empty tree root
            root_bytes = build_root_from_hashes([])
            root_hex = bytes_to_hex(root_bytes)
        else:
            # Collect row_hash bytes (convert from MySQL BINARY(32) / hex)
            leaf_hashes = []
            for row in rows:
                patient_id, row_hash_binary = row
                # row_hash_binary is already bytes from MySQLdb
                if row_hash_binary:
                    leaf_hashes.append(row_hash_binary)
                else:
                    print(f"Warning: patient {patient_id} has NULL row_hash")
            
            if not leaf_hashes:
                root_bytes = build_root_from_hashes([])
                root_hex = bytes_to_hex(root_bytes)
            else:
                root_bytes = build_root_from_hashes(leaf_hashes)
                root_hex = bytes_to_hex(root_bytes)
        
        # Store root locally (in-memory cache and optionally to file)
        merkle_root_cache["root"] = root_hex
        merkle_root_cache["timestamp"] = __import__("datetime").datetime.utcnow().isoformat()
        
        # Optionally persist to file
        try:
            with open(MERKLE_ROOT_FILE, "w") as f:
                json.dump(merkle_root_cache, f)
            print(f"Merkle root saved to {MERKLE_ROOT_FILE}")
        except Exception as e:
            print(f"Warning: could not save root to file: {e}")
        
        print(f"Computed Merkle root: {root_hex}")
        return root_hex
        
    except Exception as e:
        print(f"Error computing Merkle root: {e}")
        return None
    finally:
        try:
            cur.close()
        except Exception:
            pass


def get_patient_with_merkle_proof(patient_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a patient record and compute Merkle proof for integrity verification.
    
    Returns dict with keys:
    - patient: patient record (all fields)
    - row_hash: patient's row hash (hex string)
    - proof: list of [sibling_hex, is_left_bool] for proof verification
    - merkle_root: the current trusted root (hex string)
    
    Returns None if patient not found or error occurs.
    """
    cur = _get_db_cursor()
    if cur is None:
        print("No database cursor available")
        return None
    
    try:
        # Fetch the patient
        cur.execute(
            "SELECT id, first_name, last_name, health_history, gender, age, weight, height, row_hash FROM Patients WHERE id = %s",
            (patient_id,)
        )
        row = cur.fetchone()
        
        if not row:
            return None
        
        patient_id, first_name, last_name, health_history, gender, age, weight, height, row_hash_binary = row
        
        # Build patient dict
        patient = {
            "id": patient_id,
            "first_name": first_name,
            "last_name": last_name,
            "health_history": health_history,
            "gender": gender,
            "age": age,
            "weight": weight,
            "height": height,
        }
        
        row_hash_hex = bytes_to_hex(row_hash_binary) if row_hash_binary else None
        
        # Fetch all row_hashes to compute proof
        cur.execute("SELECT row_hash FROM Patients ORDER BY id ASC")
        all_rows = cur.fetchall()
        leaf_hashes = [r[0] for r in all_rows if r[0]]
        
        if not leaf_hashes:
            return None
        
        # Find index of this patient in the ordered list
        patient_index = None
        cur.execute("SELECT id FROM Patients ORDER BY id ASC")
        ids = [r[0] for r in cur.fetchall()]
        try:
            patient_index = ids.index(patient_id)
        except ValueError:
            return None
        
        # Generate proof
        try:
            proof_tuples = get_proof(leaf_hashes, patient_index)
            # Convert proof to JSON-serializable format
            proof = [[bytes_to_hex(sibling), is_left] for sibling, is_left in proof_tuples]
        except Exception as e:
            print(f"Error generating proof: {e}")
            proof = []
        
        # Get trusted root
        root = merkle_root_cache.get("root")
        if not root:
            # Compute it if not cached
            root = compute_patients_merkle_root()
        
        return {
            "patient": patient,
            "row_hash": row_hash_hex,
            "proof": proof,
            "merkle_root": root,
        }
        
    except Exception as e:
        print(f"Error getting patient with proof: {e}")
        return None
    finally:
        try:
            cur.close()
        except Exception:
            pass


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


@app.post("/compute_merkle_root")
def compute_merkle_root():
    """Compute and store the Merkle root for all Patients.
    
    Call this endpoint after adding/updating patients to refresh the root.
    """
    root = compute_patients_merkle_root()
    if root:
        return jsonify({
            "message": "Merkle root computed and stored locally",
            "merkle_root": root,
            "timestamp": merkle_root_cache.get("timestamp"),
        })
    else:
        return jsonify({"error": "Failed to compute Merkle root"}), 500


@app.get("/patient/<int:patient_id>/with_proof")
def get_patient_with_proof(patient_id: int):
    """Fetch a patient record with Merkle proof for integrity verification.
    
    Server-side verification: Before returning data, verifies that the row hash
    and proof are consistent with the trusted Merkle root. If verification fails,
    returns a 400 error instead of the data.
    
    On success, returns:
    - patient: patient data (id, first_name, last_name, health_history, gender, age, weight, height)
    - row_hash: SHA-256 hash of this patient's row
    - proof: list of [sibling_hash, is_left] tuples for verifying proof
    - merkle_root: the current trusted root
    - verified: boolean (true if proof verified successfully)
    
    On failure, returns 400 with error message.
    """
    result = get_patient_with_merkle_proof(patient_id)
    if not result:
        return jsonify({"error": "Patient not found"}), 404

    # Data integrity check: verify that the received data matches the stored row_hash
    patient = result.get("patient")
    row_hash_hex = result.get("row_hash")
    if patient and row_hash_hex:
        expected_hash_hex = compute_patient_row_hash(patient)
        if expected_hash_hex != row_hash_hex:
            return jsonify({
                "error": "Data integrity breach detected. The patient data does not match the stored hash.",
                "patient_id": patient_id,
                "alert": "This record may have been tampered with. Contact system administrator."
            }), 400

    # Server-side verification: verify the proof against the trusted root
    row_hash_hex = result.get("row_hash")
    proof_data = result.get("proof")
    merkle_root = result.get("merkle_root")
    
    if not row_hash_hex or not merkle_root:
        return jsonify({"error": "Missing row_hash or merkle_root; cannot verify"}), 400
    
    try:
        row_hash_bytes = hex_to_bytes(row_hash_hex)
        merkle_root_bytes = hex_to_bytes(merkle_root)
        
        # Convert proof back to byte format for verification
        proof_tuples = [(hex_to_bytes(sibling), is_left) for sibling, is_left in proof_data]
        
        # Verify proof
        is_valid = verify_proof(row_hash_bytes, proof_tuples, merkle_root_bytes)
        
        if not is_valid:
            # Proof verification failed — potential tampering detected
            return jsonify({
                "error": "Merkle proof verification failed. Data integrity compromised.",
                "patient_id": patient_id,
                "alert": "This record may have been tampered with. Contact system administrator."
            }), 400
        
        # Verification passed — include verification flag in response
        result["verified"] = True
        return jsonify(result)
        
    except Exception as e:
        print(f"Error during proof verification: {e}")
        return jsonify({
            "error": "Internal error during proof verification",
            "details": str(e)
        }), 500


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
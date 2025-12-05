import os
import re
from typing import Optional, Dict, Any, List

from flask import Flask, render_template, request, session, redirect, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# 1) Load .env into environment first
load_dotenv()

# 2) then import crypto_helpers (so GENDER_AGE_KEY is visible)
from crypto_helpers import encrypt_gender_age, decrypt_gender_age
# 3) Import Merkle utilities, including the verification tools
from merkle import compute_row_hash, build_root_from_hashes, bytes_to_hex, get_proof, verify_proof, hex_to_bytes


app = Flask(__name__)
input_file = '.env'
variables = {}
with open(input_file, 'r') as f:
    for line in f:
        line = line.strip()
        if '=' in line:
            key, value = line.split('=', 1)
            variables[key] = value

DSP_SECRET_KEY = variables['DSP_SECRET_KEY']
MYSQL_HOST = variables['MYSQL_HOST']
MYSQL_USER = variables['MYSQL_USER']
MYSQL_PASSWORD = variables['MYSQL_PASSWORD']
MYSQL_DB = variables['MYSQL_DB']

app.secret_key = DSP_SECRET_KEY
app.config["MYSQL_HOST"] = MYSQL_HOST
app.config["MYSQL_USER"] = MYSQL_USER
app.config["MYSQL_PASSWORD"] = MYSQL_PASSWORD
app.config["MYSQL_DB"] = MYSQL_DB
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' #account always returns a dictonary

mysql = MySQL(app)

# -------------------------------------------------------------
# !!! NEW: SECURE ROOT FOR TESTING INTEGRITY !!!
# Set this to the root of the database when it was known to be clean.
# Using the root you provided: b4f82e7a03ce104b7a449b791e11c20a7f94730b9670d34349582d6fef73be23
# When testing, keep this constant while you tamper with the MySQL data.
SECURED_ROOT_HEX: Optional[str] = "b4f82e7a03ce104b7a449b791e11c20a7f94730b9670d34349582d6fef73be23"
# -------------------------------------------------------------


# --- MERKLE TREE HELPERS ---

def _calculate_merkle_root() -> Optional[str]:
    """
    1. Fetches all required patient fields in a deterministic order (ORDER BY id).
    2. Calculates a Merkle leaf hash for each row.
    3. Builds the Merkle root from the leaf hashes.
    4. Returns the root as a hex string.
    """
    cursor = mysql.connection.cursor()
    
    cursor.execute(
        """
        SELECT
            id, first_name, last_name, Weight, Height, health_history,
            gender_age_nonce, gender_age_cipher
        FROM Patients
        ORDER BY id ASC
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    if not rows:
        return None

    leaf_hashes = []
    for row in rows:
        # Values must be in the same order as defined for compute_row_hash
        # and include all fields that should be covered by the integrity check.
        values = [
            row["id"],
            row["first_name"],
            row["last_name"],
            row["Weight"],
            row["Height"],
            row["health_history"],
            row["gender_age_nonce"],
            row["gender_age_cipher"],
        ]
        leaf_hash = compute_row_hash(values)
        leaf_hashes.append(leaf_hash)

    root_bytes = build_root_from_hashes(leaf_hashes)
    return bytes_to_hex(root_bytes)




#start of patient helper functions
def insert_patient(first_name, last_name, gender, age, weight, height, history):
    """
    Insert a patient, encrypting gender+age before sending to DB.
    Only call this for Group H users.
    """
    nonce, cipher = encrypt_gender_age(gender, age)

    cursor = mysql.connection.cursor()
    cursor.execute(
        """
        INSERT INTO Patients
        (first_name, last_name, weight, height, health_history,
         gender_age_nonce, gender_age_cipher)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (first_name, last_name, weight, height, history, nonce, cipher),
    )
    mysql.connection.commit()
    cursor.close()
    
    # Recalculate root after insertion ---
    new_root = _calculate_merkle_root()
    print(f"[MERKLE ROOT] RECALCULATED: {new_root}")
    # In a real system, you would store this root securely here.


def fetch_all_patients_for_current_user():
    """
    NOTE: This helper is now largely unused. Logic was moved to admin_page for Merkle integration.
    """
    pass

#end of patient helper functions  

def get_group_table(group_value):
    if group_value == 'H':
        return 'GroupH'
    if group_value == 'R':
        return 'GroupR'
    return None


@app.route("/")
def index():
    #print(key)
    return render_template("index.html")


@app.route("/register_group", methods=['GET', 'POST'])
def register_user():
    message = ""
    if request.method == 'POST':
        if 'username' in request.form and 'password' in request.form and 'group' in request.form:
            username = request.form['username']
            password = request.form['password']
            group_value = request.form['group']  # 'H' or 'R'

            table = get_group_table(group_value)
            if table is None:
                message = "Invalid group selection."
                return render_template("register_group.html", message=message)

            cursor = mysql.connection.cursor()

            # Check if username already exists in that group table
            query1 = f"SELECT * FROM {table} WHERE username = %s;"
            cursor.execute(query1, (username,))
            account = cursor.fetchone()

            if account:
                message = "Account already exists in this group."
                cursor.close()
                return render_template("register_group.html", message=message)

            # Insert into that group table
            hashed_password = generate_password_hash(
                password,
                method='pbkdf2:sha256',
                salt_length=16
            )
            query2 = f"INSERT INTO {table} (username, password) VALUES (%s, %s);"
            cursor.execute(query2, (username, hashed_password))
            mysql.connection.commit()
            cursor.close()

            message = "You have successfully registered."
            return render_template("Admin.html", message=message, username=username, group=group_value)

    # GET or missing fields
    return render_template("register_group.html", message=message)


@app.route("/login", methods=['GET', 'POST'])
def login_user():
    message = ""

    if request.method == 'POST':
        if 'username' in request.form and 'password' in request.form:
            username = request.form['username']
            password = request.form['password']

            cursor = mysql.connection.cursor()

            # 1) Try to find the user in GroupH
            cursor.execute("SELECT * FROM GroupH WHERE username = %s;", (username,))
            account = cursor.fetchone()
            group = None

            if account:
                group = 'H'
            else:
                # 2) If not in GroupH, try GroupR
                cursor.execute("SELECT * FROM GroupR WHERE username = %s;", (username,))
                account = cursor.fetchone()
                if account:
                    group = 'R'

            cursor.close()

            # 3) If we didn't find them in either table, invalid login
            if not account or group is None:
                message = "Invalid username or password"
                return render_template("login.html", message=message)

            # 4) Check the password hash from the group table
            stored_password = account['password']
            if check_password_hash(stored_password, password):
                # Login successful: save identity and group in session
                session['username'] = username
                session['group'] = group

                message = "Login Successful"
                return render_template(
                    "index.html",
                    message=message,
                    username=username,
                    group=group
                )
            else:
                message = "Invalid username or password"
                return render_template("login.html", message=message)

    # GET request or missing fields
    return render_template("login.html", message=message)



@app.route("/Admin", methods=['GET'])
def admin_page():
    if "username" not in session:
        return redirect(url_for("login_user"))

    username = session.get('username')
    group = session.get('group')
    show_names = (group == 'H')
    integrity_failed_count = 0

    # 1. Fetch ALL data deterministically for Merkle Tree construction
    cursor = mysql.connection.cursor()
    cursor.execute(
        """
        SELECT
            id,
            first_name,
            last_name,
            Gender,
            Age,
            Weight,
            Height,
            health_history,
            gender_age_nonce,
            gender_age_cipher
        FROM Patients
        ORDER BY id ASC
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    leaf_hashes: List[bytes] = []
    id_to_index: Dict[int, int] = {} # Maps patient ID to its index in the leaf_hashes list

    for index, row in enumerate(rows):
        id_to_index[row['id']] = index
        # The values for leaf hashing must be consistent
        values = [
            row["id"],
            row["first_name"],
            row["last_name"],
            row["Weight"],
            row["Height"],
            row["health_history"],
            row["gender_age_nonce"],
            row["gender_age_cipher"],
        ]
        leaf_hash = compute_row_hash(values)
        leaf_hashes.append(leaf_hash)

    # 2. Calculate the CURRENT Merkle Root (for comparison/debugging)
    current_root_bytes = build_root_from_hashes(leaf_hashes)
    current_root_hex = bytes_to_hex(current_root_bytes)
    print(f"\n[MERKLE ROOT] Current Live Root (from DB query): {current_root_hex}")

    # 3. SET UP VERIFICATION
    if SECURED_ROOT_HEX is None:
        print("[MERKLE AUDIT ERROR] SECURED_ROOT_HEX is not set. Skipping integrity check.")
        verification_root_bytes = None
    else:
        # This is the key: we verify against the SECURED root, NOT the current live root.
        verification_root_bytes = hex_to_bytes(SECURED_ROOT_HEX)
        
    patients = []
    for row in rows:
        # --- Decryption and group filtering logic (existing) ---
        nonce = row["gender_age_nonce"]
        cipher = row["gender_age_cipher"]

        if nonce is None or cipher is None:
            gender = row.get("Gender")
            age = row.get("Age")
        else:
            try:
                gender, age = decrypt_gender_age(nonce, cipher)
            except Exception:
                gender, age = "ERROR", -1

        row["Gender"] = gender
        row["Age"] = age

        if not show_names:
            row["first_name"] = None
            row["last_name"] = None
        # --- End decryption/filtering ---
        
        # 4. Integrity Check (Simulated Client Check)
        if verification_root_bytes is not None:
            record_index = id_to_index[row['id']]
            leaf_hash_for_verification = leaf_hashes[record_index]

            # Generate the proof for this leaf based on the CURRENT (potentially tampered) tree state
            proof_tuples = get_proof(leaf_hashes, record_index)
            
            # Convert proof tuples (bytes, bool) to (hex_str, bool)
            proof_hex = [(bytes_to_hex(h), is_left) for h, is_left in proof_tuples]
            proof_for_verification = [
                (hex_to_bytes(h), is_left) for h, is_left in proof_hex
            ]
            
            # C. Perform the verification: leaf + proof must lead back to the SECURED root
            is_valid = verify_proof(
                leaf_hash=leaf_hash_for_verification,
                proof=proof_for_verification,
                root=verification_root_bytes # <<< Use the SECURED root here
            )
            
            if not is_valid:
                integrity_failed_count += 1
                print(f"!!! MERKLE PROOF FAILURE DETECTED: Record ID {row['id']} is corrupt or tampered with. !!!")

        patients.append(row)
    
    # D. Final status message to the terminal
    if verification_root_bytes is not None:
        if integrity_failed_count > 0:
            print(f"\n[MERKLE TREE AUDIT RESULT]: {integrity_failed_count} out of {len(patients)} records FAILED integrity verification.")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!! WARNING: DATABASE INTEGRITY FAILURE. Check records with FAILED status above. !!!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        else:
            print(f"\n[MERKLE TREE AUDIT RESULT]: All {len(patients)} records PASSED integrity verification.")


    return render_template(
        "Admin.html",
        username=username,
        group=group,
        patients=patients,
        show_names=show_names,
    )



@app.route("/add_patient", methods=['GET', 'POST'])
def add_patient():
    username = session.get('username')
    group = session.get('group')

    if not username or group != 'H':
        message = 'Only group H can Modify patients table!'
        return render_template("login.html", message=message)
    
    if request.method == 'GET':
        return render_template("add_patient.html", username=username, group=group, message=None)

    return redirect(url_for('add_patient_route'))


@app.route("/logout", methods=['GET', 'POST'])
def logout_user():
    session.clear()
    return render_template("index.html")

#patient routes (gav)
@app.route("/patients")
def show_patients():
    return redirect(url_for("admin_page"))


@app.route("/patients/add", methods=["GET", "POST"])
def add_patient_route():
    if "username" not in session:
        return redirect(url_for("login_user"))

    if session.get("group") != "H":
        return "You do not have permission to add patients.", 403

    message = ""
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        gender = request.form["Gender"]
        try:
            age = int(request.form["Age"])
            weight = float(request.form["Weight"])
            height = float(request.form["Height"])
        except ValueError:
            message = "Age, Weight, and Height must be valid numbers."
            return render_template("add_patient.html", message=message, group=session.get("group"))

        history = request.form["health_history"]

        # This will AES-GCM encrypt gender+age and store nonce/cipher in DB
        insert_patient(first_name, last_name, gender, age, weight, height, history)
        
        return redirect(url_for('admin_page'))

    return render_template("add_patient.html", message=message, group=session.get("group"))
#patient routes end


if __name__ == '__main__':
    app.run(debug=True)
import os
import re

from flask import Flask, render_template, request, session, redirect, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# 1) Load .env into environment first
load_dotenv()

# 2) then import crypto_helpers (so GENDER_AGE_KEY is visible)
from crypto_helpers import encrypt_gender_age, decrypt_gender_age


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


def fetch_all_patients_for_current_user():
    """
    Fetch patients from the DB, decrypt gender+age locally, and
    shape the rows to match what the admin template expects.

    - If session['group'] == 'R', we will still pass first_name/last_name,
      but the template will decide whether to show them based on show_names.
      (If you want extra safety, we COULD blank them here too.)
    """
    cursor = mysql.connection.cursor()

    # IMPORTANT: use column names / aliases that match our template keys
    cursor.execute(
        """
        SELECT
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
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    group = session.get("group")

    processed = []
    for row in rows:
        nonce = row["gender_age_nonce"]
        cipher = row["gender_age_cipher"]

        # Decrypt gender+age from ciphertext
        try:
            gender, age = decrypt_gender_age(nonce, cipher)
        except Exception:
            # Tampered / corrupted
            gender, age = "ERROR", -1

        # Make sure the keys our template uses are present:
        # p.Gender, p.Age, p.Weight, p.Height, p.health_history
        row["Gender"] = gender
        row["Age"] = age
        # Weight, Height, health_history already in row from SELECT

        # If we want to be extra strict, we can blank names for Group R here:
        # if group == "R":
        #     row["first_name"] = None
        #     row["last_name"] = None

        processed.append(row)

    return processed
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

    cursor = mysql.connection.cursor()
    cursor.execute(
        """
        SELECT
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
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    patients = []
    for row in rows:
        nonce = row["gender_age_nonce"]
        cipher = row["gender_age_cipher"]

        if nonce is None or cipher is None:
            # Old/legacy row: no encrypted data, keep DB's Gender/Age
            gender = row.get("Gender")
            age = row.get("Age")
        else:
            try:
                gender, age = decrypt_gender_age(nonce, cipher)
            except Exception:
                # Real tampering or wrong key
                gender, age = "ERROR", -1

        # Overwrite with whatever we decided
        row["Gender"] = gender
        row["Age"] = age

        # Hide names for Group R
        if not show_names:
            row["first_name"] = None
            row["last_name"] = None

        patients.append(row)

    return render_template(
        "Admin.html",   # or "admin.html" – just be consistent with filename
        username=username,
        group=group,
        patients=patients,
        show_names=show_names,
    )

 #I modified the admin route so that gender and age are stored
 # encrypted in the DB using AES-GCM and are decrypted locally before display.
 # Group H still sees names, Group R doesn’t. The DB never sees plaintext gender/age.”
 #All of our existing (unencrypted) rows will show their normal Gender/Age values.
 #Only rows that actually have encrypted data will be decrypted.
 #If we later corrupt encrypted data or change the key, those rows will show ERROR/-1, which is what we want.




@app.route("/add_patient", methods=['GET', 'POST'])
def add_patient():
    username = session.get('username')
    group = session.get('group')

    if not username or group != 'H':
        message = 'Only group H can Modify patients table!'
        return render_template("login.html", message=message)
    
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        Gender = request.form['Gender']
        Age = request.form['Age']
        Weight = request.form['Weight']
        Height = request.form['Height']
        health_history = request.form['health_history']

        #Check common errors?
        errors = []
        if not first_name:
            errors.append('First name is required')
        if not last_name:
            errors.append("Last name is required")
        if not Gender:
            errors.append('Gender is required')

        try:
            weight_val = float(Weight)
            height_val = float(Height)
        except ValueError:
            errors.append("Weight and height must be numbers")

        if errors:
            return render_template("add_patient.html", message=" ".join(errors), username=username, group=group)

        
        #All error checks have cleared
        #Generate insert query for Patients table

        cursor = mysql.connection.cursor()
        query = """
        INSERT INTO Patients (first_name, last_name, Gender, Age, Weight, Height, health_history)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (first_name, last_name, Gender, Age, Weight, Height, health_history))
        mysql.connection.commit()
        cursor.close()


        #Go back to table view to see results
        return redirect(url_for('admin_page'))

    return render_template("add_patient.html", username=username, group=group, message=None)
        

@app.route("/logout", methods=['GET', 'POST'])
def logout_user():
    session.clear()
    return render_template("index.html")

#patient routes (gav)
@app.route("/patients")
def show_patients():
    # No separate patients page redirect to Admin Panel
    return redirect(url_for("admin_page"))



@app.route("/patients/add", methods=["GET", "POST"])
def add_patient_route():
    if "username" not in session:
        return redirect(url_for("login_user"))

    # Only Group H can add patients
    if session.get("group") != "H":
        return "You do not have permission to add patients.", 403

    message = ""
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        gender = request.form["Gender"]
        age = int(request.form["Age"])
        weight = float(request.form["Weight"])
        height = float(request.form["Height"])
        history = request.form["health_history"]

        # This will AES-GCM encrypt gender+age and store nonce/cipher in DB
        insert_patient(first_name, last_name, gender, age, weight, height, history)
        message = "Patient added successfully."

    return render_template("add_patient.html", message=message)
#patient routes end



# def encrypt_phone(phone, key):
#     cipher = AES.new(key, AES.MODE_CBC)
#     ct_bytes = cipher.encrypt(pad(phone.encode('utf-8'), AES.block_size))
#     iv = base64.b64encode(cipher.iv).decode('utf-8')
#     ct = base64.b64encode(ct_bytes).decode('utf-8')
#     return iv + ':' + ct

# """def decrypt_phone(encrypted_phone, key):
#     iv, ct = encrypted_phone.split(':')
#     iv = base64.b64decode(iv)
#     ct = base64.b64decode(ct)
#     cipher = AES.new(key, AES.MODE_CBC, iv)
#     pt = unpad(cipher.decrypt(ct), AES.block_size)
#     return pt.decode('utf-8')"""

if __name__ == '__main__':
    app.run(debug=True)


    
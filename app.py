import os
import re

from flask import Flask, render_template, request, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()

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
    cursor = mysql.connection.cursor()

    if request.method == 'POST':
        if 'username' in request.form and 'password' in request.form:
            username = request.form['username']
            password = request.form['password']
            group_value = request.form['group']
            table = get_group_table(group_value)

            if table is None:
                message = "inavlid group!"
                return render_template("login.html", message=message)

            cursor = mysql.connection.cursor()
            query = f"SELECT * FROM {table} WHERE username = %s;"
            cursor.execute(query, (username,))
            account = cursor.fetchone()
            cursor.close()

            if account:
                stored_password = account['password']

                if(check_password_hash(stored_password, password)):
                    message = "login success!"
                    session['username'] = username
                    session['group'] = group_value
                    return render_template("index.html", message=message, username=username, group=group_value)
                else:
                    message = "invalid username or password"
                    return render_teplate("login.html", message=message)
            else:
                message = 'invalid username or password'
                return render_template('login.html', message=message)
        return render_template("login.html", message=message)
    return render_template("login.html", message=message)

@app.route("/Admin", methods=['GET'])
def admin_page():
    username = session.get('username')
    group = session.get('group')
    cursor = mysql.connection.cursor()

    if group == 'H':
        query = """
        SELECT first_name, last_name, Gender, Age, Weight, Height, health_history
        FROM Patients
        """
        cursor.execute(query)
        patients = cursor.fetchall()
        show_names = True
    else:
        query = """
        SELECT Gender,Age, Weight, Height, health_history
        FROM Patients
        """
        cursor.execute(query)
        patients = cursor.fetchall()
        show_names = False

    cursor.close()
    return render_template("admin.html", username=username, group=group, patients=patients, show_names=show_names)


@app.route("/logout", methods=['GET', 'POST'])
def logout_user():
    session.clear()
    return render_template("index.html")





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


    
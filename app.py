import os
import re
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import MySQLdb.cursors

app = Flask(__name__)

input_file = '.env'
variables = {}
with open(input_file, 'r') as f:
    for line in f:
        line = line.strip()
        if '=' in line:
            key, value = line.split('=', 1)
            variables[key] = value

BORNEO_SECRET_KEY = variables['BORNEO_SECRET_KEY']
MYSQL_HOST = variables['MYSQL_HOST']
MYSQL_USER = variables['MYSQL_USER']
MYSQL_PASSWORD = variables['MYSQL_PASSWORD']
MYSQL_DB = variables['MYSQL_DB']
ADMIN_YUG_PW = variables['ADMIN_YUG_PW']
ADMIN_NICK_PW = variables['ADMIN_NICK_PW']

app.secret_key = BORNEO_SECRET_KEY
app.config["MYSQL_HOST"] = MYSQL_HOST
app.config["MYSQL_USER"] = MYSQL_USER
app.config["MYSQL_PASSWORD"] = MYSQL_PASSWORD
app.config["MYSQL_DB"] = MYSQL_DB

mysql = MySQL(app)


@app.route("/")
def index():
    message = request.args.get('message', '')
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT name, price, ID from product")
    mysql.connection.commit()
    data = cursor.fetchall()
    cursor.close()
    # print(data)
    # print(data)
    if 'loggedin' in session:
        return render_template("index.html", data=data, email=session['email'])
    else:
        return render_template("index.html", data=data, email=None, message=message)

@app.route("/view_product/<int:product_id>", methods=['GET'])
def view_product(product_id):
    cursor = mysql.connection.cursor()
    query = 'SELECT * FROM product WHERE ID = %s'
    cursor.execute(query, (product_id,))
    mysql.connection.commit()
    product_data = cursor.fetchone()
    print(product_data)
    query2 = 'SELECT seller_ID from products_offered where product_ID = %s'
    cursor.execute(query2, (product_id,))
    seller_id = cursor.fetchone()
    seller_id = seller_id[0]
    print("SELLER_ID", seller_id)

    query3 = 'SELECT name from seller where id = %s'
    cursor.execute(query3, (seller_id,))
    seller_name = cursor.fetchone()
    print("OBTAINED SELLER NAME", seller_name)
    # because the return value for default cursor() is tuple
    seller_name = seller_name[0]
    cursor.close()
    return render_template('view_product.html', product=product_data, seller_name=seller_name)


@app.route("/buy_product/<int:product_id>", methods=['GET', 'POST'])
def buy_product(product_id):
    message = ''
    # Check if user is a buyer
    buyer_email = session['email']
    buyer_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM buyer WHERE email = %s', (buyer_email,))
    buyer_account = cursor.fetchone() 

    print("HERE")
    print("BUYER EMAIL", buyer_email)
    print('BUYER ACC', buyer_account)
    print(session['loggedin'])
    print(request.method)
    if buyer_account and ('loggedin' in session) and request.method == 'POST':
        query1 = "SELECT name from product WHERE id = %s"
        cursor.execute(query1, (product_id,))
        product_name = cursor.fetchone()
        query2 = "INSERT INTO `bought_by`(`product_ID`, `buyer_ID`) VALUES (%s,%s)"
        cursor.execute(query2, (product_id, buyer_id))
        mysql.connection.commit()
        product_name = product_name['name']
        message = f"{buyer_email} successfully purchased {product_name}"

        query3 = 'SELECT ID, name, price from product where ID IN (SELECT product_id from bought_by where buyer_id = %s)'
        cursor.execute(query3, (buyer_id,))
        past_purchases = cursor.fetchall()
        print("PAST PURCHASES", past_purchases)
        mysql.connection.commit()
        return render_template('buy_product.html', message=message, product_name=product_name, buyer_email=buyer_email, past_purchases=past_purchases)
    else:
        message = "Please log in before purchase"
        return render_template('buyer_login.html', message=message)


@app.route("/past_purchases", methods = ['GET'])
def past_purchases():
    # Check if user is a buyer

    if 'email' not in session or session['email'] is None:
        message = "Please login as a buyer first!"
        return redirect(url_for('index', message=message))
      
    buyer_email = session['email']
    buyer_id = session['id']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM buyer WHERE email = %s', (buyer_email,))
    buyer_account = cursor.fetchone() 
    if buyer_account and 'loggedin' in session:
        query = 'SELECT ID, name, price from product where ID IN (SELECT product_id from bought_by where buyer_id = %s)'
        cursor.execute(query, (buyer_id,))
        past_purchases = cursor.fetchall()
        return render_template('past_purchases.html', past_purchases=past_purchases, buyer_email= buyer_email)
    else:
        return redirect("index.html")



@app.route("/add_product", methods = ['GET', 'POST'])
def add_product():
    message= ""
    # Check if user is a seller
    if 'email' not in session or session['email'] is None:
        message = "Please login as a seller first!"
        return redirect(url_for('index', message=message))

    seller_email = session['email']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM seller WHERE email = %s', (seller_email,))
    seller_account = cursor.fetchone() 

    print("REQUEST.FORM ADD PROD")
    print(request.form)
    if 'loggedin' in session and seller_account and request.method == 'POST':
        seller_ID = session['id']
        name = request.form['product_name']
        price = request.form['product_price']
        description = request.form['product_description']
        stars = None
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = "INSERT INTO `product`(`seller_ID`, `name`, `price`, `stars`, `description`) VALUES (%s,%s,%s,%s,%s)"
        cursor.execute(query, (seller_ID, name, price,stars , description))
        mysql.connection.commit()

        query2 = 'SELECT ID from product WHERE name = %s'
        cursor.execute(query2, (name,))
        product_ID= cursor.fetchone()
        print("new product_ID", product_ID)
        product_ID = product_ID['ID']
        print("again new product_id", product_ID)

        print("BEFORE Q3")

        query3 = 'INSERT into products_offered VALUES (%s, %s)'
        cursor.execute(query3,(seller_ID, product_ID))
        mysql.connection.commit()
        print("QUERY 3 SUCCESS")
        message = f'Successfully added product {name}'
        print(message)
    else:
        message = "Please log in as a Seller before you add a product."
        return render_template('add_product.html', message=message)
    return redirect(url_for('index', message=message))
    
    


@app.route("/buyer_login", methods=["GET","POST"])
def buyer_login():
    message = ""
    print(request.form)
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        print("PASSWORD", password)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = "SELECT * from buyer WHERE email = %s"
        cursor.execute(query, (email,))
        account = cursor.fetchone()
        
        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['email'] = account['email']
            print("successful")
            return redirect(url_for('index'))
        else:
            message = "Incorrect email/password"
            print(message)
    return render_template('buyer_login.html', message=message)

@app.route("/register_new_buyer", methods= ['POST', 'GET'])
def register_new_buyer():
    message = ""
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        address = request.form['address']
        phone_number = request.form['phone_number']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = 'SELECT * from buyer WHERE email = %s'
        cursor.execute(query, (email,))
        account = cursor.fetchone()
        if account:
            message = 'Account already exists.'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = "Invalid email address"
        elif len(phone_number) > 10:
            message = "Invalid phone number" 
        elif not email or not password or not name or not address or not phone_number:
            message = "Please fill out the entire form"
        else:
            hashed_password = generate_password_hash(password)
            query = 'INSERT INTO `buyer`(`name`, `address`, `phone_number`, `email`, `password`) VALUES (%s,%s,%s,%s,%s);'
            cursor.execute(query, (name, address, phone_number, email, hashed_password))
            mysql.connection.commit()

            query2 = 'SELECT id from buyer where name = %s'
            cursor.execute(query2, (name,))
            buyer_id = cursor.fetchone()
            buyer_id = buyer_id['id']
            print("after buyer_id", buyer_id)

            query3 = 'INSERT INTO `buyer_ph_numbers`(`ID`, `phone_number`) VALUES (%s,%s)'
            cursor.execute(query3, (buyer_id, phone_number))
            mysql.connection.commit()
            print("BUYER PHONE NUMBER ADDEED")
            message = f"Successful buyer Registration for {name}"
    elif request.method == 'POST':
        message = render_template('index.html', message=message)

    return render_template('register_new_buyer.html', message=message)


@app.route("/seller_login", methods=["GET","POST"])
def seller_login():
    message = ""
    print("REQUEST.FORM")
    print(request.form)
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        print("PASSWORD", password)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = "SELECT * from seller WHERE email = %s"
        cursor.execute(query, (email,))
        account = cursor.fetchone()
        
        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['id'] = account['id']
            session['email'] = account['email']
            return redirect(url_for('index'))
        else:
            message = "Incorrect email/password"
    return render_template('seller_login.html', message=message)

@app.route("/register_new_seller", methods= ['POST', 'GET'])
def register_new_seller():
    message = ""
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        address = request.form['address']
        phone_number = request.form['phone_number']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = 'SELECT * from seller WHERE email = %s'
        cursor.execute(query, (email,))
        account = cursor.fetchone()
        if account:
            message = 'Account already exists.'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            message = "Invalid email address"
        elif len(phone_number) > 10:
            message = "Invalid phone number" 
        elif not email or not password or not name or not address or not phone_number:
            message = "Please fill out the entire form"
        else:
            hashed_password = generate_password_hash(password)
            query = 'INSERT INTO `seller`(`name`, `address`, `phone_number`, `email`, `password`) VALUES (%s,%s,%s,%s,%s);'
            cursor.execute(query, (name, address, phone_number, email, hashed_password))
            mysql.connection.commit()

            query2 = 'SELECT id from seller where name = %s'
            cursor.execute(query2, (name,))
            seller_id = cursor.fetchone()
            seller_id = seller_id['id']
            print("after seller_id", seller_id)

            query3 = 'INSERT INTO `seller_ph_numbers`(`ID`, `phone_number`) VALUES (%s,%s)'
            cursor.execute(query3, (seller_id, phone_number))
            mysql.connection.commit()
            print("SELLER PHONE NUMBER ADDEED")
            message = f"Successful SELLER Registration for {name}"
    elif request.method == 'POST':
        message = render_template('index.html', message=message)
    return render_template('register_new_seller.html', message=message)

@app.route("/admin", methods=['GET', 'POST'])
def admin():
    pass

@app.route('/admin_dashboard')
def admin_dashboard():
    message= ""
    # Check if user is a admin
    if 'email' not in session or session['email'] is None:
        message = "Please login as Admin first!"
        return redirect(url_for('admin_login', message=message))

    admin_email = session['email']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM admin WHERE email = %s', (admin_email,))
    admin_account = cursor.fetchone() 

    if 'loggedin' in session and admin_account :
        print("INSIDE ADMIN IF")
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("select ID, name from product")
        products = cursor.fetchall()

        cursor.execute("select ID, name from seller")
        sellers = cursor.fetchall()

        cursor.execute("select ID, name from buyer")
        buyers = cursor.fetchall()

        message = f'Successfully retrieved all 3'
        print(message)
        return render_template('admin_dashboard.html', message=message, products=products, sellers=sellers, buyers=buyers)

    message = "Please log in as an Admin."
    session['message'] = message
    return redirect(url_for('admin_login', message=message))
    # return render_template('admin_dashboard.html')

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    message = ""
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        query = "SELECT * from admin WHERE email = %s"
        cursor.execute(query, (email,))
        account = cursor.fetchone()
        
        if account and password in [ADMIN_NICK_PW, ADMIN_YUG_PW]:
            session['loggedin'] = True
            session['id'] = account['ID']
            session['email'] = account['email']
            return redirect(url_for('admin_dashboard'))
        else:
            message = "Incorrect email/password"
    return render_template('admin_login.html', message=message)

@app.route("/delete_product/<int:product_id>", methods=['POST'])
def delete_product(product_id):
    print("INSIDE def delete_product(product_id)")
    message = ""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = "delete from product where ID = %s"
    cursor.execute(query, (product_id,))
    message = f"Successfully Deleted product ID {product_id}"
    return redirect(url_for('admin_dashboard', message=message))

@app.route("/delete_seller/<int:seller_id>", methods=['POST'])
def delete_seller(seller_id):
    print("INSIDE def dele seller(product_id)")
    message = ""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = "delete from seller where ID = %s"
    cursor.execute(query, (seller_id,))
    message = f"Successfully Deleted Seller ID {seller_id}"
    return redirect(url_for('admin_dashboard', message=message))

@app.route("/delete_buyer/<int:buyer_id>", methods=['POST'])
def delete_buyer(buyer_id):
    print("INSIDE def delete_buyer(product_id)")
    message = ""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = "delete from buyer where ID = %s"
    cursor.execute(query, (buyer_id,))
    message = f"Successfully Deleted Buyer ID {buyer_id}"
    return redirect(url_for('admin_dashboard', message=message))

@app.route("/logout", methods=['POST'])
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('email', None)
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(port=9998, debug=True)

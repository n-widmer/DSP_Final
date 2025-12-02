import os
import re

from flask import Flask, render_template, request, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
@app.get("/")
def home():
    return {"message": "Hello world!"}

if __name__ == "__main__":
    app.run(debug=True)


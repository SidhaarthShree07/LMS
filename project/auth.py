import sqlite3
from sqlite3 import Cursor, connect
from flask import Blueprint,Flask,render_template,request,redirect,url_for,flash,make_response
from flask_login import UserMixin,login_user,login_manager,LoginManager,logout_user,login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from . import db
import secrets
auth = Blueprint('auth', __name__)

@auth.route('/Login')
def Login():
    remember_token = request.cookies.get('remember_token')
    print(remember_token)
    if remember_token:
        user = User.query.filter_by(remember_token=remember_token).first()
        if user:
            remember_username = user.username
            remember_password = ''
            return render_template('Login.html', remember_username=remember_username, remember_password=remember_password)
    return render_template('Login.html')

@auth.route('/Login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('rememberMe')
        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password.')
            return redirect(url_for('auth.login'))

        login_user(user)

        if remember_me:
            remember_token = secrets.token_hex(32)
            user.remember_token = remember_token
            db.session.commit()
            response = make_response(redirect(url_for('main.profile')))
            response.set_cookie('remember_token', remember_token, max_age=604800)
            return response

        return redirect(url_for('main.profile'))

    return render_template('Login.html')

@auth.route('/Register')
def Register():
    return render_template('Register.html')

@auth.route('/Register' , methods=['POST'])
def Register_Post():
    username= request.form.get('username')
    name= request.form.get('name')
    password= request.form.get('password')
    
    if not (username and name and password):
        flash('Name, username, and password are compulsory fields.')
        return redirect(url_for('auth.Register'))
    if len(password) < 5:
        flash('Password is weak. It should be at least 5 characters long.')
        return redirect(url_for('auth.Register'))
    
    user = User.query.filter_by(username=username).first()
    mem = secrets.token_hex(32)
    if user:
        flash('Username already exists.')
        return redirect(url_for('auth.Register'))
    new_user = User(username=username, name=name, password=generate_password_hash(password, method='scrypt'),remember_token=mem)
    
    db.session.add(new_user)
    db.session.commit()
 
    
    return redirect(url_for('auth.Login'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))



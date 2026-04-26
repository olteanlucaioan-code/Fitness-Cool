import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import stripe
import qrcode

app = Flask(__name__)
app.config['SECRET_KEY'] = 'atestat-fitness-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Inlocuieste cu cheia ta reala de la Stripe
stripe.api_key = "sk_test_PUNE_CHEIA_TA_AICI"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    expiry_date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Folosim 'username' pentru a evita eroarea 400 Bad Request
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Utilizatorul exista deja!')
            return redirect(url_for('register'))
        
        new_user = User(username=username, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Date incorecte!')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    is_active = current_user.expiry_date > datetime.utcnow()
    qr_url = None
    if is_active:
        qr_data = f"MEMBRU:{current_user.username}|VALID:{current_user.expiry_date.date()}"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_data}"
    return render_template('dashboard.html', user=current_user, is_active=is_active, qr_url=qr_url)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)

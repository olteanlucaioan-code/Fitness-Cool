import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import stripe

app = Flask(__name__)
app.config['SECRET_KEY'] = 'atestat-fitness-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# !!! PUNE AICI CHEIA TA SECRETĂ DE LA STRIPE (cea cu sk_test_...) !!!
stripe.api_key = "sk_test_PUNE_CHEIA_TA_AICI"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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
        u = request.form.get('username')
        p = request.form.get('password')
        if User.query.filter_by(username=u).first():
            return "Utilizator existent!"
        new_user = User(username=u, password=generate_password_hash(p))
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
        return "Eroare login!"
    return render_template('login.html')

# --- LOGICA STRIPE ---
@app.route('/pay/<int:amount>')
@login_required
def create_checkout_session(amount):
    try:
        # Mapăm sumele la nume de produse
        titles = {50: "Abonament 1 Zi", 150: "Abonament 7 Zile", 300: "Abonament 30 Zile"}
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'ron',
                    'product_data': {'name': titles.get(amount, "Abonament Fitness")},
                    'unit_amount': amount * 100, # Stripe vrea banii in bani marunti (bani, nu lei)
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('payment_success', amount=amount, _external=True),
            cancel_url=url_for('dashboard', _external=True),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return str(e)

@app.route('/payment-success/<int:amount>')
@login_required
def payment_success(amount):
    days = {50: 1, 150: 7, 300: 30}.get(amount, 0)
    if current_user.expiry_date < datetime.utcnow():
        current_user.expiry_date = datetime.utcnow() + timedelta(days=days)
    else:
        current_user.expiry_date += timedelta(days=days)
    db.session.commit()
    flash(f"Plată reușită! Ai primit {days} zile de acces.")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    is_active = current_user.expiry_date > datetime.utcnow()
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=MEMBRU_{current_user.username}"
    return render_template('dashboard.html', user=current_user, is_active=is_active, qr_url=qr_url)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()

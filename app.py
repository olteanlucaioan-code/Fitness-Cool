from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import os
from datetime import datetime, timedelta
import stripe

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cheie-secreta-foarte-sigura'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gym_users.db'

# --- PUNE CHEIA TA AICI ---
stripe.api_key = "sk_test_51TQOxULiFOYtlLchfpq0zSALAYu0zqXI7N1lk3ZCvEXZnGTh3SeXHpWSzBzqLd88CkwlRe6QAXxABb6XQDR3BqQ200LmQhvRYA"
# --------------------------

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

QR_FOLDER = os.path.join('static', 'qr')
if not os.path.exists(QR_FOLDER): os.makedirs(QR_FOLDER)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    expiry_date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

@app.route('/')
def home(): return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(username=request.form['username'], email=request.form['email'], password=hashed_pw)
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except: return "Eroare: Username/Email deja folosit!"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Email sau parolă greșită!')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    is_active = current_user.expiry_date > datetime.utcnow()
    qr_path = None
    if is_active:
        qr_data = f"USER:{current_user.id}|EXP:{current_user.expiry_date.strftime('%Y-%m-%d')}"
        img = qrcode.make(qr_data)
        qr_filename = f"{current_user.id}.png"
        img.save(os.path.join(QR_FOLDER, qr_filename))
        qr_path = f"qr/{qr_filename}"
    return render_template('dashboard.html', user=current_user, is_active=is_active, qr_path=qr_path)

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    amount = request.form.get('amount')
    nume_pachet = "Acces 24H" if amount == "50" else ("7 Zile" if amount == "200" else "30 Zile VIP")
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'ron',
                    'product_data': {'name': f"Fitness Cool - {nume_pachet}"},
                    'unit_amount': int(amount) * 100, # 50 RON = 5000 bani
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

@app.route('/payment-success')
@login_required
def payment_success():
    amount = request.args.get('amount')
    zile = 1 if amount == "50" else (7 if amount == "200" else 30)
    
    # Adăugăm zilele la abonament
    start_date = max(current_user.expiry_date, datetime.utcnow())
    current_user.expiry_date = start_date + timedelta(days=zile)
    db.session.commit()
    
    flash(f"Plată reușită! Ai primit {zile} zile de acces.")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
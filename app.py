import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import stripe
import qrcode

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-pentru-atestat'
# Baza de date SQLite
app.config['SQLALCHEMY_DATABASE_DATABASE_URI'] = 'sqlite:///gym_users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Cheia ta Stripe (Sandbox)
stripe.api_key = "sk_test_51P2u..." # Pune cheia ta completa aici

# Folder pentru salvat coduri QR
QR_FOLDER = os.path.join('static', 'qrcodes')
if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

# Modelul Bazei de Date
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    expiry_date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- RUTE APLICAȚIE ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user:
            flash('Utilizatorul există deja!')
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(request.form['password'])
        new_user = User(username=request.form['username'], password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Date incorecte!')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Verificăm dacă abonamentul este activ
    is_active = current_user.expiry_date > datetime.utcnow()
    qr_path = None

    if is_active:
        # Generăm Codul QR
        qr_data = f"MEMBRU:{current_user.username}|EXPIRA:{current_user.expiry_date.strftime('%Y-%m-%d')}"
        qr = qrcode.make(qr_data)
        qr_filename = f"qr_{current_user.id}.png"
        qr.save(os.path.join(QR_FOLDER, qr_filename))
        qr_path = url_for('static', filename=f'qrcodes/{qr_filename}')

    return render_template('dashboard.html', user=current_user, is_active=is_active, qr_path=qr_path)

@app.route('/pay/<amount>')
@login_required
def pay(amount):
    # Creare sesiune de plată Stripe
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'ron',
                'product_data': {'name': f'Abonament Fitness Cool - {amount} RON'},
                'unit_amount': int(amount) * 100,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=url_for('payment_success', amount=amount, _external=True),
        cancel_url=url_for('dashboard', _external=True),
    )
    return redirect(session.url, code=303)

@app.route('/payment-success/<amount>')
@login_required
def payment_success(amount):
    # Prelungim abonamentul în funcție de sumă
    days = 1 if amount == "50" else (7 if amount == "200" else 30)
    
    if current_user.expiry_date < datetime.utcnow():
        current_user.expiry_date = datetime.utcnow() + timedelta(days=days)
    else:
        current_user.expiry_date += timedelta(days=days)
    
    db.session.commit()
    flash(f'Plată reușită! Abonament prelungit cu {days} zile.')
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Creare tabele la pornire
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)

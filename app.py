from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
from markupsafe import Markup


app = Flask(__name__)
app.secret_key = "secret123"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bank.db'
db = SQLAlchemy(app)

# =====================
# Database Models
# =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    accounts = db.relationship("Account", backref="owner", lazy=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, nullable=False)

    # 🔹 New fields
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    routing_number = db.Column(db.String(20), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    transactions = db.relationship("Transaction", backref="account", lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))  # credit or debit
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    description = db.Column(db.String(200))
    account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=False)

import random

def generate_account_number():
    return str(random.randint(1000000000, 9999999999))  # 10-digit number

def generate_routing_number():
    return "000138582"  # fixed routing number for all accounts

# =====================
# Helper Functions
# =====================
def random_time(year, month, day):
    return datetime(
        year, month, day,
        random.randint(8, 20),   # Hour
        random.randint(0, 59),   # Minute
        random.randint(0, 59)    # Second
    )

# =====================
# Routes
# =====================
@app.route("/")
def home():
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        return render_template("home.html", user=user, accounts=user.accounts)
    return render_template("base.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect("/signup")
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Signup successful, please login.", "success")
        return redirect("/login")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user_id"] = user.id
            flash("Login successful! 👋", "success")
            return redirect("/")
        flash("Invalid credentials!", "danger")
        return redirect("/login")
    return render_template("login.html")

@app.route("/deposit/<int:account_id>", methods=["POST"])
def deposit(account_id):
    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect("/login")
    amount = float(request.form["amount"])
    account = db.session.get(Account, from_account_id)
    if account and account.owner.id == session["user_id"]:
        account.balance += amount
        db.session.add(Transaction(type="credit", amount=amount, description="Deposit", account=account))
        db.session.commit()
        flash(f"Successfully deposited ${amount:,.2f} into {account.name}.", "success")
    return redirect("/")

@app.route("/withdraw/<int:account_id>", methods=["POST"])
def withdraw(account_id):
    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect("/login")
    amount = float(request.form["amount"])
    account = db.session.get(Account, from_account_id)
    if account and account.owner.id == session["user_id"]:
        if account.balance >= amount:
            account.balance -= amount
            db.session.add(Transaction(type="debit", amount=amount, description="Withdrawal", account=account))
            db.session.commit()
            flash(f"Successfully withdrew ${amount:,.2f} from {account.name}.", "success")
        else:
            flash("Not enough balance!", "danger")
    return redirect("/")

# =====================
# Transfer Route
# =====================
@app.route("/transfer/<int:from_account_id>", methods=["GET", "POST"])
def transfer(from_account_id):
    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect("/login")

    from_account = db.session.get(Account, from_account_id)
    if not from_account or from_account.owner.id != session["user_id"]:
        flash("Unauthorized access!", "danger")
        return redirect("/")

    if request.method == "POST":
        # Freeze message with chat button
        error_message = Markup(
            """
            <div class="alert alert-danger">
                A freeze has been placed on this account. All outgoing transactions are temporarily suspended. <br>
                For assistance, please click below to chat with our Customer Care:
                <br><br>
                <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#chatModal">
                    💬 Start Live Chat
                </button>
            </div>
            """
        )
        flash(error_message, "danger")
        return redirect(f"/transfer/{from_account_id}")

    return render_template("transfer.html", account=from_account)


# =====================
# Customer Care Chat Route
# =====================
@app.route("/customer-care")
def customer_care():
    return render_template("chat.html")  # chat UI loads here


@app.route("/history/<int:account_id>")
def history(account_id):
    if "user_id" not in session:
        flash("Please log in first.", "danger")
        return redirect("/login")

    account = db.session.get(Account, account_id)  # ✅ use account_id
    if not account or account.owner.id != session["user_id"]:
        flash("Unauthorized access!", "danger")
        return redirect("/")

    transactions = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.timestamp.desc()).all()
    return render_template("history.html", account=account, transactions=transactions)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "success")
    return redirect("/")

@app.context_processor
def inject_user():
    if "user_id" in session:
        return {"user": db.session.get(User, session["user_id"])}
    return {"user": None}

# =====================
# Run App + Seed Data
# =====================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # ---- Functions for random account numbers ----
        def random_account_number():
            return str(random.randint(1000000000, 9999999999))  # 10-digit account

        routing_number = "000138582"  # example: Chase Bank routing

        # ---- Seed Data ----
        if not User.query.filter_by(username="Melodee").first():
            user = User(username="Melodee", password="Goodluck60!")
            db.session.add(user)
            db.session.commit()

            # Personal Account
            personal = Account(
                name="Diane Nowell (Personal)",
                balance=75000.65,
                account_number=random_account_number(),
                routing_number=routing_number,
                owner=user
            )
            db.session.add(personal)

            personal_txns = [
                Transaction(type="credit", amount=2000, description="Salary bonus – August", timestamp=random_time(2025,8,3), account=personal),
                Transaction(type="debit", amount=450, description="Grocery shopping – Carrefour", timestamp=random_time(2025,8,4), account=personal),
                Transaction(type="debit", amount=120, description="Coffee shop – Starbucks", timestamp=random_time(2025,8,5), account=personal),
                Transaction(type="credit", amount=1500, description="Gift received from family", timestamp=random_time(2025,8,7), account=personal),
                Transaction(type="debit", amount=300, description="Movie tickets – VOX Cinemas", timestamp=random_time(2025,8,8), account=personal),
                Transaction(type="debit", amount=250, description="Taxi fare – Uber", timestamp=random_time(2025,8,9), account=personal),
                Transaction(type="credit", amount=800, description="Refund – Online order cancellation", timestamp=random_time(2025,8,10), account=personal),
                Transaction(type="debit", amount=1000, description="Shopping – Zara", timestamp=random_time(2025,8,12), account=personal),
                Transaction(type="debit", amount=600, description="Restaurant dinner – Nusr-Et Steakhouse", timestamp=random_time(2025,8,13), account=personal),
                Transaction(type="credit", amount=2200, description="Freelance payment – Graphic design project", timestamp=random_time(2025,8,15), account=personal),
                Transaction(type="debit", amount=200, description="Pharmacy – Medcare", timestamp=random_time(2025,8,16), account=personal),
                Transaction(type="debit", amount=350, description="Gym subscription – Anytime Fitness", timestamp=random_time(2025,8,18), account=personal),
                Transaction(type="credit", amount=950, description="Reimbursement – Office expense", timestamp=random_time(2025,8,20), account=personal),
                Transaction(type="debit", amount=420, description="Internet bill payment – Ooredoo", timestamp=random_time(2025,8,21), account=personal),
                Transaction(type="credit", amount=1500, description="Friend repayment", timestamp=random_time(2025,8,23), account=personal),
                Transaction(type="debit", amount=750, description="Weekend getaway – Hotel booking", timestamp=random_time(2025,8,25), account=personal),
                Transaction(type="debit", amount=90, description="Fast food – McDonald's", timestamp=random_time(2025,8,26), account=personal),
                Transaction(type="credit", amount=1000, description="Side hustle payment – Photography gig", timestamp=random_time(2025,8,27), account=personal),
                Transaction(type="debit", amount=600, description="Restaurant dinner – September special", timestamp=random_time(2025,9,5), account=personal),
                Transaction(type="debit", amount=150, description="Mobile recharge – Vodafone", timestamp=random_time(2025,9,6), account=personal),
                Transaction(type="credit", amount=1200, description="Savings interest payout", timestamp=random_time(2025,9,7), account=personal),
                Transaction(type="debit", amount=200, description="Spa & wellness center", timestamp=random_time(2025,9,8), account=personal),
                Transaction(type="debit", amount=300, description="Taxi fare – Careem", timestamp=random_time(2025,9,9), account=personal),
            ]
            db.session.add_all(personal_txns)

            # Business Account
            business = Account(
                name="Danowell LLC",
                balance=3_750_000,
                account_number=random_account_number(),
                routing_number=routing_number,  # same routing number
                owner=user
            )
            db.session.add(business)

            business_txns = [
                Transaction(type="credit", amount=500000, description="Contract advance – Skyline Constructions", timestamp=random_time(2025,8,2), account=business),
                Transaction(type="debit", amount=15000, description="Office furniture purchase – IKEA", timestamp=random_time(2025,8,3), account=business),
                Transaction(type="debit", amount=22000, description="Staff salaries – August payroll", timestamp=random_time(2025,8,5), account=business),
                Transaction(type="credit", amount=120000, description="Consulting fee – Al Jazeera Media", timestamp=random_time(2025,8,6), account=business),
                Transaction(type="debit", amount=12500, description="Office supplies – Stationery World", timestamp=random_time(2025,8,10), account=business),
                Transaction(type="credit", amount=250000, description="IT project settlement – Doha Tech", timestamp=random_time(2025,8,12), account=business),
                Transaction(type="debit", amount=8000, description="Electricity & internet bills", timestamp=random_time(2025,8,15), account=business),
                Transaction(type="credit", amount=75000, description="Legal advisory refund – Global Chambers", timestamp=random_time(2025,8,18), account=business),
                Transaction(type="debit", amount=11000, description="Business lunch – Marriott", timestamp=random_time(2025,8,20), account=business),
                Transaction(type="credit", amount=97000, description="Consultancy retainer – Qatar Gas", timestamp=random_time(2025,8,22), account=business),
                Transaction(type="debit", amount=5000, description="Transportation – Company vehicles fueling", timestamp=random_time(2025,8,25), account=business),
                Transaction(type="credit", amount=180000, description="Advance payment – Lusail Developers", timestamp=random_time(2025,8,28), account=business),
                Transaction(type="debit", amount=3200, description="Utility bills – Water & Waste management", timestamp=random_time(2025,9,1), account=business),
                Transaction(type="credit", amount=65000, description="Design project fee – Aspire Academy", timestamp=random_time(2025,9,4), account=business),
                Transaction(type="credit", amount=2500000, description="Payment from Ministry of Works Qatar", timestamp=random_time(2025,9,8), account=business),
                Transaction(type="debit", amount=10282, description="Flight ticket fee – Qatar Airways", timestamp=random_time(2025,9,9), account=business),
                Transaction(type="debit", amount=7800, description="Printing & branding – SignWorks Qatar", timestamp=random_time(2025,9,10), account=business),
                Transaction(type="credit", amount=420000, description="Engineering consultancy payment – Doha Ports", timestamp=random_time(2025,9,12), account=business),
                Transaction(type="debit", amount=9300, description="Event sponsorship – Business Expo", timestamp=random_time(2025,9,13), account=business),
                Transaction(type="debit", amount=6000, description="Courier & logistics fees", timestamp=random_time(2025,9,14), account=business),
            ]
            db.session.add_all(business_txns)

            db.session.commit()
            print("✅ Seed data created successfully!")

    app.run(debug=True)



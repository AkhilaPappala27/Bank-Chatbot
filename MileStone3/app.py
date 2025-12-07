from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from chatbot.chatbot import bot   # rule-based chatbot
import os
import sqlite3
import random


app = Flask(__name__)
app.secret_key = "testkey"   # needed for session

def get_transactions(acc_no):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT receiver_name, amount, txn_type, txn_date, txn_time
        FROM transactions
        WHERE sender_acc = ?
        ORDER BY id DESC
    """, (acc_no,))
    
    rows = cur.fetchall()
    conn.close()
    return rows


# ============================
# ROUTES
# ============================

# Redirect root to login
@app.route("/")
def root():
    return redirect(url_for("login"))

# -----------------------------
# LOGIN PAGE
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        account = request.form.get("account")
        password = request.form.get("password")

        # Connect to SQLite and validate login
        conn = sqlite3.connect("bank.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE accountNumber=? AND password=?", (account, password))
        user = cur.fetchone()
        conn.close()

        if user:
            # Save user details into session
            session["user_account"] = user[1]       # accountNumber
            session["user_balance"] = user[2]       # currentBalance
            session["user_name"] = user[3]          # accountName
            session["user_email"] = user[4]         # email
            session["user_phone"] = user[5]         # phone
            session["user_address"] = user[6]       # address
            session["user_dob"] = user[7]           # dob
            session["user_gender"] = user[8]        # gender
            session["user_prevTxn"] = user[9]       # previous transaction
            session["user_txnType"] = user[10]      # previous transaction type
            session["user_lastTxnDate"] = user[11]  # last transaction date
            session["user_lastTxnTime"] = user[12]  # last transaction time
            session["user_receiverName"] = user[13] # last receiver name
            session["user_receiverAcc"] = user[14]  # last receiver account

            return redirect(url_for("dashboard"))
        else:
            error = "Invalid account number or password."

    return render_template("login.html", error=error)

# -----------------------------
# SIGNUP PAGE
# -----------------------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        # Fetch all form values
        acc = request.form.get("accountNumber")
        bal = request.form.get("currentBalance")
        name = request.form.get("accountName")

        email = request.form.get("email")
        phone = request.form.get("phone")
        address = request.form.get("address")

        dob = request.form.get("dob")
        gender = request.form.get("gender")

        prev = request.form.get("prevTxn")
        txn = request.form.get("txnType")
        last_date = request.form.get("lastTxnDate")
        last_time = request.form.get("lastTxnTime")

        receiver_name = request.form.get("receiverName")
        receiver_acc = request.form.get("receiverAcc") or "N/A"   # ⭐ default if empty


        pwd = request.form.get("password")
        confirm_pwd = request.form.get("confirmPassword")

        # 1️⃣ Check password match
        if pwd != confirm_pwd:
            return "<script>alert('❌ Passwords do not match!'); window.history.back();</script>"

        # Connect to DB
        conn = sqlite3.connect("bank.db")
        cur = conn.cursor()

        # 2️⃣ Check duplicate account
        cur.execute("SELECT * FROM users WHERE accountNumber=?", (acc,))
        existing_user = cur.fetchone()

        if existing_user:
            conn.close()
            return "<script>alert('❌ Account already exists!'); window.history.back();</script>"

        # 3️⃣ Insert new user
        cur.execute("""
            INSERT INTO users 
            (accountNumber, currentBalance, accountName, 
             email, phone, address, dob, gender, 
             prevTxn, txnType, lastTxnDate, lastTxnTime,
             receiverName, receiverAcc, password)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            acc, bal, name, email, phone, address,
            dob, gender, prev, txn, last_date, last_time,
            receiver_name, receiver_acc, pwd
        ))

        # ⭐ 4️⃣ INSERT SIGNUP TRANSACTION INTO TRANSACTIONS TABLE
        if prev and txn:
            txn_id = "TXN" + str(random.randint(100000, 999999))

            cur.execute("""
    INSERT INTO transactions (
        sender_acc, receiver_acc, receiver_name, 
        amount, txn_type, txn_date, txn_time, txn_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (
    # sender
    acc if txn == "debit" else receiver_acc,

    # receiver
    receiver_acc if txn == "debit" else acc,

    receiver_name if receiver_name else name,
    prev,
    txn,
    last_date,
    last_time,
    txn_id
))


        # Commit and close DB
        conn.commit()
        conn.close()

        return "<script>alert('✔ Signup successful! Please login.'); window.location='/login';</script>"

    return render_template("signup.html")

# -----------------------------
# DASHBOARD PAGE
# -----------------------------
@app.route("/dashboard")
def dashboard():
    username = session.get("user_name", "User")
    return render_template("home.html")

# -----------------------------
# CHATBOT UI PAGE
# -----------------------------
@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")

@app.route("/get", methods=["POST"])
def chat():
    user_message = request.form["message"]
    sender_account = session.get("user_account")   # Logged-in user

    reply = bot(user_message, sender_account)

    # 🔥 If bot returns (message, updated_balance)
    if isinstance(reply, tuple):
        message, new_balance = reply
        session["user_balance"] = new_balance  # update session balance
        return jsonify({"response": message})

    # Normal text response
    return jsonify({"response": reply})

@app.route("/profile")
def profile():
    if "user_account" not in session:
        return redirect(url_for("login"))

    accno = session.get("user_account")

    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    # 🔥 Fetch latest balance from DB
    cur.execute("SELECT currentBalance FROM users WHERE accountNumber=?", (accno,))
    latest_balance = cur.fetchone()[0]

    # Fetch DEBITS (sent by user)
    cur.execute("""
        SELECT receiver_name, amount, 'debit', txn_date, txn_time
        FROM transactions
        WHERE sender_acc = ?
    """, (accno,))
    debits = cur.fetchall()

    # Fetch CREDITS (received by user)
    cur.execute("""
        SELECT receiver_name, amount, 'credit', txn_date, txn_time
        FROM transactions
        WHERE receiver_acc = ?
    """, (accno,))
    credits = cur.fetchall()

    conn.close()

    # Merge and sort newest → oldest
    history = debits + credits
    history.sort(key=lambda x: (x[3] or "", x[4] or ""), reverse=True)

    total_debit = sum(t[1] for t in debits) if debits else 0
    total_credit = sum(t[1] for t in credits) if credits else 0
    txn_count = len(history)

    return render_template(
        "profile.html",
        name=session.get("user_name"),
        acc=accno,
        balance=latest_balance,      # 🔥 always use updated balance
        email=session.get("user_email"),
        phone=session.get("user_phone"),
        dob=session.get("user_dob"),
        gender=session.get("user_gender"),
        address=session.get("user_address"),
        history=history,
        total_credit=total_credit,
        total_debit=total_debit,
        txnCount=txn_count
    )

@app.route("/show_transactions")
def show_transactions():
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions")
    data = cur.fetchall()
    conn.close()
    return {"transactions": data}

# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from chatbot.chatbot import bot
import re
import sqlite3
import random
import json
from datetime import datetime
import time
from flask import Response
import json
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = "testkey"
# -----------------------------
# MAIL CONFIG (USE YOUR EMAIL)
# -----------------------------
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "pappalakhila27@gmail.com"      # change
app.config["MAIL_PASSWORD"] = "cfgsbdjgakwjtmhgp"        # Gmail App Password
app.config["MAIL_DEFAULT_SENDER"] = "pappalakhila27@gmail.com"
mail = Mail(app)

@app.post("/reset_admin_password")
def reset_admin_password():
    admin = load_admin_data()

    msg = Message(
        subject="🔐 Admin Password Reset - BankBot",
        sender=app.config["MAIL_USERNAME"],
        recipients=[admin["email"]],
        body=f"""
Hello {admin['name']},

You requested a password reset for your Admin account.

Click the link below to reset your password:
https://your-domain.com/reset_password_page

If you didn’t request this request, please ignore this email.

Regards,
BankBot Security Team
"""
    )

    try:
        print("Sending email to:", admin["email"])
        print("Using Gmail account:", app.config["MAIL_USERNAME"])

        mail.send(msg)
        return jsonify({"message": "Password reset email sent successfully!"})
    except Exception as e:
        print("Email Error:", e)
        return jsonify({"message": "Failed to send email"}), 500

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.start()

def send_daily_report():
    with app.app_context():   # <-- REQUIRED FIX
        admin = load_admin_data()

        if admin["email_notifications"] != True:
            print("Email notifications OFF — skipping daily email.")
            return

        msg = Message(
            subject="📊 Daily Chatbot Report",
            sender=app.config["MAIL_USERNAME"],
            recipients=[admin["email"]],
            body="Here is your daily chatbot report."
        )

        try:
            mail.send(msg)
            print("Daily email sent successfully!")
        except Exception as e:
            print("Daily Email Error:", e)

scheduler.add_job(send_daily_report, "cron", hour=9, minute=30)  # 9:30 AM daily

def load_admin_data():
    with open("admin_data.json", "r") as f:
        return json.load(f)

def save_admin_data(data):
    with open("admin_data.json", "w") as f:
        json.dump(data, f, indent=4)

def insert_training_row(intent, examples_list, entities):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    examples_json = json.dumps(examples_list, ensure_ascii=False)
    date_added = datetime.now().strftime("%Y-%m-%d")
    
    cur.execute("""
        INSERT INTO training_data (intent, examples, entities, status, date_added)
        VALUES (?, ?, ?, 'pending', ?)
    """, (intent, examples_json, entities, date_added))
    
    conn.commit()
    conn.close()


def get_all_training_rows():
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    cur.execute("SELECT id, intent, examples, entities, status, date_added FROM training_data ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "intent": r[1],
            "examples": json.loads(r[2]),
            "entities": r[3] or "",
            "status": r[4],
            "date_added": r[5]
        })
    return result


def get_pending_rows():
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, intent, examples, entities, date_added 
        FROM training_data 
        WHERE status='pending'
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "intent": r[1],
            "examples": json.loads(r[2]),
            "entities": r[3] or "",
            "date_added": r[4]
        })
    return result


def mark_rows_trained(row_ids):
    if not row_ids:
        return
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in row_ids)
    cur.execute(f"UPDATE training_data SET status='trained' WHERE id IN ({placeholders})", row_ids)
    conn.commit()
    conn.close()

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

def search_faq(user_message):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    # Simple contains search (case-insensitive)
    cur.execute("""
        SELECT question, answer 
        FROM faqs
        WHERE LOWER(question) LIKE LOWER(?)
    """, (f"%{user_message}%",))

    row = cur.fetchone()
    conn.close()

    if row:
        return row[1]     # only answer

    return None

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

        role = request.form.get("role")
        print("ROLE RECEIVED:", role)   # Debug print

        # -------------------------------------------------
        # 1️⃣ ADMIN LOGIN
        # -------------------------------------------------
        if role == "admin":
            admin_email = request.form.get("admin_email")
            admin_password = request.form.get("password")

            admin_data = load_admin_data()

            if admin_email == admin_data["email"] and admin_password == admin_data["password"]:
                session["admin"] = admin_data["email"]
                return redirect(url_for("admin_dashboard"))
            else:
                return render_template("login.html", error="Incorrect admin email or password", role="admin")

        # -------------------------------------------------
        # 2️⃣ USER LOGIN (Original Milestone 3 Logic)
        # -------------------------------------------------
        account = request.form.get("account")
        password = request.form.get("password")

        conn = sqlite3.connect("bank.db")
        cur = conn.cursor()

        try:
            cur.execute("SELECT * FROM users WHERE accountNumber=? AND password=?", (account, password))
        except sqlite3.Error as e:
            return f"Database error: {e}"

        user = cur.fetchone()
        conn.close()

        if user:
            # Save ALL user session details (Your original code)
            session["user_account"] = user[1]
            session["user_balance"] = user[2]
            session["user_name"] = user[3]
            session["user_email"] = user[4]
            session["user_phone"] = user[5]
            session["user_address"] = user[6]
            session["user_dob"] = user[7]
            session["user_gender"] = user[8]
            session["user_prevTxn"] = user[9]
            session["user_txnType"] = user[10]
            session["user_lastTxnDate"] = user[11]
            session["user_lastTxnTime"] = user[12]
            session["user_receiverName"] = user[13]
            session["user_receiverAcc"] = user[14]

            return redirect(url_for("dashboard"))
        else:
            error = "Invalid account number or password."

    # DEFAULT (GET)
    return render_template("login.html", error=error, role="user")

admin_data = load_admin_data()
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("login"))

    admin_data = load_admin_data()   # ← ADD THIS

    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM query_logs")
    total_queries = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM query_logs WHERE intent != 'fallback'")
    successful = cur.fetchone()[0]

    success_rate = round((successful / total_queries) * 100, 2) if total_queries > 0 else 0

    cur.execute("SELECT COUNT(DISTINCT intent) FROM query_logs")
    total_intents = cur.fetchone()[0]

    entity_types = 12

    cur.execute("""
        SELECT query, intent, confidence, timestamp
        FROM query_logs
        ORDER BY id DESC
        LIMIT 5
    """)
    recent_queries = cur.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_queries=total_queries,
        success_rate=success_rate,
        total_intents=total_intents,
        entity_types=entity_types,
        recent_queries=recent_queries,

        # ⏬ ADD THESE
        admin_name=admin_data["name"],
        admin_email=admin_data["email"]
    )

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
    user_message = request.form.get("message", "").strip()
    sender_account = session.get("user_account")   # Logged-in user

    # check FAQ first (same as you already do)
    faq_answer = search_faq(user_message)
    if faq_answer:
        return jsonify({"response": faq_answer})

    # measure start
    start_ts = time.time()
    reply = bot(user_message, sender_account)
    end_ts = time.time()
    response_time = round(end_ts - start_ts, 3)  # seconds, 3 decimal places

    # normalize reply (your existing logic)...
    resp = ""
    intent = "unknown"
    conf = 0.60
    extra = None

    if isinstance(reply, tuple):
        if len(reply) == 4:
            resp, extra, intent, conf = reply
        elif len(reply) == 3:
            resp, intent, conf = reply
        else:
            resp = str(reply)
    else:
        resp = str(reply)
        m = re.search(r"\(([^)]+)\)\s*$", resp)
        if m:
            intent = m.group(1).strip()
            resp = re.sub(r"\s*\([^)]+\)\s*$", "", resp).strip()
        else:
            intent = "unknown"
            conf = 0.60

    # update session if extra present
    if extra is not None:
        try:
            session["user_balance"] = extra
        except Exception:
            pass

    # SAVE query + response_time
    try:
        conn = sqlite3.connect("bank.db")
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO query_logs (query, intent, confidence, timestamp, response_time)
            VALUES (?, ?, ?, datetime('now'), ?)
        """, (user_message, intent, float(conf), response_time))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Failed to write query_log:", e)

    return jsonify({"response": resp})

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

@app.route("/get_training_data")
def get_training_data():
    data = get_all_training_rows()
    return jsonify({"data": data})

@app.route("/add_training_data", methods=["POST"])
def add_training_data():
    intent = request.form.get("intent", "").strip()
    examples_raw = request.form.get("examples", "").strip()
    entities = request.form.get("entities", "").strip()

    if not intent or not examples_raw:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    examples_list = [e.strip() for e in examples_raw.split("\n") if e.strip()]

    insert_training_row(intent, examples_list, entities)

    return jsonify({"status": "success"})

@app.route("/delete_training_data/<int:row_id>", methods=["POST"])
def delete_training_data(row_id):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM training_data WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route("/train_model", methods=["POST"])
def train_model():
    import csv
    import pickle
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    pending = get_pending_rows()

    if not pending:
        return jsonify({"status": "no_pending"})

    csv_path = "banking_chatbot_dataset.csv"

    # Append pending examples to CSV
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in pending:
            for ex in row["examples"]:
                writer.writerow([ex, row["intent"]])

    # Mark database rows as trained
    ids = [str(r["id"]) for r in pending]
    mark_rows_trained(ids)

    # Retrain model
    X, y = [], []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for r in reader:
            if len(r) < 2:
                continue
            X.append(r[0])
            y.append(r[1])

    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=4000)
    Xv = vec.fit_transform(X)

    clf = LogisticRegression(max_iter=1000)
    clf.fit(Xv, y)

    # Save updated model
    with open("vectorizer.pkl", "wb") as f:
        pickle.dump(vec, f)

    with open("intent_model.pkl", "wb") as f:
        pickle.dump(clf, f)

    return jsonify({"status": "trained", "count": len(pending)})

from flask import jsonify

@app.route("/get_unanswered_queries")
def get_unanswered_queries():
    conn = None
    try:
        # <-- use your actual DB file name
        conn = sqlite3.connect("bank.db")
        cur = conn.cursor()

        cur.execute("""
            SELECT 
                query,
                intent,
                confidence,
                timestamp,
                CASE
                    WHEN confidence < 0.15 THEN 'low_confidence'
                    WHEN intent = 'fallback' THEN 'fallback'
                    WHEN intent = 'irrelevant' THEN 'irrelevant'
                END AS reason
            FROM query_logs
            WHERE confidence < 0.15
               OR intent = 'fallback'
               OR intent = 'irrelevant'
            ORDER BY timestamp DESC;
        """)

        rows = cur.fetchall()

        data = []
        for q, intent, conf, time, reason in rows:
            data.append({
                "query": q,
                "intent": intent,
                "confidence": round(conf * 100),  # convert to %
                "reason": reason,
                "time": time
            })

        return jsonify({"rows": data})

    except sqlite3.OperationalError as e:
        # helpful message in server logs and return safe JSON for frontend
        app.logger.error("DB error in get_unanswered_queries: %s", e)
        return jsonify({"error": "database error"}), 500

    finally:
        if conn:
            conn.close()

@app.route("/get_faq/<int:id>")
def get_faq(id):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()
    cur.execute("SELECT id, question, answer, category FROM faqs WHERE id=?", (id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return jsonify({"faq": {
            "id": row[0],
            "question": row[1],
            "answer": row[2],
            "category": row[3]
        }})

    return jsonify({"faq": None})

@app.route("/get_faqs")
def get_faqs():
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    cur.execute("SELECT id, question, answer, category FROM faqs ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    faqs = []
    for r in rows:
        faqs.append({
            "id": r[0],
            "question": r[1],
            "answer": r[2],
            "category": r[3]
        })

    return jsonify({"faqs": faqs})

@app.route("/update_faq", methods=["POST"])
def update_faq():
    faq_id = request.form.get("id")
    question = request.form.get("question")
    answer = request.form.get("answer")
    category = request.form.get("category")

    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    cur.execute("""
        UPDATE faqs
        SET question=?, answer=?, category=?
        WHERE id=?
    """, (question, answer, category, faq_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

@app.route("/add_faq", methods=["POST"])
def add_faq():
    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()
    category = request.form.get("category", "").strip()

    if not question or not answer or not category:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    date_added = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        INSERT INTO faqs (question, answer, category, date_added)
        VALUES (?, ?, ?, ?)
    """, (question, answer, category, date_added))

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

@app.route("/delete_faq/<int:id>", methods=["POST"])
def delete_faq(id):
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM faqs WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

@app.route("/get_analytics")
def get_analytics():
    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    # Total conversations
    cur.execute("SELECT COUNT(*) FROM query_logs")
    total = cur.fetchone()[0] or 0

    # Avg confidence overall (0-100)
    cur.execute("SELECT AVG(confidence) FROM query_logs")
    avg_conf = cur.fetchone()[0] or 0
    avg_conf_percent = round(avg_conf * 100, 2)

    # Avg response time (seconds) (ignores NULLs)
    try:
        cur.execute("SELECT AVG(response_time) FROM query_logs WHERE response_time IS NOT NULL")
        avg_resp = cur.fetchone()[0] or 0.0
        avg_resp = round(avg_resp, 3)
    except Exception:
        avg_resp = 0.0

    # User rating (if you have stored ratings elsewhere — fallback to dummy)
    user_rating = 4.5

    # Intent performance: total queries per intent and average confidence per intent -> use avg_confidence*100 as "accuracy"
    cur.execute("""
        SELECT intent, COUNT(*) AS cnt, AVG(confidence) AS avg_conf
        FROM query_logs
        WHERE intent IS NOT NULL AND intent != ''
        GROUP BY intent
        ORDER BY cnt DESC
        LIMIT 50
    """)
    intent_perf = []
    intent_labels = []
    intent_values = []
    for intent, cnt, avg_conf_int in cur.fetchall():
        avg_conf_int = avg_conf_int or 0
        accuracy_pct = round(avg_conf_int * 100, 2)
        intent_perf.append({
            "intent": intent,
            "total_queries": cnt,
            "accuracy": accuracy_pct
        })
        intent_labels.append(intent)
        intent_values.append(cnt)

    # Entity performance: if you have a table, compute it; else return whatever static fallback you had
    # Here we try to fetch if you have an entity performance table; else keep sample
    entities = [
        {"entity": "account_number", "detected": 4520, "accuracy": 98.2},
        {"entity": "amount", "detected": 3890, "accuracy": 96.5},
        {"entity": "date", "detected": 2340, "accuracy": 94.8},
    ]

    # top queries overall
    cur.execute("""
        SELECT query, COUNT(*) as cnt
        FROM query_logs
        GROUP BY query
        ORDER BY cnt DESC
        LIMIT 10
    """)
    top_queries = [{"question": q, "count": c} for q, c in cur.fetchall()]

    # daily stats for the last 30 days: avg confidence and counts (group by date)
    cur.execute("""
        SELECT DATE(timestamp) as d, COUNT(*) as cnt, AVG(confidence) as avg_conf
        FROM query_logs
        GROUP BY d
        ORDER BY d ASC
    """)
    dates = []
    volumes = []
    confs = []
    for d, cnt, avgconf in cur.fetchall():
        dates.append(d)
        volumes.append(cnt)
        confs.append(round((avgconf or 0) * 100, 2))

    conn.close()

    return jsonify({
        "total_chats": total,
        "avg_confidence": avg_conf_percent,
        "avg_response": avg_resp,
        "user_rating": user_rating,
        "intent_performance": intent_perf,
        "entities": entities,
        "top_queries": top_queries,
        # chart payloads (frontend expects intent_chart, confidence_chart, volume_chart)
        "intent_chart": {"labels": intent_labels, "values": intent_values},
        "confidence_chart": {"labels": dates, "values": confs},
        "volume_chart": {"labels": dates, "values": volumes}
    })

@app.route("/export_analytics_csv")
def export_analytics_csv():
    import csv
    from io import StringIO
    import sqlite3

    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["Intent", "Total Queries", "Accuracy (%)", "Avg Confidence (%)", "Top Query", "Top Query Count"])

    conn = sqlite3.connect("bank.db")
    cur = conn.cursor()

    # Get intents with average confidence
    cur.execute("""
        SELECT intent, COUNT(*) AS cnt, AVG(confidence) AS avg_conf
        FROM query_logs
        WHERE intent IS NOT NULL AND intent != ''
        GROUP BY intent
        ORDER BY cnt DESC
    """)
    intents = cur.fetchall()

    for intent, cnt, avg_conf in intents:
        avg_conf_pct = round((avg_conf or 0) * 100, 2)
        # use avg_conf_pct as accuracy proxy
        accuracy = avg_conf_pct

        # get top query for this intent
        cur.execute("""
            SELECT query, COUNT(*) as q_cnt
            FROM query_logs
            WHERE intent = ?
            GROUP BY query
            ORDER BY q_cnt DESC
            LIMIT 1
        """, (intent,))
        top = cur.fetchone()
        top_q = top[0] if top else ""
        top_q_count = top[1] if top else 0

        writer.writerow([intent, cnt, accuracy, avg_conf_pct, top_q, top_q_count])

    # Also append an empty row and top queries overall section (optional)
    writer.writerow([])
    writer.writerow(["Top Queries Overall", "Count"])
    cur.execute("""
        SELECT query, COUNT(*) as cnt
        FROM query_logs
        GROUP BY query
        ORDER BY cnt DESC
        LIMIT 50
    """)
    for q, c in cur.fetchall():
        writer.writerow([q, c])

    conn.close()

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics.csv"}
    )

@app.route("/update_admin_profile", methods=["POST"])
def update_admin_profile():
    data = load_admin_data()

    new_name = request.form.get("name")
    new_email = request.form.get("email")

    data["name"] = new_name
    data["email"] = new_email

    save_admin_data(data)   # 🔥 writes to admin_data.json

    return jsonify({"status": "success"})

@app.post("/update_email_notifications")
def update_email_notifications():
    data = load_admin_data()

    enabled = request.json.get("enabled", False)

    data["email_notifications"] = enabled
    save_admin_data(data)

    return jsonify({"status": "success", "enabled": enabled})

@app.get("/get_admin_data")
def get_admin_data():
    return jsonify(load_admin_data())

@app.get("/test_daily_email")
def test_daily_email():
    print("TEST EMAIL TRIGGERED")         # <-- debug
    send_daily_report()
    return "Email function executed (check terminal)"

# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)

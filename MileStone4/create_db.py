import sqlite3

conn = sqlite3.connect('bank.db')
cur = conn.cursor()

# USERS TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- BASIC ACCOUNT DETAILS
    accountNumber TEXT UNIQUE,
    currentBalance REAL,
    accountName TEXT,

    -- CONTACT INFO
    email TEXT,
    phone TEXT,
    address TEXT,

    -- PERSONAL DETAILS
    dob TEXT,
    gender TEXT,

    -- LAST TRANSACTION INFO
    prevTxn REAL,
    txnType TEXT,
    lastTxnDate TEXT,
    lastTxnTime TEXT,

    -- RECEIVER DETAILS
    receiverName TEXT,
    receiverAcc TEXT,

    -- SECURITY
    password TEXT
)
""")

# TRANSACTIONS TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_acc TEXT NOT NULL,
    receiver_acc TEXT NOT NULL,
    receiver_name TEXT NOT NULL,
    amount REAL NOT NULL,
    txn_type TEXT NOT NULL,
    txn_date TEXT NOT NULL,
    txn_time TEXT NOT NULL,
    txn_id TEXT NOT NULL
)
""")

# QUERY LOGS TABLE
cur.execute("""
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    intent TEXT,
    confidence REAL,
    timestamp TEXT
)
""")

# ⭐ TRAINING DATA TABLE (CORRECT PLACE)
cur.execute("""
CREATE TABLE IF NOT EXISTS training_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intent TEXT NOT NULL,
    examples TEXT NOT NULL,   -- JSON list of strings
    entities TEXT,            -- comma-separated
    status TEXT NOT NULL DEFAULT 'pending', -- pending or trained
    date_added TEXT NOT NULL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT NOT NULL,
    date_added TEXT NOT NULL
)
""")

conn.commit()
conn.close()

print("✅ 'users' table ensured!")
print("✅ 'transactions' table ensured!")
print("✅ 'query_logs' table ensured!")
print("✅ 'training_data' table ensured!")
print("✅ 'faqs' table ensured")
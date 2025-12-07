import sqlite3

conn = sqlite3.connect('bank.db')
cur = conn.cursor()

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


conn.commit()
conn.close()

print("✅ New database 'bank.db' created with updated users table!")

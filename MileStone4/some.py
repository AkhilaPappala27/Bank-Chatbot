import sqlite3
conn = sqlite3.connect('bank.db')
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE query_logs ADD COLUMN response_time REAL")
    conn.commit()
except Exception as e:
    print("Already added or error:", e)
conn.close()

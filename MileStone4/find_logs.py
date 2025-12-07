import sqlite3
conn = sqlite3.connect("bank.db")
cur = conn.cursor()
cur.execute("SELECT id, query, intent, confidence, timestamp FROM query_logs ORDER BY id DESC LIMIT 10")
rows = cur.fetchall()
conn.close()
print("LAST 10 rows in query_logs:")
for r in rows:
    print(r)

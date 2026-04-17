import sqlite3
conn = sqlite3.connect('database/pets.db')
cur = conn.cursor()
cur.execute('SELECT category, COUNT(*) FROM pets GROUP BY category')
rows = cur.fetchall()
print('DB stats:', rows)
cur.execute('SELECT name, category FROM pets LIMIT 10')
print('Sample:', cur.fetchall())
conn.close()

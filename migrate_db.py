import sqlite3

conn = sqlite3.connect('classroom.db')
cursor = conn.cursor()

# Check existing columns
cursor.execute('PRAGMA table_info(timetable_entries)')
cols = [row[1] for row in cursor.fetchall()]
print('Existing columns:', cols)

# Add missing columns if not present
if 'class_type' not in cols:
    cursor.execute("ALTER TABLE timetable_entries ADD COLUMN class_type VARCHAR(20) DEFAULT 'regular'")
    print('Added: class_type')
else:
    print('Already exists: class_type')

if 'is_public' not in cols:
    cursor.execute('ALTER TABLE timetable_entries ADD COLUMN is_public BOOLEAN DEFAULT 0')
    print('Added: is_public')
else:
    print('Already exists: is_public')

if 'join_code' not in cols:
    cursor.execute('ALTER TABLE timetable_entries ADD COLUMN join_code VARCHAR(10)')
    print('Added: join_code')
else:
    print('Already exists: join_code')

conn.commit()
conn.close()
print('\nMigration complete! Restart your Flask app now.')

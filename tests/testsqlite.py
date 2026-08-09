import sqlite3
import toga

# File paths
db_file = toga.App.app.paths.data / "Liveability.db"

# Standard query joining address and route
debug_sql = """
SELECT 
    a.id AS address_id,
    r.address_id AS route_address_fk,
    r.mode AS route_mode,
    r.service_id AS route_service_fk
FROM address AS a
LEFT JOIN route AS r ON a.id = r.address_id;
"""

sql_conditional = """
SELECT 
    a.id AS address_id,
    a.title,
    a.subtitle, 
    COUNT(r.id) AS total_routes,
    SUM(CASE WHEN r.mode = 0 THEN 1 ELSE 0 END) AS walking_count,
    SUM(CASE WHEN r.id IS NOT NULL AND r.mode IS NULL THEN 1 ELSE 0 END) AS error_count
FROM address AS a
LEFT JOIN route AS r ON a.id = r.address_id
GROUP BY a.id;
"""

try:
    with sqlite3.connect(db_file) as conn:
        # Enable dictionary access for row columns
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Inspect Table Schemas (verifies foreign key column names)
        print("--- Table Schema Check ---")
        for table in ["address", "route"]:
            print(f"Schema for '{table}':")
            for col in cursor.execute(f"PRAGMA table_info({table});").fetchall():
                print(f"  Col ID: {col['cid']} | Name: {col['name']} | Type: {col['type']}")
        print("-" * 30)

        # 2. Execute Debug Join Query
        print("\n--- Executing Direct LEFT JOIN ---")
        rows = cursor.execute(sql_conditional).fetchall()

        if not rows:
            print("No rows returned from address table.")
        else:
            for row in rows:
                print(f"Address ID: {row['address_id']} | Subtitle: {row['subtitle']}")
                print(f"  -> Total Routes: {row['total_routes']}")
                print(f"  -> Walking:   {row['walking_count']}")
                print(f"  -> Errors ⚠️:  {row['error_count']}")
                print("-" * 40)

except sqlite3.Error as e:
    print(f"An error occurred: {e}")

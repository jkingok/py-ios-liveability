import sqlite3

DB_FILE = "liveability_cache.db"

def get_cached_amenities(addressstring):
    """Fetches cached metrics from local SQLite or returns clean seed data."""
    # Seed Data Fallback Matrix
    default_records = [
        {"name": "Aldi Supermarket", "category": "Grocery", "distance": "320m", "time": "4 min", "score": "Excellent", "color": "#2ec4b6"},
        {"name": "Pyrmont Point Park", "category": "Park/Recreation", "distance": "650m", "time": "8 min", "score": "Excellent", "color": "#2ec4b6"},
        {"name": "Quarry St Café", "category": "Dining", "distance": "180m", "time": "2 min", "score": "Excellent", "color": "#2ec4b6"}
    ]
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                target TEXT, name TEXT, category TEXT, distance TEXT, time TEXT, score TEXT, color TEXT
            )
        """)
        conn.commit()
        
        # Query for records matching our target property
        cursor.execute("SELECT name, category, distance, time, score, color FROM cache WHERE target=?", (addressstring,))
        rows = cursor.fetchall()
        
        if not rows:
            return default_records
            
        return [{"name": r[0], "category": r[1], "distance": r[2], "time": r[3], "score": r[4], "color": r[5]} for r in rows]
    except Exception:
        return default_records

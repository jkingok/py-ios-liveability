import sqlite3
import toga

# File paths
db_file = toga.App.app.paths.data / input("File name?")
#dump_file = "dump.sql"

try:
    # Connect to the SQLite database
    with sqlite3.connect(db_file) as conn:
        # Iteratively write SQL dump commands line by line
        for line in conn.iterdump():
            print(line)

    print(f"Successfully dumped '{db_file}'.")

except sqlite3.Error as e:
    print(f"An error occurred: {e}")

# scripts/reset_db.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db.database import reports_col, incidents_col, links_col

def reset():
    print("Resetting database...\n")

    reports_col.delete_many({})
    incidents_col.delete_many({})
    links_col.delete_many({})

    print("Database cleared successfully.")


if __name__ == "__main__":
    reset()
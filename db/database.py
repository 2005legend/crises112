from pymongo import MongoClient
from config import MONGO_URI, DB_NAME


# Create client with timeout (prevents hanging)
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)

# Force connection check (CRITICAL)
try:
    client.server_info()
    print("MongoDB connected successfully")
except Exception as e:
    print("MongoDB connection failed:", e)
    raise e


# Select database
db = client[DB_NAME]


# Collections
reports_col = db["reports"]
incidents_col = db["incidents"]
links_col = db["incident_reports"]
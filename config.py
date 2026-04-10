import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "emergency_db")

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001/ai/fuse-report")
GEO_SERVICE_URL = os.getenv("GEO_SERVICE_URL", "http://localhost:8002/assign")
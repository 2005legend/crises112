import datetime
import uuid
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import contextmanager

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class Incident(Base):
    """
    Hackathon DB representation of incidents for the Geo Service to run standalone.
    In prod, this could point to the shared Postgres DB or be fetched from the Backend API.
    """
    __tablename__ = 'incidents'
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    summary = Column(Text, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    severity_label = Column(String, default="Low")
    report_count = Column(Integer, default=1)
    # Storing area name for frontend cluster queries
    area_name = Column(String, nullable=True)

class GeocodeCache(Base):
    """Caches direct geocoding by normalized text (R3-1.5)"""
    __tablename__ = 'geocode_cache'
    id = Column(String, primary_key=True, default=generate_uuid)
    query = Column(String, unique=True, index=True) # Normalized string
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    resolved_name = Column(String, nullable=True)
    landmarks = Column(String, nullable=True)  # R3-1: bonus landmark extraction

class ReverseGeocodeCache(Base):
    """Caches reverse geocoding by rounded lat/lon to 3 decimal places (R3-5.3)"""
    __tablename__ = 'reverse_geocode_cache'
    id = Column(String, primary_key=True, default=generate_uuid)
    lat_rounded = Column(Float, index=True)
    lon_rounded = Column(Float, index=True)
    area_name = Column(String, nullable=True)
    district = Column(String, nullable=True)
    city = Column(String, nullable=True)

# Database setup
DATABASE_URL = "sqlite:///./hackathon_geo.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

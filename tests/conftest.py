"""
conftest.py — shared pytest fixtures for geo-service tests.
"""
import datetime
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from models import Base, Incident


@pytest.fixture
def db_session():
    """In-memory SQLite session, isolated per test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_incidents(db_session):
    """Insert a handful of Incident rows into the in-memory DB."""
    rows = [
        Incident(
            id=str(uuid.uuid4()),
            summary="Road accident near Anna Flyover",
            lat=13.0878,
            lon=80.2185,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
            severity_label="High",
            report_count=3,
            area_name="Anna Nagar",
        ),
        Incident(
            id=str(uuid.uuid4()),
            summary="Fire at T. Nagar market",
            lat=13.0418,
            lon=80.2341,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
            severity_label="Critical",
            report_count=5,
            area_name="T. Nagar",
        ),
        Incident(
            id=str(uuid.uuid4()),
            summary="Flooding in Adyar river area",
            lat=13.0012,
            lon=80.2565,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
            severity_label="High",
            report_count=6,
            area_name="Adyar",
        ),
    ]
    for row in rows:
        db_session.add(row)
    db_session.commit()
    return rows

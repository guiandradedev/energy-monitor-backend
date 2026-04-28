from sqlalchemy import create_engine, text
import os

def create_db_engine():
    """Create a SQLAlchemy engine using environment variables"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return create_engine(db_url)

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine
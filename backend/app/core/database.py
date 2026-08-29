import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

Base = declarative_base()

def create_db_engine():
    # 1. Try PostgreSQL / TimescaleDB
    try:
        pg_engine = create_engine(
            settings.SQLALCHEMY_DATABASE_URI,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=10,
            connect_args={"connect_timeout": 2}
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return pg_engine
    except Exception:
        pass

    # 2. Resilient SQLite fallback (ensures zero-downtime offline functionality)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    db_dir = os.path.join(base_dir, "data")
    os.makedirs(db_dir, exist_ok=True)
    sqlite_path = os.path.join(db_dir, "skyguard_local.db")
    sqlite_uri = f"sqlite:///{sqlite_path}"
    return create_engine(sqlite_uri, connect_args={"check_same_thread": False})

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for obtaining a SQLAlchemy session per request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

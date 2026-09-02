import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

Base = declarative_base()

def create_db_engine():
    # 1. Try PostgreSQL / TimescaleDB / Supabase
    try:
        pg_engine = create_engine(
            settings.SQLALCHEMY_DATABASE_URI,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=5,
            connect_args={"connect_timeout": 10}
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return pg_engine
    except Exception as e:
        print(f"[Database] PostgreSQL connection note: {e}. Using fallback...")

    # 2. Resilient SQLite fallback (ensures zero-downtime offline functionality)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    db_dir = os.path.join(base_dir, "data")
    os.makedirs(db_dir, exist_ok=True)
    sqlite_path = os.path.join(db_dir, "skyguard_local.db")
    sqlite_uri = f"sqlite:///{sqlite_path}"
    fallback_engine = create_engine(sqlite_uri, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=fallback_engine)
    return fallback_engine

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for obtaining a SQLAlchemy session per request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..core.config import settings

connect_args = {}
ssl_config = {}


def _is_valid_file(path: str) -> bool:
    return bool(path and os.path.isfile(path) and os.path.getsize(path) > 10)


# ── SSL certificate wiring (identical pattern to tanuh_bcd_website) ───────────
if settings.MYSQL_SSL_CA and _is_valid_file(settings.MYSQL_SSL_CA):
    ssl_config["ca"] = settings.MYSQL_SSL_CA
if settings.MYSQL_SSL_CERT and _is_valid_file(settings.MYSQL_SSL_CERT):
    ssl_config["cert"] = settings.MYSQL_SSL_CERT
if settings.MYSQL_SSL_KEY and _is_valid_file(settings.MYSQL_SSL_KEY):
    ssl_config["key"] = settings.MYSQL_SSL_KEY

# PyMySQL requires an ssl dict (even empty) to initiate SSL on Cloud SQL
connect_args["ssl"] = ssl_config

if ssl_config:
    # Disable hostname verification when connecting via public IP
    ssl_config["check_hostname"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,         # auto-reconnect on stale connections
    pool_recycle=1800,          # recycle connections every 30 min
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import os
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

#DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db") has to be changed for writing
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/returns.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    poolclass=StaticPool,
    echo=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

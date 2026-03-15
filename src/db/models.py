import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Float
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pegaso:pegaso_pass@db/pegaso_db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(String(16), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    persona = Column(String(16), default="work")
    created_at = Column(DateTime, default=datetime.utcnow)


class IndexedFile(Base):
    __tablename__ = "indexed_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(512), unique=True, nullable=False)
    file_hash = Column(String(64), nullable=False)
    chunks_count = Column(Integer, default=0)
    indexed_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Crea las tablas si no existen."""
    Base.metadata.create_all(bind=engine)

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'alerts.db')
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    tf = Column(String)
    side = Column(String)
    score = Column(Integer)
    entry = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    session = Column(String)
    htf_mid = Column(Float)
    regime = Column(Integer)
    choch_up = Column(Integer)
    choch_down = Column(Integer)
    bos_up = Column(Integer)
    bos_down = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

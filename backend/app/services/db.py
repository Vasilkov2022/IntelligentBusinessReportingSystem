import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from app.config import DATABASE_URL
from app.models.report import Base

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Инициализация таблицы при старте
def init_db(retries=5, delay=2):
    for i in range(retries):
        try:
            Base.metadata.create_all(engine)
            break
        except OperationalError:
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise
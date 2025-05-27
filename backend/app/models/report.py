from sqlalchemy import Column, Integer, Text, TIMESTAMP, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Report(Base):
    __tablename__ = 'reports'

    id          = Column(Integer, primary_key=True, index=True)
    filename    = Column(Text, nullable=False)
    upload_time = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status      = Column(Text, default='uploaded')
    analysis    = Column(Text)
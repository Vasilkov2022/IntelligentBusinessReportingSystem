from sqlalchemy import Column, Integer, Text, Numeric, Date, TIMESTAMP, ForeignKey, func
from .base import Base

class KPI(Base):
    __tablename__ = 'kpi'

    id         = Column(Integer, primary_key=True, index=True)
    report_id  = Column(Integer, ForeignKey('reports.id', ondelete='CASCADE'), nullable=False)
    name       = Column(Text, nullable=False)
    value      = Column(Numeric)
    period     = Column(Date)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
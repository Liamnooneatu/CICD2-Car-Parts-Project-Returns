from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()

class Return(Base):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String, default="created")



"""
ORM models.

Day 1 only needs one table: `orders`. It mirrors the real Online Retail II
dataset columns (see docs/DATASET.md) plus a couple of bookkeeping columns
that our own pipeline adds (is_cancelled, created_at).

We deliberately do NOT add extra tables (customers, products, quality_events,
etc.) yet. Those come later, once we actually need them.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Boolean,
    Text,
    func,
)

from database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    # Original dataset fields (see docs/DATASET.md for column mapping)
    invoice_no = Column(String(20), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)
    description = Column(Text, nullable=True)
    quantity = Column(Integer, nullable=False)
    invoice_date = Column(DateTime, nullable=False, index=True)
    unit_price = Column(Numeric(10, 2), nullable=False)
    customer_id = Column(Integer, nullable=True, index=True)
    country = Column(String(100), nullable=True)

    # Derived / pipeline fields
    is_cancelled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Order invoice={self.invoice_no} stock={self.stock_code}>"

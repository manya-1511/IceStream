"""Declarative base for all ORM models. Import all models here so Alembic
autogenerate can discover them (populated starting Day 2+)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Future model imports go here, e.g.:
# from app.models.order import Order  # noqa: F401

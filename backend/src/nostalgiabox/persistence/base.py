"""Declarative metadata shared by future approved persistence mappings."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for SQLAlchemy mappings; intentionally has no Task 2.1 tables."""

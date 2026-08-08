"""Declarative metadata shared by NostalgiaBox persistence mappings."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for SQLAlchemy mappings owned by the core persistence layer."""

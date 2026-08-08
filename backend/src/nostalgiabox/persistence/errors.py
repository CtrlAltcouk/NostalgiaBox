"""Controlled persistence-layer failures."""


class PersistenceError(Exception):
    """Base class for persistence failures exposed outside ORM internals."""


class PersistenceConversionError(PersistenceError):
    """Persisted data cannot be reconstructed as an approved domain value."""


class UnknownContentKindError(PersistenceConversionError):
    """A stored content-kind value is unknown to the current domain."""


class InvalidStoredMediaError(PersistenceConversionError):
    """Stored media metadata or its location is invalid."""


class RecordNotFoundError(PersistenceError):
    """A required persistent record or timeline does not exist."""


class SeedError(PersistenceError):
    """A proof seed operation cannot be completed safely."""


class SeedConflictError(SeedError):
    """Seed identity conflicts with existing persistent state."""


class SeedSchemaMissingError(SeedError):
    """The target database has not been migrated to the required schema."""

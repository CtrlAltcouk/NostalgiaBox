"""Short SQLAlchemy transaction boundary for scan application services."""

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaSourceRepository
from nostalgiabox.persistence.scan_repositories import (
    SqlAlchemyMediaInventoryRepository,
    SqlAlchemyScanIssueRepository,
    SqlAlchemyScanRunRepository,
)


class SqlAlchemyScanUnitOfWork:
    """Open one short scan session and commit only at application-owned boundaries."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.runs: SqlAlchemyScanRunRepository
        self.inventory: SqlAlchemyMediaInventoryRepository
        self.issues: SqlAlchemyScanIssueRepository
        self.sources: SqlAlchemyMediaSourceRepository

    def __enter__(self) -> "SqlAlchemyScanUnitOfWork":
        self._session = self._session_factory()
        self.runs = SqlAlchemyScanRunRepository(self._session)
        self.inventory = SqlAlchemyMediaInventoryRepository(self._session)
        self.issues = SqlAlchemyScanIssueRepository(self._session)
        self.sources = SqlAlchemyMediaSourceRepository(self._session)
        return self

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("scan unit of work is not active")
        self._session.commit()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        if exc_type is not None:
            self._session.rollback()
        self._session.close()
        self._session = None

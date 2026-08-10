"""SQLAlchemy transaction boundary for source application services."""

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaSourceRepository


class SqlAlchemySourceUnitOfWork:
    """Open one short session and commit only when the service requests it."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.repository: SqlAlchemyMediaSourceRepository

    def __enter__(self) -> "SqlAlchemySourceUnitOfWork":
        self._session = self._session_factory()
        self.repository = SqlAlchemyMediaSourceRepository(self._session)
        return self

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("source unit of work is not active")
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

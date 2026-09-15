"""Short SQLAlchemy transaction boundary for probe coordination."""

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.persistence.probe_repositories import SqlAlchemyProbeRepository


class SqlAlchemyProbeUnitOfWork:
    """A short session; process execution is deliberately outside this boundary."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self.probes: SqlAlchemyProbeRepository

    def __enter__(self) -> "SqlAlchemyProbeUnitOfWork":
        self._session = self._session_factory()
        self.probes = SqlAlchemyProbeRepository(self._session)
        return self

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("probe unit of work is not active")
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

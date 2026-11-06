from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.db.session import get_session


@pytest.mark.parametrize("failure", [False, True])
def test_session_dependency_lifecycle(failure, monkeypatch):
    session = Session()
    close = Mock(wraps=session.close)
    rollback = Mock(wraps=session.rollback)
    monkeypatch.setattr(session, "close", close)
    monkeypatch.setattr(session, "rollback", rollback)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(database=SimpleNamespace(session_factory=lambda: session))
        )
    )
    dependency = get_session(request)
    assert next(dependency) is session
    if failure:
        with pytest.raises(RuntimeError, match="test failure"):
            dependency.throw(RuntimeError("test failure"))
        rollback.assert_called_once()
    else:
        dependency.close()
    close.assert_called_once()

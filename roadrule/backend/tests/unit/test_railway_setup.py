from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import setup_railway_production as setup


def connection_with(relations, identity=("railway", "postgres", "180001"), tls_status=(True,)):
    connection = Mock()
    connection.execute.side_effect = [
        SimpleNamespace(fetchone=lambda: identity),
        SimpleNamespace(fetchone=lambda: tls_status),
        SimpleNamespace(fetchall=lambda: relations),
    ]
    return connection


def test_inspect_empty_database_is_read_only():
    connection = connection_with([])
    setup.inspect(connection, Mock(), "migration_role")
    assert all(call.args[0].startswith("SELECT ") for call in connection.execute.call_args_list)


@pytest.mark.parametrize("tls_status", [None, (False,), (None,)])
def test_inspect_requires_tls_before_reading_schema(tls_status):
    connection = connection_with([], tls_status=tls_status)
    with pytest.raises(setup.SetupError, match="Verified TLS is required"):
        setup.inspect(connection, Mock(), "migration_role")
    assert connection.execute.call_count == 2
    assert "pg_catalog.pg_stat_ssl" in connection.execute.call_args.args[0]


def test_inspect_refuses_wrong_target_before_querying_tls():
    connection = connection_with([], identity=("other", "postgres", "180001"))
    with pytest.raises(setup.SetupError, match="identity or version"):
        setup.inspect(connection, Mock(), "migration_role")
    assert connection.execute.call_count == 1


def test_inspect_refuses_untracked_schema():
    connection = connection_with([("legacy_table", "postgres", "r")])
    with pytest.raises(setup.SetupError, match="without Alembic history"):
        setup.inspect(connection, Mock(), "migration_role")


def test_existing_managed_role_is_never_rotated(monkeypatch):
    connection = Mock()
    monkeypatch.setattr(
        setup,
        "role_state",
        lambda *_: (True, False, False, False, False, False, False, setup.MARKER, False),
    )
    setup.ensure_role(connection, "runtime_role", "existing-password")
    connection.execute.assert_not_called()
    connection.pgconn.encrypt_password.assert_not_called()


def test_unmanaged_role_is_refused(monkeypatch):
    connection = Mock()
    monkeypatch.setattr(setup, "role_state", lambda *_: (True, True))
    with pytest.raises(setup.SetupError, match="unmanaged"):
        setup.ensure_role(connection, "runtime_role", "existing-password")
    connection.execute.assert_not_called()


def test_apply_declined_stops_before_writes(monkeypatch, tmp_path):
    ca = tmp_path / "root.pem"
    ca.touch()
    monkeypatch.setattr(setup.ssl, "create_default_context", Mock())
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        setup.sys,
        "argv",
        [
            "setup",
            "--ca",
            str(ca),
            "--runtime",
            "runtime_role",
            "--migrator",
            "migration_role",
            "--apply",
            "--api-host",
            "api.example.com",
            "--frontend-origin",
            "https://frontend.example.com",
        ],
    )
    monkeypatch.setattr(setup, "getpass", lambda _: "test-only")
    monkeypatch.setattr("builtins.input", lambda _: "decline")
    connection = Mock()
    manager = Mock()
    manager.__enter__ = Mock(return_value=connection)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(setup, "connect", lambda *_: manager)
    monkeypatch.setattr(setup, "inspect", Mock())
    monkeypatch.setattr(setup, "role_state", lambda *_: None)
    with pytest.raises(setup.SetupError, match="Approval"):
        setup.main()
    connection.execute.assert_not_called()
    connection.transaction.assert_not_called()


def test_operator_connection_requires_verified_hostname(monkeypatch, tmp_path):
    connect = Mock()
    monkeypatch.setattr(setup.psycopg, "connect", connect)
    ca = tmp_path / "root.pem"
    setup.connect("runtime_role", "local-fixture", ca)
    arguments = connect.call_args.kwargs
    assert arguments["host"] == "postgres.railway.internal"
    assert arguments["sslmode"] == "verify-full"
    assert arguments["sslrootcert"] == str(ca)
    assert arguments["gssencmode"] == "disable"


def test_password_prompt_refuses_echo_fallback(monkeypatch):
    import warnings

    def fallback(_prompt):
        warnings.warn("unavailable", setup.GetPassWarning, stacklevel=2)
        pytest.fail("Password input must stop before reading unmasked input")

    monkeypatch.setattr(setup, "getpass", fallback)
    with pytest.raises(setup.SetupError, match="masked password"):
        setup.read_password("Password: ")

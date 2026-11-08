from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import setup_railway_production as setup


def connection_with(relations, identity=("railway", "postgres", "180001"), tls=True):
    connection = Mock()
    connection.info.ssl_in_use = tls
    connection.execute.side_effect = [
        SimpleNamespace(fetchone=lambda: identity),
        SimpleNamespace(fetchall=lambda: relations),
    ]
    return connection


def test_inspect_empty_database_is_read_only():
    connection = connection_with([])
    setup.inspect(connection, Mock(), "migration_role")
    assert all(call.args[0].startswith("SELECT ") for call in connection.execute.call_args_list)


@pytest.mark.parametrize(
    "relations,identity,tls",
    [
        ([("legacy_table", "postgres", "r")], ("railway", "postgres", "180001"), True),
        ([], ("other", "postgres", "180001"), True),
        ([], ("railway", "postgres", "180001"), False),
    ],
)
def test_inspect_refuses_unknown_existing_data_or_wrong_target(relations, identity, tls):
    with pytest.raises(setup.SetupError):
        setup.inspect(connection_with(relations, identity, tls), Mock(), "migration_role")


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

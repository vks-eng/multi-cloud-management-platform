"""Provision a PostgreSQL database for the test-suite (PostgreSQL only, never SQLite).

Resolution order:
1. ``TEST_DATABASE_URL`` - use an existing server (CI uses a postgres service container).
2. ``pgserver`` package - embedded throwaway Postgres (wheels for CPython <= 3.12).
3. ``PG_BIN_DIR`` - directory containing ``initdb``/``pg_ctl``; a throwaway cluster is
   created in a temp dir on a free port and removed afterwards.
"""

from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path


class PostgresUnavailable(RuntimeError):
    pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _from_pg_bin_dir(bin_dir: Path) -> str:
    exe = ".exe" if os.name == "nt" else ""
    initdb, pg_ctl = bin_dir / f"initdb{exe}", bin_dir / f"pg_ctl{exe}"
    if not initdb.exists() or not pg_ctl.exists():
        raise PostgresUnavailable(f"initdb/pg_ctl not found in PG_BIN_DIR={bin_dir}")
    # psycopg's pure-python implementation locates libpq on PATH.
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    data_dir = Path(tempfile.mkdtemp(prefix="mcmp-test-pg-"))
    port = _free_port()
    subprocess.run(
        [str(initdb), "-D", str(data_dir), "-U", "postgres", "-A", "trust", "-E", "UTF8"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            str(pg_ctl),
            "-D",
            str(data_dir),
            "-o",
            f"-p {port} -h 127.0.0.1 -F",
            "-l",
            str(data_dir / "server.log"),
            "-w",
            "start",
        ],
        # The postmaster inherits pg_ctl's handles: never pipe them, or this call blocks forever.
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def _stop() -> None:
        subprocess.run(
            [str(pg_ctl), "-D", str(data_dir), "-m", "immediate", "-w", "stop"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        shutil.rmtree(data_dir, ignore_errors=True)

    atexit.register(_stop)
    return f"postgresql+psycopg://postgres@127.0.0.1:{port}/postgres"


def _from_pgserver() -> str:
    import pgserver  # type: ignore[import-not-found]

    data_dir = tempfile.mkdtemp(prefix="mcmp-pgserver-")
    server = pgserver.get_server(data_dir, cleanup_mode="delete")
    uri: str = server.get_uri()
    return uri.replace("postgresql://", "postgresql+psycopg://", 1)


def resolve_test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    try:
        return _from_pgserver()
    except ImportError:
        pass
    bin_dir = os.environ.get("PG_BIN_DIR")
    if bin_dir:
        return _from_pg_bin_dir(Path(bin_dir))
    raise PostgresUnavailable(
        "No PostgreSQL available for tests. Set TEST_DATABASE_URL, install 'pgserver' "
        "(Python <= 3.12) or set PG_BIN_DIR to a directory containing initdb/pg_ctl."
    )

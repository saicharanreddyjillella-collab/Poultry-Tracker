"""E9 — automated backups: run the real deploy/*.sh scripts against real
PostgreSQL databases (docker swapped for direct pg_dump/psql via the scripts'
override hooks). Skipped when no PostgreSQL server or client tools are present.
"""
import gzip
import json
import os
import shutil
import subprocess
import tarfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"
PG_URL = os.environ.get("BACKUP_TEST_PG_URL") or os.environ.get("DATABASE_URL", "")

SCHEMA = """
CREATE TABLE django_migrations (id serial primary key, app text);
CREATE TABLE auth_user (id serial primary key, username text);
CREATE TABLE core_farm (id serial primary key, name text);
CREATE TABLE core_flock (id serial primary key, farm_id int);
CREATE TABLE core_bill (id serial primary key, flock_id int, net_payable numeric(12,2));
CREATE TABLE core_dailyentry (id serial primary key, flock_id int);
CREATE TABLE core_sale (id serial primary key, flock_id int);
INSERT INTO django_migrations (app) VALUES ('core'), ('auth');
INSERT INTO auth_user (username) VALUES ('admin');
INSERT INTO core_farm (name) VALUES ('Lakshmi Farm'), ('Venkat Farm');
INSERT INTO core_flock (farm_id) VALUES (1);
INSERT INTO core_bill (flock_id, net_payable) VALUES (1, 39055.20);
"""


def _tools_ok():
    return all(shutil.which(t) for t in ("pg_dump", "psql", "flock", "sha256sum", "gzip", "bash"))


def _with_db(url, name):
    p = urlparse(url)
    return urlunparse(p._replace(path="/" + name))


def _psql(url, sql):
    return subprocess.run(["psql", url, "-v", "ON_ERROR_STOP=1", "-Atqc", sql],
                          check=True, capture_output=True, text=True).stdout.strip()


pytestmark = pytest.mark.skipif(
    not PG_URL.startswith(("postgres://", "postgresql://")) or not _tools_ok(),
    reason="needs a PostgreSQL server (DATABASE_URL/BACKUP_TEST_PG_URL) and pg client tools",
)


@pytest.fixture
def pg():
    """Create scratch databases on the server; drop them afterwards."""
    try:
        server_major = int(_psql(PG_URL, "show server_version_num")) // 10000
    except Exception:
        pytest.skip("PostgreSQL not reachable")
    client = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True).stdout
    client_major = int(client.split()[-1].split(".")[0])
    if client_major != server_major:
        # Production always dumps/restores with the db container's own tools;
        # mixing majors (e.g. pg_dump 18 → server 16) isn't a supported restore.
        pytest.skip(f"pg_dump {client_major} vs server {server_major}: install matching client tools")
    made = []

    def make(prefix, schema=SCHEMA):
        name = f"bk_{prefix}_{uuid.uuid4().hex[:8]}"
        _psql(PG_URL, f"CREATE DATABASE {name}")
        made.append(name)
        url = _with_db(PG_URL, name)
        if schema:
            _psql(url, schema)
        return url

    yield make
    for name in made:
        subprocess.run(["psql", PG_URL, "-qc", f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"],
                       capture_output=True)


@pytest.fixture
def box(tmp_path):
    """Isolated backup dir, media folder, and fake curl/rclone that log calls."""
    (tmp_path / "media/documents/farm_1").mkdir(parents=True)
    (tmp_path / "media/documents/farm_1/agreement.pdf").write_bytes(b"%PDF-1.4 farmer agreement")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("curl", "rclone"):
        f = bin_dir / tool
        f.write_text(f'#!/bin/bash\necho "$@" >> "{tmp_path}/{tool}.log"\n'
                     f'[[ -n "${{FAKE_{tool.upper()}_FAIL:-}}" && "$1" == "copy" ]] && exit 1\nexit 0\n')
        f.chmod(0o755)
    return tmp_path


def _env(box, src_url, **extra):
    env = dict(os.environ)
    env.update({
        "PATH": f"{box / 'bin'}:{env['PATH']}",
        "BACKUP_CONFIG": "/nonexistent",
        "BACKUP_DIR": str(box / "backups"),
        "PG_DUMP_CMD": f"pg_dump {src_url}",
        "PSQL_CMD": f"psql {src_url}",
        "MEDIA_TAR_CMD": f"tar -C {box} -cf - media",
        "MEDIA_RESTORE_CMD": f"sh -c 'mkdir -p {box}/media && find {box}/media -mindepth 1 -delete && tar -C {box} -xf -'",
        "STOP_CMD": f"echo stop >> {box}/backend.log",
        "START_CMD": f"echo start >> {box}/backend.log",
        "BACKUP_REMOTE": "",
        "BACKUP_PING_URL": "",
    })
    env.update({k: str(v) for k, v in extra.items()})
    return env


def run(script, env, *args):
    return subprocess.run(["bash", str(DEPLOY / script), *args], env=env,
                          capture_output=True, text=True, timeout=120)


def backups(box, prefix="poultrytrack_"):
    return sorted((box / "backups").glob(f"{prefix}*.gz"))


def status(box, name="last_backup.json"):
    return json.loads((box / "backups" / name).read_text())


# ── backup.sh ──────────────────────────────────────────────────────────────
class TestBackup:
    def test_creates_verified_db_and_media_backups(self, pg, box):
        src = pg("src")
        r = run("backup.sh", _env(box, src))
        assert r.returncode == 0, r.stdout + r.stderr

        [db] = backups(box)
        [media] = backups(box, "media_")
        bdir = box / "backups"
        assert subprocess.run(["sha256sum", "-c", db.name + ".sha256"], cwd=bdir).returncode == 0
        assert subprocess.run(["sha256sum", "-c", media.name + ".sha256"], cwd=bdir).returncode == 0
        sql = gzip.decompress(db.read_bytes()).decode()
        assert "PostgreSQL database dump complete" in sql
        assert "DROP TABLE IF EXISTS public.core_farm" in sql     # restorable over live data
        with tarfile.open(media) as t:
            assert "media/documents/farm_1/agreement.pdf" in t.getnames()
        assert not list(bdir.glob("*.partial"))
        assert oct(bdir.stat().st_mode & 0o777) == "0o700"
        st = status(box)
        assert st["status"] == "ok" and st["db_file"] == db.name and st["media_file"] == media.name
        assert st["offsite"] == "skipped" and st["db_bytes"] > 0
        assert "on this server only" in r.stdout                  # nudges toward off-box copy

    def test_media_can_be_disabled(self, pg, box):
        r = run("backup.sh", _env(box, pg("src"), BACKUP_MEDIA=0))
        assert r.returncode == 0
        assert backups(box) and not backups(box, "media_")

    def test_dump_failure_fails_cleanly_and_alerts(self, pg, box):
        env = _env(box, pg("src"), PG_DUMP_CMD="false", BACKUP_PING_URL="https://hc.example/abc")
        r = run("backup.sh", env)
        assert r.returncode == 1
        assert "pg_dump failed" in r.stdout
        assert not list((box / "backups").glob("*.gz")) and not list((box / "backups").glob("*.partial"))
        assert status(box)["status"] == "failed"
        assert (box / "curl.log").read_text().split()[-1] == "https://hc.example/abc/fail"

    def test_incomplete_dump_is_rejected(self, pg, box):
        # '#' swallows the args the script appends; output lacks pg_dump's completion marker
        env = _env(box, pg("src"), PG_DUMP_CMD="printf 'SELECT 1;\\n' #")
        r = run("backup.sh", env)
        assert r.returncode == 1 and "incomplete" in r.stdout
        assert not backups(box)

    def test_success_pings_monitor(self, pg, box):
        r = run("backup.sh", _env(box, pg("src"), BACKUP_PING_URL="https://hc.example/abc"))
        assert r.returncode == 0
        assert (box / "curl.log").read_text().split()[-1] == "https://hc.example/abc"

    def test_retention_prunes_old_but_keeps_min_keep(self, pg, box):
        bdir = box / "backups"
        bdir.mkdir()
        old = []
        for day in range(1, 7):                                   # 6 backups, 60 days old
            f = bdir / f"poultrytrack_2020-01-0{day}_02-30-00.sql.gz"
            f.write_bytes(gzip.compress(b"old"))
            (bdir / (f.name + ".sha256")).write_text("x")
            t = time.time() - 60 * 86400
            os.utime(f, (t, t))
            old.append(f)
        r = run("backup.sh", _env(box, pg("src"), MIN_KEEP=3, RETENTION_DAYS=30))
        assert r.returncode == 0, r.stdout
        left = backups(box)
        assert len(left) == 3                                     # new + 2 newest old
        assert old[-1] in left and old[-2] in left and old[0] not in left
        assert not (bdir / (old[0].name + ".sha256")).exists()    # checksum pruned with it

    def test_retention_never_drops_below_min_keep(self, pg, box):
        bdir = box / "backups"
        bdir.mkdir()
        for day in range(1, 4):
            f = bdir / f"poultrytrack_2020-01-0{day}_02-30-00.sql.gz"
            f.write_bytes(gzip.compress(b"old"))
            os.utime(f, (0, 0))
        assert run("backup.sh", _env(box, pg("src"), MIN_KEEP=10)).returncode == 0
        assert len(backups(box)) == 4

    def test_offsite_copy_with_rclone(self, pg, box):
        r = run("backup.sh", _env(box, pg("src"), BACKUP_REMOTE="fake:bk", REMOTE_RETENTION_DAYS=45))
        assert r.returncode == 0, r.stdout + r.stderr
        calls = (box / "rclone.log").read_text().splitlines()
        copies = [c for c in calls if c.startswith("copy ")]
        assert len(copies) == 4 and all(c.endswith(" fake:bk/") for c in copies)
        assert any(".sql.gz.sha256" in c for c in copies) and any("media_" in c for c in copies)
        assert "delete --min-age 45d fake:bk/" in calls
        assert status(box)["offsite"] == "ok"

    def test_offsite_failure_fails_but_keeps_local_copy(self, pg, box):
        env = _env(box, pg("src"), BACKUP_REMOTE="fake:bk", FAKE_RCLONE_FAIL=1)
        r = run("backup.sh", env)
        assert r.returncode == 1 and "off-box copy" in r.stdout
        assert backups(box)                                       # local backup survives
        assert status(box)["status"] == "failed"

    def test_concurrent_run_is_refused(self, pg, box):
        (box / "backups").mkdir()
        holder = subprocess.Popen(["flock", str(box / "backups/.backup.lock"), "sleep", "10"])
        try:
            time.sleep(0.5)
            r = run("backup.sh", _env(box, pg("src")))
            assert r.returncode == 1 and "already running" in r.stdout
        finally:
            holder.kill()


# ── restore.sh ─────────────────────────────────────────────────────────────
class TestRestore:
    def test_round_trip_restores_db_and_documents(self, pg, box):
        src = pg("src")
        env = _env(box, src)
        assert run("backup.sh", env).returncode == 0

        # disaster: data and documents changed after the backup
        _psql(src, "DELETE FROM core_bill; INSERT INTO core_farm (name) VALUES ('junk')")
        (box / "media/documents/farm_1/agreement.pdf").unlink()
        (box / "media/junk.txt").write_text("junk")

        r = run("restore.sh", env, "latest", "--yes")
        assert r.returncode == 0, r.stdout + r.stderr
        assert _psql(src, "SELECT string_agg(name, ',' ORDER BY id) FROM core_farm") == "Lakshmi Farm,Venkat Farm"
        assert _psql(src, "SELECT net_payable FROM core_bill") == "39055.20"
        assert (box / "media/documents/farm_1/agreement.pdf").read_bytes() == b"%PDF-1.4 farmer agreement"
        assert not (box / "media/junk.txt").exists()
        assert list((box / "backups").glob("pre_restore_*.sql.gz"))   # safety copy taken
        assert (box / "backend.log").read_text().split() == ["stop", "start"]

    def test_database_only(self, pg, box):
        src = pg("src")
        env = _env(box, src)
        run("backup.sh", env)
        (box / "media/new.txt").write_text("keep me")
        assert run("restore.sh", env, "latest", "--yes", "--no-media").returncode == 0
        assert (box / "media/new.txt").exists()

    def test_tampered_backup_is_refused_before_touching_anything(self, pg, box):
        src = pg("src")
        env = _env(box, src)
        run("backup.sh", env)
        _psql(src, "INSERT INTO core_farm (name) VALUES ('after-backup')")
        [db] = backups(box)
        db.write_bytes(db.read_bytes() + b"tamper")
        r = run("restore.sh", env, str(db), "--yes")
        assert r.returncode == 1 and "Checksum mismatch" in r.stdout
        assert _psql(src, "SELECT count(*) FROM core_farm") == "3"     # untouched
        assert not (box / "backend.log").exists()                       # backend never stopped

    def test_failed_restore_rolls_back_and_restarts_backend(self, pg, box):
        src = pg("src")
        env = _env(box, src)
        bad = box / "backups/poultrytrack_2026-01-01_00-00-00.sql.gz"
        bad.parent.mkdir(parents=True)
        bad.write_bytes(gzip.compress(b"DELETE FROM core_farm;\nSELECT * FROM no_such_table;\n"))
        r = run("restore.sh", env, str(bad), "--yes", "--no-media")
        assert r.returncode == 1 and "rolled back" in r.stdout
        assert _psql(src, "SELECT count(*) FROM core_farm") == "2"     # single transaction
        assert (box / "backend.log").read_text().split() == ["stop", "start"]

    def test_requires_confirmation(self, pg, box):
        src = pg("src")
        env = _env(box, src)
        run("backup.sh", env)
        _psql(src, "INSERT INTO core_farm (name) VALUES ('x')")
        r = subprocess.run(["bash", str(DEPLOY / "restore.sh"), "latest"], env=env, input="no\n",
                           capture_output=True, text=True, timeout=60)
        assert "Cancelled" in r.stdout
        assert _psql(src, "SELECT count(*) FROM core_farm") == "3"


# ── verify-backup.sh ───────────────────────────────────────────────────────
class TestVerify:
    def test_latest_backup_restores_into_scratch_db(self, pg, box):
        env = _env(box, pg("src"))
        run("backup.sh", env)
        scratch = pg("scratch", schema=None)
        r = run("verify-backup.sh", {**env, "VERIFY_DB_URL": scratch}, "latest")
        assert r.returncode == 0, r.stdout + r.stderr
        st = status(box, "last_verify.json")
        assert st["status"] == "ok" and "farm=2" in st["message"] and "bill=1" in st["message"]

    def test_corrupt_backup_fails(self, pg, box):
        env = _env(box, pg("src"), BACKUP_VERIFY_PING_URL="https://hc.example/v")
        bad = box / "backups/poultrytrack_2026-01-01_00-00-00.sql.gz"
        bad.parent.mkdir(parents=True)
        bad.write_bytes(gzip.compress(b"SELECT 1;")[:-6])
        r = run("verify-backup.sh", {**env, "VERIFY_DB_URL": pg("scratch", schema=None)}, str(bad))
        assert r.returncode == 1 and "corrupt" in r.stdout
        assert status(box, "last_verify.json")["status"] == "failed"
        assert (box / "curl.log").read_text().split()[-1] == "https://hc.example/v/fail"

    def test_non_app_database_fails(self, pg, box):
        other = pg("other", schema="CREATE TABLE t (id int); INSERT INTO t VALUES (1);")
        env = _env(box, other, BACKUP_MEDIA=0)
        run("backup.sh", env)
        r = run("verify-backup.sh", {**env, "VERIFY_DB_URL": pg("scratch", schema=None)})
        assert r.returncode == 1 and "django_migrations" in r.stdout

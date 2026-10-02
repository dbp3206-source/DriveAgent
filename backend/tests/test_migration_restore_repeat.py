import sqlite3
import sys
from types import SimpleNamespace

from scripts import check_migration_restore, state_archive
from scripts.state_archive import backup_state


def test_migration_restore_can_be_verified_twice_without_overwriting(tmp_path, monkeypatch):
    folder = tmp_path / '.local-backups' / 'migration-20260930'
    folder.mkdir(parents=True)
    source = tmp_path / 'source'
    source.mkdir()
    with sqlite3.connect(source / 'drive_agent.db') as db:
        db.execute('CREATE TABLE sentinel (value TEXT)')
        db.execute("INSERT INTO sentinel VALUES ('synthetic-acceptance')")
    archive = folder / 'state-pre-migration-20261002T120000Z.vrd'
    secret = 'synthetic-backup-test-passphrase'
    backup_state(source, archive, secret, port=None)
    monkeypatch.setattr(check_migration_restore, 'ROOT', tmp_path)
    monkeypatch.setattr('app.core.config.get_settings', lambda: SimpleNamespace(app_secret=secret))
    monkeypatch.setitem(sys.modules, 'state_archive', state_archive)
    first = check_migration_restore.run(archive)
    second = check_migration_restore.run(archive)
    assert first['restore_verified'] and second['restore_verified']
    assert first['isolated_directory'] != second['isolated_directory']
    for result in (first, second):
        with sqlite3.connect(result['isolated_directory'] + '/drive_agent.db') as db:
            assert db.execute('SELECT value FROM sentinel').fetchone()[0] == 'synthetic-acceptance'

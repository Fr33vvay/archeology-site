"""Isolated backup/cron integration checks; never contact Docker, mail or cloud."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="backup-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "site"
        (self.root / "scripts").mkdir(parents=True)
        for name in ("backup.sh", "setup-backup-cron.sh", "backup-config.sh"):
            if (SCRIPTS / name).exists():
                shutil.copy2(SCRIPTS / name, self.root / "scripts" / name)
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.calls = Path(self.temp.name) / "calls"
        self.cron = Path(self.temp.name) / "crontab"
        self.env = os.environ.copy()
        for key in list(self.env):
            if key.startswith("BACKUP_") or key in ("POSTGRES_USER", "POSTGRES_DB"):
                del self.env[key]
        self.env.update(
            HOME=self.temp.name,
            PATH=f"{self.bin}:{self.env['PATH']}",
            CALLS=str(self.calls),
            CRON_FILE=str(self.cron),
        )
        self.stub("crontab", '''
import os, pathlib, sys
p = pathlib.Path(os.environ["CRON_FILE"])
if sys.argv[1] == "-l":
    if not p.exists():
        print("no crontab for test", file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(p.read_text())
else:
    p.write_text(sys.stdin.read())
''')
        for command in ("docker", "rclone"):
            self.stub(command, '''
import os, pathlib, sys
with open(os.environ["CALLS"], "a") as f:
    f.write(pathlib.Path(sys.argv[0]).name + " called\\n")
sys.exit(90)
''')

    def stub(self, name, code):
        path = self.bin / name
        path.write_text("#!/usr/bin/env python3\n" + code)
        path.chmod(0o755)

    def config(self, enabled="0", schedule="monthly", extra=""):
        (self.root / ".env").write_text(
            f"BACKUP_ENABLED={enabled}\nBACKUP_SCHEDULE={schedule}\n{extra}"
        )

    def run_script(self, name):
        return subprocess.run(
            ["bash", str(self.root / "scripts" / name)],
            env=self.env, text=True, capture_output=True, timeout=15,
        )

    def test_disabled_backup_is_successful_without_work_or_alert(self):
        self.config(extra="UNRELATED_SECRET=$(touch should-not-exist)\n")
        result = self.run_script("backup.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("BACKUP_ENABLED=0", result.stdout)
        self.assertFalse(self.calls.exists(), result.stdout)
        self.assertFalse((self.root / "backups").exists())
        self.assertNotIn("ОШИБКА", result.stdout + result.stderr)
        self.assertFalse((self.root / "should-not-exist").exists())

    def test_monthly_cron_is_idempotent_and_preserves_other_jobs(self):
        self.config("1", extra="BACKUP_LOG='/tmp/backup log'\n")
        unrelated = "0 5 * * * /other/site/scripts/backup.sh\n30 * * * * check-disk\n"
        legacy = f"15 4 */2 * * cd {self.root} && /bin/bash {self.root}/scripts/backup.sh\n"
        self.cron.write_text(unrelated + legacy + legacy)
        for _ in range(2):
            result = self.run_script("setup-backup-cron.sh")
            self.assertEqual(result.returncode, 0, result.stderr)
        actual = self.cron.read_text()
        self.assertTrue(actual.startswith(unrelated), actual)
        self.assertEqual(actual.count(str(self.root / "scripts/backup.sh")), 1)
        self.assertIn("15 4 1 * *", actual)
        self.assertIn("/tmp/backup\\ log", actual)
        self.config("0")
        self.assertEqual(self.run_script("setup-backup-cron.sh").returncode, 0)
        self.assertEqual(self.cron.read_text(), unrelated)

    def test_invalid_settings_do_not_replace_crontab(self):
        for enabled, schedule in (("maybe", "monthly"), ("1", "hourly")):
            self.config(enabled, schedule)
            self.cron.write_text("30 * * * * check-disk\n")
            result = self.run_script("setup-backup-cron.sh")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.cron.read_text(), "30 * * * * check-disk\n")

    def test_enabled_backup_uploads_archive_and_preserves_previous(self):
        self.config("1", extra="POSTGRES_USER=custom\nPOSTGRES_DB=customdb\n")
        archives = self.root / "backups"
        archives.mkdir()
        previous = archives / "backup-20000101-000000.tar.gz"
        previous.write_bytes(b"previous archive")
        self.stub("docker", '''
import pathlib, sys, tarfile
if "exec" in sys.argv:
    assert sys.argv[-3:] == ["-U", "custom", "customdb"], sys.argv
    print("-- database dump")
else:
    mount = sys.argv[sys.argv.index("-v") + 1].removesuffix(":/backup")
    with tarfile.open(pathlib.Path(mount) / "media.tar.gz", "w:gz"):
        pass
''')
        self.stub("rclone", '''
import os, pathlib, sys, tarfile
if sys.argv[1] == "listremotes":
    print("yadisk:")
elif sys.argv[1] == "copy":
    with tarfile.open(sys.argv[2]) as archive:
        assert archive.getnames() == ["db.sql", "media.tar.gz"]
    pathlib.Path(os.environ["CALLS"]).write_text("upload " + sys.argv[2])
''')
        result = self.run_script("backup.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(previous.read_bytes(), b"previous archive")
        self.assertEqual(len(list(archives.glob("backup-*.tar.gz"))), 2)
        self.assertTrue(self.calls.read_text().startswith("upload "))

    def test_environment_override_can_disable_backup(self):
        self.config("1")
        self.env["BACKUP_ENABLED"] = "0"
        result = self.run_script("backup.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()

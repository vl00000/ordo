"""Backup: surət işləyən bazanın son vəziyyətini tam saxlayır, bərpa yoxlaması pozuntunu tutur."""
import json
import os
import sqlite3

import pytest

from ordo import backup
from ordo.backup import BackupError
from ordo.keys import KeyStore
from ordo.sectors import setup_b2b_sales
from ordo.store import Store


@pytest.fixture
def live(tmp_path):
    """İşləyən server kimi: Store və KeyStore açıqdır, data WAL-dadır."""
    path = str(tmp_path / "ordo.db")
    s = Store(db_path=path)
    setup_b2b_sales(s)
    keys = KeyStore(path)
    keys.create("A", "user1", "writer")
    c = s.add_object("A", "user1", "Company", {"name": "X", "ad_count": 1})
    lead = s.add_object("A", "user1", "Lead", {"contact": "x"})
    s.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)
    s.update_object("A", "user1", c.id, expected_version=1, props={"ad_count": 2})
    yield path, s, c
    keys.close()
    s.close()


def test_snapshot_aciq_bazanin_son_yazilarini_saxlayir(live, tmp_path):
    path, s, c = live
    dst = str(tmp_path / "snap.db")
    found = backup.snapshot(path, dst)
    assert found["objects"] == 2 and found["relations"] == 1 and found["api_keys"] == 1
    assert found["object_history"] == 1 and found["audit"] == 4
    assert not os.path.exists(dst + "-wal")

    restored = Store(db_path=dst)
    assert restored.get_object("A", c.id).props == {"name": "X", "ad_count": 2}
    assert KeyStore(dst).list()[0][1:4] == ("A", "user1", "writer")
    restored.close()


def test_verify_snapshot_saylari_ile_kecir(live, tmp_path):
    path, _, _ = live
    dst = str(tmp_path / "snap.db")
    expected = backup.snapshot(path, dst)
    assert backup.verify(dst, expected) == expected


def test_verify_say_uygunsuzlugunu_tutur(live, tmp_path):
    path, _, _ = live
    dst = str(tmp_path / "snap.db")
    expected = backup.snapshot(path, dst)
    with pytest.raises(BackupError, match="uyğun deyil"):
        backup.verify(dst, {**expected, "objects": expected["objects"] + 1})


def test_verify_pozulmus_fayli_tutur(live, tmp_path):
    path, _, _ = live
    dst = str(tmp_path / "snap.db")
    backup.snapshot(path, dst)
    with open(dst, "r+b") as f:
        f.seek(4096)
        f.write(b"\xff" * 4096)
    with pytest.raises(BackupError):
        backup.verify(dst)


def test_verify_ordo_bazasi_olmayan_fayli_redd_edir(tmp_path):
    other = str(tmp_path / "other.db")
    sqlite3.connect(other).execute("CREATE TABLE x (a)").connection.commit()
    with pytest.raises(BackupError, match="Cədvəl yoxdur"):
        backup.verify(other)
    not_db = tmp_path / "text.db"
    not_db.write_bytes(b"bu baza deyil" * 100)
    with pytest.raises(BackupError):
        backup.verify(str(not_db))
    with pytest.raises(BackupError, match="Fayl yoxdur"):
        backup.verify(str(tmp_path / "yoxdur.db"))


def test_verify_ordo_yuklemesindeki_xetani_tutur(live, tmp_path):
    path, _, _ = live
    dst = str(tmp_path / "snap.db")
    backup.snapshot(path, dst)
    conn = sqlite3.connect(dst)
    conn.execute("UPDATE objects SET props = 'json deyil'")
    conn.commit()
    conn.close()
    with pytest.raises(BackupError, match="yükləyə bilmədi"):
        backup.verify(dst)


def test_snapshot_kohne_sureti_evez_edir(live, tmp_path):
    path, s, _ = live
    dst = str(tmp_path / "snap.db")
    backup.snapshot(path, dst)
    s.add_object("A", "user1", "Company", {"name": "Y"})
    assert backup.snapshot(path, dst)["objects"] == 3


def test_cli_snapshot_ve_verify(live, tmp_path, capsys):
    path, _, _ = live
    dst = str(tmp_path / "snap.db")
    assert backup.main(["snapshot", path, dst]) == 0
    printed = capsys.readouterr().out
    assert backup.main(["verify", dst, "--expect", printed]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(printed)
    assert backup.main(["verify", dst, "--expect", '{"objects": 99}']) == 1
    assert backup.main(["verify", dst, "--expect", "json deyil"]) == 1


def test_verify_cedvel_yerine_view_olan_fayli_redd_edir(live, tmp_path):
    # Hücum: sertifikat açıqdır, kimsə "objects" adlı view ilə saxta backup hazırlayır
    path, _, _ = live
    dst = str(tmp_path / "snap.db")
    backup.snapshot(path, dst)
    conn = sqlite3.connect(dst)
    conn.executescript("DROP TABLE objects; CREATE VIEW objects AS SELECT * FROM audit;")
    conn.close()
    with pytest.raises(BackupError, match="Cədvəl yoxdur: objects"):
        backup.verify(dst)

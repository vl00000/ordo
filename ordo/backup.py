"""Backup və bərpa yoxlaması.

snapshot: işləyən bazanın SQLite backup API ilə ardıcıl surəti (WAL-da olan son yazılar da daxil;
sadə fayl surəti WAL-ı buraxa bilər). Surət tək fayldır (journal_mode=DELETE), şifrələmək üçün hazırdır.
verify: surətin tam olduğunu yoxlayır — integrity_check, cədvəllərdəki sətir sayları gözlənilənlə
eynidir və ORDO-nun özü (Store + KeyStore) bazanı xətasız yükləyib eyni sayda qeyd görür.

İstifadə (Ordo qovluğunda və ya konteynerdə):
  python -m ordo.backup snapshot /data/ordo.db /data/.backup-snapshot.db   → sayları JSON kimi çap edir
  python -m ordo.backup verify /yol/ordo.db --expect '{"objects": 3, ...}'
verify bazaya yazır (Store açılanda sxemi yoxlayır), ona görə yalnız surət üzərində işlədilməlidir.
"""
import argparse
import json
import os
import sqlite3
import sys

from .keys import KeyStore
from .store import Store

TABLES = ("object_types", "relation_types", "objects", "object_history", "relations", "audit",
          "api_keys")


class BackupError(Exception):
    pass


def counts(path):
    """Bazanın tamlığını yoxlayır və hər cədvəldəki sətir sayını qaytarır."""
    if not os.path.isfile(path):
        raise BackupError(f"Fayl yoxdur: {path}")
    # mode=ro: yoxlama faylı dəyişməsin
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        # Fayl şifrəni bilən istənilən kəs tərəfindən hazırlana bilər (sertifikat açıqdır):
        # sxemdəki trigger/view-lar heç bir funksiyanı işlədə bilməsin
        conn.execute("PRAGMA trusted_schema=OFF")
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise BackupError(f"integrity_check: {result}")
        present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [t for t in TABLES if t not in present]
        if missing:
            raise BackupError(f"Cədvəl yoxdur: {', '.join(missing)}")
        # Cədvəl adları yalnız sabit TABLES siyahısından gəlir, kənar data SQL-ə düşmür
        return {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
    except sqlite3.DatabaseError as e:
        raise BackupError(f"Baza oxunmur: {e}") from None
    finally:
        conn.close()


def snapshot(src, dst):
    """src-in ardıcıl surətini dst-yə yazır (dst varsa, əvəz olunur) və sayları qaytarır."""
    if not os.path.isfile(src):
        raise BackupError(f"Fayl yoxdur: {src}")
    for suffix in ("", "-wal", "-shm", "-journal"):
        if os.path.exists(dst + suffix):
            os.remove(dst + suffix)
    source = sqlite3.connect(src)
    target = sqlite3.connect(dst)
    try:
        source.backup(target)
        # Surət tək fayl olsun: yanında -wal qalmasın
        target.execute("PRAGMA journal_mode=DELETE")
    finally:
        target.close()
        source.close()
    return counts(dst)


def verify(path, expected=None):
    """Surəti ORDO-nun özü ilə açır. Uyğunsuzluq olsa BackupError, əks halda sayları qaytarır."""
    found = counts(path)
    if expected is not None and found != expected:
        raise BackupError(f"Saylar uyğun deyil: gözlənilən {expected}, tapılan {found}")
    try:
        store = Store(db_path=path)
        keys = KeyStore(path)
    except Exception as e:
        raise BackupError(f"ORDO bazanı yükləyə bilmədi: {type(e).__name__}: {e}") from None
    try:
        loaded = {
            "object_types": len(store._object_types),
            "relation_types": len(store._relation_types),
            "objects": len(store._objects),
            "object_history": sum(len(v) for v in store._history.values()),
            "relations": len(store._relations),
            "audit": len(store._audit),
            "api_keys": len(keys.list()),
        }
    finally:
        keys.close()
        store.close()
    if loaded != found:
        raise BackupError(f"ORDO-nun yüklədiyi saylar fərqlidir: {loaded}, cədvəllərdə {found}")
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description="ORDO backup və bərpa yoxlaması")
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("src")
    snap.add_argument("dst")
    ver = sub.add_parser("verify")
    ver.add_argument("path")
    ver.add_argument("--expect", help="snapshot-un çap etdiyi JSON")
    args = parser.parse_args(argv)

    try:
        if args.command == "snapshot":
            result = snapshot(args.src, args.dst)
        else:
            expected = json.loads(args.expect) if args.expect else None
            result = verify(args.path, expected)
    except (BackupError, json.JSONDecodeError) as e:
        print(f"XƏTA: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

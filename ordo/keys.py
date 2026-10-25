"""API açarları: hər açar bir tenant-a, bir actor-a və bir rola bağlıdır.

Açarın özü heç yerdə saxlanmır, yalnız SHA-256 həşi. Açar yaradılanda yalnız bir dəfə göstərilir.
Açarlar 256 bitlik təsadüfi mətndir, ona görə yavaş həş (bcrypt) lazım deyil.

İstifadə (Ordo qovluğunda):
  python -m ordo.keys create --tenant A --actor user1 --role writer
  python -m ordo.keys list
  python -m ordo.keys revoke 3
Baza yolu: --db və ya ORDO_DB mühit dəyişəni (standart: ordo.db).
Açarın müddəti: yaradılandan ORDO_KEY_MAX_DAYS gün (standart 90, 1-365). Müddət bitəndə
yeni açar yarat və köhnəsini ləğv et. Oğurlanmış açar ən çox bu müddət qədər işləyir.
"""
import argparse
import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .store import _check_actor, _check_tenant

ROLES = ("reader", "writer")
PREFIX = "ordo_"
DEFAULT_MAX_DAYS = 90


def _max_days(value=None):
    raw = value if value is not None else os.environ.get("ORDO_KEY_MAX_DAYS", DEFAULT_MAX_DAYS)
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = DEFAULT_MAX_DAYS
    # Müddətsiz açar olmasın: ən çox bir il
    return min(max(days, 1), 365)


@dataclass(frozen=True)
class Principal:
    """Açarı yoxlanmış çağıran: tenant və actor yalnız buradan gəlir."""
    key_id: int
    tenant_id: str
    actor: str
    role: str


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


class KeyStore:
    def __init__(self, path, max_days=None):
        self.max_age = timedelta(days=_max_days(max_days))
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._conn:
            self._conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT, key_hash TEXT NOT NULL UNIQUE,
                tenant_id TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
                created_at TEXT NOT NULL, revoked_at TEXT)""")

    def close(self):
        self._conn.close()

    def create(self, tenant_id, actor, role):
        """Yeni açar yaradır. (id, açar) qaytarır; açarı yalnız indi görmək olar."""
        _check_tenant(tenant_id)
        actor = _check_actor(actor)
        if role not in ROLES:
            raise ValueError(f"role must be one of: {', '.join(ROLES)}")
        key = PREFIX + secrets.token_urlsafe(32)
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO api_keys (key_hash, tenant_id, actor, role, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (_hash(key), tenant_id, actor, role, datetime.now(timezone.utc).isoformat()))
        return cur.lastrowid, key

    def authenticate(self, key):
        """Etibarlı və ləğv olunmamış açar üçün Principal, əks halda None."""
        if not isinstance(key, str) or not key.startswith(PREFIX) or len(key) > 200:
            return None
        row = self._conn.execute(
            "SELECT id, tenant_id, actor, role, created_at FROM api_keys "
            "WHERE key_hash = ? AND revoked_at IS NULL", (_hash(key),)).fetchone()
        if row is None or self.is_expired(row[4]):
            return None
        return Principal(*row[:4])

    def expires_at(self, created_at):
        return datetime.fromisoformat(created_at) + self.max_age

    def is_expired(self, created_at, now=None):
        # Tarixi oxunmayan açar etibarsız sayılır (fail-closed)
        try:
            return (now or datetime.now(timezone.utc)) >= self.expires_at(created_at)
        except (TypeError, ValueError):
            return True

    def revoke(self, key_id):
        with self._conn:
            cur = self._conn.execute(
                "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (datetime.now(timezone.utc).isoformat(), key_id))
        return cur.rowcount == 1

    def list(self):
        # Həşlər qaytarılmır: siyahı ekrana çıxanda da açarla bağlı heç nə sızmasın
        return self._conn.execute(
            "SELECT id, tenant_id, actor, role, created_at, revoked_at FROM api_keys ORDER BY id"
        ).fetchall()


def main(argv=None):
    parser = argparse.ArgumentParser(description="ORDO API açarları")
    parser.add_argument("--db", default=os.environ.get("ORDO_DB", "ordo.db"))
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--tenant", required=True)
    create.add_argument("--actor", required=True)
    create.add_argument("--role", choices=ROLES, required=True)
    sub.add_parser("list")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("key_id", type=int)
    args = parser.parse_args(argv)

    keys = KeyStore(args.db)
    try:
        if args.command == "create":
            key_id, key = keys.create(args.tenant, args.actor, args.role)
            print(f"Açar #{key_id} yaradıldı ({args.tenant} / {args.actor} / {args.role}).")
            print(f"Müddəti: {keys.max_age.days} gün. Açar yalnız indi göstərilir, təhlükəsiz yerdə saxla:")
            print(key)
        elif args.command == "list":
            for row in keys.list():
                if row[5]:
                    state = "ləğv edilib"
                elif keys.is_expired(row[4]):
                    state = "müddəti bitib"
                else:
                    state = f"aktiv, bitir: {keys.expires_at(row[4]):%Y-%m-%d}"
                print(f"#{row[0]}  tenant={row[1]}  actor={row[2]}  role={row[3]}  {state}")
        elif args.command == "revoke":
            print("Ləğv edildi." if keys.revoke(args.key_id) else "Belə aktiv açar yoxdur.")
    finally:
        keys.close()


if __name__ == "__main__":
    main()

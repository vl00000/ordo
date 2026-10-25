"""SQLite saxlama qatı: Store-un vəziyyətini diskdə saxlayır və açılışda geri yükləyir.

Hər Store əməliyyatı bir tranzaksiyadır: dəyişiklik və onun audit qeydi ya birlikdə yazılır, ya heç biri.
Bütün sorğular parametrlidir (?), data heç vaxt SQL mətninə birləşdirilmir.
"""
import json
import sqlite3
from datetime import datetime

from .store import ALLOWED_TYPES, AuditEvent, Object, ObjectType, Relation, RelationType

SCHEMA = """
CREATE TABLE IF NOT EXISTS object_types (
    name TEXT PRIMARY KEY, required TEXT NOT NULL, types TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS relation_types (
    name TEXT PRIMARY KEY, source_type TEXT NOT NULL, target_type TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS objects (
    id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, type TEXT NOT NULL, props TEXT NOT NULL,
    status TEXT NOT NULL, source TEXT, version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS object_history (
    object_id INTEGER NOT NULL, version INTEGER NOT NULL, tenant_id TEXT NOT NULL,
    type TEXT NOT NULL, props TEXT NOT NULL, status TEXT NOT NULL, source TEXT,
    PRIMARY KEY (object_id, version));
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, type TEXT NOT NULL,
    source_id INTEGER NOT NULL, target_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
    seq INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
    target TEXT NOT NULL, at TEXT NOT NULL, details TEXT NOT NULL);
"""


def _object_row(o):
    return (o.id, o.tenant_id, o.type, json.dumps(o.props), o.status, o.source, o.version)


class SQLiteBackend:
    def __init__(self, path):
        # check_same_thread=False: API sorğuları fərqli thread-lərdən gəlir;
        # eyni anda yalnız bir sorğunun Store-a toxunmasını api.py-dəki kilid təmin edir
        self._conn = sqlite3.connect(path, check_same_thread=False)
        # WAL: proses yazarkən qəfil dayansa, baza yarımçıq qalmır
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    def close(self):
        self._conn.close()

    def write(self, object_types=(), relation_types=(), objects=(), history=(),
              relations=(), audit=()):
        # "with" bloku: hamısı uğurlu olsa commit, biri xəta versə rollback
        with self._conn:
            self._conn.executemany(
                "INSERT INTO object_types VALUES (?, ?, ?)",
                [(t.name, json.dumps(list(t.required)),
                  json.dumps({f: [x.__name__ for x in ts] for f, ts in t.types.items()}))
                 for t in object_types])
            self._conn.executemany(
                "INSERT INTO relation_types VALUES (?, ?, ?)",
                [(t.name, t.source_type, t.target_type) for t in relation_types])
            self._conn.executemany(
                "INSERT INTO object_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(o.id, o.version, o.tenant_id, o.type, json.dumps(o.props), o.status, o.source)
                 for o in history])
            self._conn.executemany(
                "INSERT OR REPLACE INTO objects VALUES (?, ?, ?, ?, ?, ?, ?)",
                [_object_row(o) for o in objects])
            self._conn.executemany(
                "INSERT INTO relations VALUES (?, ?, ?, ?, ?)",
                [(r.id, r.tenant_id, r.type, r.source_id, r.target_id) for r in relations])
            self._conn.executemany(
                "INSERT INTO audit VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(e.seq, e.tenant_id, e.actor, e.action, e.target, e.at.isoformat(),
                  json.dumps(list(e.details))) for e in audit])

    def load_into(self, store):
        q = self._conn.execute
        for name, required, types in q("SELECT name, required, types FROM object_types"):
            store._object_types[name] = ObjectType(
                name, tuple(json.loads(required)),
                {f: tuple(ALLOWED_TYPES[x] for x in ts) for f, ts in json.loads(types).items()})
        for name, source_type, target_type in q("SELECT * FROM relation_types"):
            store._relation_types[name] = RelationType(name, source_type, target_type)
        for row in q("SELECT * FROM objects"):
            store._objects[row[0]] = _load_object(row)
        for object_id, version, tenant_id, type_, props, status, source in q(
                "SELECT * FROM object_history ORDER BY object_id, version"):
            store._history.setdefault(object_id, []).append(
                Object(object_id, tenant_id, type_, json.loads(props), status, source, version))
        for row in q("SELECT * FROM relations"):
            store._relations[row[0]] = Relation(*row)
        for seq, tenant_id, actor, action, target, at, details in q(
                "SELECT * FROM audit ORDER BY seq"):
            store._audit.append(AuditEvent(seq, tenant_id, actor, action, target,
                                           datetime.fromisoformat(at), tuple(json.loads(details))))
        # Obyektlər və əlaqələr ortaq id sayğacından istifadə edir: köhnə id təkrar verilməsin
        store._next_id = max([0, *store._objects, *store._relations]) + 1


def _load_object(row):
    id_, tenant_id, type_, props, status, source, version = row
    return Object(id_, tenant_id, type_, json.loads(props), status, source, version)

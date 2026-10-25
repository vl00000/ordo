"""ORDO v0.1 — generic ontology nüvəsi.

Company, Lead kimi biznes tipləri kodda sinif deyil, qeydiyyatdan keçən ObjectType-lardır.
Yeni sektor = yeni tiplər, yeni kod yox (bax: sectors.py).
Obyektin id-si dəyişmir; hər dəyişiklik yeni versiyadır, köhnəsi tarixçədə qalır.
Store(db_path=None) yalnız yaddaşda işləyir; Store(db_path="ordo.db") hər dəyişikliyi SQLite-a yazır
və növbəti açılışda oradan yükləyir (bax: db.py).
"""
import json
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

# SCOUT-dan gələn məlumat həmişə fakt deyil: hər obyekt öz statusunu daşıyır
STATUSES = ("fact", "claim", "hypothesis")

# Sahə tipləri yalnız JSON-a yazılıb eyni şəkildə geri oxuna bilən tiplər ola bilər
ALLOWED_TYPES = {t.__name__: t for t in (str, int, float, bool, list, dict)}


class TenantError(Exception):
    """Tenant etibarsızdır və ya obyekt bu tenant-a aid deyil."""


class SchemaError(Exception):
    """Obyekt və ya əlaqə qeydiyyatdakı tipə uyğun deyil."""


class ConflictError(Exception):
    """Obyekt oxunandan sonra başqası tərəfindən dəyişdirilib: expected_version köhnədir."""


@dataclass(frozen=True)
class ObjectType:
    name: str
    required: tuple = ()
    types: dict = field(default_factory=dict)  # sahə adı -> icazəli Python tipləri


@dataclass(frozen=True)
class RelationType:
    name: str
    source_type: str
    target_type: str


@dataclass(frozen=True)
class Object:
    id: int
    tenant_id: str
    type: str
    props: dict
    status: str = "fact"
    source: str | None = None
    version: int = 1


@dataclass(frozen=True)
class Relation:
    id: int
    tenant_id: str
    type: str
    source_id: int
    target_id: int


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    tenant_id: str
    actor: str
    action: str
    target: str
    at: datetime
    details: tuple = ()  # dəyişən sahələrin adları; dəyərlər yazılmır ki, audit şəxsi data sızdırmasın


def _check_tenant(tenant_id):
    # Boş və ya str olmayan tenant qəbul olunmur, yoxsa "tenant-sız" çağırışlar ortaq tenant yaradar
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise TenantError("Invalid tenant")


def _check_actor(actor):
    # Audit "kim etdi?" sualına cavab verməlidir, ona görə anonim dəyişiklik yoxdur
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("Invalid actor")
    # " user1" və "user1" auditdə iki fərqli adam kimi görünməsin
    return actor.strip()


def _check_name(name, what):
    if not isinstance(name, str) or not name.strip():
        raise SchemaError(f"{what} name cannot be empty")


def _check_meta(status, source):
    if status not in STATUSES:
        raise SchemaError(f"Invalid status: {status}")
    if source is not None and not isinstance(source, str):
        raise SchemaError("source must be a string")


def _is_blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _validate(object_type, props):
    if not isinstance(props, dict):
        raise SchemaError("props must be a dict")
    # Diskə yazılıb geri oxunanda eyni qalmayan data (tuple, set, rəqəm açar, NaN) qəbul olunmur
    try:
        round_trip = json.loads(json.dumps(props, allow_nan=False))
    except (TypeError, ValueError):
        raise SchemaError("props must contain only JSON values") from None
    if round_trip != props:
        raise SchemaError("props must contain only JSON values with string keys")
    missing = [f for f in object_type.required if _is_blank(props.get(f))]
    if missing:
        raise SchemaError(f"Missing required fields: {', '.join(missing)}")
    for name, allowed in object_type.types.items():
        value = props.get(name)
        if value is None:
            continue
        # bool Python-da int-in alt tipidir: amount=True rəqəm kimi keçməsin
        if (isinstance(value, bool) and bool not in allowed) or not isinstance(value, allowed):
            names = " or ".join(t.__name__ for t in allowed)
            raise SchemaError(f"Field {name} must be {names}")


class Store:
    def __init__(self, db_path=None):
        # Kolleksiyalar daxilidir: kənar kod yalnız metodlardan istifadə etməlidir
        self._object_types = {}
        self._relation_types = {}
        self._objects = {}
        self._history = {}  # object_id -> köhnə versiyalar (ən köhnəsi əvvəldə)
        self._relations = {}
        self._audit = []
        self._next_id = 1
        self._db = None
        if db_path is not None:
            from .db import SQLiteBackend
            self._db = SQLiteBackend(db_path)
            self._db.load_into(self)

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    # --- Sxem: bütün tenant-lar üçün ortaqdır ---

    def register_object_type(self, name, required=(), types=None):
        _check_name(name, "Object type")
        normalized = {}
        for field_name, allowed in (types or {}).items():
            allowed = allowed if isinstance(allowed, tuple) else (allowed,)
            if not allowed or not all(t in ALLOWED_TYPES.values() for t in allowed):
                raise SchemaError(f"Invalid type spec for field: {field_name}")
            normalized[field_name] = allowed
        new = ObjectType(name, tuple(required), normalized)
        existing = self._object_types.get(name)
        if existing is not None:
            # Eyni tərif təkrar qeydiyyat sayılmır (hər açılışda sectors.py yenidən işləyir);
            # fərqli tərif köhnə obyektləri sındırar: "köhnəni atmır"
            if existing == new:
                return existing
            raise SchemaError(f"Object type already exists with a different definition: {name}")
        self._persist(object_types=[new])
        self._object_types[name] = new
        return new

    def register_relation_type(self, name, source_type, target_type):
        _check_name(name, "Relation type")
        for type_name in (source_type, target_type):
            if type_name not in self._object_types:
                raise SchemaError(f"Unknown object type: {type_name}")
        new = RelationType(name, source_type, target_type)
        existing = self._relation_types.get(name)
        if existing is not None:
            if existing == new:
                return existing
            raise SchemaError(f"Relation type already exists with a different definition: {name}")
        self._persist(relation_types=[new])
        self._relation_types[name] = new
        return new

    # --- Obyektlər ---

    def add_object(self, tenant_id, actor, type_name, props, status="fact", source=None):
        _check_tenant(tenant_id)
        actor = _check_actor(actor)
        object_type = self._object_types.get(type_name)
        if object_type is None:
            raise SchemaError(f"Unknown object type: {type_name}")
        _validate(object_type, props)
        _check_meta(status, source)

        # deepcopy: çağıranın əlində qalan dict-i sonradan dəyişmək store-a təsir etməsin
        obj = Object(self._new_id(), tenant_id, type_name, deepcopy(props), status, source)
        event = self._event(tenant_id, actor, "create", f"object:{obj.id}")
        self._persist(objects=[obj], audit=[event])
        self._objects[obj.id] = obj
        self._audit.append(event)
        return _copy(obj)

    def get_object(self, tenant_id, object_id):
        _check_tenant(tenant_id)
        return _copy(self._own(tenant_id, object_id))

    def update_object(self, tenant_id, actor, object_id, expected_version,
                      props=None, status=None, source=None):
        """props verilən sahələri dəyişir (qalanları saxlanır). Yeni versiyanı qaytarır.

        expected_version: çağıranın oxuduğu versiya. Arada başqası dəyişibsə, ConflictError.
        """
        _check_tenant(tenant_id)
        actor = _check_actor(actor)
        current = self._own(tenant_id, object_id)
        # type() is int: True == 1 olduğu üçün bool versiya kimi keçməsin
        if type(expected_version) is not int:
            raise ValueError("expected_version must be an int")
        if expected_version != current.version:
            raise ConflictError(
                f"Object {object_id} is at version {current.version}, not {expected_version}"
            )
        if props is not None and not isinstance(props, dict):
            raise SchemaError("props must be a dict")

        new_props = deepcopy(current.props)
        new_props.update(deepcopy(props or {}))
        new_status = current.status if status is None else status
        new_source = current.source if source is None else source
        _validate(self._object_types[current.type], new_props)
        _check_meta(new_status, new_source)

        changed = sorted(k for k in set(new_props) | set(current.props)
                         if new_props.get(k) != current.props.get(k))
        if new_status != current.status:
            changed.append("status")
        if new_source != current.source:
            changed.append("source")
        # Heç nə dəyişmirsə, yeni versiya və audit yaranmır: təkrar idxal zərərsizdir
        if not changed:
            return _copy(current)

        updated = replace(current, props=new_props, status=new_status,
                          source=new_source, version=current.version + 1)
        event = self._event(tenant_id, actor, "update", f"object:{object_id}", tuple(changed))
        # Yeni versiya, köhnə versiyanın tarixçəyə köçməsi və audit bir tranzaksiyadır
        self._persist(objects=[updated], history=[current], audit=[event])
        self._history.setdefault(object_id, []).append(current)
        self._objects[object_id] = updated
        self._audit.append(event)
        return _copy(updated)

    def history(self, tenant_id, object_id):
        """Obyektin bütün versiyaları, ən köhnəsi əvvəldə, sonuncusu cari versiyadır."""
        _check_tenant(tenant_id)
        current = self._own(tenant_id, object_id)
        return [_copy(v) for v in self._history.get(object_id, [])] + [_copy(current)]

    def find(self, tenant_id, type_name, **match):
        """Bu tenant-da type_name tipli, props-u match-ə uyğun obyektlər."""
        _check_tenant(tenant_id)
        return [
            _copy(o) for o in self._objects.values()
            if o.tenant_id == tenant_id and o.type == type_name
            and all(o.props.get(k) == v for k, v in match.items())
        ]

    # --- Əlaqələr ---

    def add_relation(self, tenant_id, actor, type_name, source_id, target_id):
        _check_tenant(tenant_id)
        actor = _check_actor(actor)
        relation_type = self._relation_types.get(type_name)
        if relation_type is None:
            raise SchemaError(f"Unknown relation type: {type_name}")
        # Hər iki tərəf bu tenant-a aid olmalıdır: tenant-lar arası əlaqə qurula bilməz
        source = self._own(tenant_id, source_id)
        target = self._own(tenant_id, target_id)
        if source.type != relation_type.source_type or target.type != relation_type.target_type:
            raise SchemaError(
                f"{type_name} must link {relation_type.source_type} -> {relation_type.target_type}"
            )

        relation = Relation(self._new_id(), tenant_id, type_name, source_id, target_id)
        event = self._event(tenant_id, actor, "create", f"relation:{relation.id}")
        self._persist(relations=[relation], audit=[event])
        self._relations[relation.id] = relation
        self._audit.append(event)
        return relation

    def related(self, tenant_id, object_id, type_name, direction="out"):
        """direction="out": object_id-dən çıxan əlaqələr (Company -> Lead-lər).
        direction="in": object_id-yə gələn əlaqələr (Lead -> onun Company-si).
        """
        if direction not in ("out", "in"):
            raise ValueError("direction must be 'out' or 'in'")
        _check_tenant(tenant_id)
        self._own(tenant_id, object_id)
        result = []
        for r in self._relations.values():
            if r.tenant_id != tenant_id or r.type != type_name:
                continue
            if direction == "out" and r.source_id == object_id:
                result.append(_copy(self._objects[r.target_id]))
            elif direction == "in" and r.target_id == object_id:
                result.append(_copy(self._objects[r.source_id]))
        return result

    # --- Audit ---

    def audit_log(self, tenant_id):
        _check_tenant(tenant_id)
        return [e for e in self._audit if e.tenant_id == tenant_id]

    # --- Daxili köməkçilər ---

    def _own(self, tenant_id, object_id):
        # Tapılmadı və başqasınındır eyni xətanı verir: hücumçu id-lərin mövcudluğunu öyrənə bilməz
        obj = self._objects.get(object_id)
        if obj is None or obj.tenant_id != tenant_id:
            raise TenantError("Object not found")
        return obj

    def _new_id(self):
        new_id = self._next_id
        self._next_id += 1
        return new_id

    def _event(self, tenant_id, actor, action, target, details=()):
        return AuditEvent(len(self._audit) + 1, tenant_id, actor, action, target,
                          datetime.now(timezone.utc), details)

    def _persist(self, **records):
        # Əvvəl disk, sonra yaddaş: disk yazısı alınmasa, yaddaş da dəyişmir
        if self._db is not None:
            self._db.write(**records)


def _copy(obj):
    # Çağırana props-un surəti verilir ki, store-dakı datanı kənardan dəyişə bilməsin
    return replace(obj, props=deepcopy(obj.props))

"""ORDO HTTP API.

Tenant və actor heç vaxt sorğunun içindən oxunmur: yalnız API açarından gəlir.
  Authorization: Bearer ordo_...
Rollar: reader yalnız oxuyur, writer həm oxuyur, həm yazır. Sxem API ilə dəyişdirilmir (sectors.py).
"""
import threading

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

from .store import ConflictError, SchemaError, TenantError

MAX_BODY_BYTES = 64 * 1024


class _Body(BaseModel):
    # extra="forbid": sorğuya tenant_id və ya actor əlavə etmək xəta verir, səssizcə atılmır
    model_config = ConfigDict(extra="forbid")


class ObjectIn(_Body):
    type: StrictStr
    props: dict
    status: StrictStr = "fact"
    source: StrictStr | None = None


class ObjectPatch(_Body):
    expected_version: StrictInt
    props: dict | None = None
    status: StrictStr | None = None
    source: StrictStr | None = None


class RelationIn(_Body):
    type: StrictStr
    source_id: StrictInt
    target_id: StrictInt


def _object(o):
    return {"id": o.id, "type": o.type, "props": o.props, "status": o.status,
            "source": o.source, "version": o.version}


def _relation(r):
    return {"id": r.id, "type": r.type, "source_id": r.source_id, "target_id": r.target_id}


def _event(e):
    return {"seq": e.seq, "actor": e.actor, "action": e.action, "target": e.target,
            "at": e.at.isoformat(), "details": list(e.details)}


class BodyLimit:
    """Böyük sorğularla yaddaşı doldurmağın qarşısını alır."""

    def __init__(self, app, limit=MAX_BODY_BYTES):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in ("POST", "PATCH", "PUT"):
            length = dict(scope["headers"]).get(b"content-length")
            # Uzunluğu bildirməyən (chunked) sorğu qəbul olunmur: limiti yoxlamaq mümkün olmazdı
            if length is None:
                return await JSONResponse({"detail": "Content-Length required"}, 411)(scope, receive, send)
            if not length.isdigit() or int(length) > self.limit:
                return await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)
        await self.app(scope, receive, send)


def create_app(store, keys):
    # Store və SQLite thread-safe deyil: eyni anda yalnız bir sorğu onlara toxunur
    lock = threading.Lock()
    # Sənəd səhifələri bağlıdır: API-nin xəritəsi kənar şəxsə göstərilmir
    app = FastAPI(title="ORDO", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimit)

    def principal(request: Request):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(401, "Missing API key", headers={"WWW-Authenticate": "Bearer"})
        with lock:
            p = keys.authenticate(token.strip())
        if p is None:
            raise HTTPException(401, "Invalid API key", headers={"WWW-Authenticate": "Bearer"})
        return p

    def writer(p=Depends(principal)):
        if p.role != "writer":
            raise HTTPException(403, "This key can only read")
        return p

    # Tapılmadı və başqasınındır eyni cavabı verir (404), store-dakı qayda kimi
    @app.exception_handler(TenantError)
    async def _not_found(request, exc):
        return JSONResponse({"detail": "Not found"}, 404)

    @app.exception_handler(SchemaError)
    async def _schema(request, exc):
        return JSONResponse({"detail": str(exc)}, 422)

    @app.exception_handler(ConflictError)
    async def _conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, 409)

    @app.exception_handler(ValueError)
    async def _value(request, exc):
        return JSONResponse({"detail": str(exc)}, 422)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/types")
    def types(p=Depends(principal)):
        with lock:
            object_types = list(store._object_types.values())
            relation_types = list(store._relation_types.values())
        return {
            "objects": [{"name": t.name, "required": list(t.required),
                         "types": {f: [x.__name__ for x in ts] for f, ts in t.types.items()}}
                        for t in object_types],
            "relations": [{"name": r.name, "source": r.source_type, "target": r.target_type}
                          for r in relation_types],
        }

    @app.post("/objects", status_code=201)
    def create_object(body: ObjectIn, p=Depends(writer)):
        with lock:
            o = store.add_object(p.tenant_id, p.actor, body.type, body.props,
                                 status=body.status, source=body.source)
        return _object(o)

    @app.get("/objects")
    def find_objects(type: str, p=Depends(principal)):
        with lock:
            return [_object(o) for o in store.find(p.tenant_id, type)]

    @app.get("/objects/{object_id}")
    def get_object(object_id: int, p=Depends(principal)):
        with lock:
            return _object(store.get_object(p.tenant_id, object_id))

    @app.patch("/objects/{object_id}")
    def update_object(object_id: int, body: ObjectPatch, p=Depends(writer)):
        with lock:
            o = store.update_object(p.tenant_id, p.actor, object_id, body.expected_version,
                                    props=body.props, status=body.status, source=body.source)
        return _object(o)

    @app.get("/objects/{object_id}/history")
    def history(object_id: int, p=Depends(principal)):
        with lock:
            return [_object(o) for o in store.history(p.tenant_id, object_id)]

    @app.get("/objects/{object_id}/related")
    def related(object_id: int, type: str, direction: str = "out", p=Depends(principal)):
        with lock:
            return [_object(o) for o in store.related(p.tenant_id, object_id, type, direction)]

    @app.post("/relations", status_code=201)
    def create_relation(body: RelationIn, p=Depends(writer)):
        with lock:
            r = store.add_relation(p.tenant_id, p.actor, body.type, body.source_id, body.target_id)
        return _relation(r)

    @app.get("/audit")
    def audit(p=Depends(principal)):
        with lock:
            return [_event(e) for e in store.audit_log(p.tenant_id)]

    return app

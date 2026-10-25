"""HTTP API: açarla giriş, rollar, tenant ayrılığı və xəta cavabları."""
import pytest
from fastapi.testclient import TestClient

from ordo.api import MAX_BODY_BYTES, create_app
from ordo.keys import KeyStore
from ordo.sectors import setup_b2b_sales
from ordo.store import Store


class Env:
    def __init__(self, path):
        self.path = path
        self.open()
        _, self.a_writer = self.keys.create("A", "user1", "writer")
        _, self.a_reader = self.keys.create("A", "viewer1", "reader")
        _, self.b_writer = self.keys.create("B", "user2", "writer")

    def open(self):
        self.store = Store(db_path=self.path)
        setup_b2b_sales(self.store)
        self.keys = KeyStore(self.path)
        self.client = TestClient(create_app(self.store, self.keys))

    def close(self):
        self.client.close()
        self.store.close()
        self.keys.close()

    def call(self, method, url, key=None, **kw):
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        return self.client.request(method, url, headers=headers, **kw)

    def company(self, key, name="Logistika MMC"):
        r = self.call("POST", "/objects", key, json={"type": "Company", "props": {"name": name}})
        assert r.status_code == 201, r.text
        return r.json()


@pytest.fixture
def env(tmp_path):
    e = Env(str(tmp_path / "ordo.db"))
    yield e
    e.close()


# --- Giriş ---

def test_health_acarsiz_isleyir(env):
    assert env.call("GET", "/health").json() == {"status": "ok"}


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer ", "Basic abc", "Bearer ordo_yanlis",
                                    "Bearer not-an-ordo-key", "Bearer " + "ordo_" + "x" * 500])
def test_acarsiz_ve_ya_yanlis_acarla_giris_yoxdur(env, header):
    headers = {"Authorization": header} if header is not None else {}
    r = env.client.get("/objects?type=Company", headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_legv_edilmis_acar_islemir(env):
    key_id, key = env.keys.create("A", "temp", "writer")
    assert env.call("GET", "/audit", key).status_code == 200
    env.keys.revoke(key_id)
    assert env.call("GET", "/audit", key).status_code == 401


def test_acar_bazada_aciq_saxlanmir(env):
    env.close()
    raw = open(env.path, "rb").read()
    assert env.a_writer.encode() not in raw
    env.open()


# --- Rollar ---

def test_reader_oxuyur_amma_yaza_bilmir(env):
    c = env.company(env.a_writer)
    assert env.call("GET", f"/objects/{c['id']}", env.a_reader).status_code == 200
    r = env.call("POST", "/objects", env.a_reader, json={"type": "Company", "props": {"name": "X"}})
    assert r.status_code == 403
    r = env.call("PATCH", f"/objects/{c['id']}", env.a_reader,
                 json={"expected_version": 1, "props": {"name": "Hack"}})
    assert r.status_code == 403


# --- Tenant açardan gəlir ---

def test_tenant_ve_actor_sorgudan_oxunmur(env):
    r = env.call("POST", "/objects", env.a_writer,
                 json={"type": "Company", "props": {"name": "X"}, "tenant_id": "B"})
    assert r.status_code == 422
    r = env.call("POST", "/objects", env.a_writer,
                 json={"type": "Company", "props": {"name": "X"}, "actor": "admin"})
    assert r.status_code == 422


def test_audit_actoru_acardan_gelir(env):
    env.company(env.a_writer)
    assert [(e["actor"], e["action"]) for e in env.call("GET", "/audit", env.a_writer).json()] == [
        ("user1", "create")]


@pytest.mark.parametrize("method,suffix,body", [
    ("GET", "", None),
    ("PATCH", "", {"expected_version": 1, "props": {"name": "Hack"}}),
    ("GET", "/history", None),
    ("GET", "/related?type=HAS_LEAD", None),
])
def test_basqa_tenant_obyekte_toxuna_bilmir(env, method, suffix, body):
    c = env.company(env.a_writer)
    r = env.call(method, f"/objects/{c['id']}{suffix}", env.b_writer, json=body)
    assert r.status_code == 404
    assert r.json() == {"detail": "Not found"}
    assert env.call("GET", f"/objects/{c['id']}", env.a_writer).json()["props"]["name"] == "Logistika MMC"


def test_olmayan_ve_basqasinin_obyekti_eyni_cavab_verir(env):
    c = env.company(env.a_writer)
    foreign = env.call("GET", f"/objects/{c['id']}", env.b_writer)
    missing = env.call("GET", "/objects/99999", env.b_writer)
    assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())


def test_tenantlar_arasi_elaqe_api_ile_de_qurulmur(env):
    c = env.company(env.a_writer)
    lead_b = env.call("POST", "/objects", env.b_writer,
                      json={"type": "Lead", "props": {"contact": "gizli"}}).json()
    r = env.call("POST", "/relations", env.a_writer,
                 json={"type": "HAS_LEAD", "source_id": c["id"], "target_id": lead_b["id"]})
    assert r.status_code == 404


def test_axtaris_ve_audit_yalniz_oz_tenantini_gosterir(env):
    env.company(env.a_writer, "A MMC")
    env.company(env.b_writer, "B MMC")
    names = [o["props"]["name"] for o in env.call("GET", "/objects?type=Company", env.b_writer).json()]
    assert names == ["B MMC"]
    assert [e["actor"] for e in env.call("GET", "/audit", env.b_writer).json()] == ["user2"]


# --- Tam axın ---

def test_tam_axin_api_ile(env):
    k = env.a_writer
    c = env.company(k)
    lead = env.call("POST", "/objects", k, json={"type": "Lead", "props": {"contact": "x@y.az"}}).json()
    assert env.call("POST", "/relations", k, json={
        "type": "HAS_LEAD", "source_id": c["id"], "target_id": lead["id"]}).status_code == 201
    v2 = env.call("PATCH", f"/objects/{c['id']}", k,
                  json={"expected_version": 1, "props": {"ad_count": 3}}).json()
    assert v2["version"] == 2
    assert [o["id"] for o in env.call("GET", f"/objects/{c['id']}/related?type=HAS_LEAD", k).json()] == [lead["id"]]
    back = env.call("GET", f"/objects/{lead['id']}/related?type=HAS_LEAD&direction=in", k).json()
    assert back[0]["props"]["ad_count"] == 3
    assert len(env.call("GET", f"/objects/{c['id']}/history", k).json()) == 2


def test_data_server_yeniden_acilanda_qalir(env):
    c = env.company(env.a_writer)
    env.close()
    env.open()
    assert env.call("GET", f"/objects/{c['id']}", env.a_writer).json()["props"]["name"] == "Logistika MMC"


# --- Xəta cavabları ---

def test_kohne_versiya_409(env):
    c = env.company(env.a_writer)
    env.call("PATCH", f"/objects/{c['id']}", env.a_writer, json={"expected_version": 1, "props": {"name": "Y"}})
    r = env.call("PATCH", f"/objects/{c['id']}", env.a_writer, json={"expected_version": 1, "props": {"name": "Z"}})
    assert r.status_code == 409


@pytest.mark.parametrize("body", [
    {"type": "Sale", "props": {"amount": "çox"}},
    {"type": "Spaceship", "props": {}},
    {"type": "Company", "props": {}},
    {"type": "Company", "props": {"name": "X"}, "status": "rumor"},
    {"type": 123, "props": {"name": "X"}},
    {"type": "Company", "props": "not a dict"},
])
def test_sehv_data_422(env, body):
    assert env.call("POST", "/objects", env.a_writer, json=body).status_code == 422


def test_versiya_metn_ola_bilmez(env):
    c = env.company(env.a_writer)
    r = env.call("PATCH", f"/objects/{c['id']}", env.a_writer, json={"expected_version": "1"})
    assert r.status_code == 422


def test_sehv_istiqamet_422(env):
    c = env.company(env.a_writer)
    r = env.call("GET", f"/objects/{c['id']}/related?type=HAS_LEAD&direction=up", env.a_writer)
    assert r.status_code == 422


# --- Hücum səthi ---

def test_cox_boyuk_sorgu_redd_olunur(env):
    big = {"type": "Company", "props": {"name": "X", "blob": "a" * (MAX_BODY_BYTES + 1)}}
    r = env.call("POST", "/objects", env.a_writer, json=big)
    assert r.status_code == 413
    assert env.call("GET", "/objects?type=Company", env.a_writer).json() == []


@pytest.mark.parametrize("url", ["/docs", "/redoc", "/openapi.json"])
def test_api_xeritesi_gizlidir(env, url):
    assert env.call("GET", url).status_code == 404

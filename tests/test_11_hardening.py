"""Sərtləşdirmə: açar müddəti, SCOUT-un fact qaydası, ölçü və versiya limitləri, səhifələmə."""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import ordo.store as store_module
from ordo import scout
from ordo.keys import KeyStore
from ordo.store import SchemaError
from test_09_api import env  # noqa: F401  (fixture)


# --- Açar müddəti ---

def _age_key(path, key_id, days):
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = sqlite3.connect(path)
    with conn:
        conn.execute("UPDATE api_keys SET created_at = ? WHERE id = ?", (old, key_id))
    conn.close()


def test_muddeti_bitmis_acar_islemir(env):
    key_id, key = env.keys.create("A", "old", "writer")
    assert env.call("GET", "/audit", key).status_code == 200
    _age_key(env.path, key_id, 91)
    assert env.call("GET", "/audit", key).status_code == 401


def test_muddet_bitmemis_acar_isleyir(env):
    key_id, key = env.keys.create("A", "fresh", "writer")
    _age_key(env.path, key_id, 89)
    assert env.call("GET", "/audit", key).status_code == 200


def test_tarixi_pozulmus_acar_etibarsizdir(env):
    key_id, key = env.keys.create("A", "broken", "writer")
    conn = sqlite3.connect(env.path)
    with conn:
        conn.execute("UPDATE api_keys SET created_at = 'not-a-date' WHERE id = ?", (key_id,))
    conn.close()
    assert env.call("GET", "/audit", key).status_code == 401


@pytest.mark.parametrize("raw, days", [("0", 1), ("-5", 1), ("10000", 365), ("abc", 90), ("30", 30)])
def test_muddet_hemise_1_ile_365_gun_arasindadir(tmp_path, monkeypatch, raw, days):
    monkeypatch.setenv("ORDO_KEY_MAX_DAYS", raw)
    keys = KeyStore(str(tmp_path / "k.db"))
    try:
        assert keys.max_age == timedelta(days=days)
    finally:
        keys.close()


# --- SCOUT fact verə bilməz ---

@pytest.mark.parametrize("actor", ["scout", " SCOUT", "Scout "])
def test_scout_birbasa_fact_yarada_bilmez(store, actor):
    with pytest.raises(SchemaError):
        store.add_object("A", actor, "Company", {"name": "X"}, status="fact")


def test_scout_birbasa_update_ile_fact_ede_bilmez(store):
    o = scout.observe(store, "A", "Company", "name", {"name": "X"}, source="https://example.com")
    with pytest.raises(SchemaError):
        store.update_object("A", "scout", o.id, o.version, status="fact")
    assert store.get_object("A", o.id).status == "claim"


def test_scout_tesdiqlenmis_faktin_datasini_fact_saxlayaraq_deyise_bilmez(store):
    o = scout.observe(store, "A", "Company", "name", {"name": "X"}, source="https://example.com")
    fact = scout.confirm(store, "A", "user1", o.id, o.version)
    with pytest.raises(SchemaError):
        store.update_object("A", "scout", fact.id, fact.version, props={"website": "evil"})
    assert store.get_object("A", fact.id).props == {"name": "X"}


def test_api_ile_scout_acari_fact_yarada_bilmez(env):
    _, key = env.keys.create("A", "scout", "writer")
    r = env.call("POST", "/objects", key, json={"type": "Company", "props": {"name": "X"}})
    assert r.status_code == 422
    r = env.call("POST", "/objects", key,
                 json={"type": "Company", "props": {"name": "X"}, "status": "claim", "source": "s"})
    assert r.status_code == 201


# --- Ölçü və versiya limitləri ---

def test_props_limitden_boyuk_ola_bilmez(store):
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Company", {"name": "x" * (store_module.MAX_PROPS_BYTES + 1)})


def test_patch_ile_props_limitsiz_boyuya_bilmez(store):
    o = store.add_object("A", "user1", "Company", {"name": "X"})
    chunk = "y" * 8000
    with pytest.raises(SchemaError):
        for i in range(10):
            o = store.update_object("A", "user1", o.id, o.version, props={f"f{i}": chunk})
    assert len(str(store.get_object("A", o.id).props)) <= store_module.MAX_PROPS_BYTES + 100


def test_cox_derin_json_xeta_verir_cokmur(store):
    deep = current = {}
    for _ in range(5000):
        current["a"] = {}
        current = current["a"]
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Company", {"name": "X", "extra": deep})


def test_versiya_limiti(store, monkeypatch):
    monkeypatch.setattr(store_module, "MAX_VERSIONS", 3)
    o = store.add_object("A", "user1", "Company", {"name": "X"})
    o = store.update_object("A", "user1", o.id, o.version, props={"website": "a"})
    o = store.update_object("A", "user1", o.id, o.version, props={"website": "b"})
    with pytest.raises(SchemaError):
        store.update_object("A", "user1", o.id, o.version, props={"website": "c"})


# --- Səhifələmə ---

def test_siyahi_cavablari_sehifelenir(env):
    for i in range(5):
        env.company(env.a_writer, name=f"C{i}")
    r = env.call("GET", "/objects?type=Company&limit=2&offset=1", env.a_writer)
    assert [o["props"]["name"] for o in r.json()] == ["C1", "C2"]
    assert len(env.call("GET", "/audit?limit=3", env.a_writer).json()) == 3


@pytest.mark.parametrize("query", ["limit=0", "limit=1001", "offset=-1", "limit=abc"])
def test_yanlis_sehife_parametrleri_redd_edilir(env, query):
    assert env.call("GET", f"/objects?type=Company&{query}", env.a_writer).status_code == 422

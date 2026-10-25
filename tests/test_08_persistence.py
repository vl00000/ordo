"""SQLite: data proqram bağlanıb açılanda itmir, yazılar atomikdir."""
import sqlite3

import pytest

from ordo import scout
from ordo.sectors import setup_b2b_sales
from ordo.store import ConflictError, SchemaError, Store, TenantError


def open_store(path):
    s = Store(db_path=path)
    setup_b2b_sales(s)  # hər açılışda təkrar işləyir, eyni tərif problem yaratmır
    return s


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "ordo.db")


def test_data_yeniden_acilisda_qalir(db):
    s = open_store(db)
    c = s.add_object("A", "user1", "Company", {"name": "X", "ad_count": 7})
    lead = s.add_object("A", "user1", "Lead", {"contact": "x"})
    s.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)
    s.update_object("A", "user1", c.id, expected_version=1, props={"ad_count": 2})
    s.close()

    s2 = open_store(db)
    assert s2.get_object("A", c.id).props == {"name": "X", "ad_count": 2}
    assert [v.props["ad_count"] for v in s2.history("A", c.id)] == [7, 2]
    assert [o.id for o in s2.related("A", c.id, "HAS_LEAD")] == [lead.id]
    assert [(e.actor, e.action) for e in s2.audit_log("A")] == [
        ("user1", "create"), ("user1", "create"), ("user1", "create"), ("user1", "update")]
    assert s2.audit_log("A")[-1].details == ("ad_count",)
    s2.close()


def test_yeni_id_kohne_id_ile_toqqusmur(db):
    s = open_store(db)
    old = s.add_object("A", "user1", "Company", {"name": "X"})
    s.close()
    s2 = open_store(db)
    new = s2.add_object("A", "user1", "Company", {"name": "Y"})
    assert new.id > old.id
    assert s2.get_object("A", old.id).props["name"] == "X"
    s2.close()


def test_versiya_yoxlamasi_yeniden_acilisdan_sonra_da_isleyir(db):
    s = open_store(db)
    c = scout.observe(s, "A", "Company", "name", {"name": "X"}, "https://x.az")
    scout.confirm(s, "A", "user1", c.id, expected_version=1)
    s.close()
    s2 = open_store(db)
    assert s2.get_object("A", c.id).status == "fact"
    with pytest.raises(ConflictError):
        s2.update_object("A", "user1", c.id, expected_version=1, props={"name": "Y"})
    s2.close()


def test_tenant_ayriligi_yeniden_acilisdan_sonra_qalir(db):
    s = open_store(db)
    c = s.add_object("A", "user1", "Company", {"name": "X"})
    s.close()
    s2 = open_store(db)
    with pytest.raises(TenantError):
        s2.get_object("B", c.id)
    s2.close()


def test_ferqli_sxem_yeniden_qeydiyyatdan_kecmir(db):
    open_store(db).close()
    s = Store(db_path=db)
    with pytest.raises(SchemaError):
        s.register_object_type("Company", required=[], types={})
    s.close()


def test_eyni_sxem_iki_defe_qeydiyyat_problemsizdir(store):
    setup_b2b_sales(store)
    assert store.add_object("A", "user1", "Company", {"name": "X"}).id == 1


def test_disk_yazisi_alinmasa_yaddas_da_deyismir(db, monkeypatch):
    s = open_store(db)
    c = s.add_object("A", "user1", "Company", {"name": "X"})

    def broken_write(**records):
        raise sqlite3.OperationalError("disk is full")

    monkeypatch.setattr(s._db, "write", broken_write)
    with pytest.raises(sqlite3.OperationalError):
        s.update_object("A", "user1", c.id, expected_version=1, props={"name": "Y"})
    with pytest.raises(sqlite3.OperationalError):
        s.add_object("A", "user1", "Company", {"name": "Z"})
    assert s.get_object("A", c.id).props["name"] == "X"
    assert len(s.find("A", "Company")) == 1
    assert len(s.audit_log("A")) == 1
    s.close()


def test_redd_olunan_emeliyyat_diske_dusmur(db):
    s = open_store(db)
    with pytest.raises(SchemaError):
        s.add_object("A", "user1", "Sale", {"amount": "çox"})
    s.close()
    s2 = open_store(db)
    assert s2.find("A", "Sale") == []
    assert s2.audit_log("A") == []
    s2.close()


def test_sql_injection_data_kimi_saxlanir(db):
    evil = "A'); DROP TABLE objects; --"
    s = open_store(db)
    s.add_object(evil, "user1", "Company", {"name": "x'); DELETE FROM audit; --"})
    s.add_object("A", "user1", "Company", {"name": "normal"})
    s.close()
    s2 = open_store(db)
    assert s2.find(evil, "Company")[0].props["name"] == "x'); DELETE FROM audit; --"
    assert len(s2.find("A", "Company")) == 1
    assert len(s2.audit_log(evil)) == 1
    s2.close()


@pytest.mark.parametrize("pis_props", [
    {"name": "X", "tags": ("a", "b")},    # tuple diskdən list kimi qayıdardı
    {"name": "X", "tags": {"a"}},         # set JSON deyil
    {"name": "X", 1: "rəqəm açar"},       # açar diskdən "1" kimi qayıdardı
    {"name": "X", "score": float("nan")},
    {"name": "X", "obj": object()},
])
def test_diske_eyni_yazila_bilmeyen_data_redd_olunur(store, pis_props):
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Company", pis_props)


def test_icaze_verilmeyen_sahe_tipi_qeydiyyatdan_kecmir():
    from datetime import datetime
    with pytest.raises(SchemaError):
        Store().register_object_type("Thing", types={"at": datetime})

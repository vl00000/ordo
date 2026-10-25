"""Audit: kim, nə vaxt, hansı obyektdə nə etdi."""
import pytest

from ordo.store import TenantError


def test_her_yaratma_audite_yazilir(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    lead = store.add_object("A", "user2", "Lead", {"contact": "x"})
    r = store.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)

    log = store.audit_log("A")
    assert [(e.actor, e.action, e.target) for e in log] == [
        ("user1", "create", f"object:{c.id}"),
        ("user2", "create", f"object:{lead.id}"),
        ("user1", "create", f"relation:{r.id}"),
    ]
    assert all(e.at is not None for e in log)


def test_tenant_yalniz_oz_auditini_gorur(store):
    store.add_object("A", "user1", "Company", {"name": "A MMC"})
    store.add_object("B", "user2", "Company", {"name": "B MMC"})
    assert [e.actor for e in store.audit_log("A")] == ["user1"]
    assert [e.actor for e in store.audit_log("B")] == ["user2"]


@pytest.mark.parametrize("pis_actor", ["", "  ", None])
def test_anonim_deyisiklik_qadagandir(store, pis_actor):
    with pytest.raises(ValueError):
        store.add_object("A", pis_actor, "Company", {"name": "X"})
    assert store.audit_log("A") == []


def test_actor_bosluqlari_temizlenir(store):
    store.add_object("A", "  user1 ", "Company", {"name": "X"})
    assert store.audit_log("A")[0].actor == "user1"


def test_redd_olunan_emeliyyat_audite_dusmur(store):
    with pytest.raises(TenantError):
        store.add_relation("A", "user1", "HAS_LEAD", 1, 2)
    assert store.audit_log("A") == []

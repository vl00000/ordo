"""Update, versiya tarixçəsi və toqquşma (konflikt) yoxlaması."""
import pytest

from ordo.store import ConflictError, SchemaError, TenantError


def test_update_yeni_versiya_yaradir_kohnesi_qalir(store):
    c = store.add_object("A", "user1", "Company", {"name": "X Logistics", "ad_count": 7})
    v2 = store.update_object("A", "user1", c.id, expected_version=1, props={"ad_count": 2})
    assert v2.id == c.id
    assert v2.version == 2
    assert v2.props == {"name": "X Logistics", "ad_count": 2}
    assert [v.props["ad_count"] for v in store.history("A", c.id)] == [7, 2]


def test_kohne_versiya_ile_yazmaq_redd_olunur(store):
    # İki SCOUT işçisi eyni v1-i oxuyub: birincisi yazır, ikincisi köhnə məlumatla yaza bilməz
    c = store.add_object("A", "user1", "Company", {"name": "X", "ad_count": 7})
    store.update_object("A", "user1", c.id, expected_version=1, props={"ad_count": 2})
    with pytest.raises(ConflictError):
        store.update_object("A", "user2", c.id, expected_version=1, props={"ad_count": 9})
    assert store.get_object("A", c.id).props["ad_count"] == 2


def test_redd_olunan_update_hec_neyi_deyismir(store):
    c = store.add_object("A", "user1", "Company", {"name": "X"})
    with pytest.raises(SchemaError):
        store.update_object("A", "user1", c.id, expected_version=1, props={"name": ""})
    assert store.get_object("A", c.id).version == 1
    assert [e.action for e in store.audit_log("A")] == ["create"]


def test_basqa_tenant_update_ede_bilmez(store):
    c = store.add_object("A", "user1", "Company", {"name": "X"})
    with pytest.raises(TenantError):
        store.update_object("B", "user2", c.id, expected_version=1, props={"name": "Hack"})
    with pytest.raises(TenantError):
        store.history("B", c.id)


def test_deyisiklik_yoxdursa_versiya_artmir(store):
    c = store.add_object("A", "user1", "Company", {"name": "X"})
    same = store.update_object("A", "user1", c.id, expected_version=1, props={"name": "X"})
    assert same.version == 1
    assert len(store.audit_log("A")) == 1


def test_audit_deyisen_sahelerin_adini_yazir_deyerini_yox(store):
    c = store.add_object("A", "user1", "Company", {"name": "X", "website": "https://x.az"})
    store.update_object("A", "user2", c.id, expected_version=1,
                        props={"website": "https://y.az"}, status="claim")
    event = store.audit_log("A")[-1]
    assert (event.actor, event.action, event.details) == ("user2", "update", ("website", "status"))
    assert "https://y.az" not in repr(event)


def test_update_sonrasi_elaqeler_qorunur(store):
    # id dəyişmir: lead yeni versiyada da eyni şirkətə bağlı qalır
    c = store.add_object("A", "user1", "Company", {"name": "X"})
    lead = store.add_object("A", "user1", "Lead", {"contact": "x"})
    store.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)
    store.update_object("A", "user1", c.id, expected_version=1, props={"name": "X Logistics MMC"})
    assert store.related("A", lead.id, "HAS_LEAD", direction="in")[0].props["name"] == "X Logistics MMC"


@pytest.mark.parametrize("pis_versiya", [True, "1", 1.0, None])
def test_versiya_yalniz_tam_eded_ola_biler(store, pis_versiya):
    c = store.add_object("A", "user1", "Company", {"name": "X"})
    with pytest.raises(ValueError):
        store.update_object("A", "user1", c.id, expected_version=pis_versiya, props={"name": "Y"})


def test_tarixceden_alinan_versiyani_deyismek_olmur(store):
    c = store.add_object("A", "user1", "Company", {"name": "X"})
    store.update_object("A", "user1", c.id, expected_version=1, props={"name": "Y"})
    store.history("A", c.id)[0].props["name"] = "Hack"
    assert store.history("A", c.id)[0].props["name"] == "X"

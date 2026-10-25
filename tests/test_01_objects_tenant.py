"""Obyektlər və tenant ayrılığı."""
import pytest

from ordo.store import SchemaError, TenantError


def test_tenant_oz_obyektini_gorur(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    assert store.get_object("A", c.id).props["name"] == "Logistika MMC"


def test_iki_obyekt_ferqli_id_alir(store):
    c1 = store.add_object("A", "user1", "Company", {"name": "Birinci"})
    c2 = store.add_object("A", "user1", "Company", {"name": "İkinci"})
    assert c1.id != c2.id


def test_basqa_tenant_gore_bilmir(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    with pytest.raises(TenantError):
        store.get_object("B", c.id)


def test_olmayan_obyekt_tenant_xetasi_verir(store):
    with pytest.raises(TenantError):
        store.get_object("A", 999)


@pytest.mark.parametrize("pis_tenant", ["", "   ", None, 123])
def test_bos_ve_ya_sehv_tenant_qebul_olunmur(store, pis_tenant):
    with pytest.raises(TenantError):
        store.add_object(pis_tenant, "user1", "Company", {"name": "Gizli"})
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    with pytest.raises(TenantError):
        store.get_object(pis_tenant, c.id)


@pytest.mark.parametrize("props", [{}, {"name": ""}, {"name": "   "}, {"name": None}])
def test_mecburi_sahe_olmadan_qebul_olunmur(store, props):
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Company", props)


def test_qeydiyyatsiz_tip_qebul_olunmur(store):
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Spaceship", {"name": "X"})


def test_status_ve_menbe_saxlanir(store):
    # SCOUT-dan gələn məlumat: fakt deyil, mənbəsi olan iddia
    c = store.add_object(
        "A", "scout", "Company", {"name": "X Logistics"}, status="claim", source="https://example.az"
    )
    saved = store.get_object("A", c.id)
    assert saved.status == "claim"
    assert saved.source == "https://example.az"


def test_sehv_status_qebul_olunmur(store):
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Company", {"name": "X"}, status="rumor")


def test_qaytarilan_obyekti_deyismek_store_u_deyismir(store):
    c = store.add_object("A", "user1", "Company", {"name": "Orijinal"})
    c.props["name"] = "Hack"
    assert store.get_object("A", c.id).props["name"] == "Orijinal"


def test_ic_ice_datani_kenardan_deyismek_olmur(store):
    # Hacker yoxlaması PoC: əvvəl props içindəki siyahını kənardan dəyişmək mümkün idi
    p = {"name": "X", "tags": ["a"]}
    c = store.add_object("A", "user1", "Company", p)
    p["tags"].append("INJECT")
    store.get_object("A", c.id).props["tags"].append("INJECT2")
    assert store.get_object("A", c.id).props["tags"] == ["a"]


def test_menbe_yalniz_metn_ola_biler(store):
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Company", {"name": "X"}, source=["not", "a", "string"])

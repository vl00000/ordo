"""Əlaqələr: Company —HAS_LEAD→ Lead və qaydalar."""
import pytest

from ordo.store import SchemaError, TenantError


def test_company_has_lead(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    lead = store.add_object("A", "user1", "Lead", {"contact": "+994 XX XXX XX XX"})
    store.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)
    assert [o.id for o in store.related("A", c.id, "HAS_LEAD")] == [lead.id]


def test_ters_sorgu_lead_kimindir(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    lead = store.add_object("A", "user1", "Lead", {"contact": "x"})
    store.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)
    assert [o.id for o in store.related("A", lead.id, "HAS_LEAD", direction="in")] == [c.id]
    assert store.related("A", lead.id, "HAS_LEAD", direction="out") == []


def test_sehv_istiqamet_redd_olunur(store):
    c = store.add_object("A", "user1", "Company", {"name": "X"})
    with pytest.raises(ValueError):
        store.related("A", c.id, "HAS_LEAD", direction="sideways")


def test_tam_zencir_company_campaign_lead_sale(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    camp = store.add_object("A", "user1", "Campaign", {"name": "Oktyabr Meta"})
    lead = store.add_object("A", "user1", "Lead", {"contact": "anar@example.az"})
    sale = store.add_object("A", "user1", "Sale", {"amount": 1200})
    store.add_relation("A", "user1", "OWNS", c.id, camp.id)
    store.add_relation("A", "user1", "GENERATES", camp.id, lead.id)
    store.add_relation("A", "user1", "CONVERTS_TO", lead.id, sale.id)

    camp_ = store.related("A", c.id, "OWNS")[0]
    lead_ = store.related("A", camp_.id, "GENERATES")[0]
    sale_ = store.related("A", lead_.id, "CONVERTS_TO")[0]
    assert sale_.props["amount"] == 1200


def test_olmayan_obyekte_elaqe_redd_olunur(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    with pytest.raises(TenantError):
        store.add_relation("A", "user1", "HAS_LEAD", c.id, 999)


def test_sehv_tipler_arasinda_elaqe_redd_olunur(store):
    # Sale birbaşa Company-yə HAS_LEAD ilə bağlana bilməz
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    sale = store.add_object("A", "user1", "Sale", {"amount": 100})
    with pytest.raises(SchemaError):
        store.add_relation("A", "user1", "HAS_LEAD", c.id, sale.id)


def test_qeydiyyatsiz_elaqe_tipi_redd_olunur(store):
    c = store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    lead = store.add_object("A", "user1", "Lead", {"contact": "x"})
    with pytest.raises(SchemaError):
        store.add_relation("A", "user1", "LOVES", c.id, lead.id)


def test_tenantlar_arasi_elaqe_qurula_bilmez(store):
    # A öz şirkətini B-nin lead-inə bağlamağa çalışır
    c_a = store.add_object("A", "user1", "Company", {"name": "A MMC"})
    lead_b = store.add_object("B", "user2", "Lead", {"contact": "gizli"})
    with pytest.raises(TenantError):
        store.add_relation("A", "user1", "HAS_LEAD", c_a.id, lead_b.id)


def test_basqa_tenant_elaqeleri_gormur(store):
    c = store.add_object("A", "user1", "Company", {"name": "A MMC"})
    lead = store.add_object("A", "user1", "Lead", {"contact": "x"})
    store.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)
    with pytest.raises(TenantError):
        store.related("B", c.id, "HAS_LEAD")


def test_movcud_tipi_yeniden_qeydiyyat_qadagandir(store):
    with pytest.raises(SchemaError):
        store.register_object_type("Company", required=[])
    with pytest.raises(SchemaError):
        store.register_relation_type("HAS_LEAD", "Company", "Sale")


def test_olmayan_tiple_elaqe_tipi_yaradila_bilmez(store):
    with pytest.raises(SchemaError):
        store.register_relation_type("USES", "Company", "Spaceship")

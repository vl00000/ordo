"""SCOUT v0.1: kənardan müşahidə -> claim -> insan təsdiqi -> fact."""
import pytest

from ordo import scout
from ordo.store import ConflictError, SchemaError

SRC = "https://instagram.com/xlogistics"


def test_musahide_claim_kimi_menbe_ile_yazilir(store):
    c = scout.observe(store, "A", "Company", "name", {"name": "X Logistics", "ad_count": 7}, SRC)
    assert (c.status, c.source, c.version) == ("claim", SRC, 1)
    assert store.audit_log("A")[-1].actor == "scout"


def test_eyni_musahide_tekrar_dublikat_yaratmir(store):
    first = scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 7}, SRC)
    again = scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 7}, SRC)
    assert again.id == first.id
    assert again.version == 1
    assert len(store.find("A", "Company")) == 1
    assert len(store.audit_log("A")) == 1


def test_deyisen_musahide_yeni_versiya_olur(store):
    # "Dünən 7 reklam var idi, bu gün 2" — SIGNAL üçün dəyərli siqnal tarixçədə qalır
    c = scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 7}, SRC)
    scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 2}, SRC)
    assert [v.props["ad_count"] for v in store.history("A", c.id)] == [7, 2]


def test_insan_tesdiqleyir_claim_fact_olur(store):
    c = scout.observe(store, "A", "Company", "name", {"name": "X"}, SRC)
    fact = scout.confirm(store, "A", "user1", c.id, expected_version=1)
    assert (fact.status, fact.version) == ("fact", 2)
    assert store.audit_log("A")[-1].actor == "user1"


@pytest.mark.parametrize("ad", ["scout", " scout", "SCOUT", "Scout "])
def test_scout_oz_musahidesini_tesdiqleye_bilmez(store, ad):
    # Hacker yoxlaması PoC: əvvəl " scout" və "SCOUT" yazılışları yoxlamadan keçirdi
    c = scout.observe(store, "A", "Company", "name", {"name": "X"}, SRC)
    with pytest.raises(ValueError):
        scout.confirm(store, "A", ad, c.id, expected_version=1)
    assert store.get_object("A", c.id).status == "claim"


def test_kohne_versiyani_tesdiqlemek_olmur(store):
    # İnsan v1-i yoxlayıb, amma arada SCOUT yeni məlumat yazıb: köhnəni təsdiqləmək olmaz
    c = scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 7}, SRC)
    scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 2}, SRC)
    with pytest.raises(ConflictError):
        scout.confirm(store, "A", "user1", c.id, expected_version=1)


def test_faktdan_sonra_yeni_melumat_yeniden_claim_olur(store):
    c = scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 7}, SRC)
    scout.confirm(store, "A", "user1", c.id, expected_version=1)
    now = scout.observe(store, "A", "Company", "name", {"name": "X", "ad_count": 0}, SRC)
    assert now.status == "claim"
    assert [v.status for v in store.history("A", c.id)] == ["claim", "fact", "claim"]


@pytest.mark.parametrize("pis_menbe", ["", "  ", None, 123])
def test_menbesiz_musahide_qebul_olunmur(store, pis_menbe):
    with pytest.raises(ValueError):
        scout.observe(store, "A", "Company", "name", {"name": "X"}, pis_menbe)


def test_acar_sahesiz_musahide_qebul_olunmur(store):
    with pytest.raises(SchemaError):
        scout.observe(store, "A", "Company", "name", {"website": "https://x.az"}, SRC)


def test_scout_tenantlari_qarisdirmir(store):
    a = scout.observe(store, "A", "Company", "name", {"name": "X"}, SRC)
    b = scout.observe(store, "B", "Company", "name", {"name": "X"}, SRC)
    assert a.id != b.id


def test_tam_ssenari_outside_in(store):
    # 1) SCOUT kənardan şirkəti tapır  2) satış komandası lead əlavə edir
    # 3) insan şirkəti təsdiqləyir     4) lead-dən şirkətə tərs sorğu
    c = scout.observe(store, "A", "Company", "name", {"name": "X Logistics", "ad_count": 7}, SRC)
    lead = store.add_object("A", "user1", "Lead", {"contact": "info@x.az"})
    store.add_relation("A", "user1", "HAS_LEAD", c.id, lead.id)
    scout.confirm(store, "A", "user1", c.id, expected_version=1)

    company = store.related("A", lead.id, "HAS_LEAD", direction="in")[0]
    assert (company.props["name"], company.status, company.source) == ("X Logistics", "fact", SRC)
    assert [e.action for e in store.audit_log("A")] == ["create", "create", "create", "update"]

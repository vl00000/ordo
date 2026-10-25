"""Sahə tiplərinin yoxlanması."""
import pytest

from ordo.store import SchemaError, Store


@pytest.mark.parametrize("pis_mebleg", ["çox", "1200", True, [1200]])
def test_sale_meblegi_reqem_olmalidir(store, pis_mebleg):
    # Debatda tapılan açıq: əvvəl amount="çox" qəbul olunurdu
    with pytest.raises(SchemaError):
        store.add_object("A", "user1", "Sale", {"amount": pis_mebleg})


@pytest.mark.parametrize("yaxsi_mebleg", [1200, 1200.5, 0])
def test_duzgun_mebleg_qebul_olunur(store, yaxsi_mebleg):
    assert store.add_object("A", "user1", "Sale", {"amount": yaxsi_mebleg}).props["amount"] == yaxsi_mebleg


def test_update_de_tipi_yoxlayir(store):
    s = store.add_object("A", "user1", "Sale", {"amount": 100})
    with pytest.raises(SchemaError):
        store.update_object("A", "user1", s.id, expected_version=1, props={"amount": "çox"})


def test_tipsiz_elave_sahe_serbestdir(store):
    # Tipi təyin edilməmiş sahələr sərbəstdir: sektor sonradan sahə əlavə edə bilər
    c = store.add_object("A", "user1", "Company", {"name": "X", "note": "VIP"})
    assert c.props["note"] == "VIP"


@pytest.mark.parametrize("pis_tip", ["str", None, (), (str, "int")])
def test_sehv_tip_tesviri_qeydiyyatdan_kecmir(pis_tip):
    with pytest.raises(SchemaError):
        Store().register_object_type("Thing", types={"x": pis_tip})

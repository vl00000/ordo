"""Reusable core: eyni nüvə ikinci sektorda kod dəyişmədən işləyir."""
from ordo.sectors import setup_b2b_sales, setup_dental_clinic
from ordo.store import Store


def test_stomatologiya_eyni_nuveyle_isleyir():
    store = Store()
    setup_dental_clinic(store)
    clinic = store.add_object("D", "user1", "Clinic", {"name": "Dental Plus"})
    patient = store.add_object("D", "user1", "Patient", {"contact": "x"})
    visit = store.add_object("D", "user1", "Appointment", {"date": "2026-11-01"})
    store.add_relation("D", "user1", "HAS_PATIENT", clinic.id, patient.id)
    store.add_relation("D", "user1", "BOOKED", patient.id, visit.id)

    assert store.related("D", patient.id, "BOOKED")[0].props["date"] == "2026-11-01"
    assert len(store.audit_log("D")) == 5


def test_iki_sektor_bir_store_da_qarismir():
    store = Store()
    setup_b2b_sales(store)
    setup_dental_clinic(store)
    store.add_object("A", "user1", "Company", {"name": "Logistika MMC"})
    store.add_object("D", "user1", "Clinic", {"name": "Dental Plus"})
    assert [e.tenant_id for e in store.audit_log("A")] == ["A"]
    assert [e.tenant_id for e in store.audit_log("D")] == ["D"]

"""Sektor konfiqurasiyaları: eyni ORDO nüvəsi, fərqli tiplər.

Yeni sektor əlavə etmək üçün store.py-yə toxunulmur, yalnız burada yeni funksiya yazılır.
"""

NUMBER = (int, float)


def setup_b2b_sales(store):
    """İlk vertikal: B2B satış–marketinq (məsələn, logistika)."""
    store.register_object_type("Company", required=["name"],
                               types={"name": str, "website": str, "ad_count": int})
    store.register_object_type("Campaign", required=["name"],
                               types={"name": str, "budget": NUMBER})
    store.register_object_type("Lead", required=["contact"], types={"contact": str})
    store.register_object_type("Sale", required=["amount"], types={"amount": NUMBER})

    store.register_relation_type("OWNS", "Company", "Campaign")
    store.register_relation_type("GENERATES", "Campaign", "Lead")
    store.register_relation_type("HAS_LEAD", "Company", "Lead")
    store.register_relation_type("CONVERTS_TO", "Lead", "Sale")


def setup_dental_clinic(store):
    """İkinci sektor testi: nüvənin təkrar istifadəsini yoxlamaq üçün."""
    store.register_object_type("Clinic", required=["name"], types={"name": str})
    store.register_object_type("Patient", required=["contact"], types={"contact": str})
    store.register_object_type("Appointment", required=["date"], types={"date": str})

    store.register_relation_type("HAS_PATIENT", "Clinic", "Patient")
    store.register_relation_type("BOOKED", "Patient", "Appointment")

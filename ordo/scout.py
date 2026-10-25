"""SCOUT v0.1 — xarici müşahidələri ORDO-ya yazan sadə qat.

SCOUT hələ internetdən özü məlumat toplamır: müşahidəni insan və ya gələcək kolleksiyaçı verir.
SCOUT-un işi:
  1) müşahidəni mənbəsi ilə "claim" (iddia) kimi yazmaq;
  2) eyni şeyi ikinci dəfə görəndə dublikat yaratmamaq, dəyişibsə yeni versiya yazmaq;
  3) təsdiqi insana buraxmaq: "fact" statusunu yalnız insan verir (human-in-the-loop).
"""
from .store import SchemaError

ACTOR = "scout"


def observe(store, tenant_id, type_name, key, props, source):
    """Müşahidəni yazır və cari versiyanı qaytarır.

    key: obyekti tanıyan sahə (məsələn, Company üçün "name").
    Eyni key dəyəri ilə obyekt varsa, yenisi yaradılmır:
      - heç nə dəyişməyibsə, heç nə yazılmır;
      - dəyişibsə, yeni versiya "claim" statusu ilə yazılır (köhnə versiya tarixçədə qalır).
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("SCOUT observation needs a source")
    if not isinstance(props, dict) or key not in props:
        raise SchemaError(f"Observation must contain key field: {key}")

    existing = store.find(tenant_id, type_name, **{key: props[key]})
    if not existing:
        return store.add_object(tenant_id, ACTOR, type_name, props, status="claim", source=source)
    if len(existing) > 1:
        raise SchemaError(f"Ambiguous key: several {type_name} objects with {key}={props[key]!r}")

    current = existing[0]
    if all(current.props.get(k) == v for k, v in props.items()):
        return current
    # Yeni məlumat təsdiqlənməyib: əvvəl fakt olsa belə, yenidən iddiaya düşür
    return store.update_object(tenant_id, ACTOR, current.id, current.version,
                               props=props, status="claim", source=source)


def confirm(store, tenant_id, actor, object_id, expected_version):
    """İnsan müşahidəni yoxlayıb təsdiqləyir: claim -> fact."""
    # " scout", "SCOUT" kimi yazılışlarla yoxlamadan yan keçmək olmasın
    if isinstance(actor, str) and actor.strip().casefold() == ACTOR:
        raise ValueError("SCOUT cannot confirm its own observations")
    return store.update_object(tenant_id, actor, object_id, expected_version, status="fact")

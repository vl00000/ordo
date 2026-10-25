# ORDO

[![tests](https://github.com/vl00000/ordo/actions/workflows/tests.yml/badge.svg)](https://github.com/vl00000/ordo/actions/workflows/tests.yml)

**English summary.** ORDO is a small multi-tenant object/relation store with a versioned history, an audit log, SQLite storage and a FastAPI HTTP API protected by hashed API keys. Object and relation types are registered data, not hard-coded classes, so a new business sector only needs new type definitions (`ordo/sectors.py`). Tenant and actor come only from the API key; cross-tenant access returns the same 404 as a missing object. The project was security-reviewed in 8 rounds (see `SECURITY.md`), has 163 passing tests, and runs in a hardened Docker container. Docs below are in Azerbaijani; `ORDO_SCHEMA.md` has the full rules.

```bash
pip install -r requirements-dev.txt && python -m pytest -q      # 163 passed
python -m ordo.keys create --tenant A --actor alice --role writer   # prints the key once
docker compose up --build                                        # 127.0.0.1:8000
curl -H "Authorization: Bearer ordo_..." -H "Content-Type: application/json" -d '{"type":"Company","props":{"name":"Acme"}}' http://127.0.0.1:8000/objects
```

License: all rights reserved (source available for viewing / portfolio only, see `LICENSE`).

---

Çox-müştərili (multi-tenant) obyekt və əlaqə bazası: versiya tarixçəsi, audit jurnalı, SQLite saxlama və açarla qorunan FastAPI HTTP API. Biznes layihəsinin nüvə hissəsidir.

Status: **v0.1.1** · 163 test keçir · Docker ilə işləyir

## Repo nələri daşıyır

| Yol | Nə |
|---|---|
| `ordo/store.py` | Nüvə: tiplər, obyektlər, versiyalar, əlaqələr, tenant izolyasiyası, audit |
| `ordo/db.py` | SQLite saxlama, atomik yazılar |
| `ordo/api.py`, `keys.py`, `server.py` | HTTP API, API açarları (bazada yalnız həş), uvicorn giriş nöqtəsi |
| `ordo/sectors.py` | Sektor tipləri (B2B satış, klinika). Yeni sektor = yeni tiplər, nüvə dəyişmir |
| `ordo/backup.py` | Backup surəti və bərpa yoxlaması |
| `ordo/scout.py` | Gözləmədə olan modul: iddia (`claim`) → insan təsdiqi (`fact`) axını |
| `tests/` | 11 test faylı, 163 test |
| `Dockerfile`, `docker-compose.yml` | Sərtləşdirilmiş konteyner |
| `ORDO_SCHEMA.md` | Bütün qaydalar, API siyahısı, bilinən məhdudiyyətlər |
| `SECURITY.md` | Təhlükəsizlik yoxlamalarının tarixçəsi və qalan risklər |
| `CHANGELOG.md` | Mərhələlər və versiyalar |

## Dizayn qərarları

- **Generic nüvə:** `Company`, `Lead` kimi tiplər kodda sinif deyil, qeydiyyatdan keçən tiplərdir.
- **Tenant yalnız açardan gəlir.** Sorğuda `tenant_id` və ya `actor` yazmaq rədd edilir. Başqa tenant-ın obyekti "tapılmadı" kimi görünür.
- **Hər dəyişiklik yeni versiyadır**, köhnəsi tarixçədə qalır. `expected_version` ilə eyni anda yazma toqquşması tutulur.
- **Audit dəyərləri yox, yalnız dəyişən sahələrin adlarını yazır.**
- **Sxem API ilə dəyişmir**, yalnız kodda.

## İşə salmaq

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # 163 passed
docker compose up --build    # yalnız 127.0.0.1:8000
python -m ordo.keys create --tenant A --actor user1 --role writer
```

Sorğu başlığı: `Authorization: Bearer ordo_...`

Bu repoda açar, parol, baza faylı, server ünvanı və ya müştəri datası saxlanmır.

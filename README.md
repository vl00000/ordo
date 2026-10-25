# ORDO

Çox-müştərili (multi-tenant) obyekt və əlaqə bazası: versiya tarixçəsi, audit jurnalı, SQLite saxlama və açarla qorunan FastAPI HTTP API. Biznes layihəsinin nüvə hissəsidir.

Status: **v0.1** · 140 test keçir · Docker ilə işləyir

## Repo nələri daşıyır

| Yol | Nə |
|---|---|
| `ordo/store.py` | Nüvə: tiplər, obyektlər, versiyalar, əlaqələr, tenant izolyasiyası, audit |
| `ordo/db.py` | SQLite saxlama, atomik yazılar |
| `ordo/api.py`, `keys.py`, `server.py` | HTTP API, API açarları (bazada yalnız həş), uvicorn giriş nöqtəsi |
| `ordo/sectors.py` | Sektor tipləri (B2B satış, klinika). Yeni sektor = yeni tiplər, nüvə dəyişmir |
| `ordo/backup.py` | Backup surəti və bərpa yoxlaması |
| `ordo/scout.py` | Gözləmədə olan modul: iddia (`claim`) → insan təsdiqi (`fact`) axını |
| `tests/` | 10 test faylı, 140 test |
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
python -m pytest -q          # 140 passed
docker compose up --build    # yalnız 127.0.0.1:8000
python -m ordo.keys create --tenant A --actor user1 --role writer
```

Sorğu başlığı: `Authorization: Bearer ordo_...`

Bu repoda açar, parol, baza faylı, server ünvanı və ya müştəri datası saxlanmır.

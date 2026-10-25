# ORDO v0.1 — sxem və qaydalar

Son yenilənmə: 2026-10-25
Kod: `ordo/store.py` (nüvə), `ordo/db.py` (SQLite), `ordo/api.py` + `ordo/keys.py` + `ordo/server.py` (HTTP API), `ordo/sectors.py` (sektorlar), `ordo/backup.py` (backup surəti və bərpa yoxlaması), `ordo/scout.py` (SCOUT v0.1, hazırda gözləmədə)
Testlər: `tests/` — işlətmək üçün `..\venv\Scripts\python.exe -m pytest -q`

## 1. Nüvə anlayışları

| Anlayış | Nədir | Nümunə |
|---|---|---|
| **Tenant** | Müştəri şirkət. Hər əməliyyat bir tenant adından edilir | `"A"` |
| **ObjectType** | Obyekt növü: məcburi sahələr və sahə tipləri | `Company`: `name` məcburi, `str` |
| **Object** | Konkret qeyd. `id` heç vaxt dəyişmir | `Company #1 "X Logistics"` |
| **RelationType** | Əlaqə növü: hansı tipdən hansı tipə | `HAS_LEAD`: Company → Lead |
| **Relation** | Konkret əlaqə | `#1 HAS_LEAD #2` |
| **Versiya** | Hər dəyişiklik yeni versiyadır, köhnəsi tarixçədə qalır | `v1: ad_count=7`, `v2: ad_count=2` |
| **AuditEvent** | Kim, nə, nə vaxt (UTC), hansı sahələr dəyişdi | `user1 update object:1 (status)` |

Hər obyektdə əlavə olaraq:
- `status`: `fact` (təsdiqlənib), `claim` (iddia), `hypothesis` (fərziyyə);
- `source`: məlumatın mənbəyi (link və s.).

## 2. Sektorlar (`sectors.py`)

**B2B satış:**

```text
Company (name*, website, ad_count:int)
  --OWNS-->      Campaign (name*, budget:number)
  --HAS_LEAD-->  Lead (contact*)
Campaign --GENERATES--> Lead
Lead --CONVERTS_TO--> Sale (amount*:number)
```

**Stomatologiya** (reusable core sübutu):

```text
Clinic (name*) --HAS_PATIENT--> Patient (contact*) --BOOKED--> Appointment (date*)
```

`*` = məcburi. Tipi göstərilməyən sahələr sərbəstdir.

## 3. Qaydalar (hamısı testlə qorunur)

**Tenant**
- Tenant boş və ya mətn deyilsə, rədd edilir.
- Başqa tenant-ın obyekti "tapılmadı" kimi görünür (oxumaq, yeniləmək, tarixçə, əlaqə, sorğu).
- Tenant-lar arası əlaqə qurula bilməz.

**Sxem**
- Qeydiyyatsız tip və ya əlaqə tipi qəbul olunmur.
- Məcburi sahə boş ola bilməz; sahə tipi uyğun olmalıdır (`amount="çox"` rədd edilir, `True` da rəqəm sayılmır).
- Mövcud tipi yenidən qeydiyyatdan keçirmək qadağandır.
- Əlaqə yalnız düzgün istiqamətdə qurulur.

**Versiya və toqquşma**
- `update_object(..., expected_version=N)`: yalnız obyekt hələ də N versiyasındadırsa yazır, yoxsa `ConflictError`. Bu, iki nəfərin eyni anda yazıb bir-birinin işini silməsinin qarşısını alır.
- Heç nə dəyişmirsə, yeni versiya və audit yaranmır.
- Rədd olunan əməliyyat heç nəyi dəyişmir və auditə düşmür.

**Audit**
- Hər yaratma və yeniləmə yazılır. Anonim dəyişiklik qadağandır.
- Yeniləmədə dəyişən sahələrin **adları** yazılır, **dəyərləri** yox.

**Saxlama (SQLite)**
- `Store(db_path="ordo.db")`: hər dəyişiklik diskə yazılır, növbəti açılışda geri yüklənir. `Store()` yalnız yaddaşda işləyir (testlər üçün).
- Hər əməliyyat bir tranzaksiyadır: dəyişiklik, köhnə versiyanın tarixçəyə köçməsi və audit ya birlikdə yazılır, ya heç biri. Disk yazısı alınmasa, yaddaş da dəyişmir.
- Eyni sxem hər açılışda yenidən qeydiyyatdan keçə bilər; fərqli tərif rədd edilir.
- `props` yalnız JSON dəyərlərindən ibarət ola bilər (mətn açarlar; tuple, set, NaN yox), ki diskdən eyni şəkildə qayıtsın.
- Sorğular parametrlidir: SQL injection mətni data kimi saxlanır.
- Sahə tipləri: `str`, `int`, `float`, `bool`, `list`, `dict`.

## 4. HTTP API (`api.py`, `keys.py`, `server.py`)

**İşə salmaq** (Ordo qovluğunda):

```bash
..\venv\Scripts\python.exe -m uvicorn ordo.server:app --host 127.0.0.1 --port 8000 --workers 1 --no-server-header
```

**Açarlar:** hər açar bir tenant-a, bir actor-a və bir rola bağlıdır. Bazada yalnız həşi saxlanır, açarın özü bir dəfə göstərilir.

```bash
..\venv\Scripts\python.exe -m ordo.keys create --tenant A --actor user1 --role writer
..\venv\Scripts\python.exe -m ordo.keys list
..\venv\Scripts\python.exe -m ordo.keys revoke 1
```

Sorğu başlığı: `Authorization: Bearer ordo_...`

| Metod | Yol | Rol | Nə edir |
|---|---|---|---|
| GET | `/health` | — | Server işləyirmi |
| GET | `/types` | reader | Qeydiyyatdakı tiplər və əlaqələr |
| POST | `/objects` | writer | `{type, props, status?, source?}` → yeni obyekt |
| GET | `/objects?type=Company` | reader | Tipə görə axtarış |
| GET | `/objects/{id}` | reader | Bir obyekt |
| PATCH | `/objects/{id}` | writer | `{expected_version, props?, status?, source?}` → yeni versiya |
| GET | `/objects/{id}/history` | reader | Bütün versiyalar |
| GET | `/objects/{id}/related?type=HAS_LEAD&direction=out\|in` | reader | Əlaqəli obyektlər |
| POST | `/relations` | writer | `{type, source_id, target_id}` |
| GET | `/audit` | reader | Bu tenant-ın audit jurnalı |

**Qaydalar:**
- Tenant və actor **yalnız açardan** gəlir. Sorğuya `tenant_id` və ya `actor` yazmaq 422 verir.
- `writer` oxuyur və yazır; `reader` yalnız oxuyur (yazma cəhdi 403).
- Sxem API ilə dəyişdirilmir, yalnız `sectors.py`-dən gəlir.
- Cavab kodları: 401 açar yoxdur/yanlışdır, 403 rol icazə vermir, 404 tapılmadı **və ya başqa tenant-ındır** (eyni cavab), 409 köhnə versiya, 411 Content-Length yoxdur, 413 sorğu 64 KB-dan böyükdür, 422 səhv data.
- `/docs` və `/openapi.json` bağlıdır.

## 5. SCOUT v0.1 axını (`scout.py`)

```text
scout.observe(...)   → yeni obyekt, status="claim", source=link, actor="scout"
scout.observe(eyni)  → heç nə dəyişmir (dublikat yoxdur)
scout.observe(fərqli)→ yeni versiya, yenə "claim" (köhnə dəyər tarixçədə)
scout.confirm(insan) → status="fact"
```

- SCOUT özü internetdən məlumat toplamır; müşahidəni insan və ya gələcək kolleksiyaçı verir.
- Mənbəsiz müşahidə qəbul olunmur.
- `fact` statusunu yalnız insan verir. SCOUT öz müşahidəsini təsdiqləyə bilməz (`" scout"`, `"SCOUT"` kimi yazılışlarla da).
- Təsdiqlənmiş faktdan sonra fərqli müşahidə gəlsə, obyekt yenidən `claim` olur; fakt versiyası tarixçədə qalır.

## 6. Bilinən məhdudiyyətlər (növbəti mərhələlər)

| Məhdudiyyət | Nə vaxt həll olunur |
|---|---|
| Eyni `ordo.db` faylını yalnız **bir** ORDO prosesi açmalıdır. İkinci proses yazanda xəta alır (data pozulmur, amma işləmir) | Serverdə tək proses (1 worker) |
| `ordo.db` faylına diskdən birbaşa çatan şəxs bütün qaydaları keçir | Serverdə fayl icazələri (yalnız ORDO istifadəçisi) + şifrəli backup (həll olunub: `deploy/DEPLOY.md` → "Backup və bərpa") |
| API açarı oğurlansa, sahibi kimi işləmək olar. Açarlar müddətsizdir | Açarı ləğv et (`keys revoke`) və yenisini yarat; serverdə HTTPS tunel |
| `store.update_object(status="fact")` birbaşa çağırılsa, SCOUT-un insan təsdiqi qaydası keçilir | Mərhələ B: rollar (SCOUT rolu `fact` verə bilməz) |
| Sxem yalnız server kodunda (`sectors.py`) dəyişir, API ilə yox | Həll olunub |
| Silmə yoxdur; silmə siyasəti (cascade və ya qadağa) seçilməlidir | Ehtiyac yarananda |
| Status obyekt səviyyəsindədir, sahə səviyyəsində deyil | Real SCOUT datası göstərsə |
| Backup faylı açıq sertifikatla şifrələnir: serveri sındıran saxta (amma düzgün şifrəli) backup yarada bilər. Laptop hər faylı yoxlayır, amma datanın *doğruluğunu* yox, yalnız *tamlığını* | Qəbul edilib: server sındırılıbsa, onsuz da canlı baza onun əlindədir |
| Laptopdakı deşifrə açarı parolsuzdur (avtomatik yoxlama üçün); yalnız Windows istifadəçisi oxuya bilir | Laptopun diski şifrəli olmalıdır (BitLocker) |
| Tarixçə və `props` ölçüsü limitsizdir; `find` və `related` bütün obyektləri gəzir | DB: limitlər və indekslər |

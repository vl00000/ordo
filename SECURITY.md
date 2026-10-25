# Təhlükəsizlik

Hər kod dəyişikliyindən sonra layihə xarici hücumçu gözü ilə yoxlanıb: əvvəl gizli məlumat skanı, sonra hücum ssenariləri lokal mühitdə sınanıb, tapılanlar düzəldilib və testə çevrilib.

## Yoxlama tarixçəsi

| Tur | Sahə | Tapıntı | Nəticə |
|---|---|---|---|
| 1 | Nüvə | Boş və ya `None` tenant qəbul olunurdu | Düzəldildi + test |
| 2 | Nüvə | `props` içindəki siyahı kənardan dəyişdirilə bilirdi (shallow copy); `source` istənilən tip ola bilirdi | `deepcopy` + tip yoxlaması + test |
| 3 | SCOUT | Modul öz iddiasını `" scout"` / `"SCOUT"` yazılışı ilə `fact` edə bilirdi | Ad normallaşdırıldı + test |
| 4 | SQLite | SQL injection, atomiklik, iki proses eyni bazada | İnjection yoxdur (parametrli sorğular); tək proses qaydası |
| 5 | API | Lokal serverə 20 hücum: başqa tenant, body-də `tenant_id`, saxta açar, qəribə id, SQLi, 2 MB chunked sorğu, yalan `Content-Length`, 20 000 qat JSON | Hamısı dəf edildi; `--no-server-header` |
| 6 | Konteyner | Kənardan port skanı, konteyner qorumaları, restart sonrası data | Yalnız SSH açıq; data qalır |
| 7 | Backup | Root skriptinə symlink tələsi, zərərli SQLite faylı (view/trigger), dəyişdirilmiş və ya yanlış açarlı şifrəli fayl, qəribə fayl adları | Düzəldildi + test; semgrep-in 2 yalançı tapıntısı ayıklandı |
| 8 | Sərtləşdirmə | Açarlar müddətsiz idi; `scout` actor-u birbaşa `store` çağırışı ilə `fact` yarada və ya təsdiqlənmiş faktın datasını dəyişə bilirdi; PATCH ilə `props` və versiya sayı limitsiz böyüyürdü; çox dərin JSON; siyahı cavabları ölçüsüz idi | Açar müddəti (90 gün, ən çox 365), SCOUT qaydası nüvədə, `props` ≤ 32 KB, ≤ 10 000 versiya, `limit`/`offset` (≤ 1000). 23 PoC testi (`test_11_hardening.py`): köhnə kodda 22-si uğursuz olur |

## Qoruma qatları

**Tətbiq**
- Tenant və actor yalnız API açarından gəlir.
- Açarlar bazada yalnız həş kimi saxlanır, açar bir dəfə göstərilir, ləğv oluna bilər və müddəti bitir (`ORDO_KEY_MAX_DAYS`, standart 90 gün). Tarixi oxunmayan açar etibarsızdır.
- Avtomatik toplayıcı (`scout`) heç bir yolla `fact` statuslu versiya yarada bilməz: qayda API-də yox, nüvədədir.
- `props` 32 KB, obyekt başına 10 000 versiya, siyahı cavabları 1000 qeyd ilə məhdudlaşıb.
- Rollar: `reader` oxuyur, `writer` oxuyur və yazır.
- Başqa tenant-ın obyekti ilə mövcud olmayan obyekt eyni 404 cavabını verir (varlığı sızmır).
- Sorğu ölçüsü 64 KB ilə məhdudlaşıb (411/413). `/docs` və `/openapi.json` bağlıdır.

**Konteyner**
- Root olmayan istifadəçi, read-only fayl sistemi, `cap_drop: ALL`, `no-new-privileges`
- Yaddaş və proses limiti
- Port yalnız `127.0.0.1`-də açılır (Docker UFW-dan yan keçdiyi üçün `0.0.0.0` yazmaq olmaz)
- Qoşulma SSH tunel ilə; internetə heç bir ORDO portu açılmır

**Backup**
- Gündəlik SQLite backup API surəti, ayrıca şəbəkəsiz konteynerdə bərpa testi
- AES-256-GCM / RSA-OAEP ilə şifrələmə: serverdə yalnız açıq sertifikat var, deşifrə açarı serverdə yoxdur
- Server sındırılsa belə, köhnə backup-lar oxunmur

**Proses**
- gitleaks (gizli məlumat), semgrep, pip-audit
- Asılılıqların versiyaları sabitlənib

## Bilinən məhdudiyyətlər

- Oğurlanmış açar müddəti bitənə qədər işləyir; dərhal `keys revoke` ilə ləğv et.
- Bir bazanı yalnız bir proses açmalıdır (`--workers 1`); bu, dizayn qərarıdır.
- Rate limit yoxdur. Açarlar 256 bitdir, təxmin etmək mümkün deyil; xidmət yalnız SSH tunel arxasındadır.
- Silmə əməliyyatı yoxdur (tarixçə və audit tam qalsın deyə).
- Backup şifrəli faylın tamlığını yoxlayır, datanın doğruluğunu yox.
- `find` və `related` bütün obyektləri gəzir; çox böyük bazada indeks lazım olacaq.

Tam siyahı: `ORDO_SCHEMA.md`, 6-cı bölmə.

## Zəiflik bildirmək

Bu repo üzərindən issue açmayın; repo sahibinə şəxsi kanaldan yazın.

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

## Qoruma qatları

**Tətbiq**
- Tenant və actor yalnız API açarından gəlir.
- Açarlar bazada yalnız həş kimi saxlanır, açar bir dəfə göstərilir, ləğv oluna bilər.
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

- API açarları müddətsizdir; oğurlansa, `keys revoke` ilə ləğv et.
- Bir bazanı yalnız bir proses açmalıdır (`--workers 1`).
- `update_object(status="fact")` birbaşa çağırılsa SCOUT-un insan təsdiqi qaydası keçilir (modul gözləmədədir; gələcək addım: rollar).
- Silmə əməliyyatı yoxdur.
- Backup şifrəli faylın tamlığını yoxlayır, datanın doğruluğunu yox.

Tam siyahı: `ORDO_SCHEMA.md`, 6-cı bölmə.

## Zəiflik bildirmək

Bu repo üzərindən issue açmayın; repo sahibinə şəxsi kanaldan yazın.

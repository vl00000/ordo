# Dəyişikliklər

## v0.1.1 (2026-10-25) — sərtləşdirmə

- API açarlarının müddəti: yaradılandan 90 gün (`ORDO_KEY_MAX_DAYS`, 1–365). `keys list` bitmə tarixini göstərir.
- SCOUT qaydası nüvəyə köçdü: `scout` actor-u heç bir yolla `fact` versiyası yarada bilməz.
- Limitlər: `props` ≤ 32 KB, obyekt başına ≤ 10 000 versiya, çox dərin JSON rədd edilir.
- API: `GET /objects`, `/history`, `/related`, `/audit` üçün `limit` (1–1000, standart 100) və `offset`.
- 23 yeni test (`tests/test_11_hardening.py`), cəmi 163.
- CI: hər push-da `pytest` (GitHub Actions).

## v0.1 (2026-10-25) — serverdə işləyir

Mərhələlər:

1. **Nüvə məntiqi:** tiplər, obyektlər, əlaqələr, tenant izolyasiyası, audit
2. **Mərhələ A (boşluqların bağlanması):** update, versiya, toqquşma (`expected_version`), tip yoxlaması, tərs sorğu
3. **SQLite saxlama:** atomik yazılar, hər əməliyyat bir tranzaksiya
4. **HTTP API:** açarla giriş, rollar, ölçü limitləri
5. **Docker:** sərtləşdirilmiş konteyner, SSH tunel ilə qoşulma
6. **Avtomatik backup və bərpa testi:** şifrəli, gündəlik, bərpa sınağı ilə
7. **SCOUT v0.1:** `claim` → insan təsdiqi → `fact` axını (hazırda gözləmədə)

Hər mərhələdən sonra təhlükəsizlik yoxlaması aparılıb: bax `SECURITY.md`.

## Gələcək (təsdiqlənməyib)

Silmə siyasəti, indekslər, PostgreSQL.

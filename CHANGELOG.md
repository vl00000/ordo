# Dəyişikliklər

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

Test sayı: 140, hamısı keçir.

## Gələcək (təsdiqlənməyib)

Rollar (SCOUT `fact` verə bilməsin), silmə siyasəti, indekslər və limitlər, PostgreSQL.

# AI Coding Agent Rehberi

Bu projede görev alan AI coding agent'ları (Claude Code, Codex, Cursor vb.)
için katkı kuralları ve görev formatı. Oturum başında `CLAUDE.md` dosyasını
oku — proje haritası ve komutlar oradadır.

## Görev Verme Formatı

```text
Context:
Bu proje deterministic gamification engine projesidir. İş kuralları LLM'e
bırakılmaz. Mevcut mimari src/gamification_engine altında modülerdir.

Task:
[Sprint X kapsamında] [modül adı] içinde [değişiklik].

Constraints:
- Type hint zorunlu
- Docstring zorunlu
- ruff check + ruff format temiz
- mypy strict temiz
- Unit test zorunlu
- Deterministic output zorunlu
- Existing patterns korunacak

Deliverables:
- Oluşturulacak/güncellenecek dosyalar
- Test dosyaları
- Kabul kriterleri

Do not:
- İş kurallarını başka modüllere yayma
- eval kullanma
- Random veya sistem saati kullanma (run_date esastır)
- Ledger update/delete yapma
```

## Değiştirilemez Kurallar

1. **Determinizm:** `random`, `datetime.now()`/`date.today()` iş mantığında
   kullanılamaz. ID'ler SHA-256 ile deterministik üretilir. Her sıralamada
   açık tie-break olmalı.
2. **Append-only ledger:** `ledger.json` girdileri asla güncellenmez veya
   silinmez; yalnızca eklenir.
3. **Güvenli kurallar:** Koşullar yalnızca `rules/condition_parser.py`
   üzerinden ayrıştırılır; alan whitelist'i `DailyUserState.to_rule_context()`.
4. **LLM sınırı:** LLM yalnızca `LLMAdapter.enhance()` üzerinden cevabı
   yeniden ifade eder. Ortam değişkenleri yalnızca `config/llm_config.py`
   içinde okunur.
5. **Katman sorumlulukları:** `domain` iş kuralı çalıştırmaz; `pipeline`
   iş kuralı içermez; `export` hesaplama yapmaz.

## Değişiklik Yaparken

- Testler `tests/` altında src yapısını aynalar; yeni modül = yeni test
  dosyası.
- İş kuralı değişikliği golden testleri kırar — bu **beklenen** davranıştır.
  Bilinçliyse goldenları yeniden üret (süreç:
  `docs/testing_and_determinism.md`), aynı commit'te gönder.
- Yeni challenge/rozet/koşul alanı ekleme adımları: `docs/rule_engine.md`.
- Kalite kapısı (hepsi geçmeli):

```bash
ruff check src tests && ruff format --check src tests && mypy && pytest
```

- Commit'ler `Implement Sprint N: ...` veya kısa açıklayıcı başlık; golden
  güncellemeleri gerekçesiyle commit mesajında belirtilir.

## Sık Yapılan Hatalar

| Hata | Doğrusu |
|---|---|
| Testte gerçek LLM çağrısı | `FakeLLMAdapter` veya `GAMIFICATION_LLM_ENABLED=0` |
| `os.environ` okumayı modüle gömme | `config/llm_config.py`'ye ekle |
| Sıralamayı `dict` iterasyon sırasına bırakma | Açık `sorted(..., key=...)` + tie-break |
| Golden dosyayı elle düzenleme | Pipeline'ı çalıştırıp çıktıyı kopyala |
| `# type: ignore` ile mypy susturma | Tipi düzelt; ignore yalnızca test decorator sınırlarında |

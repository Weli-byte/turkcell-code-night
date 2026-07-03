# AI Explanation Layer

Bu doküman, oyunlaştırma motorunun açıklama katmanının mimarisini, opsiyonel
LLM adapter yapısını, prompt sözleşmesini ve guardrail'leri tanımlar.

## Temel İlke

**Sistem LLM olmadan tam ve deterministik çalışır.** LLM katmanı yalnızca
kural motorunun ürettiği deterministik cevabı dilsel olarak yeniden ifade
eden opsiyonel bir kabuktur. Puan, rozet, sıralama veya herhangi bir iş
kararı hiçbir koşulda LLM'e devredilmez.

## Mimari

```text
soru ──> explanation_engine (deterministik)
              │
              ▼
        ExplanationResponse          ← her zaman üretilir, otoriter cevap
              │
              ▼
        LLMAdapter.enhance()         ← opsiyonel dilsel iyileştirme
              │
   ┌──────────┴──────────┐
   │ başarı              │ hata / kapalı / boş cevap
   ▼                     ▼
yeniden yazılmış     deterministik cevap
cevap                aynen döner (fallback)
```

### Modüller

| Modül | Sorumluluk |
|---|---|
| `ai/explanation_engine.py` | Deterministik, template tabanlı cevap üretimi (intent → template + evidence) |
| `ai/templates.py` | Deterministik cevap şablonları |
| `ai/llm_adapter.py` | `LLMAdapter` arayüzü, `NoOpLLMAdapter`, `GeminiLLMAdapter`, `OpenAILLMAdapter`, factory'ler |
| `ai/llm_client.py` | Saf HTTP transport ve prompt sözleşmesi; provider seçimi veya karar mantığı içermez |
| `config/llm_config.py` | Ortam değişkenlerinin okunduğu **tek** yer; `LLMConfig` üretir |

### LLMAdapter Sözleşmesi

```python
class LLMAdapter(ABC):
    def enhance(self, response: ExplanationResponse) -> ExplanationResponse: ...
```

Bir adapter implementasyonu:

- `user_id`, `question` ve `evidence` alanlarını **asla değiştiremez**;
  yalnızca `answer` alanını yeniden ifade edilmiş metinle değiştirebilir.
- Herhangi bir hata (bağlantı, timeout, geçersiz payload) veya boş LLM
  çıktısında orijinal `ExplanationResponse` nesnesini **aynen** döndürür.
- İş kararı üretemez: yeni puan, rozet, rank veya kural uyduramaz.

`NoOpLLMAdapter` kapalı moddur: cevabı hiç dokunmadan döndürür ve
deterministik motorla bayt düzeyinde aynı çıktıyı garanti eder.

## Konfigürasyon

Ortam değişkenleri yalnızca `config/llm_config.py` içinde okunur:

| Değişken | Anlamı |
|---|---|
| `GAMIFICATION_LLM_ENABLED` | Kill switch. `0`, `false`, `no`, `off` → API anahtarları mevcut olsa bile LLM tamamen kapalı. |
| `GEMINI_API_KEY` | Google Gemini anahtarı. İki anahtar da varsa **Gemini öncelikli**dir. |
| `OPENAI_API_KEY` | OpenAI anahtarı. |

Hiçbir anahtar yoksa veya kill switch aktifse factory `NoOpLLMAdapter`
döndürür; sistem deterministik modda çalışır.

Testlerde gerçek API'ye ihtiyaç yoktur: `LLMAdapter` arayüzünü uygulayan bir
fake adapter enjekte edilir (bkz. `tests/unit/ai/test_llm_adapter.py`).

## Prompt Sözleşmesi (Prompt Contract)

LLM'e gönderilen sistem prompt'u (`ai/llm_client.py` → `SYSTEM_PROMPT`)
şu kuralları dayatır:

1. **Veri değişmezliği:** Kural motorunun kararı, sayısal veriler, tarihler
   ve puanlar asla değiştirilemez; yeni kural veya veri uydurulamaz.
2. **Sadece yeniden ifade:** Cevap daha akıcı ve doğal Türkçe ile yeniden
   yazılır; anlam korunur.
3. **Fallback mesajları korunur:** Bilinmeyen soru/hata mesajları anlam
   bozulmadan iletilir.
4. **Sade çıktı:** Yalnızca yeniden yazılmış cevap döndürülür; giriş,
   açıklama veya ek yorum eklenmez.

Kullanıcı prompt'u üç deterministik alan içerir: kullanıcının sorusu, kural
motorunun cevabı ve JSON evidence. LLM'in görebildiği tek veri budur.

## Guardrail'ler

| Guardrail | Uygulama noktası |
|---|---|
| LLM kapalıyken tam çalışma | `NoOpLLMAdapter` + factory; anahtar yoksa devreye girer |
| Hata durumunda deterministik fallback | `_RephrasingLLMAdapter.enhance` yalnızca `OSError`/`ValueError` yakalar ve orijinal cevabı döndürür |
| Boş LLM çıktısı reddedilir | Boş/whitespace cevap orijinali değiştirmez |
| Evidence dokunulmazlığı | Adapter yalnızca `answer` alanını değiştirir |
| Sadece HTTPS | `_post_https_json` şemayı istekten önce doğrular |
| Düşük yaratıcılık | `temperature=0.2` |
| Zaman sınırı | 5 sn timeout (config üzerinden ayarlanabilir) |

## Yeni Provider Ekleme

1. `ai/llm_client.py` içine `call_<provider>_api(...)` transport fonksiyonu
   ekle (yalnızca HTTP + payload parse; `ValueError`/`OSError` fırlatır).
2. `ai/llm_adapter.py` içinde `_RephrasingLLMAdapter`'ı genişleten bir
   adapter sınıfı yaz (`_rephrase` metodunu doldur).
3. `config/llm_config.py` içindeki `LLMProvider` enum'ına değeri ekle ve
   `llm_config_from_env` önceliklendirmesini güncelle.
4. `create_llm_adapter` factory'sine eşlemeyi ekle.
5. `tests/unit/ai/test_llm_adapter.py` içine başarı + fallback testleri yaz.

## LLM Çıktı Loglama Kararı

MVP'de LLM çıktısı loglanmaz; `explain` komutunun stdout çıktısı tek
kayıttır. İleride loglama eklenirse deterministik cevap ile LLM cevabı
yan yana saklanmalıdır (denetlenebilirlik için).

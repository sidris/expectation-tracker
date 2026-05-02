# Expectation Tracker

Streamlit + Supabase tabanlı enflasyon ve PPK beklenti takip sistemi.

## Özellikler

- Kişi, kurum ve medya/anket kaynağı takibi
- Aylık TÜFE, yıllık TÜFE, yıl sonu TÜFE, PPK ve yıl sonu PPK tahminleri
- Aynı katılımcının aynı hedef için birden fazla tahminini revizyon olarak saklama
- Reuters/Matriks tarzı anket özeti + tek tek kurum cevaplarını aynı ekrandan girme
- Dashboard, trend, hata ısı haritası, boxplot ve madalya kürsüsü
- Veri havuzu ve Excel export
- EVDS/BIS gerçekleşme senkronizasyonu
- GitHub Actions ile günlük otomatik gerçekleşme sync seçeneği
- Telegram bot başlangıç dosyası

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Secrets

`.streamlit/secrets.toml` veya Streamlit Cloud Secrets:

```toml
SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY="YOUR_SUPABASE_ANON_OR_PUBLISHABLE_KEY"

EVDS_API_KEY="YOUR_EVDS_API_KEY"
EVDS_TUFE_OLD="TP.FE.OKTG01"
EVDS_TUFE_NEW="TP.FE.OKTG01"
```

## Supabase

Yeni kurulumda:

1. `supabase/reset_dev.sql` çalıştır.
2. `supabase/schema.sql` çalıştır.

Mevcut v7/v8 projesinden geliyorsan veri silmeden:

1. `supabase/migration_v9.sql` çalıştır.

## GitHub Actions ile otomatik EVDS/BIS sync

Repo Settings → Secrets and variables → Actions içine şunları ekle:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `EVDS_API_KEY`
- `EVDS_TUFE_OLD`
- `EVDS_TUFE_NEW`

Workflow: `.github/workflows/sync_actuals.yml`

Her gün çalışır. İstersen GitHub Actions sekmesinden manuel de çalıştırabilirsin.

## Reuters/Matriks tarzı anket girişi

1. Katılımcılar sayfasında kurumları ekle: Albaraka, QNB, Deutsche Bank vb.
2. Kaynaklar sayfasında Reuters, Bloomberg HT, Matriks vb. ekle.
3. `Anket + Kurum Toplu Girişi` sayfasında:
   - Anket özetini gir: min, max, medyan, ortalama
   - Alt kırılımda kurum değerlerini gir
4. Sistem hem `poll_summaries` hem de bağlı `forecasts` kayıtlarını oluşturur.

## Revizyon mantığı

Aynı kişi/kurum aynı hedef dönem ve gösterge için farklı tarihlerde tahmin verdiğinde ayrı kayıt tutulur:

- 2026-04-11: yıl sonu TÜFE 28
- 2026-04-18: yıl sonu TÜFE 30

`Revizyon Takibi` sayfası bunları çizgi grafik ve ısı haritası olarak gösterir.

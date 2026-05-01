# Beklenti Takip Sistemi v5

Streamlit + Supabase ile enflasyon ve TCMB PPK faiz beklentilerini toplama, filtreleme, Excel dışa aktarma, modern dashboard, revizyon takibi, konsensüs analizi, kaynak güven skoru, tahminci profili, ham metinden tahmin çıkarma ve Telegram bot başlangıcı.

## Kurulum

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

## Supabase

`supabase/schema.sql` dosyasını Supabase SQL Editor'da çalıştırın. Mevcut projede yeniden çalıştırılabilir şekilde `if not exists` ve `create or replace view` kullanılmıştır.

## v5 ekleri

- Revizyon takibi: aynı kişi/kurumun aynı dönem için değişen tahminleri
- Tahminci profili: toplam tahmin, skorlanan tahmin, ortalama hata, geçmiş grafik
- Konsensüs sapması: ortalama/medyan beklentiden fark
- Kaynak güven skoru: manuel kaynak değerlendirmesi + gerçekleşmeye göre hata
- Metinden tahmin çıkarma: haber/TV notundan ön ayrıştırma
- Aktivite akışı: son işlemler ve notlar
- Telegram bot başlangıcı: `/expect 2026-03 monthly_cpi`, `/top`

## Telegram bot

```bash
export SUPABASE_URL="..."
export SUPABASE_KEY="..."
export TELEGRAM_BOT_TOKEN="..."
python telegram_bot/bot.py
```

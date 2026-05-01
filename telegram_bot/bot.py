"""Telegram bot başlangıç dosyası.
Komut örnekleri:
/expect 2026-03 monthly_cpi
/top year_end_cpi
"""
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

async def expect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("Kullanım: /expect 2026-03 [monthly_cpi|year_end_cpi|policy_rate]")
        return
    period = context.args[0] + "-01"
    target_type = context.args[1] if len(context.args) > 1 else None
    q = sb.table("v_forecasts").select("participant_name,target_type,forecast_value,forecast_date,source_name").eq("target_period", period)
    if target_type:
        q = q.eq("target_type", target_type)
    rows = q.limit(20).execute().data
    if not rows:
        await update.message.reply_text("Kayıt bulunamadı.")
        return
    msg = "\n".join([f"{r['participant_name']} | {r['target_type']} | {r['forecast_value']} | {r.get('forecast_date')}" for r in rows])
    await update.message.reply_text(msg[:3900])

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = sb.table("v_leaderboard").select("participant_name,avg_abs_error,scored_forecasts").limit(10).execute().data
    msg = "🏅 En iyi tahminciler\n" + "\n".join([f"{i+1}. {r['participant_name']} | hata: {r['avg_abs_error']} | n={r['scored_forecasts']}" for i, r in enumerate(rows)])
    await update.message.reply_text(msg[:3900])

if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("expect", expect))
    app.add_handler(CommandHandler("top", top))
    app.run_polling()

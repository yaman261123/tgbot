async def sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen sorgulanacak domaini girin.\nÖrnek: `/sorgula example.com`", parse_mode="Markdown")
        return
    
    domain = context.args[0].lower().replace("https://", "").replace("http://", "").strip("/")
    await update.message.reply_text(f"🔍 `{domain}` için BTK sorgusu yapılıyor, lütfen bekleyin...", parse_mode="Markdown")
    
    result = btk_sorgula(domain)
    await update.message.reply_text(f"🌐 **Domain:** `{domain}`\n📋 **Sonuç:** {result}", parse_mode="Markdown")

if __name__ == '__main__':
    BOT_TOKEN = "7957246046:AAfVn5_6tvWCC9DidW6YUR7ak709jJsFc9Q"
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komutların Eklenmesi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ekle", ekle))
    app.add_handler(CommandHandler("sil", sil))
    app.add_handler(CommandHandler("liste", liste))
    app.add_handler(CommandHandler("durum", durum))
    app.add_handler(CommandHandler("bildirim", bildirim))
    app.add_handler(CommandHandler("sorgula", sorgula))  # <-- BURA EKLENDİ

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(ototakip_job, interval=900, first=10)

    print("Bot başlatılıyor...")
    app.run_polling()

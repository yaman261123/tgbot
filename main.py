import asyncio
import logging
import requests
from bs4 import BeautifulSoup
import io
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# OCR kütüphanesi yoksa botun çökmemesi için try-except
try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

user_data = {}

def btk_sorgula(domain: str) -> str:
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # PythonAnywhere engelini aşmak için harici bir proxy tüneli
    proxy_url = "http://pubproxy.com/api/proxy?country=TR&type=http"
    
    try:
        # Önce çalışan bir TR proxy almayı dener
        proxy_res = requests.get(proxy_url, timeout=5).json()
        proxy_ip = proxy_res['data'][0]['ipPort']
        proxies = {"http": f"http://{proxy_ip}", "https": f"http://{proxy_ip}"}
    except:
        proxies = None

    try:
        main_url = "https://internet.btk.gov.tr/sitesorgu/"
        response = session.post(
            main_url, 
            data={"deger": domain, "submit1": "Sorgula"}, 
            headers=headers, 
            proxies=proxies, 
            timeout=15
        )
        soup = BeautifulSoup(response.text, 'html.parser')
        karar_div = soup.find("div", class_="kararSonucInner")
        
        if karar_div:
            return karar_div.get_text(strip=True)
        return "Uygulanan bir karar bulunamadı veya siteye erişim sağlanıyor."
    except Exception as e:
        return f"Sorgu hatası (Proxy/Bağlantı): {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 **BTK Domain Takip Botuna Hoşgeldiniz!**\n\n"
        "**Kullanılabilir Komutlar:**\n"
        "• `/ekle <domain>` - Listeye yeni domain ekler.\n"
        "• `/sil <domain>` - Domaini listeden çıkarır.\n"
        "• `/liste` - Takip edilen tüm domainleri listeler.\n"
        "• `/durum` - Tüm domainlerin son durumunu gösterir.\n"
        "• `/sorgula <domain>` - Anlık BTK sorgusu yapar.\n"
        "• `/bildirim` - Değişiklik bildirim modunu açar/kapatır."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen bir domain belirtin.\nÖrnek: `/ekle example.com`", parse_mode="Markdown")
        return

    domain = context.args[0].lower().replace("https://", "").replace("http://", "").strip("/")
    
    if chat_id not in user_data:
        user_data[chat_id] = {"domains": {}, "only_changes": False}
        
    user_data[chat_id]["domains"][domain] = "Henüz kontrol edilmedi"
    await update.message.reply_text(f"✅ `{domain}` takip listesine eklendi.", parse_mode="Markdown")

async def sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen silinecek domaini belirtin.\nÖrnek: `/sil example.com`", parse_mode="Markdown")
        return

    domain = context.args[0].lower().replace("https://", "").replace("http://", "").strip("/")
    
    if chat_id in user_data and domain in user_data[chat_id]["domains"]:
        del user_data[chat_id]["domains"][domain]
        await update.message.reply_text(f"🗑️ `{domain}` takip listenizden silindi.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Bu domain takip listenizde bulunamadı.")

async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_data or not user_data[chat_id]["domains"]:
        await update.message.reply_text("📋 Takip listenizde henüz hiçbir domain yok.")
        return

    domains_text = "\n".join([f"• `{d}`" for d in user_data[chat_id]["domains"].keys()])
    await update.message.reply_text(f"📋 **Takip Edilen Domainler:**\n\n{domains_text}", parse_mode="Markdown")

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_data or not user_data[chat_id]["domains"]:
        await update.message.reply_text("📋 Takip listenizde domain bulunmuyor.")
        return

    report = "📊 **Domainlerin Son Durumu:**\n\n"
    for domain, status in user_data[chat_id]["domains"].items():
        report += f"🌐 `{domain}`\n🔍 **Durum:** {status}\n-------------------\n"
    
    await update.message.reply_text(report, parse_mode="Markdown")

async def sorgula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Lütfen sorgulanacak domaini girin.\nÖrnek: `/sorgula example.com`", parse_mode="Markdown")
        return
    
    domain = context.args[0].lower().replace("https://", "").replace("http://", "").strip("/")
    await update.message.reply_text(f"🔍 `{domain}` için BTK sorgusu yapılıyor...", parse_mode="Markdown")
    
    result = btk_sorgula(domain)
    await update.message.reply_text(f"🌐 **Domain:** `{domain}`\n📋 **Sonuç:** {result}", parse_mode="Markdown")

async def bildirim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"domains": {}, "only_changes": False}

    current_mode = user_data[chat_id]["only_changes"]
    user_data[chat_id]["only_changes"] = not current_mode
    
    status_str = "Sadece Durum Değişikliklerinde" if not current_mode else "Her 15 Dakikada Bir Her Durumda"
    await update.message.reply_text(f"🔔 Bildirim modu değiştirildi:\n**Yeni Mod:** {status_str}", parse_mode="Markdown")

async def ototakip_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id, data in user_data.items():
        for domain, old_status in list(data["domains"].items()):
            new_status = btk_sorgula(domain)
            only_changes = data.get("only_changes", False)
            
            if only_changes:
                if old_status != new_status and old_status != "Henüz kontrol edilmedi":
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🚨 **DURUM DEĞİŞİKLİĞİ DETEKTED!**\n\n🌐 `{domain}`\n❌ **Eski:** {old_status}\n✅ **Yeni:** {new_status}",
                        parse_mode="Markdown"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ **15 Dakikalık Otomatik Kontrol**\n\n🌐 `{domain}`\n🔍 **Sonuç:** {new_status}",
                    parse_mode="Markdown"
                )
            data["domains"][domain] = new_status

if __name__ == '__main__':
    BOT_TOKEN = "7957246046:AAFVn5_6tVWCC9DidW6YUR7ak7O9jJsFc9Q"
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ekle", ekle))
    app.add_handler(CommandHandler("sil", sil))
    app.add_handler(CommandHandler("liste", liste))
    app.add_handler(CommandHandler("durum", durum))
    app.add_handler(CommandHandler("bildirim", bildirim))
    app.add_handler(CommandHandler("sorgula", sorgula))

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(ototakip_job, interval=900, first=10)

    print("Bot başlatılıyor...")
    app.run_polling()

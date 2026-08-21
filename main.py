import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import pytesseract
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Logging yapılandırması
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bellekte kullanıcı verilerini tutan sözlük
# Format: { chat_id: { "domains": { "domain.com": "Son Karar Durumu" }, "only_changes": True/False } }
user_data = {}

def btk_sorgula(domain: str) -> str:
    """
    BTK sitesinden domain sorgusu yapar.
    CAPTCHA görselini indirip OCR ile okumaya çalışır.
    """
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # 1. Ana sayfayı çek
        main_url = "https://internet.btk.gov.tr/sitesorgu/"
        res = session.get(main_url, headers=headers, timeout=10)
        
        # 2. Captcha görselini indir
        captcha_url = f"https://internet.btk.gov.tr/sitesorgu/secureimage/captcha.php"
        captcha_res = session.get(captcha_url, headers=headers, timeout=10)
        
        # OCR ile Güvenlik Kodunu Okuma
        image = Image.open(io.BytesIO(captcha_res.content))
        captcha_code = pytesseract.image_to_string(image, config='--psm 6 digits').strip()
        
        # 3. Form verilerini hazırla ve POST isteği at
        payload = {
            "deger": domain,
            "security_code": captcha_code,
            "submit1": "Sorgula",
            "ayrintili": "0"
        }
        
        response = session.post(main_url, data=payload, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 4. Karar sonucunu çek
        karar_div = soup.find("div", class_="kararSonucInner")
        if karar_div:
            return karar_div.get_text(strip=True)
        else:
            return "Sonuç alınamadı veya güvenlik kodu hatalı girildi."
            
    except Exception as e:
        return f"Sorgulama sırasında hata oluştu: {str(e)}"

# --- KOMUT İŞLEYİCİLERİ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 **BTK Domain Takip Botuna Hoşgeldiniz!**\n\n"
        "**Kullanılabilir Komutlar:**\n"
        "• `/ekle <domain>` - Listeye yeni domain ekler.\n"
        "• `/sil <domain>` - Domaini listeden çıkarır.\n"
        "• `/liste` - Takip edilen tüm domainleri listeler.\n"
        "• `/durum` - Tüm domainlerin son durumunu gösterir.\n"
        "• `/sorgula <domain>` - Anlık BTK sorgusu yapar.\n"
        "• `/bildirim` - Sadece durum değişikliğinde bildirim alma modunu açar/kapatır."
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

async def bildirim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {"domains": {}, "only_changes": False}

    current_mode = user_data[chat_id]["only_changes"]
    user_data[chat_id]["only_changes"] = not current_mode
    
    status_str = "Sadece Durum Değişikliklerinde" if not current_mode else "Her 15 Dakikada Bir Her Durumda"
    await update.message.reply_text(f"🔔 Bildirim modu değiştirildi:\n**Yeni Mod:** {status_str}", parse_mode="Markdown")

async def ototakip_job(context: ContextTypes.DEFAULT_TYPE):
    """Her 15 dakikada bir otomatik çalışan arka plan görevi."""
    for chat_id, data in user_data.items():
        for domain, old_status in list(data["domains"].items()):
            new_status = btk_sorgula(domain)
            
            only_changes = data.get("only_changes", False)
            
            # Sadece değişiklik bildirimi açık ise ve durum değiştiyse mesaj at
            if only_changes:
                if old_status != new_status and old_status != "Henüz kontrol edilmedi":
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🚨 **DURUM DEĞİŞİKLİĞİ DETEKTED!**\n\n🌐 `{domain}`\n❌ **Eski:** {old_status}\n✅ **Yeni:** {new_status}",
                        parse_mode="Markdown"
                    )
            else:
                # Her durumda bilgilendir
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ **15 Dakikalık Otomatik Kontrol**\n\n🌐 `{domain}`\n🔍 **Sonuç:** {new_status}",
                    parse_mode="Markdown"
                )
            
            # Durumu güncelle
            data["domains"][domain] = new_status

if __name__ == '__main__':
    BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Komutların Eklenmesi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ekle", ekle))
    app.add_handler(CommandHandler("sil", sil))
    app.add_handler(CommandHandler("liste", liste))
    app.add_handler(CommandHandler("durum", durum))
    app.add_handler(CommandHandler("bildirim", bildirim))

    # 15 dakikada bir (900 saniye) çalışan zamanlayıcı
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(ototakip_job, interval=900, first=10)

    print("Bot başlatılıyor...")
    app.run_polling()

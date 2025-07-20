from dotenv import load_dotenv
import os
import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_URL = os.getenv("SHEET_URL")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_url(SHEET_URL)

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}


def get_monthly_sheet():
    bulan_mapping = {
        "01": "Januari",
        "02": "Februari",
        "03": "Maret",
        "04": "April",
        "05": "Mei",
        "06": "Juni",
        "07": "Juli",
        "08": "Agustus",
        "09": "September",
        "10": "Oktober",
        "11": "November",
        "12": "Desember",
    }
    bulan_str = datetime.now().strftime("%m")
    nama_sheet = bulan_mapping[bulan_str]

    try:
        worksheet = spreadsheet.worksheet(nama_sheet)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=nama_sheet, rows="1000", cols="100")
        worksheet.append_row(["Waktu", "Kategori", "Jumlah", "Catatan"])

    return worksheet


@bot.message_handler(commands=["start"])
def catat_pengeluaran(message):
    markup = types.InlineKeyboardMarkup()
    kategori_list = ["Makan", "Jajan", "Hiburan", "Transportasi", "Bulanan", "Lainnya"]
    for kategori in kategori_list:
        markup.add(
            types.InlineKeyboardButton(kategori, callback_data=f"catat_{kategori}")
        )
    markup.add(
        types.InlineKeyboardButton(
            "Lihat Pengeluaran Hari Ini", callback_data="lihat_hari_ini"
        )
    )
    bot.send_message(
        message.chat.id, "Pilih kategori pengeluaran:", reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("catat_"))
def handle_kategori(call):
    kategori = call.data.split("_")[1]
    user_data[call.from_user.id] = {"kategori": kategori}
    msg = bot.send_message(
        call.message.chat.id,
        f"Kategori: {kategori}\nMasukkan jumlah pengeluaran",
        reply_markup=types.ForceReply(selective=False),
    )
    bot.register_next_step_handler(msg, handle_jumlah)


def handle_jumlah(message):
    try:
        jumlah = float(message.text.replace(",", "").replace(".", ""))
        user_id = message.from_user.id
        user_data[user_id]["jumlah"] = jumlah

        msg = bot.send_message(
            message.chat.id,
            "Masukkan catatan",
            reply_markup=types.ForceReply(selective=False),
        )
        bot.register_next_step_handler(msg, handle_catatan)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Harus berupa angka. Coba lagi:")
        bot.register_next_step_handler(message, handle_jumlah)


def handle_catatan(message):
    user_id = message.from_user.id
    catatan = message.text
    data = user_data.get(user_id, {})
    data["catatan"] = catatan
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        sheet = get_monthly_sheet()
        sheet.append_row(
            [
                data["timestamp"],
                data["kategori"],
                data["jumlah"],
                data["catatan"],
            ]
        )
        bot.send_message(
            message.chat.id,
            f"✅ Tersimpan:\n📅 {data['timestamp']}\n🗂 {data['kategori']}\n💰 Rp. {data['jumlah']}\n📝 {data['catatan']}",
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Gagal menyimpan ke spreadsheet.\n{e}")
    user_data.pop(user_id, None)


@bot.callback_query_handler(func=lambda call: call.data == "lihat_hari_ini")
def handle_lihat_pengeluaran(call):
    sheet = get_monthly_sheet()
    today_str = datetime.now().strftime("%Y-%m-%d")

    rows = sheet.get_all_records()
    result = []
    total = 0

    for row in rows:
        tanggal = row.get("Tanggal", "")[:10]
        if tanggal == today_str:
            kategori = row.get("Kategori", "")
            jumlah = row.get("Jumlah", "0")
            catatan = row.get("Catatan", "")
            jumlah_clean = jumlah.replace("Rp", "").replace(",", "").strip()
            try:
                total += float(jumlah_clean)
            except:
                pass

            result.append(f"- {kategori}: Rp{jumlah_clean} ({catatan})")

    if result:
        response = "\n".join(result)
        response += f"\n\n🧾 Total: Rp. {int(total)}"
    else:
        response = "📭 Belum ada pengeluaran hari ini."

    bot.send_message(call.message.chat.id, response)


bot.infinity_polling()

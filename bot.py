import os
import json
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

# ضع التوكن الخاص بك هنا
BOT_TOKEN = "8221232809:AAG4prWFuna6mqFm0enoo3CB01iCI-Irptk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def load_quiz_database():
    with open("questions.json", "r", encoding="utf-8") as f:
        return json.load(f)

quiz_db = load_quiz_database()

@dp.message(Command("export_1", "export_2", "export_3", "export_4"))
async def export_polls(message: Message):
    part_key = message.text.replace("/export_", "quiz_").split("@")[0].strip()
    questions = quiz_db.get(part_key, [])
    total = len(questions)
    
    await message.answer(f"⏳ جاري إرسال {total} سؤال تلقائياً...")
    
    for idx, q in enumerate(questions):
        q_text = q.get("question") or q.get("q")
        opts = q.get("options") or q.get("o")
        correct_id = q.get("correct_option_id") if "correct_option_id" in q else q.get("c")
        
        try:
            await bot.send_poll(
                chat_id=message.chat.id,
                question=f"Q{idx + 1}/{total}: {q_text}",
                options=opts,
                type="quiz",
                correct_option_id=correct_id,
                is_anonymous=False
            )
            # فاصل زمني ثانية واحدة لاحترام قوانين تيليجرام
            await asyncio.sleep(1.2)
        except Exception:
            await asyncio.sleep(3)
            
    await message.answer(f"✅ تم الانتهاء بنجاح! حدد الأسئلة الآن وقم بعمل Forward لها إلى @QuizBot.")

async def health_handler(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

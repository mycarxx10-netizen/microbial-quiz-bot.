import os
import json
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, PollAnswer
from aiogram.filters import Command

BOT_TOKEN = "8601813721:AAGzvfJP2nDeqzkNSpeb2yx9phvHXSeMKz4"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def load_questions():
    with open("questions.json", "r", encoding="utf-8") as f:
        return json.load(f)

questions = load_questions()

user_progress = {}
poll_to_user = {}

async def send_next_question(chat_id: int, user_id: int):
    idx = user_progress.get(user_id, 0)
    if idx >= len(questions):
        await bot.send_message(
            chat_id, 
            "🎉 أحسنت! أنهيت بنك الأسئلة بالكامل.\nلإعادة الاختبار أرسل /quiz من جديد."
        )
        user_progress[user_id] = 0
        return

    q = questions[idx]
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"[{idx + 1}/{len(questions)}] {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct_option_id"],
        is_anonymous=False
    )
    poll_to_user[msg.poll.id] = (chat_id, user_id)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 مرحباً بك في اختبار **Microbial Diversity**!\n"
        "أرسل /quiz للبدء في الاختبار.\n"
        "أرسل /stop لإلغاء الاختبار في أي وقت."
    )

@dp.message(Command("quiz"))
async def cmd_quiz(message: Message):
    user_progress[message.from_user.id] = 0
    await send_next_question(message.chat.id, message.from_user.id)

# أمر إلغاء الاختبار
@dp.message(Command("stop", "cancel"))
async def cmd_stop(message: Message):
    user_id = message.from_user.id
    user_progress[user_id] = len(questions)  # إنهاء الجلسة
    # إزالة أي سؤال معلق للمستخدم
    keys_to_del = [k for k, v in poll_to_user.items() if v[1] == user_id]
    for k in keys_to_del:
        poll_to_user.pop(k, None)
    await message.answer("🛑 تم إلغاء الاختبار بنجاح! للبدء مجدداً أرسل /quiz.")

@dp.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    user_id = poll_answer.user.id
    poll_id = poll_answer.poll_id
    
    if poll_id in poll_to_user:
        chat_id, _ = poll_to_user.pop(poll_id)
        user_progress[user_id] = user_progress.get(user_id, 0) + 1
        await asyncio.sleep(1.2)
        await send_next_question(chat_id, user_id)

async def health_handler(request):
    return web.Response(text="Bot is healthy and running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    print("جاري تشغيل البوت وخادم المراقبة...")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

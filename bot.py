import os
import json
import random
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, PollAnswer
from aiogram.filters import Command

# ضع التوكن الجديد الذي حصلت عليه بعد عمل Revoke هنا
BOT_TOKEN = "8601813721:AAGsnFO8LwzpgHlKh9hM0Px7MJu9C0BT4JI"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# قفل غير متزامن لمنع معالجة الطلبات المكررة في نفس اللحظة
chat_locks = {}

def get_chat_lock(chat_id: int) -> asyncio.Lock:
    if chat_id not in chat_locks:
        chat_locks[chat_id] = asyncio.Lock()
    return chat_locks[chat_id]

def load_quiz_database() -> dict:
    with open("questions.json", "r", encoding="utf-8") as f:
        return json.load(f)

quiz_db = load_quiz_database()

QUIZ_TITLES = {
    "quiz_1": "Lecture 1 (Cell Biology)",
    "quiz_2": "Lecture 2 (Microbial Diversity)",
    "quiz_3": "Lecture 3 (Principles of Microscopy)",
    "quiz_4": "Lecture 4 (Classification of Microorganisms)"
}

OPTION_LETTERS = ["A", "B", "C", "D"]

active_sessions = {}
poll_to_chat = {}

async def send_next_question(chat_id: int):
    session = active_sessions.get(chat_id)
    if not session:
        return

    part = session["part"]
    idx = session["index"]
    questions = session["questions"]
    total = len(questions)

    # التحقق من نهاية الاختبار
    if idx >= total:
        score = session["score"]
        pct = round((score / total) * 100, 1)
        title = QUIZ_TITLES.get(part, part)

        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"اكتمل الاختبار: {title}\n\n"
                f"النتيجة النهائية:\n"
                f"{score} من {total} ({pct}%)\n\n"
                f"للبدء من جديد: /start"
            )
        )
        active_sessions.pop(chat_id, None)
        return

    q = session["questions"][idx]
    q_text = q.get("question") or q.get("q")
    opts = q.get("options") or q.get("o")
    correct_id = q.get("correct_option_id") if "correct_option_id" in q else q.get("c")

    msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"Q{idx + 1}/{total}: {q_text}",
        options=opts,
        type="quiz",
        correct_option_id=correct_id,
        is_anonymous=False
    )
    poll_to_chat[msg.poll.id] = (chat_id, idx)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    async with get_chat_lock(message.chat.id):
        await message.answer(
            "قائمة الاختبارات المتاحة:\n\n"
            "/quiz_1 : Lecture 1 (137 سؤال)\n"
            "/quiz_2 : Lecture 2 (46 سؤال)\n"
            "/quiz_3 : Principles of Microscopy (19 سؤال)\n"
            "/quiz_4 : Classification of Microorganisms (63 سؤال)\n\n"
            "للإلغاء: /stop"
        )

@dp.message(Command("quiz_1", "quiz_2", "quiz_3", "quiz_4"))
async def handle_quiz(message: Message):
    chat_id = message.chat.id
    async with get_chat_lock(chat_id):
        if chat_id in active_sessions:
            await message.answer("تنبيه: يوجد اختبار نشط حالياً. أرسل /stop لإلغائه قبل بدء اختبار جديد.")
            return

        part_key = message.text.replace("/", "").split("@")[0].strip()
        source_questions = quiz_db.get(part_key, [])
        if not source_questions:
            await message.answer("خطأ: تعذر العثور على أسئلة لهذا الاختبار.")
            return

        # خلط عشوائي كامل للأسئلة
        shuffled = list(source_questions)
        random.shuffle(shuffled)

        active_sessions[chat_id] = {
            "player_id": message.from_user.id,
            "part": part_key,
            "index": 0,
            "score": 0,
            "questions": shuffled
        }

        # إرسال السؤال الأول مباشرة بدون رسائل وسيطة مكررة
        await send_next_question(chat_id)

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    chat_id = message.chat.id
    async with get_chat_lock(chat_id):
        session = active_sessions.get(chat_id)
        if not session:
            await message.answer("لا يوجد اختبار نشط لإلغائه.")
            return

        if message.from_user.id != session["player_id"]:
            await message.answer("عذراً: يحق فقط لمن بدأ الاختبار إلغاؤه.")
            return

        active_sessions.pop(chat_id, None)
        await message.answer("تم إلغاء الاختبار بنجاح.\nللبدء من جديد: /start")

@dp.poll_answer()
async def handle_answer(poll_answer: PollAnswer):
    poll_id = poll_answer.poll_id
    if poll_id not in poll_to_chat:
        return

    chat_id, q_idx = poll_to_chat[poll_id]
    async with get_chat_lock(chat_id):
        session = active_sessions.get(chat_id)
        if not session or poll_answer.user.id != session["player_id"]:
            return

        del poll_to_chat[poll_id]

        current_q = session["questions"][q_idx]
        opts = current_q.get("options") or current_q.get("o")
        correct_id = current_q.get("correct_option_id") if "correct_option_id" in current_q else current_q.get("c")

        chosen_idx = poll_answer.option_ids[0]
        is_correct = (chosen_idx == correct_id)

        chosen_letter = OPTION_LETTERS[chosen_idx] if chosen_idx < len(OPTION_LETTERS) else ""
        correct_letter = OPTION_LETTERS[correct_id] if correct_id < len(OPTION_LETTERS) else ""

        chosen_text = f"({chosen_letter}) {opts[chosen_idx]}"
        correct_text = f"({correct_letter}) {opts[correct_id]}"

        if is_correct:
            session["score"] += 1
            mark = "✅"
        else:
            mark = "❌"

        # تنسيق منفصل تماماً لكل بيان في سطر لمنع تداخل اللغات
        evaluation_msg = (
            f"الإجابة المختارة:\n"
            f"{chosen_text}\n\n"
            f"الإجابة الصحيحة:\n"
            f"{correct_text}\n\n"
            f"النتيجة:\n"
            f"{session['score']} من {q_idx + 1} {mark}"
        )

        await bot.send_message(chat_id=chat_id, text=evaluation_msg)

        session["index"] += 1
        await asyncio.sleep(1.0)
        await send_next_question(chat_id)

async def health_handler(request):
    return web.Response(text="Bot is running healthy.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    # حذف الـ Webhook وتفريغ أي رسائل متراكمة مسبقاً في تيليجرام
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())

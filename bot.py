import os
import json
import random
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, PollAnswer
from aiogram.filters import Command

BOT_TOKEN = "8601813721:AAGzvfJP2nDeqzkNSpeb2yx9phvHXSeMKz4"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def load_quiz_database():
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

    # نهاية الاختبار
    if idx >= total:
        score = session["score"]
        p_name = session["player_name"]
        pct = round((score / total) * 100, 1)
        title = QUIZ_TITLES.get(part, part)

        await bot.send_message(
            chat_id,
            f"اكتمل الاختبار: {title}\n"
            f"المختبِر: {p_name}\n"
            f"النتيجة النهائية: {score} من أصل {total} ({pct}%)\n"
            f"للبدء من جديد أرسل: /start"
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
    await message.answer(
        "قائمة الاختبارات المتاحة:\n\n"
        "/quiz_1 : Lecture 1 (137 سؤال)\n"
        "/quiz_2 : Lecture 2 (46 سؤال)\n"
        "/quiz_3 : Principles of Microscopy (19 سؤال)\n"
        "/quiz_4 : Classification of Microorganisms (63 سؤال)\n\n"
        "للإلغاء في أي وقت: /stop"
    )

@dp.message(Command("quiz_1", "quiz_2", "quiz_3", "quiz_4"))
async def handle_quiz(message: Message):
    chat_id = message.chat.id
    if chat_id in active_sessions:
        p_name = active_sessions[chat_id]["player_name"]
        await message.answer(f"تنبيه: الاختبار قيد التشغيل حالياً بواسطة {p_name}. انتظر حتى ينتهي أو يلغيه عبر /stop.")
        return

    part_key = message.text.replace("/", "").strip()
    source_questions = quiz_db.get(part_key, [])
    if not source_questions:
        await message.answer("خطأ: لا توجد أسئلة مسجلة لهذا الاختبار.")
        return

    # خلط عشوائي كامل
    shuffled = list(source_questions)
    random.shuffle(shuffled)

    title = QUIZ_TITLES.get(part_key, part_key)
    active_sessions[chat_id] = {
        "player_id": message.from_user.id,
        "player_name": message.from_user.full_name,
        "part": part_key,
        "index": 0,
        "score": 0,
        "questions": shuffled
    }

    await message.answer(
        f"بدأ الاختبار: {title}\n"
        f"المختبِر: {message.from_user.full_name}\n"
        f"عدد الأسئلة: {len(shuffled)}\n"
        f"(يمكن للمراقب متابعة النتيجة والإجابات مباشرة)"
    )
    await send_next_question(chat_id)

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    chat_id = message.chat.id
    session = active_sessions.get(chat_id)
    if not session:
        await message.answer("لا يوجد أي اختبار نشط لإلغائه.")
        return

    if message.from_user.id != session["player_id"]:
        await message.answer(f"عذراً: فقط المختبِر ({session['player_name']}) يحق له إلغاء الاختبار.")
        return

    p_name = session["player_name"]
    active_sessions.pop(chat_id, None)
    await message.answer(f"تم إلغاء الاختبار بواسطة {p_name}.\nالمحادثة متاحة الآن عبر /start.")

@dp.poll_answer()
async def handle_answer(poll_answer: PollAnswer):
    poll_id = poll_answer.poll_id
    if poll_id not in poll_to_chat:
        return

    chat_id, q_idx = poll_to_chat[poll_id]
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
        evaluation_msg = (
            f"سؤال {q_idx + 1}:\n"
            f"إجابة {session['player_name']}: {chosen_text}\n"
            f"الحالة: صحيحة ✅\n"
            f"النتيجة الحالية: {session['score']} من {q_idx + 1}"
        )
    else:
        evaluation_msg = (
            f"سؤال {q_idx + 1}:\n"
            f"إجابة {session['player_name']}: {chosen_text}\n"
            f"الحالة: خاطئة ❌\n"
            f"الإجابة الصحيحة: {correct_text}\n"
            f"النتيجة الحالية: {session['score']} من {q_idx + 1}"
        )

    await bot.send_message(chat_id, evaluation_msg)

    session["index"] += 1
    await asyncio.sleep(1.0)
    await send_next_question(chat_id)

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

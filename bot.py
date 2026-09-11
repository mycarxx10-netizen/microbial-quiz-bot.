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

# تتبع الجلسات النشطة في المحادثة
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

    if idx >= total:
        score = session["score"]
        player_name = session["player_name"]
        pct = round((score / total) * 100, 1)
        await bot.send_message(
            chat_id,
            f"🏆 **انتهى الاختبار {part} بنجاح!**\n\n"
            f"👤 المختبِر: **{player_name}**\n"
            f"🎯 النتيجة: **{score} من {total}** ({pct}%)\n"
            f"🏁 المحادثة جاهزة لاختبار جديد عبر /start."
        )
        active_sessions.pop(chat_id, None)
        return

    q = questions[idx]
    q_text = q.get("question") or q.get("q")
    opts = q.get("options") or q.get("o")
    correct_id = q.get("correct_option_id") if "correct_option_id" in q else q.get("c")

    msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"[{idx + 1}/{total}] {q_text}",
        options=opts,
        type="quiz",
        correct_option_id=correct_id,
        is_anonymous=False
    )
    poll_to_chat[msg.poll.id] = (chat_id, idx)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 **أهلاً بكم في بنك الأسئلة الشامل!**\n\n"
        "اختر الاختبار الذي تريد البدء به (يتم خلط الأسئلة عشوائياً في كل مرة):\n"
        "🔹 /quiz_1 : Lecture 1 - Cell Biology (137 سؤال)\n"
        "🔹 /quiz_2 : Lecture 2 - Microbial Diversity (46 سؤال)\n"
        "🔹 /quiz_3 : Principles of Microscopy (19 سؤال)\n"
        "🔹 /quiz_4 : Classification of Microorganisms (63 سؤال)\n\n"
        "لإلغاء الاختبار في أي وقت: /stop"
    )

@dp.message(Command("quiz_1", "quiz_2", "quiz_3", "quiz_4"))
async def handle_quiz(message: Message):
    chat_id = message.chat.id
    if chat_id in active_sessions:
        p_name = active_sessions[chat_id]["player_name"]
        await message.answer(f"⚠️ يوجد اختبار نشط حالياً لـ **{p_name}**.\nانتظر حتى ينتهي أو يلغيه بـ /stop.")
        return

    part_key = message.text.replace("/", "").strip()
    source_questions = quiz_db.get(part_key, [])
    if not source_questions:
        await message.answer("❌ لم يتم العثور على أسئلة لهذا الاختبار.")
        return

    # خلط الأسئلة عشوائياً في كل مرة يبدأ فيها الاختبار
    shuffled_questions = list(source_questions)
    random.shuffle(shuffled_questions)

    active_sessions[chat_id] = {
        "player_id": message.from_user.id,
        "player_name": message.from_user.full_name,
        "part": part_key,
        "index": 0,
        "score": 0,
        "questions": shuffled_questions
    }

    await message.answer(
        f"🚀 **بدأ الاختبار {part_key}** (عدد الأسئلة: {len(shuffled_questions)})\n"
        f"🎯 المختبِر: **{message.from_user.full_name}**\n"
        f"👁️ المراقب: يشاهد التصحيح المباشر فقط."
    )
    await send_next_question(chat_id)

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    chat_id = message.chat.id
    session = active_sessions.get(chat_id)
    if not session:
        await message.answer("لا يوجد أي اختبار نشط حالياً.")
        return

    if message.from_user.id != session["player_id"]:
        await message.answer(f"⚠️ عذراً، فقط المختبِر ({session['player_name']}) يحق له إلغاء الاختبار.")
        return

    active_sessions.pop(chat_id, None)
    await message.answer(f"🛑 قام **{message.from_user.full_name}** بإلغاء الاختبار. المحادثة جاهزة للبدء مجدداً.")

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
    correct_id = current_q.get("correct_option_id") if "correct_option_id" in current_q else current_q.get("c")
    is_correct = (poll_answer.option_ids[0] == correct_id)

    if is_correct:
        session["score"] += 1
        res = "✅ إجابة صحيحة!"
    else:
        res = "❌ إجابة خاطئة!"

    await bot.send_message(
        chat_id,
        f"📊 **تقييم السؤال [{q_idx + 1}]:**\n"
        f"{res}\n"
        f"🎯 نتيجة {session['player_name']}: {session['score']}/{q_idx + 1}"
    )

    session["index"] += 1
    await asyncio.sleep(1.5)
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

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

all_questions = load_questions()

# تقسيم الأسئلة إلى 4 أجزاء
QUIZ_PARTS = {
    "1": all_questions[0:12],
    "2": all_questions[12:24],
    "3": all_questions[24:36],
    "4": all_questions[36:46]
}

# تتبع الجلسة النشطة في المحادثة
# chat_id -> {"player_id": int, "player_name": str, "part": str, "index": 0, "score": 0}
active_sessions = {}
poll_to_chat = {}

async def send_next_question(chat_id: int):
    session = active_sessions.get(chat_id)
    if not session:
        return

    part = session["part"]
    idx = session["index"]
    questions = QUIZ_PARTS[part]
    total = len(questions)

    # التحقق من إكمال الاختبار والنجاح
    if idx >= total:
        score = session["score"]
        player_name = session["player_name"]
        percentage = round((score / total) * 100, 1)
        
        await bot.send_message(
            chat_id,
            f"🏆 **انتهى الاختبار بنجاح!**\n\n"
            f"👤 المختبِر: **{player_name}**\n"
            f"🎯 النتيجة النهائية: **{score} من {total}** ({percentage}%)\n"
            f"🏁 أصبحت المحادثة متاحة لاختبار جديد عبر /start."
        )
        active_sessions.pop(chat_id, None)
        return

    q = questions[idx]
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=f"[{idx + 1}/{total}] {q['question']}",
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct_option_id"],
        is_anonymous=False
    )
    poll_to_chat[msg.poll.id] = (chat_id, idx)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 **أهلاً بكم في اختبار Microbial Diversity!**\n\n"
        "القوانين:\n"
        "• الشخص الذي يبدأ الاختبار هو الوحيد المخوّل بالإجابة.\n"
        "• يتابع الطرف الآخر الإجابات مباشرة دون تدخل.\n\n"
        "اختر جزء الاختبار للبدء:\n"
        "🔹 /quiz_1 : الجزء الأول (1 - 12)\n"
        "🔹 /quiz_2 : الجزء الثاني (13 - 24)\n"
        "🔹 /quiz_3 : الجزء الثالث (25 - 36)\n"
        "🔹 /quiz_4 : الجزء الرابع (37 - 46)\n\n"
        "لإلغاء الاختبار: /stop"
    )

@dp.message(Command("quiz_1", "quiz_2", "quiz_3", "quiz_4"))
async def handle_quiz_start(message: Message):
    chat_id = message.chat.id
    
    # منع شخص آخر من التدخل أثناء وجود اختبار نشط
    if chat_id in active_sessions:
        current_player = active_sessions[chat_id]["player_name"]
        await message.answer(f"⚠️ يوجد اختبار نشط حالياً للمختبِر: **{current_player}**.\nانتظر حتى ينتهي أو يلغيه بـ /stop.")
        return

    part = message.text.split("_")[1]
    active_sessions[chat_id] = {
        "player_id": message.from_user.id,
        "player_name": message.from_user.full_name,
        "part": part,
        "index": 0,
        "score": 0
    }

    await message.answer(
        f"🚀 **بدأ الاختبار {part}**\n"
        f"🎯 المختبِر المحدد: **{message.from_user.full_name}**\n"
        f"👁️ المتابع: يمكنه مشاهدة التصحيح المباشر فقط."
    )
    await send_next_question(chat_id)

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    chat_id = message.chat.id
    session = active_sessions.get(chat_id)
    
    if not session:
        await message.answer("لا يوجد أي اختبار نشط حالياً.")
        return

    # السماح فقط للمختبِر نفسه بإلغاء اختباره
    if message.from_user.id != session["player_id"]:
        await message.answer(f"⚠️ عذراً، فقط المختبِر ({session['player_name']}) يحق له إلغاء الاختبار.")
        return

    active_sessions.pop(chat_id, None)
    await message.answer(f"🛑 قام **{message.from_user.full_name}** بإلغاء الاختبار بنجاح.\nالمحادثة جاهزة للبدء من جديد عبر /start.")

@dp.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    poll_id = poll_answer.poll_id
    if poll_id not in poll_to_chat:
        return

    chat_id, q_idx = poll_to_chat[poll_id]
    session = active_sessions.get(chat_id)
    if not session:
        return

    # حظر إجابة أي شخص آخر غير المختبِر المحدد
    if poll_answer.user.id != session["player_id"]:
        return  # تجاهل الإجابة تماماً ولن يتقدم السؤال

    del poll_to_chat[poll_id]

    part = session["part"]
    selected_option = poll_answer.option_ids[0]
    correct_option = QUIZ_PARTS[part][q_idx]["correct_option_id"]
    is_correct = (selected_option == correct_option)

    if is_correct:
        session["score"] += 1
        result_icon = "✅ إجابة صحيحة!"
    else:
        result_icon = "❌ إجابة خاطئة!"

    # إشعار يراه الطرفان في المحادثة
    await bot.send_message(
        chat_id,
        f"📊 **تقييم السؤال [{q_idx + 1}]:**\n"
        f"{result_icon}\n"
        f"🎯 نتيجة {session['player_name']} الحالية: {session['score']}/{q_idx + 1}"
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

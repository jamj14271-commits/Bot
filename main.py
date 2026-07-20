import io
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import os
import sys
import asyncio
import traceback
import motor.motor_asyncio
from pymongo import ReturnDocument
import certifi
import re
import google.generativeai as genai
from keep_alive import keep_alive
from datetime import datetime, timedelta, timezone

# ================= THÊM MỚI 2 THƯ VIỆN NÀY ĐỂ KẾT NỐI API ================= #
import aiohttp
import random
# ======================================================================== #

# ================= KIỂM TRA BIẾN MÔI TRƯỜNG BẮT BUỘC ================= #
# ĐÃ FIX: Kiểm tra ngay từ đầu, nếu thiếu token thì thoát sớm với log rõ ràng
# thay vì để bot crash mập mờ giữa chừng trên Render.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    print("❌ LỖI NGHIÊM TRỌNG: Thiếu biến môi trường DISCORD_TOKEN! Vào Render > Environment để thêm.")
    sys.exit(1)

if not os.getenv("MONGO_URI"):
    print("⚠️ CẢNH BÁO: Thiếu biến môi trường MONGO_URI! Các lệnh liên quan tới MP/danh hiệu sẽ không hoạt động cho đến khi cấu hình.")

# ================= CẤU HÌNH CƠ BẢN ================= #
ADMIN_CHANNEL_ID = 1525386498739015800  
REPORT_CHANNEL_ID = 1525662263502176306
WELCOME_CHANNEL_ID = 1525492114564317204  
# ĐÃ THÊM MỚI: kênh log các hành động admin (duyệt/từ chối/cộng trừ MP/xử phạt report).
# ⚠️ CẦN THAY SỐ NÀY THÀNH ID KÊNH THẬT TRƯỚC KHI DEPLOY, nếu không log sẽ không gửi được.
ADMIN_LOG_CHANNEL_ID = 0

DIFFICULTY_MP = {
    "easy": 5, "normal": 10, "hard": 25, "harder": 50, "insane": 100,
    "easy demon": 250, "medium demon": 500, "hard demon": 1000,
    "insane demon": 5000, "extreme demon": 10000,
    "daily": 150, "event": 2500
}

# ĐÃ FIX: Xóa "vua cày điểm" để tránh lách luật bằng lệnh !duyet
# ĐÃ THÊM MỚI: gộp toàn bộ 50 danh hiệu mới vào đây để member nào cũng nộp bằng
# chứng qua !duyet như nhau - admin chỉ xét bằng chứng đúng/sai (Duyệt/Từ chối),
# KHÔNG tự ý gán tay cho ai, đảm bảo công bằng như các danh hiệu gốc.
TITLES_DATA = [
    "newbie", "sự khởi đầu", "pro",
    "hardcore player", "huyền thoại",
    "vua try hard", "vua hardest",

    # --- A. Tiến trình kỹ năng ---
    "người mới toe", "tân binh", "học việc", "chiến binh", "đấu sĩ",
    "sát thủ demon", "thợ săn insane", "kẻ hủy diệt",
    "bậc thầy phản xạ", "vô địch tốc độ",

    # --- B. Cày điểm / năng suất ---
    "cày cuốc chăm chỉ", "thợ cày chuyên nghiệp", "máy cày mp",
    "nông dân demon", "vua năng suất",

    # --- C. Streak / kiên trì ---
    "kiên trì bất khuất", "không bỏ cuộc", "chiến thần bền bỉ",
    "người sắt", "ý chí thép",

    # --- D. Cống hiến cộng đồng ---
    "người bạn tốt", "trưởng lão server", "cố vấn tân binh",
    "đại sứ cộng đồng", "người truyền cảm hứng",

    # --- E. Sáng tạo ---
    "nhà thiết kế", "kiến trúc sư level", "nghệ sĩ decor",
    "bậc thầy sáng tạo", "huyền thoại sáng tác",

    # --- F. Sự kiện ---
    "chiến binh event", "vua sự kiện tháng", "người về đích đầu tiên",
    "huyền thoại mùa giải", "nhà vô địch giải đấu",

    # --- G. Vui/troll ---
    "trùm rớt điểm rơi", "vua nổ máy", "ông hoàng restart",
    "đại sư spam thử", "chúa tể rage quit",

    # --- H. Hiếm (vẫn qua !duyet - "hiếm" vì ít ai làm được, không phải vì admin ưu ái) ---
    "người được chọn", "vip server", "huyền thoại sống",
    "thánh nhân gd", "tối thượng chi vương",

    # --- I. Thâm niên ---
    "thành viên kỳ cựu", "lính cũ", "chứng nhân lịch sử",
    "linh hồn server", "vĩnh cửu",
]

# ================= THÊM MỚI: MÀU ANSI CHO DANH HIỆU TRÊN !BXH ================= #
# Discord chỉ hỗ trợ 7 màu cố định trong code block ```ansi (không custom hex được):
# 30 gray, 31 red, 32 green, 33 yellow, 34 blue, 35 pink, 36 cyan, 37 white.
# Nhiều danh hiệu dùng chung 1 màu là bình thường, phân biệt chủ yếu qua tên danh
# hiệu hiển thị kèm bên cạnh (✦ Tên Danh Hiệu ✦), không chỉ dựa vào màu.
TITLE_COLORS = {
    # --- Ngôi vị tối thượng / danh hiệu gốc (giữ nguyên) ---
    "vua cày điểm": "31",     # đỏ
    "vua hardest": "31",      # đỏ
    "vua try hard": "33",     # vàng
    "huyền thoại": "35",      # hồng/tím
    "hardcore player": "34",  # xanh dương
    "pro": "36",              # cyan
    "sự khởi đầu": "32",      # xanh lá
    "newbie": "37",           # trắng

    # --- A. Tiến trình kỹ năng (nhạt -> rực, thấp -> cao) ---
    "người mới toe": "30", "tân binh": "30",
    "học việc": "37", "chiến binh": "37",
    "đấu sĩ": "36", "sát thủ demon": "36",
    "thợ săn insane": "34", "kẻ hủy diệt": "34",
    "bậc thầy phản xạ": "35", "vô địch tốc độ": "31",

    # --- B. Cày điểm / năng suất (vàng-xanh lá, top là đỏ) ---
    "cày cuốc chăm chỉ": "33", "thợ cày chuyên nghiệp": "33",
    "máy cày mp": "33", "nông dân demon": "32",
    "vua năng suất": "31",

    # --- C. Streak / kiên trì (xanh lá bền bỉ, "thép/sắt" xám) ---
    "kiên trì bất khuất": "32", "không bỏ cuộc": "32",
    "chiến thần bền bỉ": "34", "người sắt": "30", "ý chí thép": "30",

    # --- D. Cống hiến cộng đồng (cyan thân thiện) ---
    "người bạn tốt": "36", "trưởng lão server": "36",
    "cố vấn tân binh": "36", "đại sứ cộng đồng": "34",
    "người truyền cảm hứng": "35",

    # --- E. Sáng tạo (hồng/tím nghệ thuật) ---
    "nhà thiết kế": "35", "kiến trúc sư level": "35",
    "nghệ sĩ decor": "35", "bậc thầy sáng tạo": "34",
    "huyền thoại sáng tác": "31",

    # --- F. Sự kiện (vàng lễ hội, top đỏ) ---
    "chiến binh event": "33", "vua sự kiện tháng": "33",
    "người về đích đầu tiên": "32", "huyền thoại mùa giải": "35",
    "nhà vô địch giải đấu": "31",

    # --- G. Vui/troll (xám mờ - "meme", điểm nhấn đỏ cho rage quit) ---
    "trùm rớt điểm rơi": "30", "vua nổ máy": "30",
    "ông hoàng restart": "30", "đại sư spam thử": "30",
    "chúa tể rage quit": "31",

    # --- H. Hiếm, admin cấp tay (đỏ/vàng quý hiếm) ---
    "người được chọn": "35", "vip server": "33",
    "huyền thoại sống": "31", "thánh nhân gd": "31",
    "tối thượng chi vương": "31",

    # --- I. Thâm niên (xanh dương trung thành) ---
    "thành viên kỳ cựu": "34", "lính cũ": "34",
    "chứng nhân lịch sử": "36", "linh hồn server": "35",
    "vĩnh cửu": "31",
}
DEFAULT_TITLE_COLOR = "30"  # gray - không có danh hiệu hoặc danh hiệu chưa map màu

def color_line(text: str, title: str = None) -> str:
    """Bọc 1 dòng text bằng mã màu ANSI tương ứng với danh hiệu, dùng trong
    code block ```ansi để hiển thị màu trên !bxh. Nếu không có title hoặc
    title không nằm trong TITLE_COLORS thì dùng màu mặc định (gray)."""
    code = TITLE_COLORS.get(title, DEFAULT_TITLE_COLOR) if title else DEFAULT_TITLE_COLOR
    return f"\u001b[1;{code}m{text}\u001b[0m"
# ================================================================================ #

VN_TZ = timezone(timedelta(hours=7))

# ================= CẤU HÌNH GEMINI ================= #
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = None

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gd_system_instruction = (
        "Bạn là chuyên gia về game Geometry Dash, chỉ cung cấp thông tin chính xác từ GDBrowser/nguồn uy tín.\n"
        "QUY TẮC BẮT BUỘC TUÂN THỦ:\n"
        "1. CHỈ trả lời về Geometry Dash, câu hỏi khác trả lời: 'Tôi chỉ hỗ trợ thông tin về Geometry Dash thôi nhé!'\n"
        "2. Khi đề xuất level: Sắp xếp theo thứ tự ưu tiên phù hợp nhất, mỗi level ghi rõ định dạng:\n"
        "🔹 **Tên Level**: [Tên chính xác]\n"
        "🔹 **Tác giả**: [Tên người tạo]\n"
        "🔹 **Độ khó**: [Easy/Normal/Hard/Insane/Extreme + loại Demon nếu có]\n"
        "🔹 **ID Level**: [Mã số ID chính xác trên GDBrowser - KHÔNG ĐƯỢC BỎ SÓT, KHÔNG TẠO ẢO]\n"
        "🔹 **Lý do phù hợp**: [Giải thích ngắn gọn tại sao phù hợp với yêu cầu/trình độ người chơi]\n"
        "3. Đề xuất đủ 3-5 level phù hợp, ưu tiên level có sẵn trên server, không tạo level không tồn tại.\n"
        "4. Trả lời ngắn gọn, rõ ràng, dùng Markdown dễ đọc, không viết chữ hoa toàn bộ."
    )
    
    generation_config = genai.types.GenerationConfig(
        temperature=0.1, max_output_tokens=2048, top_p=0.95
    )
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
    ]
    
    # ĐÃ FIX (NGUYÊN NHÂN CHÍNH CỦA LỖI !dexuatlevel):
    # "gemini-1.5-flash-latest" đã bị Google khai tử hoàn toàn (mọi request trả về lỗi 404
    # "model not found"). Vì lỗi 404 không nằm trong danh sách mã lỗi được retry trong code
    # cũ, và trong một số trường hợp exception xảy ra trước khi có thể ghi log rõ ràng, lệnh
    # trông như "không phản hồi gì cả". Chuyển sang "gemini-flash-latest" - đây là alias luôn
    # tự động trỏ tới bản Flash mới nhất còn được hỗ trợ (hiện tại là Gemini 3.5 Flash), giúp
    # tránh phải sửa code mỗi khi Google khai tử model theo chu kỳ ~6-12 tháng của họ.
    GEMINI_MODEL_NAME = 'gemini-flash-latest'
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL_NAME,
        system_instruction=gd_system_instruction,
        generation_config=generation_config,
        safety_settings=safety_settings
    )

    # ĐÃ THÊM MỚI: model Gemini RIÊNG, chỉ dùng để "đọc" tên level GD hiển thị trong ảnh/
    # video bằng chứng (!duyet). Tách riêng khỏi `model` ở trên vì system_instruction khác
    # hẳn mục đích (OCR nhận diện, không phải tư vấn/gợi ý level) - dùng chung 1 model sẽ
    # khiến Gemini bị "nhiễu" giữa 2 vai trò, dễ trả lời sai định dạng.
    LEVEL_SCAN_INSTRUCTION = (
        "Bạn là công cụ OCR chuyên biệt cho game Geometry Dash. Nhiệm vụ DUY NHẤT: nhìn vào "
        "ảnh/video được cung cấp (thường là màn hình kết quả hoàn thành 1 level trong game) và "
        "đọc CHÍNH XÁC tên level hiển thị trên đó (thường ở góc trên hoặc giữa màn hình).\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. CHỈ trả lời đúng tên level, không thêm bất kỳ chữ nào khác (không giải thích, không markdown).\n"
        "2. Nếu không đọc rõ được tên, ảnh mờ, hoặc ảnh/video không phải màn hình Geometry Dash, "
        "trả lời ĐÚNG CHUỖI: KHONG_XAC_DINH"
    )
    level_scan_model = genai.GenerativeModel(model_name=GEMINI_MODEL_NAME, system_instruction=LEVEL_SCAN_INSTRUCTION)
else:
    level_scan_model = None

# ================= KHỞI TẠO BOT ==================== #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
db_client, db = None, None
# ĐÃ THÊM MỚI (v12): cờ đảm bảo persistent view chỉ được đăng ký 1 LẦN, vì on_ready
# có thể được Discord gọi lại nhiều lần (VD: mất kết nối rồi reconnect), gọi add_view
# nhiều lần tuy không lỗi nhưng không cần thiết.
_views_registered = False

def require_db():
    """ĐÃ THÊM MỚI: decorator kiểm tra DB đã sẵn sàng chưa trước khi chạy lệnh.
    Tránh việc lệnh bị crash âm thầm (AttributeError: 'NoneType' object has no
    attribute 'users') khi bot vừa khởi động lại mà chưa kết nối xong Mongo,
    hoặc khi MONGO_URI bị cấu hình sai/thiếu."""
    async def predicate(ctx):
        if db is None:
            await ctx.send("⚠️ Bot chưa kết nối được database (MongoDB), vui lòng thử lại sau ít giây hoặc báo Admin kiểm tra biến môi trường MONGO_URI!")
            return False
        return True
    return commands.check(predicate)

@bot.event
async def on_ready():
    global db_client, db, _views_registered
    # ĐÃ FIX (v12 - BUG NGHIÊM TRỌNG): đăng ký lại các persistent view (ReviewView,
    # ReportReviewView) ngay khi bot khởi động, để nút "Duyệt/Từ chối" trên các tin
    # nhắn ĐÃ GỬI TỪ TRƯỚC (trước khi bot restart) vẫn hoạt động bình thường. Nếu không
    # có bước này, discord.py sẽ không biết cách xử lý các nút custom_id="btn_approve"...
    # trên message cũ sau khi bot khởi động lại (bấm vào sẽ báo lỗi tương tác thất bại).
    if not _views_registered:
        bot.add_view(ReviewView())
        bot.add_view(ReportReviewView())
        bot.add_view(ChallengeReviewView())
        _views_registered = True
        print("✅ Đã đăng ký persistent views (ReviewView, ReportReviewView, ChallengeReviewView).")

    # ĐÃ THÊM MỚI (v13): khởi động task cảnh báo hết hạn event/daily (chỉ start 1 lần).
    if not check_expiry_task.is_running():
        check_expiry_task.start()
        print("✅ Đã khởi động task cảnh báo hết hạn Event/Daily.")

    print('Đang kết nối database...')
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        print("❌ Không có MONGO_URI, bỏ qua kết nối database.")
        db_client, db = None, None
    else:
        try:
            # ĐÃ FIX: thêm serverSelectionTimeoutMS để không bị treo vô thời hạn nếu
            # sai URI/IP chưa được whitelist trên MongoDB Atlas, và thử ping ngay để
            # phát hiện lỗi kết nối SỚM thay vì chỉ phát hiện khi user gõ lệnh.
            db_client = motor.motor_asyncio.AsyncIOMotorClient(
                mongo_uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000
            )
            await db_client.admin.command('ping')
            db = db_client['gd_database']
            print("✅ Kết nối MongoDB thành công!")
        except Exception as e:
            print(f"❌ LỖI KẾT NỐI MONGODB: {e}")
            print("👉 Kiểm tra lại: chuỗi kết nối MONGO_URI, user/password, và Network Access (whitelist IP) trên MongoDB Atlas.")
            db_client, db = None, None
    print(f'Bot {bot.user} đã sẵn sàng hoạt động!')

# ================= XỬ LÝ LỖI TOÀN CỤC (MỚI) ================= #
# ĐÃ THÊM MỚI: Đây là fix quan trọng nhất cho "Lỗi 2". Trước đây bot KHÔNG có
# on_command_error, nên bất kỳ lệnh nào gặp lỗi bất ngờ (thiếu quyền, sai tham số,
# lỗi database, lỗi code...) sẽ chỉ in ra console của Render mà KHÔNG phản hồi gì
# cho người dùng trong Discord - tạo cảm giác "lệnh bị treo/không hoạt động".
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CheckFailure):
        return  # require_db() đã tự gửi thông báo riêng rồi
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send("❌ Bạn không có quyền sử dụng lệnh này!")
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(f"❌ Thiếu tham số bắt buộc! Gõ `!menu` để xem cách dùng lệnh.")
    if isinstance(error, commands.BadArgument):
        return await ctx.send("❌ Tham số không hợp lệ (VD: sai định dạng @user hoặc số).")
    if isinstance(error, commands.CommandOnCooldown):
        return await ctx.send(f"⏳ Lệnh đang hồi chiêu, thử lại sau {error.retry_after:.1f} giây!")

    print(f"[LỖI KHÔNG XÁC ĐỊNH] Lệnh: {ctx.command} | Người dùng: {ctx.author} ({ctx.author.id})")
    traceback.print_exception(type(error), error, error.__traceback__)
    try:
        await ctx.send("⚠️ Đã xảy ra lỗi không xác định khi thực hiện lệnh này. Vấn đề đã được ghi log để kiểm tra, vui lòng thử lại sau!")
    except discord.Forbidden:
        pass

async def get_user_mp(user_id):
    user = await db.users.find_one({"_id": user_id})
    return user["mp"] if user else 0

# ĐÃ THÊM MỚI (v13): ghi lại lịch sử duyệt (mp/danh hiệu/challenge) của TỪNG người dùng
# vào collection riêng db.history, phục vụ lệnh !history xem lại cá nhân.
async def log_history(user_id: int, kind: str, item_name: str, status: str, admin_id: int, detail: str = None):
    await db.history.insert_one({
        "user_id": user_id,
        "kind": kind,            # "mp" | "role" | "challenge"
        "item_name": item_name,
        "status": status,        # "approved" | "rejected"
        "admin_id": admin_id,
        "detail": detail,
        "timestamp": datetime.now(VN_TZ),
    })

async def add_user_mp(user_id, amount, guild=None):
    await db.users.update_one({"_id": user_id}, {"$inc": {"mp": amount}}, upsert=True)
    if guild:
        await check_and_transfer_top1_mp(guild)

# ĐÃ THÊM MỚI (v13): sinh mã số Challenge tự tăng (1, 2, 3...) để admin/member dễ tham
# chiếu qua !ratechallenge và !bxhchallenge, thay vì phải dùng ObjectId dài của Mongo.
async def get_next_challenge_id():
    doc = await db.settings.find_one_and_update(
        {"_id": "challenge_counter"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["seq"]

# ĐÃ THÊM MỚI: hàm dùng chung để log mọi hành động admin (duyệt/từ chối/cộng trừ
# MP/xử phạt report) vào 1 kênh riêng, giúp tra soát lại "ai duyệt/xử lý gì, khi
# nào" thay vì không có audit trail nào như trước. Nếu chưa cấu hình
# ADMIN_LOG_CHANNEL_ID (vẫn để 0) thì bỏ qua, không báo lỗi ra cho người dùng.
async def log_admin_action(admin_mention: str, action: str, target_mention: str = None, detail: str = None):
    if not ADMIN_LOG_CHANNEL_ID:
        return
    channel = bot.get_channel(ADMIN_LOG_CHANNEL_ID)
    if channel is None:
        return
    embed = discord.Embed(title="📋 LOG HÀNH ĐỘNG ADMIN", color=discord.Color.dark_grey(), timestamp=datetime.now(VN_TZ))
    embed.add_field(name="👮 Admin", value=admin_mention, inline=True)
    if target_mention:
        embed.add_field(name="🎯 Đối tượng", value=target_mention, inline=True)
    embed.add_field(name="⚡ Hành động", value=action, inline=False)
    if detail:
        embed.add_field(name="📝 Chi tiết", value=detail, inline=False)
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass

# ĐÃ THÊM MỚI: Nguyên nhân gây ra bug "top 1 cũ không bị xoá danh hiệu vẫn hiện trên bxh".
# 3 hàm grant_* trước đây chỉ $pull tên danh hiệu ra khỏi mảng "titles" của người cũ, NHƯNG
# KHÔNG reset trường "active_title" của họ. Lệnh !bxh chỉ đọc "active_title" để hiển thị chứ
# không kiểm tra lại xem danh hiệu đó có còn nằm trong "titles" hay không, nên dù đã bị $pull,
# active_title vẫn còn giá trị cũ ("vua cày điểm"/"vua hardest"/"vua try hard") và tiếp tục
# hiện ra trên bảng xếp hạng. Hàm dùng chung này xử lý đúng cả 2 bước: xoá khỏi titles VÀ
# reset active_title nếu nó đang trỏ tới đúng danh hiệu bị thu hồi.
async def revoke_title(user_id, title_name):
    await db.users.update_one({"_id": user_id}, {"$pull": {"titles": title_name}})
    doc = await db.users.find_one({"_id": user_id})
    if doc and doc.get("active_title") == title_name:
        remaining_titles = [t for t in doc.get("titles", []) if t != title_name]
        new_active = remaining_titles[-1] if remaining_titles else None
        await db.users.update_one({"_id": user_id}, {"$set": {"active_title": new_active}})

async def check_and_transfer_top1_mp(guild):
    users = await db.users.find().sort("mp", -1).limit(1).to_list(1)
    if not users: return
    new_top1_id = users[0]["_id"]
    
    config = await db.settings.find_one({"_id": "top1_mp_owner"})
    old_top1_id = config["user_id"] if config else None

    if old_top1_id != new_top1_id:
        if old_top1_id:
            await revoke_title(old_top1_id, "vua cày điểm")
        await db.users.update_one({"_id": new_top1_id}, {"$addToSet": {"titles": "vua cày điểm"}, "$set": {"active_title": "vua cày điểm"}}, upsert=True)
        await db.settings.update_one({"_id": "top1_mp_owner"}, {"$set": {"user_id": new_top1_id}}, upsert=True)

        # ĐÃ THÊM MỚI: thông báo công khai khi có Vua Cày Điểm mới. Dùng chung
        # WELCOME_CHANNEL_ID (kênh public có sẵn, không tạo thêm biến ID kênh mới)
        # - KHÔNG dùng ADMIN_CHANNEL_ID vì đây là tin công khai cho cả server xem,
        # không phải nội dung chờ admin xử lý.
        thong_bao_channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if thong_bao_channel:
            embed_top1 = discord.Embed(
                title="👑 VUA CÀY ĐIỂM MỚI!",
                description=f"<@{new_top1_id}> vừa vươn lên **Top 1 MP** toàn server và trở thành **Vua Cày Điểm** mới!",
                color=discord.Color.gold()
            )
            try:
                await thong_bao_channel.send(embed=embed_top1)
            except (discord.Forbidden, discord.HTTPException):
                pass

async def grant_vua_hardest(guild, new_owner_id):
    config = await db.settings.find_one({"_id": "vua_hardest_owner"})
    old_owner_id = config["user_id"] if config else None

    if old_owner_id and old_owner_id != new_owner_id:
        await revoke_title(old_owner_id, "vua hardest")
    await db.users.update_one({"_id": new_owner_id}, {"$addToSet": {"titles": "vua hardest"}, "$set": {"active_title": "vua hardest"}}, upsert=True)
    await db.settings.update_one({"_id": "vua_hardest_owner"}, {"$set": {"user_id": new_owner_id}}, upsert=True)

async def grant_vua_try_hard(guild, new_owner_id):
    config = await db.settings.find_one({"_id": "vua_try_hard_owner"})
    old_owner_id = config["user_id"] if config else None

    if old_owner_id and old_owner_id != new_owner_id:
        await revoke_title(old_owner_id, "vua try hard")
    await db.users.update_one({"_id": new_owner_id}, {"$addToSet": {"titles": "vua try hard"}, "$set": {"active_title": "vua try hard"}}, upsert=True)
    await db.settings.update_one({"_id": "vua_try_hard_owner"}, {"$set": {"user_id": new_owner_id}}, upsert=True)

# ================= NHẬN DIỆN LINK YOUTUBE LÀM BẰNG CHỨNG (MỚI) ================= #
# ĐÃ THÊM MỚI: cho phép nộp bằng chứng bằng link Youtube thay vì tải file trực tiếp lên
# Discord - hữu ích cho máy yếu không xuất video ra được, hoặc video quá dài/nặng.
# KHÔNG dùng API tự động xác minh chủ kênh - bot chỉ nhận diện link và gửi thẳng cho
# kiểm duyệt viên xem xét ở kênh admin; kiểm duyệt viên tự bấm vào link kiểm tra bằng
# mắt (xem tên kênh, mô tả, bình luận...) trước khi Duyệt/Từ chối như bình thường.
YOUTUBE_URL_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)

def extract_youtube_id(text: str):
    """Tìm ID video Youtube (11 ký tự) trong 1 đoạn text, trả về None nếu không có."""
    if not text: return None
    m = YOUTUBE_URL_REGEX.search(text)
    return m.group(1) if m else None

def strip_youtube_link(text: str) -> str:
    """Xoá link Youtube ra khỏi 1 đoạn text (dùng để dọn sạch tên/yêu cầu khi người dùng
    dán link Youtube làm bằng chứng ngay trong cùng câu lệnh, tránh bị dính link vào tên).
    ĐÃ FIX (lỗi 'ghép link vào tên'): trước đây !duyet/!nopchallenge dùng `*, ten: str` để
    lấy TOÀN BỘ phần còn lại của tin nhắn, nên nếu người dùng gõ kiểu
    `!nopchallenge 123 Tên Level https://youtu.be/xxxx`, biến `ten` sẽ chứa luôn cả link,
    hiện sai lệch trên cả kênh duyệt lẫn bảng xếp hạng."""
    if not text: return text
    cleaned = YOUTUBE_URL_REGEX.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()
# ================================================================================ #

# ================= TỰ ĐỘNG NHẬN DIỆN DEMON KHÓ NHẤT TỪ BẰNG CHỨNG (MỚI) ================= #
# ĐÃ THÊM MỚI: Khi Admin bấm "Duyệt" cho 1 yêu cầu MP loại Demon (easy/medium/hard/insane/
# extreme demon) có kèm ảnh/video, bot sẽ nhờ Gemini "đọc" tên level trong ảnh/video đó, rồi
# tra cứu độ khó CHÍNH THỨC của level đó qua GDBrowser (không hỏi thẳng Gemini vì Gemini có
# thể bịa độ khó - xem bài học ở lỗi !dexuatlevel trước đây). Nếu độ khó này cao hơn Demon
# khó nhất đang lưu của người dùng, bot tự động cập nhật để hiển thị ở !profile.
# Lưu ý: chỉ hoạt động với bằng chứng dạng ẢNH/VIDEO tải trực tiếp lên Discord - KHÔNG áp
# dụng cho bằng chứng dạng link Youtube (không tải xuống phân tích link ngoài).
DEMON_DIFFICULTY_ORDER = {
    "easy demon": 1, "medium demon": 2, "hard demon": 3, "insane demon": 4, "extreme demon": 5,
}

async def _download_evidence_bytes(url: str):
    """Tải bytes + content-type của 1 file bằng chứng (ảnh/video) từ URL Discord CDN.
    Trả về (bytes, content_type) hoặc (None, None) nếu lỗi."""
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as r:
                if r.status != 200: return None, None
                content_type = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                data = await r.read()
                return data, content_type
    except Exception as e:
        print(f"[LỖI TẢI BẰNG CHỨNG] {e}")
        return None, None

async def scan_level_name_from_evidence(evidence_url: str):
    """Nhờ Gemini đọc tên level GD hiển thị trong ảnh/video bằng chứng. Trả về tên level
    (str) hoặc None nếu không đọc được / không hỗ trợ định dạng / lỗi bất kỳ."""
    if level_scan_model is None or not evidence_url:
        return None
    data, content_type = await _download_evidence_bytes(evidence_url)
    if not data or not content_type:
        return None
    if not (content_type.startswith("image/") or content_type.startswith("video/")):
        return None
    if len(data) > 15 * 1024 * 1024:  # >15MB: bỏ qua để tránh request quá nặng/chậm/lỗi
        print("⚠️ Bỏ qua quét tên level: file bằng chứng vượt quá 15MB.")
        return None
    try:
        part = {"mime_type": content_type, "data": data}
        phan_hoi = await asyncio.wait_for(
            level_scan_model.generate_content_async(["Đọc tên level Geometry Dash hiển thị trong ảnh/video này:", part]),
            timeout=45
        )
        if not phan_hoi.parts: return None
        ten = (phan_hoi.text or "").strip()
        if not ten or "KHONG_XAC_DINH" in ten.upper():
            return None
        return ten
    except Exception as e:
        print(f"[LỖI QUÉT TÊN LEVEL] {e}")
        return None

async def find_level_by_name(name: str):
    """Tìm level THẬT trên GDBrowser theo tên (lấy kết quả khớp nhất đầu tiên), trả về
    dict {id, name, difficulty} hoặc None nếu không tìm thấy/lỗi mạng."""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"https://gdbrowser.com/api/search/{name}?count=1"
            async with session.get(url) as r:
                if r.status != 200: return None
                data = await r.json()
                if isinstance(data, list) and data:
                    lv = data[0]
                    return {"id": lv.get("id"), "name": lv.get("name"), "difficulty": lv.get("difficulty")}
    except Exception as e:
        print(f"[LỖI TÌM LEVEL GDBROWSER] {e}")
    return None

async def try_update_hardest_demon(user_id: int, evidence_url: str) -> str:
    """Cố gắng tự động ghi nhận Demon khó nhất người dùng từng vượt qua dựa trên bằng
    chứng vừa được duyệt. Trả về 1 dòng thông báo ngắn để thêm vào DM cho người dùng nếu
    có cập nhật, hoặc chuỗi rỗng nếu không có gì thay đổi/không xác định được.
    LUÔN bọc trong try/except ở nơi gọi - đây là tính năng PHỤ, không được phép làm gián
    đoạn luồng duyệt bài chính (cộng MP/danh hiệu) dù có lỗi gì xảy ra."""
    ten_level = await scan_level_name_from_evidence(evidence_url)
    if not ten_level: return ""

    level_info = await find_level_by_name(ten_level)
    if not level_info or not level_info.get("difficulty"): return ""

    new_order = DEMON_DIFFICULTY_ORDER.get(level_info["difficulty"].lower(), 0)
    if new_order == 0: return ""  # không phải Demon (VD: chỉ là Hard/Insane thường)

    user_doc = await db.users.find_one({"_id": user_id}) or {}
    current = user_doc.get("hardest_demon") or {}
    current_order = DEMON_DIFFICULTY_ORDER.get((current.get("difficulty") or "").lower(), 0)

    if new_order > current_order:
        await db.users.update_one(
            {"_id": user_id},
            {"$set": {"hardest_demon": {"name": level_info["name"], "level_id": level_info["id"], "difficulty": level_info["difficulty"]}}},
            upsert=True
        )
        return f"\n🔥 Bot tự động nhận diện: **{level_info['name']}** (`{level_info['difficulty']}`) là Demon khó nhất bạn từng vượt qua, đã cập nhật vào !profile!"
    return ""
# ================================================================================ #

# ================= TỰ ĐỘNG CHỌN LEVEL NGẪU NHIÊN CHO DAILY/EVENT (MỚI) ================= #
# ĐÃ THÊM MỚI: thay vì Admin phải tự tìm và nhập tay ID level cho !thongbao, bot có thể tự
# chọn NGẪU NHIÊN 1 level THẬT (không bịa) từ GDBrowser: Insane 8-9 sao cho Daily, Hard
# Demon cho Event. GDBrowser KHÔNG có tham số lọc "stars" trực tiếp trong API tìm kiếm, nên
# với Daily bot phải tự lọc lại theo field "stars" trả về sau khi lấy danh sách kết quả.
#
# ĐÃ FIX (LỖI "BỊ TRÙNG LEVEL"): trước đây bot luôn gọi GDBrowser KHÔNG kèm tham số "page",
# nên GDBrowser luôn trả về ĐÚNG CÙNG 100 level top đầu (mặc định page=0) ở mọi lần gọi. Khi
# lọc lại theo 8-9 sao, tập ứng viên còn lại thường rất ít (đôi khi chỉ 1-2 level), nên
# random.choice() gần như luôn ra lại đúng level cũ. Giờ mỗi lần gọi sẽ random 1 trang bất kỳ
# (page 0-9) để lấy một tập level khác nhau, CỘNG THÊM loại trừ các ID đã dùng gần đây (lưu
# lịch sử trong exclude_ids) để đảm bảo không lặp lại ngay lập tức.
async def pick_random_daily_level(exclude_ids=None):
    """Chọn ngẫu nhiên 1 level Insane 8 hoặc 9 sao THẬT, tránh trùng các ID trong exclude_ids.
    Trả về dict {id,name,difficulty,stars} hoặc None nếu GDBrowser lỗi/không tìm được level phù hợp."""
    exclude_ids = {str(i) for i in (exclude_ids or [])}
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            page = random.randint(0, 9)
            url = f"https://gdbrowser.com/api/search/*?diff=5&starred=true&count=100&page={page}"
            async with session.get(url) as r:
                if r.status != 200: return None
                data = await r.json()
                if not isinstance(data, list) or not data: return None
                pool = [lv for lv in data if isinstance(lv, dict) and lv.get("id")]
                # Ưu tiên: đúng 8-9 sao VÀ chưa dùng gần đây > đúng 8-9 sao (dù có trùng lịch sử)
                # > bất kỳ level nào chưa dùng gần đây > cuối cùng mới chấp nhận trùng lịch sử.
                for c in [
                    [lv for lv in pool if lv.get("stars") in (8, 9) and str(lv["id"]) not in exclude_ids],
                    [lv for lv in pool if lv.get("stars") in (8, 9)],
                    [lv for lv in pool if str(lv["id"]) not in exclude_ids],
                    pool,
                ]:
                    if c:
                        lv = random.choice(c)
                        return {"id": lv.get("id"), "name": lv.get("name"), "difficulty": lv.get("difficulty"), "stars": lv.get("stars")}
                return None
    except Exception as e:
        print(f"[LỖI CHỌN LEVEL DAILY NGẪU NHIÊN] {e}")
        return None

async def pick_random_event_level(exclude_ids=None):
    """Chọn ngẫu nhiên 1 level Hard Demon THẬT, tránh trùng các ID trong exclude_ids.
    Trả về dict {id,name,difficulty,stars} hoặc None nếu GDBrowser lỗi/không tìm được level phù hợp."""
    exclude_ids = {str(i) for i in (exclude_ids or [])}
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            page = random.randint(0, 9)
            url = f"https://gdbrowser.com/api/search/*?diff=-2&demonFilter=3&starred=true&count=100&page={page}"
            async with session.get(url) as r:
                if r.status != 200: return None
                data = await r.json()
                if not isinstance(data, list) or not data: return None
                pool = [lv for lv in data if isinstance(lv, dict) and lv.get("id")]
                candidates = [lv for lv in pool if str(lv["id"]) not in exclude_ids] or pool
                if not candidates: return None
                lv = random.choice(candidates)
                return {"id": lv.get("id"), "name": lv.get("name"), "difficulty": lv.get("difficulty"), "stars": lv.get("stars")}
    except Exception as e:
        print(f"[LỖI CHỌN LEVEL EVENT NGẪU NHIÊN] {e}")
        return None

async def get_recent_level_ids(loai: str):
    """Lấy danh sách ID level daily/event đã dùng gần đây (tối đa 8 lần gần nhất) để loại
    trừ khi chọn ngẫu nhiên, tránh lặp lại y hệt vòng trước."""
    settings = await db.settings.find_one({"_id": "gd_events"}) or {}
    return settings.get(f"{loai}_history", [])

async def push_recent_level_id(loai: str, level_id):
    """Ghi thêm 1 ID vào lịch sử daily/event, chỉ giữ tối đa 8 mục gần nhất."""
    await db.settings.update_one(
        {"_id": "gd_events"},
        {"$push": {f"{loai}_history": {"$each": [str(level_id)], "$slice": -8}}},
        upsert=True
    )
# ======================================================================================= #
# ======================================================================================= #

async def check_event_daily_validity():
    settings = await db.settings.find_one({"_id": "gd_events"})
    if not settings: return None, None
    now_ts = datetime.now(VN_TZ).timestamp()
    daily, event = settings.get("daily"), settings.get("event")
    
    def is_valid(data):
        if not data or not data.get("expires"): return False
        expires = data["expires"]
        if isinstance(expires, datetime):
            if expires.tzinfo is None: expires = expires.replace(tzinfo=VN_TZ)
            expires = expires.timestamp()
        return now_ts < expires

    return (daily if is_valid(daily) else None), (event if is_valid(event) else None)

# ĐÃ THÊM MỚI (v13): tự động cảnh báo khi Event/Daily sắp hết hạn (còn ≤1 tiếng) và khi
# đã hết hạn, thay vì phải chờ member/admin tự gõ !daily hoặc !event để biết. Mỗi mốc chỉ
# cảnh báo ĐÚNG 1 LẦN (nhờ cờ warned_soon/expired_notified, được reset về False mỗi khi
# admin đặt mục tiêu mới qua !thongbao) để tránh spam kênh mỗi 10 phút.
@tasks.loop(minutes=10)
async def check_expiry_task():
    if db is None: return
    settings = await db.settings.find_one({"_id": "gd_events"})
    if not settings: return
    now_ts = datetime.now(VN_TZ).timestamp()
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    public_channel = bot.get_channel(WELCOME_CHANNEL_ID)

    for loai in ["daily", "event"]:
        data = settings.get(loai)
        if not data or not data.get("expires"):
            # ĐÃ THÊM MỚI: nếu server CHƯA TỪNG có Daily/Event nào (kể cả sau khi bot mới
            # deploy lần đầu), tự động chọn ngay 1 level để gắn, không cần đợi Admin gõ lệnh.
            recent_ids = await get_recent_level_ids(loai)
            picked = await pick_random_daily_level(recent_ids) if loai == "daily" else await pick_random_event_level(recent_ids)
            if picked:
                now_dt = datetime.now(VN_TZ)
                new_expires = now_dt + timedelta(days=14) if loai == "event" else now_dt.replace(hour=23, minute=59, second=59)
                if new_expires <= now_dt: new_expires += timedelta(days=1)
                await db.settings.update_one({"_id": "gd_events"}, {"$set": {
                    f"{loai}": {"id": str(picked["id"]), "expires": new_expires.timestamp(), "warned_soon": False, "expired_notified": False}
                }}, upsert=True)
                await push_recent_level_id(loai, picked["id"])
                if public_channel:
                    try: await public_channel.send(f"🎲 **{loai.upper()}** đầu tiên đã được bot tự động chọn: **{picked['name']}** (ID `{picked['id']}`)!")
                    except (discord.Forbidden, discord.HTTPException): pass
            continue
        remaining = data["expires"] - now_ts

        if 0 < remaining <= 3600 and not data.get("warned_soon"):
            phut_con_lai = max(1, int(remaining // 60))
            msg = f"⏰ **{loai.upper()}** (ID: `{data['id']}`) sắp hết hạn trong khoảng **{phut_con_lai} phút** nữa, tranh thủ hoàn thành nhé!"
            if public_channel:
                try: await public_channel.send(msg)
                except (discord.Forbidden, discord.HTTPException): pass
            await db.settings.update_one({"_id": "gd_events"}, {"$set": {f"{loai}.warned_soon": True}})

        if remaining <= 0 and not data.get("expired_notified"):
            # ĐÃ THÊM MỚI: tự động chọn 1 level THẬT mới để gắn tiếp ngay khi hết hạn, không
            # cần chờ Admin gõ !thongbao thủ công nữa (Insane 8-9 sao cho daily, Hard Demon
            # cho event). Nếu GDBrowser đang lỗi/bận, rơi về hành vi CŨ: chỉ thông báo hết hạn
            # để Admin tự xử lý bằng !thongbao, tránh treo/spam lỗi liên tục mỗi 10 phút.
            recent_ids = await get_recent_level_ids(loai)
            picked = await pick_random_daily_level(recent_ids) if loai == "daily" else await pick_random_event_level(recent_ids)
            if picked:
                now_dt = datetime.now(VN_TZ)
                new_expires = now_dt + timedelta(days=14) if loai == "event" else now_dt.replace(hour=23, minute=59, second=59)
                if new_expires <= now_dt:  # phòng trường hợp task chạy sau 23:59:59 hôm nay
                    new_expires += timedelta(days=1)
                await db.settings.update_one({"_id": "gd_events"}, {"$set": {
                    f"{loai}": {"id": str(picked["id"]), "expires": new_expires.timestamp(), "warned_soon": False, "expired_notified": False}
                }})
                await push_recent_level_id(loai, picked["id"])
                msg_moi = f"🔄 **{loai.upper()}** mới đã được bot TỰ ĐỘNG chọn: **{picked['name']}** (ID `{picked['id']}`)! Hạn tới {new_expires.strftime('%d/%m/%Y %H:%M:%S')}."
                if public_channel:
                    try: await public_channel.send(msg_moi)
                    except (discord.Forbidden, discord.HTTPException): pass
                continue

            if admin_channel:
                try: await admin_channel.send(f"❌ **{loai.upper()}** (ID: `{data['id']}`) đã hết hạn! Bot không tự chọn được level mới lúc này (GDBrowser có thể đang bận). Dùng `!thongbao {loai} [ID mới]` để cập nhật mục tiêu, hoặc để trống ID để bot thử tự chọn lại.")
                except (discord.Forbidden, discord.HTTPException): pass
            if public_channel:
                try: await public_channel.send(f"❌ **{loai.upper()}** (ID: `{data['id']}`) đã hết hạn!")
                except (discord.Forbidden, discord.HTTPException): pass
            await db.settings.update_one({"_id": "gd_events"}, {"$set": {f"{loai}.expired_notified": True}})

@check_expiry_task.before_loop
async def before_check_expiry_task():
    await bot.wait_until_ready()

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title=f"🎉 Chào mừng {member.display_name} gia nhập server!", description="Dưới đây là một số hướng dẫn cơ bản để bạn làm quen với server nhé.", color=discord.Color.blue())
        embed.add_field(name="📜 Lệnh Bot Cơ Bản", value="Hãy gõ `!menu` tại kênh chat để xem toàn bộ danh sách lệnh.", inline=False)
        embed.add_field(name="💎 Nhận MP & Danh Hiệu", value="Dùng lệnh `!duyet [độ khó/event/daily/danh hiệu]` kèm video/ảnh làm bằng chứng.", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(content=member.mention, embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    bad_words = ["discord.gg/", "free nitro", "hack gem", "giftcode", "hack blox"]
    if any(word in message.content.lower() for word in bad_words):
        try:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention}, bạn không được gửi link/từ ngữ vi phạm!", delete_after=5)
            return 
        # ĐÃ FIX: bắt thêm discord.NotFound (VD: tin nhắn đã bị xoá bởi mod khác trước đó).
        # Trước đây chỉ bắt Forbidden, nên nếu xảy ra NotFound thì exception sẽ văng ra
        # ngoài, khiến on_message crash và KHÔNG BAO GIỜ gọi process_commands() cho tin
        # nhắn đó - nghĩa là lệnh trong chính tin nhắn đó (nếu có) sẽ không chạy.
        except (discord.Forbidden, discord.NotFound):
            pass
    await bot.process_commands(message)

# ================= GIAO DIỆN NÚT BẤM REPORT ================= #
class PunishmentModal(Modal):
    def __init__(self, action_type, reporter_id, reported_member, message_to_edit):
        titles = {"mute": "Khoá Chat", "ban": "Ban Khỏi Server", "deduct_mp": "Trừ MP"}
        super().__init__(title=titles.get(action_type, "Xử lý vi phạm"))
        self.action_type = action_type
        self.reporter_id = reporter_id
        self.reported_member = reported_member
        self.message_to_edit = message_to_edit

        if action_type == "mute":
            self.val_input = TextInput(label='Số phút khoá chat', placeholder="Ví dụ: 60", required=True)
            self.add_item(self.val_input)
        elif action_type == "deduct_mp":
            self.val_input = TextInput(label='Số MP cần trừ', placeholder="Ví dụ: 100", required=True)
            self.add_item(self.val_input)

        self.reason = TextInput(label='Ghi chú cho người report', style=discord.TextStyle.paragraph, placeholder="Nhập ghi chú (nếu có)...", required=False)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason_text = self.reason.value or "Không có ghi chú thêm."
        action_msg = ""
        try:
            if self.action_type == "mute":
                mins = int(self.val_input.value)
                await self.reported_member.timeout(timedelta(minutes=mins), reason=reason_text)
                action_msg = f"Đã khoá chat {mins} phút."
            elif self.action_type == "ban":
                await self.reported_member.ban(reason=reason_text)
                action_msg = "Đã Ban khỏi server."
            elif self.action_type == "deduct_mp":
                mp_amt = int(self.val_input.value)
                await db.users.update_one({"_id": self.reported_member.id}, {"$inc": {"mp": -abs(mp_amt)}})
                await check_and_transfer_top1_mp(interaction.guild)
                action_msg = f"Đã trừ {mp_amt} MP."
        except Exception as e:
            return await interaction.response.send_message(f"Lỗi khi thực hiện hình phạt: {e}", ephemeral=True)

        embed = self.message_to_edit.embeds[0]
        embed.title = "✅ BÁO CÁO ĐÃ ĐƯỢC XỬ LÝ"
        embed.color = discord.Color.green()
        embed.add_field(name="Hành động của Admin:", value=action_msg, inline=False)
        embed.add_field(name="Ghi chú:", value=reason_text, inline=False)
        await self.message_to_edit.edit(embed=embed, view=None)

        reporter = await bot.fetch_user(self.reporter_id)
        if reporter:
            dm_embed = discord.Embed(title="✅ KẾT QUẢ BÁO CÁO", color=discord.Color.green(), description=f"Báo cáo của bạn về {self.reported_member.mention} đã được xử lý.")
            dm_embed.add_field(name="Xử lý:", value=action_msg, inline=False)
            dm_embed.add_field(name="Ghi chú từ Admin:", value=reason_text, inline=False)
            try: await reporter.send(embed=dm_embed)
            except discord.Forbidden: pass
        await log_admin_action(interaction.user.mention, f"Xử lý report: {action_msg}", self.reported_member.mention, reason_text)
        # ĐÃ THÊM MỚI (v12): dọn record trong pending_actions vì report đã xử lý xong.
        await db.pending_actions.delete_one({"_id": self.message_to_edit.id})
        await interaction.response.send_message("Đã thi hành án phạt thành công!", ephemeral=True)

class ReportRejectModal(Modal, title='Từ Chối Báo Cáo'):
    reason = TextInput(label='Lý do từ chối', style=discord.TextStyle.paragraph, placeholder="Nhập lý do báo cáo này bị từ chối...", required=True)

    def __init__(self, reporter_id, message_to_edit):
        super().__init__()
        self.reporter_id = reporter_id
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.message_to_edit.embeds[0]
        embed.title = "❌ BÁO CÁO BỊ TỪ CHỐI"
        embed.color = discord.Color.red()
        embed.add_field(name="Người xử lý:", value=interaction.user.mention, inline=False)
        embed.add_field(name="Lý do từ chối:", value=self.reason.value, inline=False)
        await self.message_to_edit.edit(embed=embed, view=None)

        reporter = await bot.fetch_user(self.reporter_id)
        if reporter:
            dm_embed = discord.Embed(title="❌ BÁO CÁO BỊ TỪ CHỐI", color=discord.Color.red(), description="Báo cáo vi phạm của bạn đã bị Admin từ chối.")
            dm_embed.add_field(name="Lý do:", value=self.reason.value, inline=False)
            try: await reporter.send(embed=dm_embed)
            except discord.Forbidden: pass
        await log_admin_action(interaction.user.mention, "Từ chối report", None, self.reason.value)
        # ĐÃ THÊM MỚI (v12): dọn record trong pending_actions vì report đã xử lý xong.
        await db.pending_actions.delete_one({"_id": self.message_to_edit.id})
        await interaction.response.send_message("Đã từ chối báo cáo!", ephemeral=True)

class ReportActionView(View):
    def __init__(self, reporter_id, reported_member, message_to_edit):
        super().__init__(timeout=None)
        self.reporter_id = reporter_id
        self.reported_member = reported_member
        self.message_to_edit = message_to_edit

    @discord.ui.button(label="Khoá Chat", style=discord.ButtonStyle.blurple)
    async def btn_mute(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PunishmentModal("mute", self.reporter_id, self.reported_member, self.message_to_edit))

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def btn_ban(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PunishmentModal("ban", self.reporter_id, self.reported_member, self.message_to_edit))

    @discord.ui.button(label="Trừ MP", style=discord.ButtonStyle.secondary)
    async def btn_mp(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PunishmentModal("deduct_mp", self.reporter_id, self.reported_member, self.message_to_edit))

# ĐÃ FIX (v12): tương tự ReviewView, ReportReviewView giờ không nhận state qua __init__
# nữa mà tra lại (reporter_id, reported_member_id) từ db.pending_actions theo message_id,
# để có thể đăng ký persistent 1 lần duy nhất bằng bot.add_view(ReportReviewView()).
class ReportReviewView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _load(self, interaction: discord.Interaction):
        data = await db.pending_actions.find_one({"_id": interaction.message.id})
        if not data:
            await interaction.response.send_message(
                "⚠️ Không tìm thấy dữ liệu report này (có thể đã được xử lý bởi admin khác, "
                "hoặc dữ liệu bị mất do lỗi hệ thống).", ephemeral=True
            )
            return None
        return data

    @discord.ui.button(label="Duyệt và xử lý", style=discord.ButtonStyle.green, custom_id="btn_rep_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        data = await self._load(interaction)
        if not data: return
        try:
            reported_member = await interaction.guild.fetch_member(data["reported_member_id"])
        except discord.NotFound:
            return await interaction.response.send_message("⚠️ Người này đã rời server, không thể xử lý mute/ban (vẫn có thể trừ MP thủ công bằng `!addmp`).", ephemeral=True)
        view = ReportActionView(data["reporter_id"], reported_member, interaction.message)
        await interaction.response.send_message("Chọn hình phạt bạn muốn áp dụng:", view=view, ephemeral=True)
        
    @discord.ui.button(label="Từ chối (Kèm lý do)", style=discord.ButtonStyle.red, custom_id="btn_rep_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        data = await self._load(interaction)
        if not data: return
        await interaction.response.send_modal(ReportRejectModal(data["reporter_id"], interaction.message))

# ================= GIAO DIỆN NÚT BẤM DUYỆT BÀI ================= #
# ĐÃ FIX (v12 - BUG NGHIÊM TRỌNG): Trước đây ReviewView bắt buộc nhận (user_id,
# req_type, item_name, reward_value) qua __init__, và dù có timeout=None + custom_id
# (chủ đích làm view "sống mãi"), bot KHÔNG hề gọi bot.add_view() ở on_ready để đăng
# ký lại view khi khởi động. Trên Render, bot bị restart/redeploy thường xuyên -> mọi
# tin nhắn !duyet ĐÃ GỬI TRƯỚC ĐÓ mà admin chưa kịp bấm sẽ có nút bấm "chết": bấm vào
# Discord báo "Tương tác này thất bại" vì thư viện không thể tái tạo lại view cần state
# (user_id, req_type...) mà nó chưa từng biết tới.
# Cách fix: không lưu state trong __init__ nữa. Toàn bộ dữ liệu yêu cầu duyệt được lưu
# vào collection db.pending_actions với _id = message_id ngay khi gửi (xem lệnh !duyet).
# Khi bấm nút, view tra lại dữ liệu từ DB theo interaction.message.id. Nhờ vậy view có
# thể khởi tạo KHÔNG cần tham số và được đăng ký 1 lần duy nhất lúc on_ready bằng
# bot.add_view(ReviewView()) -> hoạt động với MỌI tin nhắn cũ, kể cả sau khi bot restart.
class RejectModal(Modal, title='Lí do từ chối bài duyệt'):
    reason = TextInput(label='Nhập lí do', style=discord.TextStyle.paragraph)
    
    def __init__(self, user_id, message_to_edit, item_name):
        super().__init__()
        self.user_id = user_id
        self.message_to_edit = message_to_edit
        self.item_name = item_name.lower() if item_name else ""

    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        extra_msg = ""
        if self.item_name == "vua try hard":
            await db.users.update_one({"_id": self.user_id}, {"$set": {"vth_streak": 0}})
            extra_msg = "\n⚠️ **CẢNH BÁO:** Chuỗi 5 Hardest liên tiếp của bạn đã bị reset về 0 do bị từ chối!"
            
        if user:
            try: await user.send(f"❌ Yêu cầu duyệt của bạn bị từ chối.\n**Lí do:** {self.reason.value}{extra_msg}")
            except discord.Forbidden: pass
        await self.message_to_edit.edit(content=f"❌ **Đã từ chối** bài của <@{self.user_id}>\nNgười duyệt: {interaction.user.mention}\nLý do: {self.reason.value}", view=None, embeds=[])
        await log_admin_action(interaction.user.mention, f"Từ chối bài: **{self.item_name.title()}**", f"<@{self.user_id}>", self.reason.value)
        # ĐÃ THÊM MỚI (v13): ghi vào lịch sử duyệt cá nhân (xem bằng !history).
        kind_for_log = "mp" if self.item_name in DIFFICULTY_MP else "role"
        await log_history(self.user_id, kind_for_log, self.item_name, "rejected", interaction.user.id, self.reason.value)
        # ĐÃ THÊM MỚI (v12): dọn record trong pending_actions vì yêu cầu đã được xử lý xong.
        await db.pending_actions.delete_one({"_id": self.message_to_edit.id})
        await interaction.response.send_message("Đã thông báo từ chối.", ephemeral=True)

class ReviewView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _load(self, interaction: discord.Interaction):
        """Tra lại dữ liệu yêu cầu duyệt từ DB theo ID tin nhắn hiện tại."""
        data = await db.pending_actions.find_one({"_id": interaction.message.id})
        if not data:
            await interaction.response.send_message(
                "⚠️ Không tìm thấy dữ liệu của yêu cầu này (có thể đã được xử lý bởi admin khác, "
                "hoặc dữ liệu bị mất do lỗi hệ thống). Vui lòng yêu cầu người dùng gửi lại `!duyet`.",
                ephemeral=True
            )
            return None
        return data

    @discord.ui.button(label="Duyệt", style=discord.ButtonStyle.green, custom_id="btn_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        # ĐÃ FIX (bug cộng MP gấp đôi): trước đây _load() chỉ ĐỌC (find_one) dữ liệu,
        # còn việc xoá pending_actions nằm ở CUỐI hàm (sau khi đã cộng MP xong). Nếu
        # admin bấm "Duyệt" 2 lần liên tiếp thật nhanh (double-tap trên điện thoại,
        # hoặc lag Discord), cả 2 lần bấm đều có thể đọc được cùng 1 dữ liệu TRƯỚC KHI
        # lần đầu kịp xoá -> add_user_mp() chạy 2 lần -> cộng gấp đôi (VD: insane demon
        # 5000 MP bị cộng thành 10000 MP).
        # Cách fix: dùng find_one_and_delete để "claim" (đọc + xoá) pending_action
        # trong 1 thao tác DUY NHẤT, atomic ở tầng MongoDB. Lần bấm thứ 2 (dù có đến
        # cùng lúc) sẽ không còn tìm thấy dữ liệu -> bị chặn ngay, không cộng MP lần nữa.
        data = await db.pending_actions.find_one_and_delete({"_id": interaction.message.id})
        if not data:
            await interaction.response.send_message(
                "⚠️ Yêu cầu này đã được xử lý rồi (có thể do bấm trùng hoặc admin khác đã duyệt).",
                ephemeral=True
            )
            return
        user_id, req_type, item_name, reward_value = data["user_id"], data["req_type"], data["item_name"], data["reward_value"]
        print(f"[DEBUG DUYỆT] message_id={interaction.message.id} user_id={user_id} req_type={req_type} item_name='{item_name}' reward_value={reward_value}")

        # ĐÃ FIX: defer ngay lập tức để Discord không báo "Tương tác thất bại" cho admin
        # nếu các bước xử lý bên dưới (đặc biệt là gọi Gemini/GDBrowser để tự nhận diện
        # tên level Demon trong bằng chứng) chạy chậm quá 3 giây. Trước đây nếu chậm quá
        # 3s, Discord tự hiển thị lỗi dù bot vẫn đang cộng MP ngầm phía sau -> admin tưởng
        # lỗi nên bấm duyệt lại lần 2 -> (trước khi có find_one_and_delete ở trên) sẽ cộng
        # MP 2 lần. Giờ đã có find_one_and_delete chặn double-submit, defer() ở đây chỉ để
        # tránh gây hoang mang không cần thiết cho admin.
        await interaction.response.defer(ephemeral=True, thinking=True)

        user = await bot.fetch_user(user_id)
        guild = interaction.guild
        msg_user, msg_admin = "", ""

        if req_type == "mp":
            await add_user_mp(user_id, reward_value, guild)
            msg_user = f"🎉 Level **{item_name.title()}** đã được duyệt! +{reward_value} MP!"
            msg_admin = f"✅ Đã duyệt +{reward_value} MP cho <@{user_id}>."
            
            auto_title = None
            if item_name == "easy demon": auto_title = "newbie"
            elif item_name == "medium demon": auto_title = "sự khởi đầu"
            elif item_name == "hard demon": auto_title = "pro"
            elif item_name == "insane demon": auto_title = "hardcore player"
            elif item_name == "extreme demon": auto_title = "huyền thoại"
                
            if auto_title:
                await db.users.update_one({"_id": user_id}, {"$addToSet": {"titles": auto_title}, "$set": {"active_title": auto_title}}, upsert=True)
                msg_user += f"\n🎖️ Hệ thống tự động thêm danh hiệu **{auto_title.title()}** vào tủ đồ của bạn!"
                msg_admin += f"\n🎖️ Đã tự động cấp danh hiệu **{auto_title.title()}** thành công."

            # ĐÃ THÊM MỚI: tự động quét tên level trong ảnh/video bằng chứng để nhận diện
            # Demon khó nhất đã vượt qua (xem try_update_hardest_demon). Bọc try/except
            # riêng vì đây CHỈ LÀ TÍNH NĂNG PHỤ - dù Gemini/GDBrowser lỗi/timeout/hết quota
            # thì việc cộng MP + cấp danh hiệu ở trên vẫn phải thành công bình thường.
            if "demon" in item_name and not data.get("is_video_link") and data.get("evidence_url"):
                try:
                    # ĐÃ FIX: nếu bằng chứng đã được đính kèm thật (has_fresh_attachment),
                    # lấy URL trực tiếp từ attachment hiện tại của message thay vì URL cũ
                    # đã lưu trong DB (dễ hết hạn nếu Admin duyệt trễ) - Discord tự ký lại
                    # URL này mỗi lần message được gửi kèm tương tác/fetch.
                    fresh_url = data["evidence_url"]
                    if data.get("has_fresh_attachment") and interaction.message.attachments:
                        fresh_url = interaction.message.attachments[0].url
                    thong_bao_demon = await try_update_hardest_demon(user_id, fresh_url)
                    if thong_bao_demon:
                        msg_user += thong_bao_demon
                except Exception as e:
                    print(f"[LỖI TỰ ĐỘNG NHẬN DIỆN DEMON] {e}")

        elif req_type == "role":
            role_name = item_name.lower()
            if role_name == "vua hardest":
                await grant_vua_hardest(guild, user_id)
                msg_user = "🏆 Chúc mừng! Bạn đã trở thành VUA HARDEST mới của server!"
                msg_admin = f"✅ Đã cấp danh hiệu **Vua Hardest** cho <@{user_id}>."
            elif role_name == "vua try hard":
                await db.users.update_one({"_id": user_id}, {"$inc": {"vth_streak": 1}}, upsert=True)
                user_doc = await db.users.find_one({"_id": user_id})
                streak = user_doc.get("vth_streak", 1)
                
                if streak >= 5:
                    await grant_vua_try_hard(guild, user_id)
                    await db.users.update_one({"_id": user_id}, {"$set": {"vth_streak": 0}})
                    msg_user = "🔥 KINH KHỦNG! Bạn đã beat 5 Hardest liên tiếp độ khó tăng dần và trở thành VUA TRY HARD mới của server!"
                    msg_admin = f"✅ Đã duyệt bài (Chuỗi 5/5). Đã tước và cấp danh hiệu **Vua Try Hard** cho <@{user_id}>."
                else:
                    msg_user = f"✅ Admin đã duyệt Hardest của bạn! Chuỗi Vua Try Hard hiện tại: **{streak}/5**. Hãy tiếp tục phá kỷ lục nhé!"
                    msg_admin = f"✅ Đã duyệt bài (Chuỗi {streak}/5 Vua Try Hard) cho <@{user_id}>."
            else:
                await db.users.update_one({"_id": user_id}, {"$addToSet": {"titles": role_name}, "$set": {"active_title": role_name}}, upsert=True)
                msg_user = f"🏆 Đỉnh quá! Bạn nhận được danh hiệu **{role_name.title()}**!"
                msg_admin = f"✅ Đã duyệt danh hiệu **{role_name.title()}** cho <@{user_id}>."

        if user and msg_user:
            try: await user.send(msg_user)
            except discord.Forbidden: pass
        # ĐÃ THÊM MỚI: đếm số bài đã được duyệt thành công (hiển thị ở !profile),
        # và ghi log admin action vào kênh log riêng.
        await db.users.update_one({"_id": user_id}, {"$inc": {"approved_count": 1}}, upsert=True)
        await log_admin_action(interaction.user.mention, f"Duyệt {req_type.upper()}: **{item_name.title()}**", f"<@{user_id}>", msg_admin)
        # ĐÃ THÊM MỚI (v13): ghi vào lịch sử duyệt cá nhân (xem bằng !history).
        await log_history(user_id, req_type, item_name, "approved", interaction.user.id, msg_admin)
        await interaction.message.edit(content=f"{msg_admin}\nBởi: {interaction.user.mention}", view=None, embeds=[])
        # (Đã xoá pending_actions ngay từ đầu hàm bằng find_one_and_delete ở trên rồi,
        # không cần xoá lại ở đây nữa.)
        await interaction.followup.send("Duyệt thành công!", ephemeral=True)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        data = await self._load(interaction)
        if not data: return
        await interaction.response.send_modal(RejectModal(data["user_id"], interaction.message, data["item_name"]))

# ================= CÁC LỆNH BOT ================= #
@bot.command()
async def menu(ctx):
    is_admin = getattr(ctx.author, 'guild_permissions', None) and ctx.author.guild_permissions.administrator
    embed = discord.Embed(
        title="📚 HƯỚNG DẪN TỔNG HỢP LỆNH BOT", 
        description="Chào mừng bạn! Dưới đây là danh sách các tính năng của server.",
        color=discord.Color.blurple()
    )
    
    embed.add_field(name="💎 1. HỆ THỐNG DUYỆT BÀI & ĐIỂM MP", value="• `!duyet [độ khó/event/daily/danh hiệu]`\n📌 Gắn kèm video/ảnh, hoặc dán **link Youtube** (máy yếu) làm bằng chứng - Admin sẽ tự kiểm tra link trước khi duyệt.\n• `!bxh` - Xem Bảng Xếp Hạng MP.", inline=False)
    embed.add_field(name="🎖️ 2. DANH HIỆU TỰ ĐỘNG NHẬN", value="• Easy Demon ➔ `Newbie`\n• Medium Demon ➔ `Sự Khởi Đầu`\n• Hard Demon ➔ `Pro`\n• Insane Demon ➔ `Hardcore Player`\n• Extreme Demon ➔ `Huyền Thoại`\n📖 Xem đủ **57 danh hiệu** + cách lấy: `!danhsachdanhhieu`", inline=False)
    embed.add_field(name="👑 3. CÁC NGÔI VỊ TỐI THƯỢNG", value="🥇 **Vua Cày Điểm**: Top 1 MP toàn server.\n🏆 **Vua Hardest**: Duyệt bằng lệnh `!duyet vua hardest`.\n🔥 **Vua Try Hard**: 5 Hardest liên tiếp tăng dần, dùng `!duyet vua try hard`.", inline=False)
    embed.add_field(name="🎒 4. QUẢN LÝ DANH HIỆU", value="• `!listdanhhieu`: Xem danh hiệu bạn có.\n• `!setdanhhieu [tên]`: Trang bị danh hiệu.\n• `!editdanhhieu [an/hien]`: Bật/Tắt hiển thị.", inline=False)
    embed.add_field(name="📇 Hồ sơ", value="`!profile [@user]` xem MP, hạng, danh hiệu, Demon/Challenge khó nhất đã vượt qua.\n`!editprofile [mô tả]` đặt/xoá mô tả cá nhân trên hồ sơ.", inline=True)
    embed.add_field(name="📜 Lịch sử", value="`!history [@user]` xem 10 lượt duyệt gần nhất.", inline=True)
    embed.add_field(name="🎯 Sự kiện", value="`!daily` / `!event` xem mục tiêu hiện tại (tự động cảnh báo khi sắp/đã hết hạn).", inline=True)
    embed.add_field(name="🤖 AI Gợi ý", value="`!dexuatlevel [yêu cầu]` đề xuất level có ID chính xác.", inline=True)
    embed.add_field(name="🚨 Tố cáo", value="`!report @user [lý do]` kèm bằng chứng.", inline=True)
    embed.add_field(name="🏁 Challenge", value="`!nopchallenge [ID level] [tên] | [tên Verify] | [tên người tạo]` nộp challenge kèm bằng chứng (ảnh/video hoặc link Youtube).\n`!bxhchallenge` xem BXH Challenge.\n`!profile` xem challenge khó nhất bạn đã vượt qua.", inline=True)
    
    if is_admin:
        embed.add_field(name="🛠️ LỆNH ADMIN", value="• `!setmp @user [số]` đặt lại điểm\n• `!addmp @user [số]` cộng/trừ điểm\n• `!thongbao [event/daily] [ID - có thể bỏ trống để bot tự chọn ngẫu nhiên]`\n📌 Daily/Event cũng TỰ ĐỘNG re-roll level mới ngay khi hết hạn, không cần Admin can thiệp.\n• `!dondanhieu` dọn dữ liệu active_title bị lỗi\n• Challenge: bấm nút Duyệt/Từ chối trên tin nhắn ở kênh admin\n• `!bxhchallenge [id] [vị trí]` xếp lại hạng Challenge\n• `!xoachallenge [id] [lý do]` gỡ challenge gian lận (hack/ăn cắp)", inline=False)
        
    embed.set_footer(text="💡 Nhớ gửi kèm ảnh/video khi dùng !duyet hay !report nhé!")
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
@require_db()
async def setmp(ctx, member: discord.Member, amount: int):
    await db.users.update_one({"_id": member.id}, {"$set": {"mp": amount}}, upsert=True)
    await check_and_transfer_top1_mp(ctx.guild)
    await log_admin_action(ctx.author.mention, "Đặt lại MP", member.mention, f"Đặt thành {amount} MP")
    await ctx.send(f"✅ Đã đặt MP của {member.mention} thành {amount}.")

@bot.command()
@commands.has_permissions(administrator=True)
@require_db()
async def addmp(ctx, member: discord.Member, amount: int):
    await add_user_mp(member.id, amount, ctx.guild)
    await log_admin_action(ctx.author.mention, "Cộng/trừ MP", member.mention, f"{'Cộng' if amount > 0 else 'Trừ'} {abs(amount)} MP")
    await ctx.send(f"✅ Đã {'cộng' if amount > 0 else 'trừ'} {abs(amount)} MP cho {member.mention}.")

@bot.command()
@commands.has_permissions(administrator=True)
@require_db()
async def thongbao(ctx, loai: str, level_id: str = None):
    loai = loai.lower()
    if loai not in ["event", "daily"]:
        return await ctx.send("❌ Loại phải là `event` hoặc `daily`.")

    # ĐÃ THÊM MỚI: nếu Admin không nhập ID level, bot tự động chọn ngẫu nhiên 1 level THẬT
    # phù hợp (Insane 8-9 sao cho daily, Hard Demon cho event) từ GDBrowser.
    level_name = None
    if not level_id:
        msg_wait = await ctx.send(f"🔎 Chưa nhập ID level, đang tự động chọn ngẫu nhiên {'1 Insane 8-9 sao' if loai == 'daily' else '1 Hard Demon'} thật từ GDBrowser...")
        recent_ids = await get_recent_level_ids(loai)
        picked = await pick_random_daily_level(recent_ids) if loai == "daily" else await pick_random_event_level(recent_ids)
        if not picked:
            return await msg_wait.edit(content=f"❌ Không tự động chọn được level nào lúc này (GDBrowser có thể đang bận). Thử lại sau, hoặc nhập ID thủ công: `!thongbao {loai} [ID]`")
        level_id, level_name = str(picked["id"]), picked["name"]
        await push_recent_level_id(loai, level_id)
        try: await msg_wait.delete()
        except (discord.Forbidden, discord.NotFound): pass

    now = datetime.now(VN_TZ)
    expires = now + timedelta(days=14) if loai == "event" else now.replace(hour=23, minute=59, second=59)
        
    await db.settings.update_one(
        {"_id": "gd_events"},
        {"$set": {f"{loai}": {"id": level_id, "expires": expires.timestamp(), "warned_soon": False, "expired_notified": False}}},
        upsert=True
    )
    if not level_name:
        # Admin tự nhập ID thủ công - vẫn ghi vào lịch sử để lần sau bot auto-pick không chọn trùng lại.
        await push_recent_level_id(loai, level_id)
    
    embed = discord.Embed(title=f"📢 THÔNG BÁO {loai.upper()} MỚI", color=discord.Color.gold())
    embed.add_field(name="ID Level", value=f"**{level_id}**" + (f" — {level_name}" if level_name else ""), inline=False)
    embed.add_field(name="Hết hạn", value=expires.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
    if level_name:
        embed.set_footer(text="🎲 Level này được bot tự động chọn ngẫu nhiên")
    await ctx.send(embed=embed)

@bot.command(aliases=["daily", "event"])
@require_db()
async def show_event(ctx):
    cmd_used = ctx.invoked_with.lower()
    if cmd_used == "show_event": cmd_used = "event"
    
    daily_valid, event_valid = await check_event_daily_validity()
    data = daily_valid if cmd_used == "daily" else event_valid
    if not data: return await ctx.send(f"❌ Chưa có {cmd_used} nào hoặc đã hết hạn!")
    
    expires_dt = datetime.fromtimestamp(data['expires'], VN_TZ)
    embed = discord.Embed(title=f"🎯 MỤC TIÊU {cmd_used.upper()}", color=discord.Color.green())
    embed.add_field(name="ID Level", value=f"**{data['id']}**", inline=False)
    embed.add_field(name="Hết hạn", value=expires_dt.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
    await ctx.send(embed=embed)

@bot.command()
@require_db()
async def duyet(ctx, *, yeu_cau: str = None):
    if not yeu_cau: return await ctx.send("❌ VD: `!duyet easy demon` hoặc `!duyet vua hardest`")
    # ĐÃ FIX: dọn link Youtube ra khỏi yeu_cau NGAY TỪ ĐẦU, tránh trường hợp người dùng gõ
    # chung 1 câu kiểu "!duyet easy demon https://youtu.be/xxxx" khiến yeu_cau không khớp
    # được với DIFFICULTY_MP/TITLES_DATA (luôn báo "Yêu cầu không hợp lệ").
    yeu_cau = strip_youtube_link(yeu_cau).lower()
    
    if yeu_cau == "vua cày điểm": 
        return await ctx.send("❌ Danh hiệu **Vua Cày Điểm** được cấp tự động cho Top 1 MP. Bạn không thể duyệt thủ công!")

    # ĐÃ THÊM MỚI: cho phép nộp bằng chứng qua link Youtube (dành cho máy yếu không xuất
    # được video ra tin nhắn) - nếu không có file đính kèm, bot tìm link Youtube trong nội
    # dung tin nhắn và gửi thẳng cho kiểm duyệt viên; kiểm duyệt viên tự bấm vào link kiểm
    # tra (không có bước xác minh tự động).
    evidence_url, la_video_link = None, False
    if ctx.message.attachments:
        evidence_url = ctx.message.attachments[0].url
    else:
        yt_id = extract_youtube_id(ctx.message.content)
        if not yt_id:
            return await ctx.send("📸 Phải gửi kèm ảnh/video bằng chứng, hoặc dán link video Youtube (dành cho máy yếu)!")
        evidence_url, la_video_link = f"https://youtu.be/{yt_id}", True

    is_mp = yeu_cau in DIFFICULTY_MP
    is_role = yeu_cau in TITLES_DATA
    if not is_mp and not is_role: return await ctx.send("❌ Yêu cầu không hợp lệ!")

    if yeu_cau in ["daily", "event"]:
        daily_valid, event_valid = await check_event_daily_validity()
        if yeu_cau == "daily" and not daily_valid: return await ctx.send("❌ Daily đã hết hạn.")
        if yeu_cau == "event" and not event_valid: return await ctx.send("❌ Event đã hết hạn.")

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)

    if is_role:
        embed = discord.Embed(title="⭐ YÊU CẦU DUYỆT DANH HIỆU", color=discord.Color.gold())
        req_type, reward_name, reward_value = "role", "Danh hiệu", yeu_cau.title()
    else:
        embed = discord.Embed(title="💎 YÊU CẦU DUYỆT ĐIỂM MP", color=discord.Color.blue())
        req_type, reward_name, reward_value = "mp", "Điểm MP", f"+{DIFFICULTY_MP[yeu_cau]} MP"
        print(f"[DEBUG DUYET] user={ctx.author} yeu_cau='{yeu_cau}' -> MP tính được = {DIFFICULTY_MP[yeu_cau]}")

    embed.add_field(name="👤 Người gửi", value=ctx.author.mention, inline=True)
    embed.add_field(name="🎁 Loại", value=f"**{reward_name}**", inline=True)
    embed.add_field(name="✨ Phần thưởng", value=f"**{reward_value}**", inline=True)

    # ĐÃ FIX (BUG "không tự thêm Demon khó nhất vào profile"): trước đây bot lưu thẳng
    # ctx.message.attachments[0].url (URL CDN Discord có chữ ký hết hạn sau vài giờ) vào
    # pending_actions. Nếu Admin bấm Duyệt SAU KHI link đã hết hạn, lúc tải ảnh về để
    # Gemini đọc tên level sẽ lỗi 403 -> try_update_hardest_demon() âm thầm return "" ->
    # hardest_demon KHÔNG được cập nhật, dù MP/danh hiệu vẫn cộng bình thường (không báo
    # lỗi gì cho Admin thấy). Giờ tải bytes về NGAY lúc nộp bài rồi re-upload thành file
    # thật lên kênh admin -> khi Duyệt, bot dùng lại chính attachment của message này
    # (URL được Discord ký lại mỗi lần fetch), thay vì dùng URL gốc đã lưu cứng.
    evidence_file = None
    if not la_video_link and evidence_url:
        try:
            raw, content_type = await _download_evidence_bytes(evidence_url)
            if raw:
                ext = (content_type or "").split("/")[-1].split(";")[0] or "png"
                evidence_file = discord.File(io.BytesIO(raw), filename=f"evidence.{ext}")
        except Exception as e:
            print(f"[LỖI TẢI TRƯỚC BẰNG CHỨNG !duyet] {e}")

    if la_video_link:
        embed.add_field(name="🔗 Bằng chứng", value=f"📺 [Video Youtube]({evidence_url}) — ⚠️ Admin vui lòng tự bấm vào link kiểm tra trước khi duyệt", inline=False)
    elif evidence_file:
        embed.add_field(name="🔗 Bằng chứng", value="📎 Xem ảnh/video đính kèm bên dưới", inline=False)
        embed.set_image(url=f"attachment://{evidence_file.filename}")
    else:
        # Không tải trước được (mạng lỗi) -> vẫn fallback về URL gốc như code cũ.
        embed.add_field(name="🔗 Bằng chứng", value=f"[Xem tại đây]({evidence_url})", inline=False)
        embed.set_image(url=evidence_url)

    if admin_channel is None:
        return await ctx.send("❌ Không tìm thấy kênh admin để gửi duyệt (kiểm tra lại ADMIN_CHANNEL_ID và quyền bot).")

    view = ReviewView()
    sent_msg = await admin_channel.send(embed=embed, view=view, file=evidence_file if evidence_file else discord.utils.MISSING)
    # ĐÃ THÊM MỚI (v12): lưu dữ liệu yêu cầu vào DB theo message_id, để ReviewView có thể
    # tra lại đúng dữ liệu ngay cả sau khi bot restart (xem giải thích ở class ReviewView).
    await db.pending_actions.insert_one({
        "_id": sent_msg.id,
        "kind": "review",
        "user_id": ctx.author.id,
        "req_type": req_type,
        "item_name": yeu_cau,
        "reward_value": DIFFICULTY_MP.get(yeu_cau, yeu_cau),
        # ĐÃ THÊM MỚI: lưu lại bằng chứng để lúc Duyệt có thể tự quét tên level (xem
        # scan_level_name_from_evidence) - không quét ngay ở bước nộp để tránh tốn quota
        # Gemini cho những bài rồi sẽ bị Admin từ chối.
        # ĐÃ FIX: evidence_url ở đây chỉ dùng làm fallback (VD: link Youtube, hoặc trường
        # hợp tải trước ảnh thất bại). Nếu evidence_file đã được đính kèm thật lên message
        # ở kênh admin, lúc Duyệt sẽ ưu tiên lấy URL TƯƠI từ chính attachment của message
        # đó (xem approve_btn) thay vì dùng URL cũ đã hết hạn.
        "evidence_url": evidence_url,
        "is_video_link": la_video_link,
        "has_fresh_attachment": evidence_file is not None,
    })
    await ctx.send("✅ Đã gửi cho Admin duyệt nhé!")

# ĐÃ THÊM MỚI (v24): tự động dồn/xếp lại thứ hạng BXH Challenge, KHÔNG cần Admin tự tay
# sửa từng challenge còn lại mỗi khi có thay đổi. 3 trường hợp cần dồn hạng:
#   1) Duyệt 1 challenge mới vào giữa bảng (VD: bảng có #1,#2,#3, gán challenge mới vào #2)
#      -> #2,#3 cũ phải lùi xuống thành #3,#4 để nhường chỗ, không bị trùng #2.
#   2) Admin xếp LẠI hạng 1 challenge đã có hạng (dời từ #2 lên #5 hoặc ngược lại)
#      -> các hạng nằm giữa vị trí cũ và mới phải dịch chuyển 1 bậc cho khớp.
#   3) Challenge bị xoá khỏi bảng (!xoachallenge) hoặc gỡ hạng
#      -> các hạng phía sau phải dồn lên để không bị hở số (VD: #1,#2,#3,#4 mất #2 thì
#      #3,#4 phải dồn thành #2,#3, KHÔNG được để trống #2).
# ĐÃ THÊM MỚI (v26): helper hiển thị "người tạo | người Verify" trên BXH Challenge.
# Nếu 2 tên GIỐNG NHAU (không phân biệt hoa/thường, khoảng trắng thừa) -> nghĩa là tự
# làm level rồi tự verify luôn -> chỉ hiện 1 tên duy nhất cho gọn, khỏi lặp lại 2 lần.
def format_creator_verifier(challenge: dict) -> str:
    creator = (challenge.get("creator_name") or "?").strip()
    verifier = (challenge.get("verifier_name") or "?").strip()
    if creator.lower() == verifier.lower():
        return f"👤 {creator} (tự làm & tự Verify)"
    return f"🛠️ Tạo: {creator} | ✅ Verify: {verifier}"

async def move_challenge_rank(challenge_id: int, old_rank, new_rank: int):
    """Gán challenge_id vào new_rank và tự động dịch chuyển các challenge đã duyệt khác
    (status='approved') để bảng luôn là dãy số liên tục 1..N, không trùng không hở.
    old_rank=None nghĩa là challenge đang được duyệt/xếp hạng LẦN ĐẦU (chưa có hạng cũ)."""
    if old_rank is None:
        # Chèn mới vào new_rank -> mọi challenge có rank >= new_rank phải lùi lại (+1).
        await db.challenges.update_many(
            {"status": "approved", "_id": {"$ne": challenge_id}, "rank": {"$gte": new_rank}},
            {"$inc": {"rank": 1}}
        )
    elif new_rank > old_rank:
        # Dời XUỐNG (số to hơn) -> các challenge nằm giữa (old_rank, new_rank] phải lùi lên (-1).
        await db.challenges.update_many(
            {"status": "approved", "_id": {"$ne": challenge_id}, "rank": {"$gt": old_rank, "$lte": new_rank}},
            {"$inc": {"rank": -1}}
        )
    elif new_rank < old_rank:
        # Dời LÊN (số nhỏ hơn) -> các challenge nằm giữa [new_rank, old_rank) phải lùi xuống (+1).
        await db.challenges.update_many(
            {"status": "approved", "_id": {"$ne": challenge_id}, "rank": {"$gte": new_rank, "$lt": old_rank}},
            {"$inc": {"rank": 1}}
        )
    # new_rank == old_rank -> không có gì để dồn, chỉ set lại cho chắc.
    await db.challenges.update_one({"_id": challenge_id}, {"$set": {"status": "approved", "rank": new_rank}})

async def close_challenge_rank_gap(old_rank):
    """Sau khi 1 challenge bị xoá khỏi bảng/gỡ hạng, dồn tất cả challenge có hạng PHÍA SAU
    old_rank lên 1 bậc để lấp chỗ trống, giữ bảng luôn liên tục không hở số."""
    if old_rank is None: return
    await db.challenges.update_many(
        {"status": "approved", "rank": {"$gt": old_rank}},
        {"$inc": {"rank": -1}}
    )
# ==================================================================== #

# ================= HỆ THỐNG CHALLENGE (MỚI - v13/v14) ================= #
# ĐÃ THÊM MỚI: hệ thống Challenge tách riêng khỏi MP/danh hiệu thường. Member tự nộp
# challenge (level tự chọn/tự thử thách, kèm ID level thật) qua !nopchallenge, Admin
# xem xét và bấm nút "Duyệt"/"Từ chối" ngay trên tin nhắn. Khác với !duyet, việc XẾP
# HẠNG trên BXH Challenge KHÔNG tự động - Admin nhập tay số thứ hạng ngay khi bấm
# "Duyệt" (và có thể xếp lại bất kỳ lúc nào qua !bxhchallenge), vì độ khó/chất lượng
# challenge cần đánh giá thủ công, không thể so sánh bằng số như MP.
#
# ĐÃ THÊM MỚI (v14): thay vì gõ lệnh !ratechallenge, Admin giờ bấm nút "Duyệt"/"Từ chối"
# ngay trên tin nhắn (giống !duyet). Bấm "Duyệt" sẽ hiện modal nhập SỐ THỨ HẠNG luôn
# trong 1 bước (không cần chạy thêm !bxhchallenge nữa, trừ khi muốn xếp lại sau này).
# Bấm "Từ chối" hiện modal nhập lý do. View dùng chung cơ chế pending_actions (giống
# ReviewView/ReportReviewView) để sống sót qua restart bot.
class ChallengeRankModal(Modal, title="Duyệt & Xếp hạng Challenge"):
    vi_tri = TextInput(label="Số thứ hạng (VD: 1, 2, 3...)", placeholder="1", required=True)

    def __init__(self, challenge_id: int, message_to_edit):
        super().__init__()
        self.challenge_id = challenge_id
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rank = int(self.vi_tri.value)
            if rank < 1: raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Số thứ hạng phải là số nguyên dương (1, 2, 3...)!", ephemeral=True)

        challenge = await db.challenges.find_one({"_id": self.challenge_id})
        if not challenge:
            return await interaction.response.send_message("❌ Không tìm thấy dữ liệu challenge này (có thể đã bị xoá).", ephemeral=True)

        # ĐÃ FIX (v24): dùng move_challenge_rank thay vì set thẳng rank, để các challenge
        # đã duyệt trước đó có rank >= rank mới TỰ ĐỘNG lùi lại nhường chỗ, tránh trùng
        # thứ hạng khi Admin chèn challenge mới vào giữa bảng (VD: gán #2 khi #2 đã có người).
        await move_challenge_rank(self.challenge_id, None, rank)
        await log_history(challenge["submitter_id"], "challenge", challenge["name"], "approved", interaction.user.id, f"Xếp hạng #{rank}")
        await log_admin_action(interaction.user.mention, f"Duyệt Challenge #{self.challenge_id}: **{challenge['name']}**", f"<@{challenge['submitter_id']}>", f"Xếp hạng #{rank} (tự động dồn các hạng phía sau)")

        submitter = await bot.fetch_user(challenge["submitter_id"])
        if submitter:
            try: await submitter.send(f"🎉 Challenge **{challenge['name']}** (ID Level: `{challenge.get('level_id', '?')}`) đã được duyệt và xếp hạng **#{rank}** trên BXH Challenge!")
            except discord.Forbidden: pass

        await self.message_to_edit.edit(content=f"✅ **Đã duyệt Challenge** `#{self.challenge_id}` — **{challenge['name']}**, xếp hạng **#{rank}**\nBởi: {interaction.user.mention}", view=None, embeds=[])
        await db.pending_actions.delete_one({"_id": self.message_to_edit.id})
        await interaction.response.send_message(f"✅ Đã duyệt và xếp hạng #{rank} thành công!", ephemeral=True)

class ChallengeRejectModal(Modal, title="Từ chối Challenge"):
    reason = TextInput(label="Lý do từ chối", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, challenge_id: int, message_to_edit):
        super().__init__()
        self.challenge_id = challenge_id
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        challenge = await db.challenges.find_one({"_id": self.challenge_id})
        if not challenge:
            return await interaction.response.send_message("❌ Không tìm thấy dữ liệu challenge này (có thể đã bị xoá).", ephemeral=True)

        await db.challenges.update_one({"_id": self.challenge_id}, {"$set": {"status": "rejected"}})
        await log_history(challenge["submitter_id"], "challenge", challenge["name"], "rejected", interaction.user.id, self.reason.value)
        await log_admin_action(interaction.user.mention, f"Từ chối Challenge #{self.challenge_id}: **{challenge['name']}**", f"<@{challenge['submitter_id']}>", self.reason.value)

        submitter = await bot.fetch_user(challenge["submitter_id"])
        if submitter:
            try: await submitter.send(f"❌ Challenge **{challenge['name']}** của bạn bị từ chối.\n**Lý do:** {self.reason.value}")
            except discord.Forbidden: pass

        await self.message_to_edit.edit(content=f"❌ **Đã từ chối Challenge** `#{self.challenge_id}` — **{challenge['name']}**\nLý do: {self.reason.value}\nBởi: {interaction.user.mention}", view=None, embeds=[])
        await db.pending_actions.delete_one({"_id": self.message_to_edit.id})
        await interaction.response.send_message("Đã thông báo từ chối.", ephemeral=True)

class ChallengeReviewView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _load_challenge_id(self, interaction: discord.Interaction):
        data = await db.pending_actions.find_one({"_id": interaction.message.id})
        if not data:
            await interaction.response.send_message(
                "⚠️ Không tìm thấy dữ liệu challenge này (có thể đã được xử lý bởi admin khác, "
                "hoặc dữ liệu bị mất do lỗi hệ thống).", ephemeral=True
            )
            return None
        return data["challenge_id"]

    @discord.ui.button(label="Duyệt", style=discord.ButtonStyle.green, custom_id="btn_chal_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        challenge_id = await self._load_challenge_id(interaction)
        if challenge_id is None: return
        await interaction.response.send_modal(ChallengeRankModal(challenge_id, interaction.message))

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_chal_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        challenge_id = await self._load_challenge_id(interaction)
        if challenge_id is None: return
        await interaction.response.send_modal(ChallengeRejectModal(challenge_id, interaction.message))

@bot.command(aliases=["submitchallenge", "nopchall"])
@require_db()
async def nopchallenge(ctx, level_id: str = None, *, noi_dung: str = None):
    # ĐÃ THÊM MỚI (v14): bắt buộc kèm ID level GD thật, để admin/member đối chiếu đúng
    # level khi xem lại, và tránh challenge "ma" không xác định được là level nào.
    #
    # ĐÃ SỬA (v25): thêm 2 trường "tên người Verify" và "tên người tạo". Vì cả 3 trường
    # (tên challenge / tên Verify / tên người tạo) đều là text tự do có thể chứa khoảng
    # trắng (VD "Nguyễn Văn A"), không thể tách bằng khoảng trắng như "ten" cũ nữa ->
    # dùng dấu "|" làm ký tự phân cách giữa 3 trường:
    #   !nopchallenge [ID level] [tên challenge] | [tên Verify] | [tên người tạo]
    USAGE = "❌ VD: `!nopchallenge 12345678 Tên Level/Challenge | Tên người Verify | Tên người tạo` (kèm ảnh/video bằng chứng, hoặc dán link Youtube)"
    if not level_id or not noi_dung:
        return await ctx.send(USAGE)

    phan = [p.strip() for p in noi_dung.split("|")]
    if len(phan) < 3 or not all(phan[:3]):
        return await ctx.send(USAGE + "\n⚠️ Nhớ tách 3 trường bằng dấu `|`, và điền đủ cả 3 (không được để trống).")
    ten, ten_verify, ten_tao = phan[0], phan[1], phan[2]

    # ĐÃ FIX: dọn link Youtube ra khỏi "ten" NGAY TỪ ĐẦU (xem giải thích chi tiết ở hàm
    # strip_youtube_link) - tránh tên challenge bị dính link khi người dùng dán link Youtube
    # làm bằng chứng chung trong cùng câu lệnh.
    ten = strip_youtube_link(ten)
    if not ten:
        return await ctx.send("❌ Tên challenge không được để trống (sau khi bỏ link Youtube). VD: `!nopchallenge 12345678 Tên Level/Challenge | Tên người Verify | Tên người tạo`")

    # ĐÃ THÊM MỚI: cho phép nộp bằng chứng qua link Youtube giống !duyet (xem giải thích
    # chi tiết ở phần xử lý bằng chứng của !duyet phía trên).
    evidence_url, la_video_link = None, False
    if ctx.message.attachments:
        evidence_url = ctx.message.attachments[0].url
    else:
        yt_id = extract_youtube_id(ctx.message.content)
        if not yt_id:
            return await ctx.send("📸 Phải gửi kèm bằng chứng (ảnh/video), hoặc dán link video Youtube (dành cho máy yếu)!")
        evidence_url, la_video_link = f"https://youtu.be/{yt_id}", True

    challenge_id = await get_next_challenge_id()
    await db.challenges.insert_one({
        "_id": challenge_id,
        "name": ten,
        "level_id": level_id,
        "verifier_name": ten_verify,
        "creator_name": ten_tao,
        "submitter_id": ctx.author.id,
        "status": "pending",
        "rank": None,
        "evidence_url": evidence_url,
        "created_at": datetime.now(VN_TZ),
    })

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        # ĐÃ THÊM MỚI: hiện đủ thông tin người nộp (mention, tên hiển thị, avatar) để
        # Admin xét duyệt dễ dàng, không chỉ 1 dòng mention như trước.
        embed = discord.Embed(title="🏁 YÊU CẦU DUYỆT CHALLENGE", color=discord.Color.orange())
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(name="🆔 Mã Challenge", value=f"`#{challenge_id}`", inline=True)
        embed.add_field(name="🎮 ID Level", value=f"`{level_id}`", inline=True)
        embed.add_field(name="👤 Người nộp", value=f"{ctx.author.mention}\n({ctx.author.display_name} | `{ctx.author.id}`)", inline=False)
        embed.add_field(name="🏷️ Tên Challenge", value=f"**{ten}**", inline=False)
        # ĐÃ THÊM MỚI (v25): hiện tên người Verify và tên người tạo level trên tin nhắn
        # duyệt, để Admin đối chiếu/kiểm tra thêm nếu cần.
        embed.add_field(name="✅ Người Verify", value=ten_verify, inline=True)
        embed.add_field(name="🛠️ Người tạo", value=ten_tao, inline=True)
        if la_video_link:
            embed.add_field(name="🔗 Bằng chứng", value=f"📺 [Video Youtube]({evidence_url}) — ⚠️ Admin vui lòng tự bấm vào link kiểm tra trước khi duyệt", inline=False)
        else:
            embed.add_field(name="🔗 Bằng chứng", value=f"[Xem tại đây]({evidence_url})", inline=False)
            embed.set_image(url=evidence_url)
        embed.set_footer(text="Bấm Duyệt để nhập số thứ hạng, hoặc Từ chối để nhập lý do")

        sent_msg = await admin_channel.send(embed=embed, view=ChallengeReviewView())
        await db.pending_actions.insert_one({"_id": sent_msg.id, "kind": "challenge", "challenge_id": challenge_id})
    await ctx.send(f"✅ Đã nộp challenge **{ten}** (ID Level `{level_id}`, Mã `#{challenge_id}`) cho Admin xem xét!")

@bot.command(aliases=["bxhchall", "challengeboard"])
@require_db()
async def bxhchallenge(ctx, challenge_id: int = None, vi_tri: int = None):
    # Có đủ 2 tham số -> đây là thao tác XẾP HẠNG LẠI (dùng khi muốn đổi vị trí challenge
    # đã duyệt từ trước), chỉ Admin được phép. Việc duyệt+xếp hạng LẦN ĐẦU giờ đã chuyển
    # sang bấm nút "Duyệt" trên tin nhắn ở kênh admin.
    if challenge_id is not None and vi_tri is not None:
        if not (getattr(ctx.author, 'guild_permissions', None) and ctx.author.guild_permissions.administrator):
            return await ctx.send("❌ Chỉ Admin mới có quyền chỉnh vị trí Bảng Xếp Hạng Challenge!")
        challenge = await db.challenges.find_one({"_id": challenge_id})
        if not challenge: return await ctx.send(f"❌ Không tìm thấy challenge `#{challenge_id}`.")
        if challenge["status"] != "approved":
            return await ctx.send(f"❌ Challenge `#{challenge_id}` chưa được duyệt, hãy bấm nút Duyệt trên tin nhắn ở kênh admin trước.")
        if vi_tri < 1: return await ctx.send("❌ Vị trí xếp hạng phải là số nguyên dương (1, 2, 3...).")

        old_rank = challenge.get("rank")
        if old_rank == vi_tri:
            return await ctx.send(f"⚠️ Challenge `#{challenge_id}` đã ở vị trí **#{vi_tri}** rồi, không có gì thay đổi.")

        # ĐÃ FIX (v24): dùng move_challenge_rank thay vì set thẳng rank, để các challenge
        # nằm giữa vị trí cũ và vị trí mới TỰ ĐỘNG dịch chuyển 1 bậc, giữ bảng luôn liên
        # tục (không trùng, không hở số) thay vì phải tự tay sửa từng challenge còn lại.
        await move_challenge_rank(challenge_id, old_rank, vi_tri)
        await log_admin_action(ctx.author.mention, f"Xếp lại hạng Challenge #{challenge_id}: **{challenge['name']}**", f"<@{challenge['submitter_id']}>", f"#{old_rank} → #{vi_tri} (tự động dồn hạng liên quan)")
        return await ctx.send(f"✅ Đã xếp lại challenge `#{challenge_id}` — **{challenge['name']}** vào vị trí **#{vi_tri}** trên BXH Challenge (các hạng liên quan đã tự động dồn lại).")

    # Không đủ 2 tham số -> hiển thị bảng xếp hạng cho mọi người xem.
    ranked = await db.challenges.find({"status": "approved", "rank": {"$ne": None}}).sort("rank", 1).to_list(None)
    unranked = await db.challenges.find({"status": "approved", "rank": None}).sort("_id", 1).to_list(None)

    embed = discord.Embed(title="🏁 BẢNG XẾP HẠNG CHALLENGE", color=discord.Color.orange())
    if ranked:
        dong = [f"**#{c['rank']}** — {c['name']} (ID Level `{c.get('level_id','?')}`)\n{format_creator_verifier(c)} — nộp bởi <@{c['submitter_id']}> `#{c['_id']}`" for c in ranked]
        embed.add_field(name="🏆 Đã xếp hạng", value="\n".join(dong)[:1024], inline=False)
    if unranked:
        dong2 = [f"{c['name']} (ID Level `{c.get('level_id','?')}`)\n{format_creator_verifier(c)} — nộp bởi <@{c['submitter_id']}> `#{c['_id']}`" for c in unranked]
        embed.add_field(name="⏳ Đã duyệt, chờ Admin xếp hạng", value="\n".join(dong2)[:1024], inline=False)
    if not ranked and not unranked:
        embed.description = "Chưa có challenge nào được duyệt."
    embed.set_footer(text="Nộp challenge: !nopchallenge [ID level] [tên] | [Verify] | [người tạo]  —  Admin xếp lại hạng: !bxhchallenge [id] [vị trí]")
    await ctx.send(embed=embed)

# ĐÃ THÊM MỚI (v14): lệnh cho Admin gỡ challenge "bẩn" (verify bằng hack, ăn cắp challenge
# của người khác...) khỏi hệ thống/BXH. Dùng soft-delete (đổi status="removed", bỏ rank)
# thay vì xoá cứng khỏi DB, để vẫn giữ được lịch sử tra soát qua !history/ADMIN_LOG_CHANNEL.
@bot.command(aliases=["xoachall", "delchallenge"])
@commands.has_permissions(administrator=True)
@require_db()
async def xoachallenge(ctx, challenge_id: int, *, ly_do: str = None):
    challenge = await db.challenges.find_one({"_id": challenge_id})
    if not challenge: return await ctx.send(f"❌ Không tìm thấy challenge `#{challenge_id}`.")
    if not ly_do:
        return await ctx.send(f"❌ Vui lòng nhập lý do xoá!\nVD: `!xoachallenge {challenge_id} dùng hack ẩn / ăn cắp challenge của người khác`")

    # ĐÃ FIX (v24): dồn các hạng phía sau lên 1 bậc TRƯỚC khi xoá, để BXH không bị hở số
    # (VD: xoá #2 trong dãy #1,#2,#3,#4 -> #3,#4 phải tự động dồn thành #2,#3).
    await close_challenge_rank_gap(challenge.get("rank"))
    await db.challenges.update_one({"_id": challenge_id}, {"$set": {"status": "removed", "rank": None}})
    await log_history(challenge["submitter_id"], "challenge", challenge["name"], "removed", ctx.author.id, ly_do)
    await log_admin_action(ctx.author.mention, f"Xoá Challenge #{challenge_id} (gian lận): **{challenge['name']}**", f"<@{challenge['submitter_id']}>", ly_do)

    submitter = await bot.fetch_user(challenge["submitter_id"])
    if submitter:
        try: await submitter.send(f"🚫 Challenge **{challenge['name']}** (Mã `#{challenge_id}`) của bạn đã bị **gỡ khỏi hệ thống**.\n**Lý do:** {ly_do}")
        except discord.Forbidden: pass

    await ctx.send(f"✅ Đã xoá challenge `#{challenge_id}` — **{challenge['name']}** khỏi hệ thống/BXH.\nCác hạng phía sau đã tự động dồn lại.\nLý do: {ly_do}")
# ==================================================================== #

# ================= PHẦN LỆNH ĐỀ XUẤT LEVEL (ĐÃ ĐƯỢC CHỈNH SỬA TOÀN DIỆN) ================= #
# ĐÃ FIX: Thêm cooldown 15s/người để tránh 1 user spam lệnh làm cạn hạn mức miễn phí
# của Gemini API (dẫn tới lỗi 429 hàng loạt cho những người dùng khác).
@bot.command(name="dexuatlevel", aliases=["goiylevel", "de-xuat-level"])
@commands.cooldown(1, 15, commands.BucketType.user)
@require_db()
async def dexuatlevel(ctx, *, yeu_cau: str = None):
    if not yeu_cau: return await ctx.send("❌ VD: `!dexuatlevel easy demon phù hợp cho người mới`")
    if not GEMINI_API_KEY or model is None: return await ctx.send("❌ Chưa cấu hình GEMINI_API_KEY!")

    waiting_msg = await ctx.send("⏳ Đang tìm kiếm level thật trên máy chủ GD và chạy AI phân tích...")

    # ĐÃ FIX: Bọc TOÀN BỘ phần logic còn lại trong 1 try/except tổng.
    # Trước đây nếu có lỗi xảy ra ở bất kỳ đâu ngoài vòng lặp gọi Gemini (VD: lỗi khi
    # gọi get_user_mp, lỗi khi tạo embed, lỗi khi waiting_msg.edit bị Discord từ chối...)
    # thì exception sẽ văng thẳng ra ngoài coroutine mà KHÔNG có phản hồi nào cho người
    # dùng - đây chính là nguyên nhân gây ra hiện tượng "lệnh treo, không phản hồi gì".
    try:
        user_mp = await get_user_mp(ctx.author.id)

        # 1. Tìm từ khóa độ khó trong câu yêu cầu để gọi API
        # ĐÃ FIX (NGUYÊN NHÂN GÂY "SAI ID / SAI ĐỘ KHÓ"):
        # Tham số `diff` của GDBrowser API BẮT BUỘC phải là SỐ, không phải chuỗi:
        #   1=Easy, 2=Normal, 3=Hard, 4=Harder, 5=Insane, -2=Demon (mọi loại), -3=Auto
        # Code cũ gửi thẳng chuỗi như "diff=easy" hoặc "diff=demon" - đây là giá trị KHÔNG
        # hợp lệ với API thật, nên GDBrowser trả về kết quả rỗng hoặc không được lọc theo ý
        # muốn. Khi đó api_levels_info luôn rỗng -> Gemini rơi vào nhánh "không có dữ liệu
        # thật" và phải TỰ BỊA ra tên level/ID/độ khó dựa trên "trí nhớ" của nó (không có khả
        # năng tra cứu database GD thật) -> sinh ra ID và độ khó sai lệch hoàn toàn.
        DIFF_ID_MAP = {"easy": "1", "normal": "2", "hard": "3", "harder": "4", "insane": "5", "auto": "-3"}
        DEMON_FILTER_MAP = {"easy demon": "1", "medium demon": "2", "hard demon": "3", "insane demon": "4", "extreme demon": "5"}

        # ĐÃ FIX (v12): "harder" phải được check TRƯỚC "hard", vì "hard" là substring
        # của "harder" - nếu "hard" đứng trước, mọi yêu cầu chứa từ "harder" sẽ luôn
        # bị nhận nhầm thành độ khó "hard" (diff=3 thay vì đúng phải là diff=4), khiến
        # GDBrowser trả về sai tập level và Gemini đề xuất sai độ khó.
        difficulties = ["easy demon", "medium demon", "hard demon", "insane demon", "extreme demon", "demon", "auto", "easy", "normal", "harder", "hard", "insane"]
        found_diff = None
        lower_yc = yeu_cau.lower()

        for d in difficulties:
            if d in lower_yc:
                found_diff = d
                break

        # 2. Gọi GDBrowser API để lấy danh sách ID 100% là thật.
        # ĐÃ FIX: kể cả khi KHÔNG tìm thấy từ khóa độ khó cụ thể, vẫn thực hiện một lượt tìm
        # kiếm chung (không lọc diff) để luôn có một tập level thật làm dữ liệu nền cho Gemini,
        # thay vì để trống hoàn toàn khiến AI phải bịa từ đầu.
        # ĐÃ FIX BUG NGHIÊM TRỌNG: phải khởi tạo api_levels_info = "" TRƯỚC khi gọi API.
        # Biến này trước đây CHỈ được gán bên trong nhánh "status==200 và có dữ liệu" ở dưới.
        # Nếu GDBrowser lỗi/timeout/status khác 200/trả về rỗng, biến sẽ KHÔNG TỒN TẠI, khiến
        # dòng "if api_levels_info:" phía sau ném UnboundLocalError. Lỗi này bị try/except tổng
        # bên ngoài nuốt mất, nên hậu quả thực tế là: nhánh fallback "không có dữ liệu thật ->
        # chỉ đưa lời khuyên chung" (đã viết sẵn ở dưới) KHÔNG BAO GIỜ chạy được - người dùng
        # luôn chỉ nhận "❌ Lỗi hệ thống" mỗi khi GDBrowser gặp sự cố, thay vì vẫn nhận được
        # gợi ý chung chung như mong muốn.
        api_levels_info = ""
        query_diff = ""
        if found_diff:
            if found_diff in DEMON_FILTER_MAP:
                query_diff = f"&diff=-2&demonFilter={DEMON_FILTER_MAP[found_diff]}"
            elif found_diff == "demon":
                query_diff = "&diff=-2"
            else:
                query_diff = f"&diff={DIFF_ID_MAP[found_diff]}"

        api_url = f"https://gdbrowser.com/api/search/*?starred=true&count=10{query_diff}"
        try:
            # ĐÃ FIX: Thêm timeout 10 giây cho request GDBrowser. Trước đây không có
            # timeout nào, mặc định của aiohttp là 5 PHÚT - nếu GDBrowser bị chậm/treo,
            # người dùng phải chờ rất lâu trước khi bot mới tiếp tục xử lý.
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        levels = await response.json()
                        if isinstance(levels, list) and len(levels) > 0:
                            sample_size = min(5, len(levels))  # Chọn random tối đa 5 level
                            selected = random.sample(levels, sample_size)
                            # ĐÃ FIX: Dùng field "difficulty" THẬT trả về từ API cho TỪNG level,
                            # thay vì gán cứng theo từ khóa người dùng gõ (found_diff.title()).
                            # Đây chính là chỗ gây "sai độ khó" trước đây - dù có lấy được level
                            # thật, độ khó hiển thị vẫn là suy đoán chứ không phải dữ liệu thật.
                            api_levels_info = "\n".join([f"- Tên: {l.get('name')} | ID: {l.get('id')} | Tác giả: {l.get('author')} | Độ khó: {l.get('difficulty')} | Lượt tải: {l.get('downloads')}" for l in selected])
                        else:
                            print(f"⚠️ GDBrowser trả về danh sách rỗng cho query: {api_url}")
                    else:
                        print(f"⚠️ GDBrowser trả về status {response.status} cho query: {api_url}")
        except asyncio.TimeoutError:
            print(f"⏳ GDBrowser API quá thời gian chờ (10s) cho yêu cầu: {yeu_cau}")
        except Exception as e:
            print(f"Lỗi gọi GDBrowser API: {e}")

        # 3. Tạo Prompt ép AI chỉ sử dụng các ID thật vừa lấy được từ API
        prompt = f"Người chơi Geometry Dash có {user_mp} MP (tượng trưng cho kinh nghiệm), yêu cầu: '{yeu_cau}'.\n"
        if api_levels_info:
            prompt += f"\nDữ liệu level THẬT lấy từ máy chủ GD:\n{api_levels_info}\n\nHãy ĐÓNG VAI LÀ BOT CHUYÊN GIA và CHỈ ĐƯỢC PHÉP chọn trong đúng danh sách level THẬT ở trên (chọn 3-5 level, giữ NGUYÊN VẸN tên/ID/độ khó như trong danh sách) và phân tích tại sao phù hợp dựa trên yêu cầu/MP. TUYỆT ĐỐI không chế/sáng tạo thêm level hay ID nào ngoài danh sách này."
        else:
            # ĐÃ FIX: Trước đây khi không có dữ liệu thật, code vẫn yêu cầu Gemini "đề xuất
            # 3-5 level kèm ID chính xác" - nhưng Gemini KHÔNG có cách nào tra cứu ID thật,
            # nên chắc chắn sẽ bịa. Giờ không còn yêu cầu AI tự nghĩ ra level/ID nữa; chỉ xin
            # lời khuyên chung chung (không kèm ID) để tránh thông tin sai lệch.
            prompt += "Máy chủ GD hiện không phản hồi nên KHÔNG có dữ liệu level thật để tham khảo. TUYỆT ĐỐI KHÔNG được tự đặt tên level, ID, hay tác giả cụ thể nào (vì không thể xác minh). Chỉ đưa ra lời khuyên chung về loại level/độ khó nên tìm và gợi ý người chơi tự tìm trên GDBrowser hoặc trong game."

        # 4. Gửi cho Gemini xử lý
        # generate_content_async đã là bất đồng bộ thật sự (không chặn event loop của bot),
        # nên KHÔNG cần chuyển sang run_in_executor. Vấn đề gốc là tên model đã bị khai tử,
        # đã fix ở phần cấu hình GEMINI_MODEL_NAME phía trên.
        thanh_cong = False
        for so_lan_thu in range(3):
            try:
                phan_hoi = await asyncio.wait_for(model.generate_content_async(prompt), timeout=30)
                if not phan_hoi.parts: raise ValueError("Phản hồi bị chặn bởi bộ lọc an toàn")

                noi_dung = phan_hoi.text.strip()
                if not noi_dung: raise ValueError("Phản hồi trống")

                embed = discord.Embed(title=f"🎯 Đề xuất level cho: {yeu_cau.title()}", description=noi_dung[:4000], color=discord.Color.green())
                embed.set_footer(text=f"Dựa trên {user_mp} MP của bạn | 100% ID thật từ máy chủ GD")
                await waiting_msg.edit(embed=embed, content=None)
                thanh_cong = True
                break
            except asyncio.TimeoutError:
                thoi_gian_cho = (2 ** so_lan_thu) + 1
                await waiting_msg.edit(content=f"⏳ AI phản hồi quá lâu, thử lại lần {so_lan_thu + 1}/3...")
                await asyncio.sleep(min(thoi_gian_cho, 5))
                continue
            except Exception as loi:
                loi_chi_tiet = str(loi)
                if any(ma_loi in loi_chi_tiet for ma_loi in ["429", "ResourceExhausted", "503", "Unavailable", "DeadlineExceeded"]):
                    thoi_gian_cho = (2 ** so_lan_thu) + 1
                    await waiting_msg.edit(content=f"⏳ Máy chủ AI đang bận, chờ {thoi_gian_cho} giây rồi thử lại...")
                    await asyncio.sleep(thoi_gian_cho)
                    continue
                print(f"[LỖI GEMINI] !dexuatlevel | {ctx.author}: {loi}")
                break

        if not thanh_cong:
            await waiting_msg.edit(embed=discord.Embed(title="❌ Lỗi kết nối AI", description="Không thể lấy gợi ý lúc này. Thử lại sau nhé!", color=discord.Color.red()), content=None)

    except Exception as loi_tong:
        # ĐÃ THÊM MỚI: lưới an toàn cuối cùng - đảm bảo người dùng LUÔN nhận được phản hồi
        print(f"[LỖI NGHIÊM TRỌNG !dexuatlevel] {ctx.author}: {loi_tong}")
        traceback.print_exc()
        try:
            await waiting_msg.edit(embed=discord.Embed(title="❌ Lỗi hệ thống", description="Có lỗi không xác định xảy ra, Admin đã được ghi log để kiểm tra!", color=discord.Color.red()), content=None)
        except Exception:
            pass
# ============================================================================== #

@bot.command()
@require_db()
async def listdanhhieu(ctx):
    u = await db.users.find_one({"_id": ctx.author.id})
    titles = u.get("titles", []) if u else []
    if not titles: return await ctx.send("Túi đồ danh hiệu của bạn hiện đang rỗng!")
    await ctx.send(f"🎖️ Danh hiệu bạn đang sở hữu:\n- " + "\n- ".join(t.title() for t in titles))

# ĐÃ THÊM MỚI: !danhsachdanhhieu - liệt kê TOÀN BỘ danh hiệu server đang có
# (cả danh hiệu gốc lẫn 50 danh hiệu mới) và cách lấy, vì trước đây !menu chỉ
# nhắc tới 5 danh hiệu tự động nhận theo Demon, member không biết 50 danh hiệu
# còn lại tồn tại hay lấy bằng cách nào.
@bot.command(aliases=["danhhieu", "alltitles"])
@require_db()
async def danhsachdanhhieu(ctx):
    # ĐÃ THÊM MỚI: bổ sung "cách lấy" cụ thể cho từng danh hiệu trong số 50 danh
    # hiệu mới (7 danh hiệu gốc GIỮ NGUYÊN mô tả như cũ, không đổi). Cách lấy vẫn
    # đi qua !duyet [tên danh hiệu] kèm bằng chứng như quy trình chung - Admin chỉ
    # xét đúng/sai bằng chứng, không tự ý ưu ái. Chia làm 2 embed vì nội dung dài.
    embed1 = discord.Embed(
        title="🎖️ TOÀN BỘ DANH HIỆU CỦA SERVER (1/2)",
        description="Dùng `!duyet [tên danh hiệu]` kèm ảnh/video bằng chứng để nộp. Admin chỉ xét đúng/sai dựa trên bằng chứng, không tự ý ưu ái ai.",
        color=discord.Color.gold()
    )
    embed1.add_field(name="🥇 Ngôi vị & tự động nhận", value="Newbie, Sự Khởi Đầu, Pro, Hardcore Player, Huyền Thoại *(tự động khi duyệt Demon tương ứng)*\nVua Hardest, Vua Try Hard *(duyệt tay qua !duyet)*\nVua Cày Điểm *(tự động cho Top 1 MP, không duyệt tay được)*", inline=False)
    embed1.add_field(name="⚔️ Tiến trình kỹ năng", value=(
        "**Người Mới Toe** — Hoàn thành level Normal đầu tiên\n"
        "**Tân Binh** — Hoàn thành 5 level Hard bất kỳ\n"
        "**Học Việc** — Hoàn thành 1 level Harder\n"
        "**Chiến Binh** — Hoàn thành 3 level Insane\n"
        "**Đấu Sĩ** — Hoàn thành 1 level Insane không dùng Practice Mode\n"
        "**Sát Thủ Demon** — Hoàn thành Demon đầu tiên (bất kỳ độ khó)\n"
        "**Thợ Săn Insane** — Hoàn thành 5 level Insane khác nhau\n"
        "**Kẻ Hủy Diệt** — Hoàn thành 3 Demon khác độ khó nhau\n"
        "**Bậc Thầy Phản Xạ** — Hoàn thành level timing khó, được Admin công nhận\n"
        "**Vô Địch Tốc Độ** — Hoàn thành level tốc độ cao được cộng đồng công nhận khó"
    ), inline=False)
    embed1.add_field(name="⛏️ Cày điểm", value=(
        "**Cày Cuốc Chăm Chỉ** — Đạt mốc 5.000 MP\n"
        "**Thợ Cày Chuyên Nghiệp** — Đạt mốc 20.000 MP\n"
        "**Máy Cày MP** — Đạt mốc 50.000 MP\n"
        "**Nông Dân Demon** — Duyệt thành công 20 Demon cộng dồn\n"
        "**Vua Năng Suất** — Đạt 50 bài duyệt thành công (xem !profile)"
    ), inline=False)
    embed1.add_field(name="🔥 Kiên trì", value=(
        "**Kiên Trì Bất Khuất** — Duyệt Demon từng bị từ chối ≥3 lần trước đó (kèm ảnh các lần thử)\n"
        "**Không Bỏ Cuộc** — Pass level từng fail ở ≥90% trước đó\n"
        "**Chiến Thần Bền Bỉ** — Hoàn thành 3 level trong cùng 1 ngày\n"
        "**Người Sắt** — Video hoàn thành Demon raw dài không chết\n"
        "**Ý Chí Thép** — Pass level sau hơn 100 lần thử (có đếm số lần)"
    ), inline=False)
    embed1.add_field(name="🤝 Cộng đồng", value=(
        "**Người Bạn Tốt** — Được 1 thành viên khác xác nhận từng được bạn giúp đỡ\n"
        "**Trưởng Lão Server** — Hoạt động liên tục ≥6 tháng (Admin xác nhận)\n"
        "**Cố Vấn Tân Binh** — Từng hướng dẫn/carry ≥3 tân binh có xác nhận\n"
        "**Đại Sứ Cộng Đồng** — Từng tổ chức/host 1 sự kiện được Admin công nhận\n"
        "**Người Truyền Cảm Hứng** — Được nhiều thành viên nhắc tên là động lực (Admin tổng hợp)"
    ), inline=False)
    embed1.add_field(name="🎨 Sáng tạo", value=(
        "**Nhà Thiết Kế** — Tự làm 1 level hoàn chỉnh đăng lên GD (kèm ID)\n"
        "**Kiến Trúc Sư Level** — Level tự làm có gameplay/deco phức tạp, cộng đồng đánh giá cao\n"
        "**Nghệ Sĩ Decor** — Level tự làm có phần decor nổi bật, Admin công nhận\n"
        "**Bậc Thầy Sáng Tạo** — Level tự làm được GD rate chính thức\n"
        "**Huyền Thoại Sáng Tác** — Level tự làm lọt Demon List thật của GD"
    ), inline=False)

    embed2 = discord.Embed(title="🎖️ TOÀN BỘ DANH HIỆU CỦA SERVER (2/2)", color=discord.Color.gold())
    embed2.add_field(name="🎉 Sự kiện", value=(
        "**Chiến Binh Event** — Hoàn thành 3 event/daily\n"
        "**Vua Sự Kiện Tháng** — Hoàn thành nhiều event nhất trong tháng (Admin tổng hợp)\n"
        "**Người Về Đích Đầu Tiên** — Người đầu tiên duyệt thành công 1 event mới ra\n"
        "**Huyền Thoại Mùa Giải** — Hoàn thành toàn bộ event trong 1 mùa/quý\n"
        "**Nhà Vô Địch Giải Đấu** — Vô địch giải đấu nội bộ do Admin tổ chức"
    ), inline=False)
    embed2.add_field(name="😂 Vui/troll", value=(
        "**Trùm Rớt Điểm Rơi** — Video rớt ngay ô cuối cùng của level\n"
        "**Vua Nổ Máy** — Video crash/lag game giữa run\n"
        "**Ông Hoàng Restart** — Video spam restart hơn 50 lần liên tục\n"
        "**Đại Sư Spam Thử** — Video thử 1 level hơn 200 lần trong 1 session\n"
        "**Chúa Tể Rage Quit** — Video rage quit ngay gần thành công"
    ), inline=False)
    embed2.add_field(name="💎 Hiếm", value=(
        "**Người Được Chọn** — Người đầu tiên hoàn thành level mới ra mắt trên server\n"
        "**VIP Server** — Đóng góp đặc biệt cho server, được Admin công nhận công khai\n"
        "**Huyền Thoại Sống** — Sở hữu từ 15 danh hiệu trở lên cùng lúc\n"
        "**Thánh Nhân GD** — Hoàn thành toàn bộ Demon trong Extended List chính thức của GD\n"
        "**Tối Thượng Chi Vương** — Giữ đồng thời cả Vua Cày Điểm/Vua Hardest/Vua Try Hard"
    ), inline=False)
    embed2.add_field(name="🕰️ Thâm niên", value=(
        "**Thành Viên Kỳ Cựu** — Tham gia server ≥3 tháng\n"
        "**Lính Cũ** — Tham gia server ≥1 năm\n"
        "**Chứng Nhân Lịch Sử** — Có mặt từ đợt đầu ra mắt hệ thống !duyet\n"
        "**Linh Hồn Server** — Có mặt ở hầu hết sự kiện lớn (Admin xác nhận)\n"
        "**Vĩnh Cửu** — Tham gia server ≥2 năm chưa từng rời"
    ), inline=False)
    embed2.set_footer(text=f"Tổng cộng {len(TITLES_DATA)} danh hiệu | Dùng !listdanhhieu để xem danh hiệu bạn đang sở hữu")

    await ctx.send(embeds=[embed1, embed2])

@bot.command()
@require_db()
async def setdanhhieu(ctx, *, ten: str = None):
    if not ten: return await ctx.send("❌ Vui lòng nhập tên danh hiệu bạn muốn trang bị!")
    ten = ten.lower()
    u = await db.users.find_one({"_id": ctx.author.id})
    if not u or ten not in u.get("titles", []): return await ctx.send("❌ Bạn không sở hữu danh hiệu này hoặc nhập sai tên!")
    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"active_title": ten}})
    await ctx.send(f"✅ Đã trang bị thành công danh hiệu: **{ten.title()}**")

@bot.command()
@require_db()
async def editdanhhieu(ctx, trang_thai: str = None):
    if trang_thai not in ["an", "hien"]: return await ctx.send("❌ Vui lòng dùng: `!editdanhhieu an` hoặc `!editdanhhieu hien`")
    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"title_visible": (trang_thai=="hien")}}, upsert=True)
    await ctx.send(f"✅ Đã cập nhật trạng thái hiển thị danh hiệu thành: **{trang_thai.upper()}**")

# ĐÃ THÊM MỚI: !profile - xem tổng quan MP, hạng, danh hiệu, số bài đã duyệt
# của bản thân hoặc người khác.
@bot.command(aliases=["hoso"])
@require_db()
async def profile(ctx, member: discord.Member = None):
    member = member or ctx.author
    u = await db.users.find_one({"_id": member.id}) or {}
    mp = u.get("mp", 0)
    active_title = u.get("active_title")
    approved_count = u.get("approved_count", 0)
    titles = u.get("titles", [])

    # Hạng = số người có MP cao hơn + 1
    rank = await db.users.count_documents({"mp": {"$gt": mp}}) + 1

    embed = discord.Embed(title=f"📇 Hồ sơ của {member.display_name}", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="💎 Điểm MP", value=str(mp), inline=True)
    embed.add_field(name="🏅 Hạng server", value=f"#{rank}", inline=True)
    embed.add_field(name="✅ Bài đã được duyệt", value=str(approved_count), inline=True)
    embed.add_field(name="🎖️ Danh hiệu đang trang bị", value=active_title.title() if active_title else "Chưa trang bị", inline=False)
    embed.add_field(name="🎒 Tổng số danh hiệu sở hữu", value=str(len(titles)), inline=True)

    # ĐÃ THÊM MỚI: hiển thị Challenge KHÓ NHẤT (rank số nhỏ nhất = khó nhất) mà người này
    # đã được duyệt. Không lưu cứng thành 1 trường riêng trong db.users - thay vào đó
    # LUÔN truy vấn trực tiếp collection db.challenges mỗi lần gọi !profile, nên nếu Admin
    # xếp lại hạng bằng !bxhchallenge sau này, profile sẽ TỰ ĐỘNG hiện đúng hạng mới nhất
    # ngay lập tức mà không cần thêm task nền hay đồng bộ thủ công nào.
    hardest = await db.challenges.find_one(
        {"submitter_id": member.id, "status": "approved", "rank": {"$ne": None}},
        sort=[("rank", 1)]
    )
    if hardest:
        embed.add_field(
            name="🏁 Challenge khó nhất đã vượt qua",
            value=f"**{hardest['name']}** (ID Level `{hardest.get('level_id', '?')}`) — Hạng **#{hardest['rank']}**",
            inline=False
        )

    # ĐÃ THÊM MỚI: Demon khó nhất, được tự động ghi nhận bởi try_update_hardest_demon()
    # mỗi khi Admin duyệt 1 bài Demon có kèm ảnh/video (xem giải thích chi tiết ở hàm đó).
    hardest_demon = u.get("hardest_demon")
    if hardest_demon:
        embed.add_field(
            name="👹 Demon khó nhất đã vượt qua (tự động nhận diện)",
            value=f"**{hardest_demon['name']}** (ID Level `{hardest_demon.get('level_id', '?')}`) — `{hardest_demon['difficulty']}`",
            inline=False
        )

    # ĐÃ THÊM MỚI: mô tả cá nhân do người dùng tự đặt qua !editprofile - KHÔNG ảnh hưởng
    # tới bất kỳ chỉ số thật nào (MP/danh hiệu/hạng), chỉ để trang trí hồ sơ.
    bio = u.get("bio")
    if bio:
        embed.add_field(name="📝 Giới thiệu", value=bio, inline=False)

    await ctx.send(embed=embed)

# ĐÃ THÊM MỚI: !editprofile - cho phép người dùng tự đặt/xoá 1 dòng mô tả cá nhân hiển
# thị trên !profile. CHỈ ảnh hưởng tới trường trang trí "bio" - KHÔNG thể dùng để chỉnh
# MP, danh hiệu, hạng, hay bất kỳ chỉ số thật nào khác (những thứ đó luôn đi qua !duyet
# + Admin duyệt, không có cách nào tự sửa trực tiếp qua lệnh này).
@bot.command(aliases=["suahoso"])
@require_db()
async def editprofile(ctx, *, noi_dung: str = None):
    if not noi_dung or noi_dung.lower() in ["xoa", "clear", "reset"]:
        await db.users.update_one({"_id": ctx.author.id}, {"$unset": {"bio": ""}}, upsert=True)
        return await ctx.send("✅ Đã xoá mô tả cá nhân trên hồ sơ của bạn." if noi_dung else "❌ VD: `!editprofile Người yêu thích Demon Insane!` (gõ `!editprofile xoa` để xoá mô tả).")

    if len(noi_dung) > 200:
        return await ctx.send(f"❌ Mô tả quá dài ({len(noi_dung)}/200 ký tự), hãy rút gọn lại nhé!")

    bad_words = ["discord.gg/", "free nitro", "hack gem", "giftcode", "hack blox"]
    if any(w in noi_dung.lower() for w in bad_words):
        return await ctx.send("❌ Mô tả chứa nội dung không hợp lệ, vui lòng sửa lại!")

    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"bio": noi_dung}}, upsert=True)
    await ctx.send(f"✅ Đã cập nhật mô tả hồ sơ thành: \n> {noi_dung}")

# ĐÃ THÊM MỚI (v13): !history - xem 10 lượt duyệt (mp/danh hiệu/challenge) gần nhất
# của bản thân hoặc người khác, để member tự tra lại vì sao được/bị từ chối, khi nào,
# admin nào xử lý - trước đây chỉ admin xem được qua ADMIN_LOG_CHANNEL_ID.
@bot.command(aliases=["lichsu"])
@require_db()
async def history(ctx, member: discord.Member = None):
    member = member or ctx.author
    logs = await db.history.find({"user_id": member.id}).sort("timestamp", -1).limit(10).to_list(10)
    if not logs: return await ctx.send(f"📭 {member.display_name} chưa có lịch sử duyệt nào.")

    ten_loai = {"mp": "💎 Điểm MP", "role": "🎖️ Danh hiệu", "challenge": "🏁 Challenge"}
    embed = discord.Embed(title=f"📜 Lịch sử duyệt gần đây của {member.display_name}", color=discord.Color.blurple())
    for log in logs:
        icon = {"approved": "✅", "rejected": "❌", "removed": "🚫"}.get(log["status"], "•")
        thoi_gian = log["timestamp"].strftime("%d/%m/%Y %H:%M")
        loai = ten_loai.get(log["kind"], log["kind"])
        gia_tri = f"{thoi_gian} | Admin: <@{log['admin_id']}>"
        if log.get("detail"): gia_tri += f"\n{log['detail']}"
        embed.add_field(name=f"{icon} {loai}: {log['item_name'].title()}", value=gia_tri, inline=False)
    embed.set_footer(text="Hiển thị tối đa 10 lượt gần nhất")
    await ctx.send(embed=embed)

@bot.command()
@require_db()
async def report(ctx, member: discord.Member = None, *, reason: str = None):
    try: await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound): pass
    if not member or not reason: return await ctx.send("❌ VD: `!report @TênNgườiDùng vi phạm quy tắc server`", delete_after=5)

    ch = bot.get_channel(REPORT_CHANNEL_ID)
    if ch is None:
        return await ctx.send("❌ Không tìm thấy kênh report (kiểm tra lại REPORT_CHANNEL_ID và quyền bot).", delete_after=5)
    embed = discord.Embed(title="🚨 BÁO CÁO VI PHẠM", color=discord.Color.red())
    embed.add_field(name="Người bị tố cáo", value=member.mention, inline=True)
    embed.add_field(name="Người báo cáo", value=ctx.author.mention, inline=True)
    embed.add_field(name="Lý do vi phạm", value=f"**{reason}**", inline=False)
    tep_dinh_kem = [await a.to_file() for a in ctx.message.attachments] if ctx.message.attachments else []
    embed.set_footer(text=f"Có {len(tep_dinh_kem)} tệp bằng chứng đính kèm" if tep_dinh_kem else "Không có bằng chứng đính kèm")
    sent_msg = await ch.send(embed=embed, files=tep_dinh_kem, view=ReportReviewView())
    # ĐÃ THÊM MỚI (v12): lưu dữ liệu report vào DB theo message_id để view sống sót qua restart.
    await db.pending_actions.insert_one({
        "_id": sent_msg.id,
        "kind": "report",
        "reporter_id": ctx.author.id,
        "reported_member_id": member.id,
    })
    await ctx.send("✅ Đã gửi báo cáo cho đội ngũ quản trị viên xem xét!", delete_after=5)

@bot.command()
@require_db()
async def bxh(ctx):
    users = await db.users.find().sort("mp", -1).limit(20).to_list(20)
    if not users: return await ctx.send("Chưa có thành viên nào có điểm MP trên server!")
    rank = {"a_than":[], "god":[], "pro":[], "thuong":[]}
    
    guild = ctx.guild
    for u in users:
        m = guild.get_member(u["_id"]) if guild else None
        if not m: m = bot.get_user(u["_id"]) 
        
        ten_hien_thi = m.display_name if m else f"ID thành viên: {u['_id']}"
        mp = u.get("mp",0)
        active_title = u.get("active_title")
        show_title = u.get("title_visible", True) and active_title
        ten_danh_hieu = f" | ✦ {active_title.title()} ✦" if show_title else ""

        # ĐÃ THÊM MỚI: tô màu dòng theo danh hiệu đang trang bị bằng ANSI, chỉ
        # có hiệu lực khi được bọc trong code block ```ansi ở dưới (xem block()).
        base = f"{ten_hien_thi} - {mp} MP{ten_danh_hieu}"
        chuoi = color_line(base, active_title if show_title else None)

        if mp>=100000: rank["a_than"].append(chuoi)
        elif mp>=50000: rank["god"].append(chuoi)
        elif mp>=10000: rank["pro"].append(chuoi)
        else: rank["thuong"].append(chuoi)

    # ĐÃ THÊM MỚI: bọc mỗi nhóm trong ```ansi ... ``` để Discord render màu.
    # Nếu không bọc bằng ```ansi thì mã màu \u001b[...] sẽ hiện ra thành ký tự
    # rác thay vì màu thật.
    def block(lines): return "```ansi\n" + "\n".join(lines) + "\n```"

    em = discord.Embed(title="🏆 BẢNG XẾP HẠNG MP SERVER", color=discord.Color.gold())
    if rank["a_than"]: em.add_field(name="👑 Á Thần (Từ 100.000 MP)", value=block(rank["a_than"]), inline=False)
    if rank["god"]: em.add_field(name="⚡ God (Từ 50.000 - 99.999 MP)", value=block(rank["god"]), inline=False)
    if rank["pro"]: em.add_field(name="⚔️ Pro (Từ 10.000 - 49.999 MP)", value=block(rank["pro"]), inline=False)
    if rank["thuong"]: em.add_field(name="👤 Thành viên thường (Dưới 10.000 MP)", value=block(rank["thuong"]), inline=False)
    await ctx.send(embed=em)

@bot.command()
@commands.has_permissions(administrator=True)
@require_db()
async def xoanhunguoichoi(ctx, member_id: int):
    result = await db.users.delete_one({"_id": member_id})
    if result.deleted_count > 0: await ctx.send(f"✅ Đã xóa thành công dữ liệu của người dùng có ID `{member_id}` khỏi hệ thống.")
    else: await ctx.send(f"❌ Không tìm thấy dữ liệu người dùng có ID `{member_id}` trong database.")

# ĐÃ THÊM MỚI: Lệnh dọn dữ liệu 1 lần cho những user đã bị "kẹt" active_title từ TRƯỚC khi
# fix revoke_title() được áp dụng (VD: top1 cũ vẫn hiện "Vua Cày Điểm" trên !bxh dù đã mất
# danh hiệu trong titles). Chỉ cần Admin chạy !dondanhieu MỘT LẦN sau khi cập nhật code này.
@bot.command()
@commands.has_permissions(administrator=True)
@require_db()
async def dondanhieu(ctx):
    all_users = await db.users.find().to_list(None)
    da_sua = 0
    for u in all_users:
        active = u.get("active_title")
        titles = u.get("titles", [])
        if active and active not in titles:
            new_active = titles[-1] if titles else None
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"active_title": new_active}})
            da_sua += 1
    await ctx.send(f"✅ Đã kiểm tra {len(all_users)} người dùng, sửa {da_sua} trường hợp active_title bị lỗi (không khớp danh hiệu đang sở hữu).")

keep_alive()
bot.run(DISCORD_TOKEN)

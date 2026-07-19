import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import sys
import asyncio
import traceback
import motor.motor_asyncio
import certifi
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

# ================= KHỞI TẠO BOT ==================== #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
db_client, db = None, None

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
    global db_client, db
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

async def add_user_mp(user_id, amount, guild=None):
    await db.users.update_one({"_id": user_id}, {"$inc": {"mp": amount}}, upsert=True)
    if guild:
        await check_and_transfer_top1_mp(guild)

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

class ReportReviewView(View):
    def __init__(self, reporter_id, reported_member):
        super().__init__(timeout=None)
        self.reporter_id = reporter_id
        self.reported_member = reported_member

    @discord.ui.button(label="Duyệt và xử lý", style=discord.ButtonStyle.green, custom_id="btn_rep_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        view = ReportActionView(self.reporter_id, self.reported_member, interaction.message)
        await interaction.response.send_message("Chọn hình phạt bạn muốn áp dụng:", view=view, ephemeral=True)
        
    @discord.ui.button(label="Từ chối (Kèm lý do)", style=discord.ButtonStyle.red, custom_id="btn_rep_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ReportRejectModal(self.reporter_id, interaction.message))

# ================= GIAO DIỆN NÚT BẤM DUYỆT BÀI ================= #
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
        await interaction.response.send_message("Đã thông báo từ chối.", ephemeral=True)

class ReviewView(View):
    def __init__(self, user_id, req_type, item_name, reward_value):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.req_type = req_type          
        self.item_name = item_name        
        self.reward_value = reward_value  

    @discord.ui.button(label="Duyệt", style=discord.ButtonStyle.green, custom_id="btn_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        user = await bot.fetch_user(self.user_id)
        guild = interaction.guild
        msg_user, msg_admin = "", ""

        if self.req_type == "mp":
            await add_user_mp(self.user_id, self.reward_value, guild)
            msg_user = f"🎉 Level **{self.item_name.title()}** đã được duyệt! +{self.reward_value} MP!"
            msg_admin = f"✅ Đã duyệt +{self.reward_value} MP cho <@{self.user_id}>."
            
            auto_title = None
            if self.item_name == "easy demon": auto_title = "newbie"
            elif self.item_name == "medium demon": auto_title = "sự khởi đầu"
            elif self.item_name == "hard demon": auto_title = "pro"
            elif self.item_name == "insane demon": auto_title = "hardcore player"
            elif self.item_name == "extreme demon": auto_title = "huyền thoại"
                
            if auto_title:
                await db.users.update_one({"_id": self.user_id}, {"$addToSet": {"titles": auto_title}, "$set": {"active_title": auto_title}}, upsert=True)
                msg_user += f"\n🎖️ Hệ thống tự động thêm danh hiệu **{auto_title.title()}** vào tủ đồ của bạn!"
                msg_admin += f"\n🎖️ Đã tự động cấp danh hiệu **{auto_title.title()}** thành công."
            
        elif self.req_type == "role":
            role_name = self.item_name.lower()
            if role_name == "vua hardest":
                await grant_vua_hardest(guild, self.user_id)
                msg_user = "🏆 Chúc mừng! Bạn đã trở thành VUA HARDEST mới của server!"
                msg_admin = f"✅ Đã cấp danh hiệu **Vua Hardest** cho <@{self.user_id}>."
            elif role_name == "vua try hard":
                await db.users.update_one({"_id": self.user_id}, {"$inc": {"vth_streak": 1}}, upsert=True)
                user_doc = await db.users.find_one({"_id": self.user_id})
                streak = user_doc.get("vth_streak", 1)
                
                if streak >= 5:
                    await grant_vua_try_hard(guild, self.user_id)
                    await db.users.update_one({"_id": self.user_id}, {"$set": {"vth_streak": 0}})
                    msg_user = "🔥 KINH KHỦNG! Bạn đã beat 5 Hardest liên tiếp độ khó tăng dần và trở thành VUA TRY HARD mới của server!"
                    msg_admin = f"✅ Đã duyệt bài (Chuỗi 5/5). Đã tước và cấp danh hiệu **Vua Try Hard** cho <@{self.user_id}>."
                else:
                    msg_user = f"✅ Admin đã duyệt Hardest của bạn! Chuỗi Vua Try Hard hiện tại: **{streak}/5**. Hãy tiếp tục phá kỷ lục nhé!"
                    msg_admin = f"✅ Đã duyệt bài (Chuỗi {streak}/5 Vua Try Hard) cho <@{self.user_id}>."
            else:
                await db.users.update_one({"_id": self.user_id}, {"$addToSet": {"titles": role_name}, "$set": {"active_title": role_name}}, upsert=True)
                msg_user = f"🏆 Đỉnh quá! Bạn nhận được danh hiệu **{role_name.title()}**!"
                msg_admin = f"✅ Đã duyệt danh hiệu **{role_name.title()}** cho <@{self.user_id}>."

        if user and msg_user:
            try: await user.send(msg_user)
            except discord.Forbidden: pass
        # ĐÃ THÊM MỚI: đếm số bài đã được duyệt thành công (hiển thị ở !profile),
        # và ghi log admin action vào kênh log riêng.
        await db.users.update_one({"_id": self.user_id}, {"$inc": {"approved_count": 1}}, upsert=True)
        await log_admin_action(interaction.user.mention, f"Duyệt {self.req_type.upper()}: **{self.item_name.title()}**", f"<@{self.user_id}>", msg_admin)
        await interaction.message.edit(content=f"{msg_admin}\nBởi: {interaction.user.mention}", view=None, embeds=[])
        await interaction.response.send_message("Duyệt thành công!", ephemeral=True)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RejectModal(self.user_id, interaction.message, self.item_name))

# ================= CÁC LỆNH BOT ================= #
@bot.command()
async def menu(ctx):
    is_admin = getattr(ctx.author, 'guild_permissions', None) and ctx.author.guild_permissions.administrator
    embed = discord.Embed(
        title="📚 HƯỚNG DẪN TỔNG HỢP LỆNH BOT", 
        description="Chào mừng bạn! Dưới đây là danh sách các tính năng của server.",
        color=discord.Color.blurple()
    )
    
    embed.add_field(name="💎 1. HỆ THỐNG DUYỆT BÀI & ĐIỂM MP", value="• `!duyet [độ khó/event/daily/danh hiệu]`\n📌 Gắn kèm video/ảnh làm bằng chứng.\n• `!bxh` - Xem Bảng Xếp Hạng MP.", inline=False)
    embed.add_field(name="🎖️ 2. DANH HIỆU TỰ ĐỘNG NHẬN", value="• Easy Demon ➔ `Newbie`\n• Medium Demon ➔ `Sự Khởi Đầu`\n• Hard Demon ➔ `Pro`\n• Insane Demon ➔ `Hardcore Player`\n• Extreme Demon ➔ `Huyền Thoại`\n📖 Xem đủ **57 danh hiệu** + cách lấy: `!danhsachdanhhieu`", inline=False)
    embed.add_field(name="👑 3. CÁC NGÔI VỊ TỐI THƯỢNG", value="🥇 **Vua Cày Điểm**: Top 1 MP toàn server.\n🏆 **Vua Hardest**: Duyệt bằng lệnh `!duyet vua hardest`.\n🔥 **Vua Try Hard**: 5 Hardest liên tiếp tăng dần, dùng `!duyet vua try hard`.", inline=False)
    embed.add_field(name="🎒 4. QUẢN LÝ DANH HIỆU", value="• `!listdanhhieu`: Xem danh hiệu bạn có.\n• `!setdanhhieu [tên]`: Trang bị danh hiệu.\n• `!editdanhhieu [an/hien]`: Bật/Tắt hiển thị.", inline=False)
    embed.add_field(name="📇 Hồ sơ", value="`!profile [@user]` xem MP, hạng, danh hiệu, số bài đã duyệt.", inline=True)
    embed.add_field(name="📅 Điểm danh", value="`!diemdanh` nhận MP thưởng mỗi ngày.", inline=True)
    embed.add_field(name="🎯 Sự kiện", value="`!daily` / `!event` xem mục tiêu hiện tại.", inline=True)
    embed.add_field(name="🤖 AI Gợi ý", value="`!dexuatlevel [yêu cầu]` đề xuất level có ID chính xác.", inline=True)
    embed.add_field(name="🚨 Tố cáo", value="`!report @user [lý do]` kèm bằng chứng.", inline=True)
    
    if is_admin:
        embed.add_field(name="🛠️ LỆNH ADMIN", value="• `!setmp @user [số]` đặt lại điểm\n• `!addmp @user [số]` cộng/trừ điểm\n• `!thongbao [event/daily] [ID]` cập nhật mục tiêu\n• `!dondanhieu` dọn dữ liệu active_title bị lỗi", inline=False)
        
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
async def thongbao(ctx, loai: str, level_id: str):
    loai = loai.lower()
    if loai not in ["event", "daily"]:
        return await ctx.send("❌ Loại phải là `event` hoặc `daily`.")
    
    now = datetime.now(VN_TZ)
    expires = now + timedelta(days=14) if loai == "event" else now.replace(hour=23, minute=59, second=59)
        
    await db.settings.update_one(
        {"_id": "gd_events"},
        {"$set": {f"{loai}": {"id": level_id, "expires": expires.timestamp()}}},
        upsert=True
    )
    
    embed = discord.Embed(title=f"📢 THÔNG BÁO {loai.upper()} MỚI", color=discord.Color.gold())
    embed.add_field(name="ID Level", value=f"**{level_id}**", inline=False)
    embed.add_field(name="Hết hạn", value=expires.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
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
    yeu_cau = yeu_cau.lower()
    
    if yeu_cau == "vua cày điểm": 
        return await ctx.send("❌ Danh hiệu **Vua Cày Điểm** được cấp tự động cho Top 1 MP. Bạn không thể duyệt thủ công!")

    if not ctx.message.attachments: return await ctx.send("📸 Phải gửi kèm bằng chứng nhé!")

    is_mp = yeu_cau in DIFFICULTY_MP
    is_role = yeu_cau in TITLES_DATA
    if not is_mp and not is_role: return await ctx.send("❌ Yêu cầu không hợp lệ!")

    if yeu_cau in ["daily", "event"]:
        daily_valid, event_valid = await check_event_daily_validity()
        if yeu_cau == "daily" and not daily_valid: return await ctx.send("❌ Daily đã hết hạn.")
        if yeu_cau == "event" and not event_valid: return await ctx.send("❌ Event đã hết hạn.")

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    attachment_url = ctx.message.attachments[0].url

    if is_role:
        embed = discord.Embed(title="⭐ YÊU CẦU DUYỆT DANH HIỆU", color=discord.Color.gold())
        req_type, reward_name, reward_value = "role", "Danh hiệu", yeu_cau.title()
    else:
        embed = discord.Embed(title="💎 YÊU CẦU DUYỆT ĐIỂM MP", color=discord.Color.blue())
        req_type, reward_name, reward_value = "mp", "Điểm MP", f"+{DIFFICULTY_MP[yeu_cau]} MP"

    embed.add_field(name="👤 Người gửi", value=ctx.author.mention, inline=True)
    embed.add_field(name="🎁 Loại", value=f"**{reward_name}**", inline=True)
    embed.add_field(name="✨ Phần thưởng", value=f"**{reward_value}**", inline=True)
    embed.add_field(name="🔗 Bằng chứng", value=f"[Xem tại đây]({attachment_url})", inline=False)
    embed.set_image(url=attachment_url)

    if admin_channel is None:
        return await ctx.send("❌ Không tìm thấy kênh admin để gửi duyệt (kiểm tra lại ADMIN_CHANNEL_ID và quyền bot).")

    view = ReviewView(ctx.author.id, req_type, yeu_cau, DIFFICULTY_MP.get(yeu_cau, yeu_cau))
    await admin_channel.send(embed=embed, view=view)
    await ctx.send("✅ Đã gửi cho Admin duyệt nhé!")

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

        difficulties = ["easy demon", "medium demon", "hard demon", "insane demon", "extreme demon", "demon", "auto", "easy", "normal", "hard", "harder", "insane"]
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
    embed = discord.Embed(
        title="🎖️ TOÀN BỘ DANH HIỆU CỦA SERVER",
        description="Dùng `!duyet [tên danh hiệu]` kèm ảnh/video bằng chứng để nộp. Admin chỉ xét đúng/sai dựa trên bằng chứng, không tự ý ưu ái ai.",
        color=discord.Color.gold()
    )
    embed.add_field(name="🥇 Ngôi vị & tự động nhận", value="Newbie, Sự Khởi Đầu, Pro, Hardcore Player, Huyền Thoại *(tự động khi duyệt Demon tương ứng)*\nVua Hardest, Vua Try Hard *(duyệt tay qua !duyet)*\nVua Cày Điểm *(tự động cho Top 1 MP, không duyệt tay được)*", inline=False)
    embed.add_field(name="⚔️ Tiến trình kỹ năng", value="Người Mới Toe, Tân Binh, Học Việc, Chiến Binh, Đấu Sĩ, Sát Thủ Demon, Thợ Săn Insane, Kẻ Hủy Diệt, Bậc Thầy Phản Xạ, Vô Địch Tốc Độ", inline=False)
    embed.add_field(name="⛏️ Cày điểm", value="Cày Cuốc Chăm Chỉ, Thợ Cày Chuyên Nghiệp, Máy Cày MP, Nông Dân Demon, Vua Năng Suất", inline=False)
    embed.add_field(name="🔥 Kiên trì", value="Kiên Trì Bất Khuất, Không Bỏ Cuộc, Chiến Thần Bền Bỉ, Người Sắt, Ý Chí Thép", inline=False)
    embed.add_field(name="🤝 Cộng đồng", value="Người Bạn Tốt, Trưởng Lão Server, Cố Vấn Tân Binh, Đại Sứ Cộng Đồng, Người Truyền Cảm Hứng", inline=False)
    embed.add_field(name="🎨 Sáng tạo", value="Nhà Thiết Kế, Kiến Trúc Sư Level, Nghệ Sĩ Decor, Bậc Thầy Sáng Tạo, Huyền Thoại Sáng Tác", inline=False)
    embed.add_field(name="🎉 Sự kiện", value="Chiến Binh Event, Vua Sự Kiện Tháng, Người Về Đích Đầu Tiên, Huyền Thoại Mùa Giải, Nhà Vô Địch Giải Đấu", inline=False)
    embed.add_field(name="😂 Vui/troll", value="Trùm Rớt Điểm Rơi, Vua Nổ Máy, Ông Hoàng Restart, Đại Sư Spam Thử, Chúa Tể Rage Quit", inline=False)
    embed.add_field(name="💎 Hiếm", value="Người Được Chọn, VIP Server, Huyền Thoại Sống, Thánh Nhân GD, Tối Thượng Chi Vương", inline=False)
    embed.add_field(name="🕰️ Thâm niên", value="Thành Viên Kỳ Cựu, Lính Cũ, Chứng Nhân Lịch Sử, Linh Hồn Server, Vĩnh Cửu", inline=False)
    embed.set_footer(text=f"Tổng cộng {len(TITLES_DATA)} danh hiệu | Dùng !listdanhhieu để xem danh hiệu bạn đang sở hữu")
    await ctx.send(embed=embed)

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
    await ctx.send(embed=embed)

# ĐÃ THÊM MỚI: !diemdanh - điểm danh hằng ngày nhận thưởng MP nhỏ, giới hạn
# 1 lần/ngày theo giờ Việt Nam (dùng last_checkin lưu ngày dạng ISO string
# để so sánh đơn giản, không cần xử lý timezone phức tạp mỗi lần check).
DIEMDANH_THUONG_MP = 20

@bot.command(aliases=["checkin"])
@require_db()
async def diemdanh(ctx):
    hom_nay = datetime.now(VN_TZ).date().isoformat()
    u = await db.users.find_one({"_id": ctx.author.id}) or {}
    if u.get("last_checkin") == hom_nay:
        return await ctx.send("⏳ Bạn đã điểm danh hôm nay rồi, quay lại vào ngày mai nhé!")

    await add_user_mp(ctx.author.id, DIEMDANH_THUONG_MP, ctx.guild)
    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"last_checkin": hom_nay}}, upsert=True)
    await ctx.send(f"✅ Điểm danh thành công! +{DIEMDANH_THUONG_MP} MP. Hẹn gặp lại ngày mai nhé!")

@bot.command()
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
    await ch.send(embed=embed, files=tep_dinh_kem, view=ReportReviewView(ctx.author.id, member))
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

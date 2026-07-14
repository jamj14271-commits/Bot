import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import asyncio
import motor.motor_asyncio
import certifi
import google.generativeai as genai
from keep_alive import keep_alive
from datetime import datetime, timedelta, timezone

# ================= CẤU HÌNH CƠ BẢN ================= #
ADMIN_CHANNEL_ID = 1525386498739015800  
REPORT_CHANNEL_ID = 1525662263502176306
WELCOME_CHANNEL_ID = 1525492114564317204  

DIFFICULTY_MP = {
    "easy": 5, "normal": 10, "hard": 25, "harder": 50, "insane": 100,
    "easy demon": 250, "medium demon": 500, "hard demon": 1000,
    "insane demon": 5000, "extreme demon": 10000,
    "daily": 150, "event": 2500
}

TITLES_DATA = [
    "newbie", "sự khởi đầu", "pro",
    "hardcore player", "huyền thoại",
    "vua try hard", "vua hardest", "vua cày điểm"
]

VN_TZ = timezone(timedelta(hours=7))

# ================= CẤU HÌNH GEMINI ĐÃ TỐI ƯU ================= #
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = None

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    gd_system_instruction = (
        "Bạn là chuyên gia về game Geometry Dash. CHỈ trả lời các câu hỏi liên quan đến Geometry Dash.\n"
        "Quy tắc BẮT BUỘC tuân thủ:\n"
        "1. Trả lời ngắn gọn, dễ đọc, dùng Markdown gọn gàng.\n"
        "2. Khi đề xuất level: Ghi rõ Tên level | Tác giả | Độ khó | ID level | Lý do phù hợp.\n"
        "3. Đề xuất đủ 3-5 level phù hợp với trình độ & điểm MP của người chơi.\n"
        "4. Nếu câu hỏi không liên quan Geometry Dash: Trả lời: 'Tôi chỉ hỗ trợ thông tin về Geometry Dash thôi nhé!'\n"
        "5. Không tạo thông tin sai lệch, không phát minh level không tồn tại."
    )
    
    generation_config = genai.types.GenerationConfig(
        temperature=0.1,
        max_output_tokens=1024,
        top_p=0.95
    )
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
    ]
    
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash-latest',
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

@bot.event
async def on_ready():
    global db_client, db
    print(f'Đang kết nối database...')
    mongo_uri = os.getenv('MONGO_URI') 
    db_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri, tlsCAFile=certifi.where())
    db = db_client['gd_database']
    print(f'Bot {bot.user} đã sẵn sàng hoạt động!')

# ================= CÁC HÀM TIỆN ÍCH ================= #
async def get_user_mp(user_id):
    user = await db.users.find_one({"_id": user_id})
    return user["mp"] if user else 0

async def add_user_mp(user_id, amount, guild=None):
    await db.users.update_one({"_id": user_id}, {"$inc": {"mp": amount}}, upsert=True)
    if guild:
        await check_and_transfer_top1_mp(guild)

async def check_and_transfer_top1_mp(guild):
    users = await db.users.find().sort("mp", -1).limit(1).to_list(1)
    if not users: return
    new_top1_id = users[0]["_id"]
    
    config = await db.settings.find_one({"_id": "top1_mp_owner"})
    old_top1_id = config["user_id"] if config else None

    if old_top1_id != new_top1_id:
        if old_top1_id:
            await db.users.update_one({"_id": old_top1_id}, {"$pull": {"titles": "vua cày điểm"}})
        
        await db.users.update_one({"_id": new_top1_id}, {"$addToSet": {"titles": "vua cày điểm"}, "$set": {"active_title": "vua cày điểm"}}, upsert=True)
        await db.settings.update_one({"_id": "top1_mp_owner"}, {"$set": {"user_id": new_top1_id}}, upsert=True)

async def grant_vua_hardest(guild, new_owner_id):
    config = await db.settings.find_one({"_id": "vua_hardest_owner"})
    old_owner_id = config["user_id"] if config else None

    if old_owner_id and old_owner_id != new_owner_id:
        await db.users.update_one({"_id": old_owner_id}, {"$pull": {"titles": "vua hardest"}})
        
    await db.users.update_one({"_id": new_owner_id}, {"$addToSet": {"titles": "vua hardest"}, "$set": {"active_title": "vua hardest"}}, upsert=True)
    await db.settings.update_one({"_id": "vua_hardest_owner"}, {"$set": {"user_id": new_owner_id}}, upsert=True)

async def grant_vua_try_hard(guild, new_owner_id):
    config = await db.settings.find_one({"_id": "vua_try_hard_owner"})
    old_owner_id = config["user_id"] if config else None

    if old_owner_id and old_owner_id != new_owner_id:
        await db.users.update_one({"_id": old_owner_id}, {"$pull": {"titles": "vua try hard"}})
        
    await db.users.update_one({"_id": new_owner_id}, {"$addToSet": {"titles": "vua try hard"}, "$set": {"active_title": "vua try hard"}}, upsert=True)
    await db.settings.update_one({"_id": "vua_try_hard_owner"}, {"$set": {"user_id": new_owner_id}}, upsert=True)

async def check_event_daily_validity():
    settings = await db.settings.find_one({"_id": "gd_events"})
    if not settings: return None, None
    
    now_ts = datetime.now(VN_TZ).timestamp()
    daily = settings.get("daily")
    event = settings.get("event")
    
    def is_valid(data):
        if not data or not data.get("expires"): return False
        expires = data["expires"]
        
        if isinstance(expires, datetime):
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=VN_TZ)
            expires = expires.timestamp()
            
        return now_ts < expires

    daily_valid = daily if is_valid(daily) else None
    event_valid = event if is_valid(event) else None
    
    return daily_valid, event_valid

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=f"🎉 Chào mừng {member.display_name} gia nhập server!",
            description="Dưới đây là một số hướng dẫn cơ bản để bạn làm quen với server nhé.",
            color=discord.Color.blue()
        )
        embed.add_field(name="📜 Lệnh Bot Cơ Bản", value="Hãy gõ `!menu` tại kênh chat để xem toàn bộ danh sách lệnh.", inline=False)
        embed.add_field(name="💎 Nhận MP & Danh Hiệu", value="Dùng lệnh `!duyet [độ khó/event/daily]` kèm video/ảnh để Admin duyệt.", inline=False)
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
        except discord.Forbidden: pass
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
                await db.users.update_one(
                    {"_id": self.user_id}, 
                    {"$addToSet": {"titles": auto_title}, "$set": {"active_title": auto_title}}, 
                    upsert=True
                )
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
        await interaction.message.edit(content=f"{msg_admin}\nBởi: {interaction.user.mention}", view=None, embeds=[])
        await interaction.response.send_message("Duyệt thành công!", ephemeral=True)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RejectModal(self.user_id, interaction.message, self.item_name))

# ================= CÁC LỆNH BOT ================= #
@bot.command()
async def menu(ctx):
    is_admin = ctx.author.guild_permissions.administrator
    embed = discord.Embed(
        title="📚 HƯỚNG DẪN TỔNG HỢP LỆNH BOT", 
        description="Chào mừng bạn! Dưới đây là danh sách các tính năng của server.",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="💎 1. HỆ THỐNG DUYỆT BÀI & ĐIỂM MP", 
        value="• `!duyet [độ khó/event/daily/danh hiệu]`\n"
              "📌 Gắn kèm video/ảnh làm bằng chứng.\n"
              "• `!bxh` - Xem Bảng Xếp Hạng MP.", 
            inline=False
    )
    
    embed.add_field(
        name="🎖️ 2. DANH HIỆU TỰ ĐỘNG NHẬN", 
        value="• Easy Demon ➔ `Newbie`\n"
              "• Medium Demon ➔ `Sự Khởi Đầu`\n"
              "• Hard Demon ➔ `Pro`\n"
              "• Insane Demon ➔ `Hardcore Player`\n"
              "• Extreme Demon ➔ `Huyền Thoại`", 
        inline=False
    )
    
    embed.add_field(
        name="👑 3. CÁC NGÔI VỊ TỐI THƯỢNG", 
        value="🥇 **Vua Cày Điểm**: Top 1 MP toàn server.\n"
              "🏆 **Vua Hardest**: Duyệt bằng lệnh `!duyet vua hardest`.\n"
              "🔥 **Vua Try Hard**: 5 Hardest liên tiếp tăng dần, dùng `!duyet vua try hard`.", 
        inline=False
    )
    
    embed.add_field(
        name="🎒 4. QUẢN LÝ DANH HIỆU", 
        value="• `!listdanhhieu`: Xem danh hiệu bạn có.\n"
              "• `!setdanhhieu [tên]`: Trang bị danh hiệu.\n"
              "• `!editdanhhieu [an/hien]`: Bật/Tắt hiển thị.", 
        inline=False
    )

    embed.add_field(name="🎯 Sự kiện", value="`!daily` / `!event` xem mục tiêu hiện tại.", inline=True)
    embed.add_field(name="🤖 AI Gợi ý", value="`!dexuatlevel [yêu cầu]` đề xuất level phù hợp.", inline=True)
    embed.add_field(name="🚨 Tố cáo", value="`!report @user [lý do]` kèm bằng chứng.", inline=True)
    
    if is_admin:
        embed.add_field(
            name="🛠️ LỆNH ADMIN", 
            value="• `!setmp @user [số]` đặt lại điểm\n"
                  "• `!addmp @user [số]` cộng/trừ điểm\n"
                  "• `!thongbao [event/daily] [ID]` cập nhật mục tiêu", 
            inline=False
        )
        
    embed.set_footer(text="💡 Nhớ gửi kèm ảnh/video khi dùng !duyet hay !report nhé!")
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def thongbao(ctx, type: str, level_id: str):
    type = type.lower()
    if type not in ["event", "daily"]:
        return await ctx.send("❌ Loại phải là `event` hoặc `daily`.")
    
    now = datetime.now(VN_TZ)
    expires = now + timedelta(days=14) if type == "event" else now.replace(hour=23, minute=59, second=59)
        
    await db.settings.update_one(
        {"_id": "gd_events"},
        {"$set": {f"{type}": {"id": level_id, "expires": expires.timestamp()}}},
        upsert=True
    )
    
    embed = discord.Embed(title=f"📢 THÔNG BÁO {type.upper()} MỚI", color=discord.Color.gold())
    embed.add_field(name="ID Level", value=f"**{level_id}**", inline=False)
    embed.add_field(name="Hết hạn", value=expires.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
    await ctx.send(embed=embed)

@bot.command(aliases=["daily", "event"])
async def show_event(ctx):
    cmd_used = ctx.invoked_with.lower()
    daily_valid, event_valid = await check_event_daily_validity()
    data = daily_valid if cmd_used == "daily" else event_valid
    if not data: return await ctx.send(f"❌ Chưa có {cmd_used} nào hoặc đã hết hạn!")
    
    expires_dt = datetime.fromtimestamp(data['expires'], VN_TZ)
    embed = discord.Embed(title=f"🎯 MỤC TIÊU {cmd_used.upper()}", color=discord.Color.green())
    embed.add_field(name="ID Level", value=f"**{data['id']}**", inline=False)
    embed.add_field(name="Hết hạn", value=expires_dt.strftime("%d/%m/%Y %H:%M:%S"), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def duyet(ctx, *, yeu_cau: str = None):
    if not yeu_cau: return await ctx.send("❌ VD: `!duyet easy demon` hoặc `!duyet vua hardest`")
    if not ctx.message.attachments: return await ctx.send("📸 Phải gửi kèm bằng chứng nhé!")

    yeu_cau = yeu_cau.lower()
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

    view = ReviewView(ctx.author.id, req_type, yeu_cau, DIFFICULTY_MP.get(yeu_cau, yeu_cau))
    await admin_channel.send(embed=embed, view=view)
    await ctx.send("✅ Đã gửi cho Admin duyệt nhé!")

# ====== LỆNH AI GEMINI ĐÃ SỬA ====== #
@bot.command()
async def dexuatlevel(ctx, *, trinh_do: str = None):
    if not trinh_do: return await ctx.send("❌ VD: `!dexuatlevel dễ cho người mới` hoặc `!dexuatlevel hard demon`")
    if not GEMINI_API_KEY or model is None: return await ctx.send("❌ Chưa cấu hình API Key AI!")

    waiting_msg = await ctx.send("⏳ Đang tìm level phù hợp...")
    user_mp = await get_user_mp(ctx.author.id)
    prompt = f"Người chơi có {user_mp} MP, yêu cầu: '{trinh_do}'. Đề xuất level Geometry Dash theo quy tắc."

    for retry in range(3):
        try:
            response = await model.generate_content_async(prompt)
            if not response.parts: raise ValueError("Phản hồi trống/bị chặn")
            reply_text = response.text.strip()
            if not reply_text: raise ValueError("Không có nội dung")

            embed = discord.Embed(title=f"🎯 Đề xuất cho: {trinh_do.title()}", description=reply_text[:4000], color=discord.Color.green())
            embed.set_footer(text=f"Dựa trên {user_mp} MP của bạn")
            await waiting_msg.edit(embed=embed, content=None)
            return

        except Exception as e:
            err = str(e)
            print(f"[LỖI AI LẦN {retry+1}]: {err}")
            if any(x in err for x in ["429", "ResourceExhausted", "503", "Unavailable"]):
                t = (2**retry)+1
                await waiting_msg.edit(content=f"⏳ AI bận, chờ {t}s...")
                await asyncio.sleep(t)
                continue
            break

    await waiting_msg.edit(embed=discord.Embed(title="❌ Lỗi kết nối AI", description="Thử lại sau vài phút nhé!", color=discord.Color.red()), content=None)

@bot.command()
async def listdanhhieu(ctx):
    u = await db.users.find_one({"_id": ctx.author.id})
    titles = u.get("titles", []) if u else []
    if not titles: return await ctx.send("Túi đồ rỗng!")
    await ctx.send(f"🎖️ Danh hiệu của bạn:\n- " + "\n- ".join(t.title() for t in titles))

@bot.command()
async def setdanhhieu(ctx, *, ten: str = None):
    if not ten: return await ctx.send("❌ Nhập tên danh hiệu nhé!")
    ten = ten.lower()
    u = await db.users.find_one({"_id": ctx.author.id})
    if not u or ten not in u.get("titles", []): return await ctx.send("❌ Bạn không có danh hiệu này!")
    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"active_title": ten}})
    await ctx.send(f"✅ Đã trang bị: **{ten.title()}**")

@bot.command()
async def editdanhhieu(ctx, trang_thai: str = None):
    if trang_thai not in ["an", "hien"]: return await ctx.send("❌ Dùng `!editdanhhieu an` hoặc `!editdanhhieu hien`")
    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"title_visible": (trang_thai=="hien")}}, upsert=True)
    await ctx.send(f"✅ Đã cập nhật hiển thị danh hiệu!")

@bot.command()
async def report(ctx, member: discord.Member = None, *, reason: str = None):
    try: await ctx.message.delete()
    except: pass
    if not member or not reason: return await ctx.send("❌ VD: `!report @User vi phạm quy tắc`", delete_after=5)

    ch = bot.get_channel(REPORT_CHANNEL_ID)
    embed = discord.Embed(title="🚨 BÁO CÁO VI PHẠM", color=discord.Color.red())
    embed.add_field(name="Bị tố cáo", value=member.mention, inline=True)
    embed.add_field(name="Người báo", value=ctx.author.mention, inline=True)
    embed.add_field(name="Lý do", value=f"**{reason}**", inline=False)
    files = [await a.to_file() for a in ctx.message.attachments] if ctx.message.attachments else []
    embed.set_footer(text=f"Có {len(files)} tệp đính kèm" if files else "Không có bằng chứng")
    await ch.send(embed=embed, files=files, view=ReportReviewView(ctx.author.id, member))
    await ctx.send("✅ Đã gửi báo cáo cho Admin!", delete_after=5)

@bot.command()
async def bxh(ctx):
    users = await db.users.find().sort("mp", -1).limit(100).to_list(100)
    if not users: return await ctx.send("Chưa có ai trên BXH!")
    rank = {"a_than":[], "god":[], "pro":[], "thuong":[]}
    
    for u in users:
        m = ctx.guild.get_member(u["_id"])
        name = m.display_name if m else f"ID:{u['_id']}"
        mp = u.get("mp",0)
        title = f" | ✦ {u.get('active_title','').title()} ✦" if u.get("title_visible",True) and u.get("active_title") else ""
        
        if mp>=100000: rank["a_than"].append(f"{name} - {mp} MP{title}")
        elif mp>=50000: rank["god"].append(f"{name} - {mp} MP{title}")
        elif mp>=10000: rank["pro"].append(f"{name} - {mp} MP{title}")
        else: rank["thuong"].append(f"{name} - {mp} MP{title}")

    em = discord.Embed(title="🏆 BẢNG XẾP HẠNG MP SERVER", color=discord.Color.gold())
    if rank["a_than"]: em.add_field(name="👑 Á Thần (100k+)", value="\n".join(rank["a_than"]), inline=False)
    if rank["god"]: em.add_field(name="⚡ God (50k-99k)", value="\n".join(rank["god"]), inline=False)
    if rank["pro"]: em.add_field(name="⚔️ Pro (10k-49k)", value="\n".join(rank["pro"]), inline=False)
    if rank["thuong"]: em.add_field(name="🌱 Thường (<10k)", value="\n".join(rank["thuong"]), inline=False)
    await ctx.send(embed=em)

@bot.command(name="setmp")
@commands.has_permissions(administrator=True)
async def set_mp(ctx, member: discord.Member=None, amount:int=None):
    if not member or amount is None: return await ctx.send("❌ `!setmp @user [số]`")
    await db.users.update_one({"_id": member.id}, {"$set":{"mp":amount}}, upsert=True)
    await check_and_transfer_top1_mp(ctx.guild)
    await ctx.send(f"✅ Đặt {amount} MP cho {member.mention}")

@bot.command(name="addmp")
@commands.has_permissions(administrator=True)
async def add_mp(ctx, member: discord.Member=None, amount:int=None):
    if not member or amount is None: return await ctx.send("❌ `!addmp @user [số]`")
    await add_user_mp(member.id, amount, ctx.guild)
    await ctx.send(f"✅ Đã cập nhật MP cho {member.mention}")

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN: bot.run(TOKEN)
    else: print("❌ Không tìm thấy DISCORD_TOKEN!")
            

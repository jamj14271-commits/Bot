import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import json
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

# Lưu trữ danh hiệu dưới dạng chuỗi (Vật phẩm ảo trong DB)
TITLES_DATA = [
    "chiến binh try hard", "chiến binh đã tốt nghiệp", "pro",
    "vua try hard", "vua hardest", "vua cày điểm"
]

VN_TZ = timezone(timedelta(hours=7))

# ================= CẤU HÌNH GEMINI ================= #
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = None

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    gd_system_instruction = (
        "Bạn là một chuyên gia uyên bác về tựa game Geometry Dash. Nhiệm vụ duy nhất của bạn là đề xuất các level phù hợp với trình độ người chơi yêu cầu.\n"
        "Quy tắc bắt buộc:\n"
        "1. Trả lời ngắn gọn, thân thiện.\n"
        "2. Đề xuất từ 3 đến 5 level. Mỗi level phải ghi rõ: Tên level, Tác giả (Creator), Độ khó, ID level (nếu có), và một câu ngắn gọn lý do khuyên chơi.\n"
        "3. Trình bày bằng cấu trúc markdown gọn gàng, đẹp mắt.\n"
        "4. TỪ CHỐI TRẢ LỜI hoặc nhắc nhở khéo léo đối với mọi câu hỏi không liên quan đến Geometry Dash."
    )
    
    generation_config = genai.types.GenerationConfig(
        temperature=0.6,
    )
    
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        system_instruction=gd_system_instruction,
        generation_config=generation_config
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
    # ================= CÁC HÀM TIỆN ÍCH & LOGIC ================= #
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
        embed.add_field(name="💎 Nhận MP & Danh Hiệu", value="Dùng lệnh `!duyet [độ khó/event/daily]` kèm video/ảnh để admin duyệt.", inline=False)
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
            if self.item_name == "easy demon": auto_title = "chiến binh try hard"
            elif self.item_name == "medium demon": auto_title = "chiến binh đã tốt nghiệp"
            elif self.item_name == "hard demon": auto_title = "pro"
                
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



# ================= CÁC LỆNH BOT (COMMANDS) ================= #
@bot.command()
async def menu(ctx):
    is_admin = ctx.author.guild_permissions.administrator
    embed = discord.Embed(
        title="📚 HƯỚNG DẪN TỔNG HỢP LỆNH BOT", 
        description="Chào mừng bạn! Dưới đây là danh sách các tính năng được thiết kế để bạn có trải nghiệm tốt nhất trên Server.",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="💎 1. HỆ THỐNG DUYỆT BÀI & ĐIỂM MP", 
        value="• `!duyet [độ khó/event/daily/danh hiệu]`\n"
              "📌 *Gắn kèm video/ảnh làm bằng chứng để Admin cấp MP cho bạn.*\n"
              "• `!bxh` - Xem Bảng Xếp Hạng MP toàn server hiện tại.", 
        inline=False
    )
    
    embed.add_field(
        name="🎖️ 2. HỆ THỐNG DANH HIỆU DEMON (Tự động nhận)", 
        value="• Duyệt **Easy Demon** ➔ Nhận ngay `Chiến Binh Try Hard`\n"
              "• Duyệt **Medium Demon** ➔ Nhận ngay `Chiến Binh Đã Tốt Nghiệp`\n"
              "• Duyệt **Hard Demon** ➔ Nhận ngay `Pro`", 
        inline=False
    )
    
    embed.add_field(
        name="👑 3. CÁC NGÔI VỊ TỐI THƯỢNG CỦA SERVER", 
        value="🥇 **Vua Cày Điểm**: Tự động phong tước cho người đứng **Top 1 MP**.\n"
              "🏆 **Vua Hardest**: Thách thức Level khó nhất Server. Lệnh `!duyet vua hardest`.\n"
              "🔥 **Vua Try Hard**: Đòi hỏi chuỗi 5 Hardest liên tiếp độ khó tăng dần. Mỗi kỷ lục dùng `!duyet vua try hard`. *(Lưu ý: Bị Admin từ chối 1 lần sẽ mất toàn bộ chuỗi!)*", 
        inline=False
    )
    
    embed.add_field(
        name="🎒 4. QUẢN LÝ DANH HIỆU CÁ NHÂN", 
        value="• `!listdanhhieu`: Xem danh hiệu bạn đang cất trong tủ.\n"
              "• `!setdanhhieu [tên]`: Trang bị danh hiệu để hiển thị lên BXH.\n"
              "• `!editdanhhieu [an/hien]`: Bật/Tắt hiển thị danh hiệu.", 
        inline=False
    )

    embed.add_field(name="🎯 Sự kiện GD", value="`!daily` hoặc `!event`\nXem mục tiêu để cày thêm MP.", inline=True)
    embed.add_field(name="🤖 AI Gợi ý Level", value="`!dexuatlevel [yêu cầu]`\nTự động đọc dữ liệu MP để gợi ý Map phù hợp.", inline=True)
    embed.add_field(name="🚨 Tố cáo vi phạm", value="`!report @user [lý do]`\nKèm theo ảnh bằng chứng.", inline=True)
    
    if is_admin:
        embed.add_field(
            name="🛠️ 5. LỆNH DÀNH CHO ADMIN", 
            value="• `!setmp @user [số]` - Đặt lại điểm gốc cho Member\n"
                  "• `!addmp @user [số]` - Cộng/Trừ thẳng điểm MP\n"
                  "• `!thongbao [event/daily] [ID]` - Cập nhật Sự kiện GD", 
            inline=False
        )
        
    embed.set_footer(text="💡 Mẹo: Nhớ gửi kèm Hình ảnh/Video mỗi khi dùng !report hoặc !duyet nhé!")
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def thongbao(ctx, type: str, level_id: str):
    type = type.lower()
    if type not in ["event", "daily"]:
        return await ctx.send("❌ Loại thông báo phải là `event` hoặc `daily`.")
    
    now = datetime.now(VN_TZ)
    if type == "event":
        expires = now + timedelta(days=14)
    else:
        expires = now.replace(hour=23, minute=59, second=59)
        
    await db.settings.update_one(
        {"_id": "gd_events"},
        {"$set": {f"{type}": {"id": level_id, "expires": expires.timestamp()}}},
        upsert=True
    )
    
    embed = discord.Embed(title=f"📢 THÔNG BÁO {type.upper()} MỚI", color=discord.Color.gold())
    embed.add_field(name="ID Level", value=f"**{level_id}**", inline=False)
    embed.add_field(name="Hết hạn vào", value=expires.strftime("%d/%m/%Y %H:%M:%S (Giờ VN)"), inline=False)
    await ctx.send(embed=embed)

@bot.command(aliases=["daily", "event"])
async def show_event(ctx):
    cmd_used = ctx.invoked_with.lower()
    daily_valid, event_valid = await check_event_daily_validity()
    
    data = daily_valid if cmd_used == "daily" else event_valid
    if not data:
        return await ctx.send(f"❌ Hiện tại chưa có level {cmd_used} nào hoặc đã hết hạn!")
    
    expires_dt = datetime.fromtimestamp(data['expires'], VN_TZ)
    
    embed = discord.Embed(title=f"🎯 MỤC TIÊU {cmd_used.upper()} HIỆN TẠI", color=discord.Color.green())
    embed.add_field(name="ID Level", value=f"**{data['id']}**", inline=False)
    embed.add_field(name="Hết hạn", value=expires_dt.strftime("%d/%m/%Y %H:%M:%S (VN)"), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def duyet(ctx, *, yeu_cau: str = None):
    if not yeu_cau:
        return await ctx.send("❌ Vui lòng nhập độ khó, event/daily hoặc tên danh hiệu! VD: `!duyet daily` hoặc `!duyet vua try hard`")
    
    if not ctx.message.attachments:
        return await ctx.send("📸 Bạn phải gửi kèm theo video/ảnh chứng minh vào tin nhắn này nhé!")

    yeu_cau = yeu_cau.lower()
    is_mp = yeu_cau in DIFFICULTY_MP
    is_role = yeu_cau in TITLES_DATA
    
    if not is_mp and not is_role:
        return await ctx.send("❌ Yêu cầu không hợp lệ. Vui lòng check lại cú pháp.")

    if yeu_cau in ["daily", "event"]:
        daily_valid, event_valid = await check_event_daily_validity()
        if yeu_cau == "daily" and not daily_valid: return await ctx.send("❌ Daily hiện tại đã hết hạn.")
        if yeu_cau == "event" and not event_valid: return await ctx.send("❌ Event hiện tại đã hết hạn.")

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    attachment_url = ctx.message.attachments[0].url

    if is_role:
        embed = discord.Embed(title="⭐ YÊU CẦU DUYỆT DANH HIỆU", color=discord.Color.gold())
        req_type, reward_name, reward_value, reward_id = "role", "Danh hiệu", yeu_cau.title(), yeu_cau.title()
    else:
        embed = discord.Embed(title="💎 YÊU CẦU DUYỆT ĐIỂM MP", color=discord.Color.blue())
        req_type, reward_name, reward_value, reward_id = "mp", "Điểm MP", f"+{DIFFICULTY_MP[yeu_cau]} MP", DIFFICULTY_MP[yeu_cau]

    embed.add_field(name="👤 Người gửi", value=ctx.author.mention, inline=True)
    embed.add_field(name="🎁 Loại thưởng", value=f"**{reward_name}**", inline=True)
    embed.add_field(name="✨ Phần thưởng", value=f"**{reward_value}**", inline=True)
    embed.add_field(name="📝 Yêu cầu ban đầu", value=yeu_cau.title(), inline=False)
    embed.add_field(name="🔗 Bằng chứng", value=f"[Nhấn vào đây để xem toàn màn hình]({attachment_url})", inline=False)
    
    embed.set_image(url=attachment_url)

    view = ReviewView(ctx.author.id, req_type, yeu_cau, reward_id)
    await admin_channel.send(embed=embed, view=view)
    await ctx.send("✅ Đã gửi bài của bạn cho Admin xét duyệt. Hãy kiên nhẫn chờ đợi nhé!")

# ====== LỆNH AI GEMINI ĐỀ XUẤT ====== #
@bot.command()
async def dexuatlevel(ctx, *, trinh_do: str = None):
    if not trinh_do:
        return await ctx.send("❌ Bạn chưa nhập yêu cầu! \nVD: `!dexuatlevel hard demon` hoặc `!dexuatlevel tìm map nhạc hay`")
    
    if not GEMINI_API_KEY or model is None:
        return await ctx.send("❌ Lỗi Server: Bot chưa nhận được API Key từ Render hoặc AI chưa khởi tạo thành công!")

    embed_loading = discord.Embed(
        title="🤖 Hệ thống AI đang phân tích...",
        description=f"Đang tiến hành lục tìm cơ sở dữ liệu các level phù hợp với: **{trinh_do}**.\nVui lòng chờ trong giây lát nhé ⏳",
        color=discord.Color.blurple()
    )
    waiting_msg = await ctx.send(embed=embed_loading)

    try:
        user_mp = await get_user_mp(ctx.author.id)
        prompt = f"Người dùng này đang có {user_mp} MP (điểm kinh nghiệm) trong hệ thống server Geometry Dash. Họ yêu cầu: '{trinh_do}'. Hãy phân tích mức MP và chuỗi yêu cầu này để đưa ra danh sách các level hợp lý nhất."

        response = await model.generate_content_async(prompt)
        
        if not response.text:
            raise ValueError("Bộ lọc Google đã chặn nội dung phản hồi do chứa từ ngữ nhạy cảm.")

        reply_text = response.text
        if len(reply_text) > 4090: 
            reply_text = reply_text[:4080] + "\n\n*(Nội dung đã tự động cắt ngắn do quá dài)*"

        embed_result = discord.Embed(
            title=f"🎯 Đề xuất Level: {trinh_do.title()}",
            description=reply_text,
            color=discord.Color.green()
        )
        embed_result.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name} | Đang có {user_mp} MP")
        
        await waiting_msg.edit(embed=embed_result, content=None)

    except Exception as e:
        print(f"[LỖI XỬ LÝ GEMINI]: {e}")
        embed_error = discord.Embed(
            title="❌ Gặp sự cố kết nối AI",
            description=f"Không thể giao tiếp với máy chủ AI Gemini hoặc hệ thống đang quá tải. Vui lòng thử lại sau.\n\n**Mã lỗi chi tiết:**\n```\n{str(e)[:450]}\n```",
            color=discord.Color.red()
        )
        await waiting_msg.edit(embed=embed_error, content=None)
    


# ====== LỆNH QUẢN LÝ DANH HIỆU ====== #
@bot.command()
async def listdanhhieu(ctx):
    user_data = await db.users.find_one({"_id": ctx.author.id})
    titles = user_data.get("titles", []) if user_data else []
    if not titles:
        return await ctx.send("Túi đồ rỗng! Bạn chưa sở hữu danh hiệu nào.")
    await ctx.send(f"🎖️ **Danh hiệu bạn đang có:**\n- " + "\n- ".join([t.title() for t in titles]))

@bot.command()
async def setdanhhieu(ctx, *, ten: str = None):
    if not ten: return await ctx.send("Vui lòng nhập tên danh hiệu: `!setdanhhieu [tên]`")
    ten = ten.lower()
    user_data = await db.users.find_one({"_id": ctx.author.id})
    if not user_data or ten not in user_data.get("titles", []):
        return await ctx.send("❌ Bạn không sở hữu danh hiệu này!")
    
    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"active_title": ten}})
    await ctx.send(f"✅ Đã trang bị danh hiệu: **{ten.title()}**")

@bot.command()
async def editdanhhieu(ctx, trang_thai: str = None):
    if trang_thai not in ["an", "hien"]: return await ctx.send("Dùng: `!editdanhhieu an` hoặc `!editdanhhieu hien`")
    is_visible = (trang_thai == "hien")
    await db.users.update_one({"_id": ctx.author.id}, {"$set": {"title_visible": is_visible}}, upsert=True)
    await ctx.send(f"✅ Đã {'hiển thị' if is_visible else 'ẩn'} danh hiệu trên BXH.")

@bot.command()
async def report(ctx, member: discord.Member = None, *, reason: str = None):
    try: await ctx.message.delete()
    except discord.Forbidden: pass 
    if not member or not reason: return await ctx.send("❌ Cú pháp đúng: `!report @user [lý do]`", delete_after=5)

    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    embed = discord.Embed(title="🚨 BÁO CÁO VI PHẠM TỪ NGƯỜI CHƠI", color=discord.Color.red())
    embed.add_field(name="👤 Người bị tố cáo", value=member.mention, inline=True)
    embed.add_field(name="🕵️ Người gửi", value=ctx.author.mention, inline=True)
    embed.add_field(name="📝 Lý do vi phạm", value=f"**{reason}**", inline=False)
    
    files = [await a.to_file() for a in ctx.message.attachments] if ctx.message.attachments else []
    if files:
        embed.set_footer(text="Có tệp tin/hình ảnh đính kèm trong báo cáo này.")
    else:
        embed.set_footer(text="⚠️ Báo cáo không có hình ảnh/video bằng chứng.")

    view = ReportReviewView(ctx.author.id, member)
    await report_channel.send(embed=embed, files=files, view=view)
    await ctx.send(f"✅ Đã gửi báo cáo vi phạm đối với {member.display_name}! Admin sẽ xem xét sớm nhất.", delete_after=5)

@bot.command()
async def bxh(ctx):
    users = await db.users.find().sort("mp", -1).to_list(100) 
    if not users: return await ctx.send("Chưa có ai trên bảng xếp hạng.")

    rankings = {"a_than": [], "god": [], "pro": [], "thuong": []}
    
    for u in users:
        member = ctx.guild.get_member(u["_id"])
        name = member.display_name if member else f"ID: {u['_id']}"
        mp = u.get("mp", 0)
        
        title_decor = ""
        if u.get("title_visible", True) and u.get("active_title"):
            title_decor = f" | ✦ {u['active_title'].title()} ✦"
            
        if mp >= 100000:
            rankings["a_than"].append(f"\u001b[1;31m{name}\u001b[0m - {mp} MP{title_decor}")
        elif mp >= 50000:
            rankings["god"].append(f"\u001b[1;35m{name}\u001b[0m - {mp} MP{title_decor}")
        elif mp >= 10000:
            rankings["pro"].append(f"\u001b[1;36m{name}\u001b[0m - {mp} MP{title_decor}")
        else:
            rankings["thuong"].append(f"\u001b[1;32m{name}\u001b[0m - {mp} MP{title_decor}")

    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG MP SERVER 🏆", color=discord.Color.gold())
    
    if rankings["a_than"]: 
        embed.add_field(name="👑 Á Thần (100k+ MP)", value="```ansi\n" + "\n".join(rankings["a_than"]) + "\n```", inline=False)
    if rankings["god"]: 
        embed.add_field(name="⚡ God (50k - 99k MP)", value="```ansi\n" + "\n".join(rankings["god"]) + "\n```", inline=False)
    if rankings["pro"]: 
        embed.add_field(name="⚔️ Pro (10k - 49k MP)", value="```ansi\n" + "\n".join(rankings["pro"]) + "\n```", inline=False)
    if rankings["thuong"]: 
        embed.add_field(name="🌱 Thường (< 10k MP)", value="```ansi\n" + "\n".join(rankings["thuong"]) + "\n```", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="setmp")
@commands.has_permissions(administrator=True)
async def set_mp(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None: return await ctx.send("❌ `!setmp @user [số]`")
    await db.users.update_one({"_id": member.id}, {"$set": {"mp": amount}}, upsert=True)
    await check_and_transfer_top1_mp(ctx.guild)
    await ctx.send(f"✅ Đã set **{amount}** MP cho {member.mention}.")

@bot.command(name="addmp")
@commands.has_permissions(administrator=True)
async def add_mp_cmd(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None: return await ctx.send("❌ `!addmp @user [số]`")
    await add_user_mp(member.id, amount, ctx.guild)
    new_mp = await get_user_mp(member.id)
    await ctx.send(f"✅ Đã {'cộng' if amount>0 else 'trừ'} **{abs(amount)}** MP. Hiện tại {member.mention} có: **{new_mp}** MP.")

if __name__ == "__main__":
    keep_alive() 
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Lỗi: Không tìm thấy DISCORD_TOKEN trong biến môi trường!")
        



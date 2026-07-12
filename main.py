import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
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

# Thêm định mức sự kiện
DIFFICULTY_MP = {
    "easy": 5, "normal": 10, "hard": 25, "harder": 50, "insane": 100,
    "easy demon": 250, "medium demon": 500, "hard demon": 1000,
    "insane demon": 5000, "extreme demon": 10000,
    "daily": 150, "event": 2500
}

TITLES_DATA = {
    "chiến binh try hard": 152548454364,
    "chiến binh đã tốt nghiệp": 152548544903,
    "pro": 152548997972,
    "vua try hard": 152549103370,
    "vua hardest": 152549140941,
    "vua cày điểm": 152549739299
}

ROLE_VUA_CAY_DIEM = 152549739299
ROLE_VUA_HARDEST = 152549140941
VN_TZ = timezone(timedelta(hours=7))

# ================= CẤU HÌNH GEMINI ================= #
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') 

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

# ================= CÁC HÀM TIỆN ÍCH & LOGIC DANH HIỆU ================= #
async def get_user_mp(user_id):
    user = await db.users.find_one({"_id": user_id})
    return user["mp"] if user else 0

async def add_user_mp(user_id, amount, guild=None):
    await db.users.update_one({"_id": user_id}, {"$inc": {"mp": amount}}, upsert=True)
    if guild:
        await check_and_transfer_top1_mp(guild)

async def check_and_transfer_top1_mp(guild):
    # Lấy top 1 hiện tại từ DB
    users = await db.users.find().sort("mp", -1).limit(1).to_list(1)
    if not users: return
    new_top1_id = users[0]["_id"]
    
    config = await db.settings.find_one({"_id": "top1_mp_owner"})
    old_top1_id = config["user_id"] if config else None

    if old_top1_id != new_top1_id:
        role = guild.get_role(ROLE_VUA_CAY_DIEM)
        if role:
            if old_top1_id:
                old_member = guild.get_member(old_top1_id)
                if old_member:
                    await old_member.remove_roles(role)
                    # Thu hồi danh hiệu trong DB
                    await db.users.update_one({"_id": old_top1_id}, {"$pull": {"titles": "vua cày điểm"}})
            
            new_member = guild.get_member(new_top1_id)
            if new_member:
                await new_member.add_roles(role)
                await db.users.update_one({"_id": new_top1_id}, {"$addToSet": {"titles": "vua cày điểm"}, "$set": {"active_title": "vua cày điểm"}}, upsert=True)
        
        await db.settings.update_one({"_id": "top1_mp_owner"}, {"$set": {"user_id": new_top1_id}}, upsert=True)

async def grant_vua_hardest(guild, new_owner_id):
    config = await db.settings.find_one({"_id": "vua_hardest_owner"})
    old_owner_id = config["user_id"] if config else None

    role = guild.get_role(ROLE_VUA_HARDEST)
    if role:
        if old_owner_id and old_owner_id != new_owner_id:
            old_member = guild.get_member(old_owner_id)
            if old_member:
                await old_member.remove_roles(role)
                await db.users.update_one({"_id": old_owner_id}, {"$pull": {"titles": "vua hardest"}})
        
        new_member = guild.get_member(new_owner_id)
        if new_member:
            await new_member.add_roles(role)
            await db.users.update_one({"_id": new_owner_id}, {"$addToSet": {"titles": "vua hardest"}, "$set": {"active_title": "vua hardest"}}, upsert=True)
    
    await db.settings.update_one({"_id": "vua_hardest_owner"}, {"$set": {"user_id": new_owner_id}}, upsert=True)

async def check_event_daily_validity():
    settings = await db.settings.find_one({"_id": "gd_events"})
    if not settings: return None, None
    
    now = datetime.now(VN_TZ)
    daily = settings.get("daily")
    event = settings.get("event")
    
    daily_valid = daily if (daily and daily.get("expires") and now < daily["expires"].replace(tzinfo=VN_TZ)) else None
    event_valid = event if (event and event.get("expires") and now < event["expires"].replace(tzinfo=VN_TZ)) else None
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
        except: pass
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

        self.reason = TextInput(label='Ghi chú cho người report', style=discord.TextStyle.paragraph, placeholder="Nhập ghi chú...")
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason_text = self.reason.value
        admin = interaction.user
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

        # Cập nhật tin nhắn report
        embed = self.message_to_edit.embeds[0]
        embed.title = "✅ BÁO CÁO ĐÃ ĐƯỢC XỬ LÝ"
        embed.color = discord.Color.green()
        embed.add_field(name="Hành động của Admin:", value=action_msg, inline=False)
        embed.add_field(name="Ghi chú:", value=reason_text, inline=False)
        await self.message_to_edit.edit(embed=embed, view=None)

        # Gửi DM cho người report
        reporter = await bot.fetch_user(self.reporter_id)
        if reporter:
            dm_embed = discord.Embed(title="✅ KẾT QUẢ BÁO CÁO", color=discord.Color.green(), description=f"Báo cáo của bạn về {self.reported_member.mention} đã được xử lý.")
            dm_embed.add_field(name="Xử lý:", value=action_msg, inline=False)
            dm_embed.add_field(name="Ghi chú từ Admin:", value=reason_text, inline=False)
            try:
                await reporter.send(embed=dm_embed)
            except: pass

        await interaction.response.send_message("Đã thi hành án phạt thành công!", ephemeral=True)

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

# ================= GIAO DIỆN NÚT BẤM DUYỆT BÀI ================= #
class RejectModal(Modal, title='Lí do từ chối'):
    reason = TextInput(label='Nhập lí do', style=discord.TextStyle.paragraph)
    def __init__(self, user_id, message_to_edit):
        super().__init__()
        self.user_id = user_id
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        if user:
            try: await user.send(f"❌ Yêu cầu duyệt của bạn bị từ chối.\n**Lí do:** {self.reason.value}")
            except: pass 
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
        member = guild.get_member(self.user_id)
        msg_user, msg_admin = "", ""

        if self.req_type == "mp":
            await add_user_mp(self.user_id, self.reward_value, guild)
            msg_user = f"🎉 Level **{self.item_name.title()}** đã được duyệt! +{self.reward_value} MP!"
            msg_admin = f"✅ Đã duyệt +{self.reward_value} MP cho <@{self.user_id}>."
            
        elif self.req_type == "role":
            role_name = self.item_name.lower()
            if role_name == "vua hardest":
                await grant_vua_hardest(guild, self.user_id)
                msg_user = "🏆 Chúc mừng! Bạn đã trở thành VUA HARDEST mới của server!"
                msg_admin = f"✅ Đã cấp danh hiệu **Vua Hardest** cho <@{self.user_id}>."
            else:
                role = guild.get_role(self.reward_value)
                if role and member:
                    await member.add_roles(role)
                    await db.users.update_one({"_id": self.user_id}, {"$addToSet": {"titles": role_name}, "$set": {"active_title": role_name}}, upsert=True)
                    msg_user = f"🏆 Đỉnh quá! Bạn nhận được danh hiệu **{role.name}**!"
                    msg_admin = f"✅ Đã duyệt danh hiệu **{role.name}** cho <@{self.user_id}>."

        if user and msg_user:
            try: await user.send(msg_user)
            except: pass
        await interaction.message.edit(content=f"{msg_admin}\nBởi: {interaction.user.mention}", view=None, embeds=[])
        await interaction.response.send_message("Duyệt thành công!", ephemeral=True)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RejectModal(self.user_id, interaction.message))
    # ================= CÁC LỆNH BOT (COMMANDS) ================= #
@bot.command()
async def menu(ctx):
    is_admin = ctx.author.guild_permissions.administrator
    embed = discord.Embed(title="📚 BẢNG HƯỚNG DẪN SỬ DỤNG LỆNH", color=discord.Color.blurple())
    
    # Lệnh cho thành viên
    embed.add_field(name="1️⃣ `!duyet [độ khó/event/daily/danh hiệu]`", value="Gửi bài để duyệt lấy MP hoặc Danh hiệu (Nhớ đính kèm ảnh/video).", inline=False)
    embed.add_field(name="2️⃣ `!daily` / `!event`", value="Xem ID level sự kiện hoặc hằng ngày đang diễn ra.", inline=False)
    embed.add_field(name="3️⃣ `!dexuatlevel`", value="`!dexuatlevel [độ khó] [dễ/khó] [né/cần] [kỹ năng]` - AI gợi ý level.", inline=False)
    embed.add_field(name="4️⃣ `!bxh`", value="Xem bảng xếp hạng điểm MP toàn server.", inline=False)
    embed.add_field(name="5️⃣ `!report @user [lý do]`", value="Tố cáo người chơi vi phạm (Kèm bằng chứng).", inline=False)
    embed.add_field(name="6️⃣ Quản lý Danh Hiệu", value="`!listdanhhieu`: Xem danh hiệu sở hữu\n`!setdanhhieu [tên]`: Trang bị danh hiệu\n`!editdanhhieu [an/hien]`: Ẩn/Hiện trên BXH.", inline=False)
    
    # Lệnh riêng cho admin
    if is_admin:
        embed.add_field(name="🛠️ Lệnh Dành Riêng Cho Admin", value="`!setmp @user [số]` - Cài đặt điểm\n`!addmp @user [số]` - Cộng/Trừ điểm\n`!thongbao [event/daily] [ID]` - Gửi báo sự kiện mới", inline=False)
        
    embed.set_footer(text="Hệ thống tự động cập nhật Vua Cày Điểm và Vua Hardest.")
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def thongbao(ctx, type: str, level_id: str):
    type = type.lower()
    if type not in ["event", "daily"]:
        return await ctx.send("❌ Loại thông báo phải là `event` hoặc `daily`.")
    
    now = datetime.now(VN_TZ)
    expires = now + timedelta(days=14) if type == "event" else now.replace(hour=23, minute=59, second=59)
    
    await db.settings.update_one(
        {"_id": "gd_events"},
        {"$set": {f"{type}": {"id": level_id, "expires": expires}}},
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
    
    embed = discord.Embed(title=f"🎯 MỤC TIÊU {cmd_used.upper()} HIỆN TẠI", color=discord.Color.green())
    embed.add_field(name="ID Level", value=f"**{data['id']}**", inline=False)
    embed.add_field(name="Hết hạn", value=data['expires'].strftime("%d/%m/%Y %H:%M:%S (VN)"), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def duyet(ctx, *, yeu_cau: str = None):
    if not yeu_cau:
        return await ctx.send("❌ Nhập độ khó, event/daily hoặc tên danh hiệu! VD: `!duyet daily` hoặc `!duyet hard demon`")
    
    if not ctx.message.attachments:
        return await ctx.send("📸 Bạn phải gửi kèm theo video/ảnh chứng minh!")

    yeu_cau = yeu_cau.lower()
    is_mp = yeu_cau in DIFFICULTY_MP
    is_role = yeu_cau in TITLES_DATA
    
    if not is_mp and not is_role:
        return await ctx.send("❌ Yêu cầu không hợp lệ.")

    if yeu_cau in ["daily", "event"]:
        daily_valid, event_valid = await check_event_daily_validity()
        if yeu_cau == "daily" and not daily_valid: return await ctx.send("❌ Daily hiện tại đã hết hạn.")
        if yeu_cau == "event" and not event_valid: return await ctx.send("❌ Event hiện tại đã hết hạn.")

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    attachment_url = ctx.message.attachments[0].url

    if is_role:
        embed = discord.Embed(title="⭐ YÊU CẦU CẤP DANH HIỆU", color=discord.Color.gold())
        req_type, reward_name, reward_value, reward_id = "role", "Danh hiệu", yeu_cau.title(), TITLES_DATA[yeu_cau]
    else:
        embed = discord.Embed(title="💎 YÊU CẦU CỘNG MP", color=discord.Color.blue())
        req_type, reward_name, reward_value, reward_id = "mp", "MP", f"{DIFFICULTY_MP[yeu_cau]}", DIFFICULTY_MP[yeu_cau]

    embed.add_field(name="Người gửi", value=ctx.author.mention)
    embed.add_field(name="Yêu cầu", value=reward_value)
    embed.set_image(url=attachment_url)

    view = ReviewView(ctx.author.id, req_type, yeu_cau, reward_id)
    await admin_channel.send(embed=embed, view=view)
    await ctx.send("✅ Đã gửi bài duyệt cho Admin!")

# Lệnh quản lý danh hiệu
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
    except: pass 
    if not member or not reason: return await ctx.send("❌ Dùng: `!report @user lý do`", delete_after=5)

    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    embed = discord.Embed(title="🚨 BÁO CÁO VI PHẠM", color=discord.Color.red())
    embed.add_field(name="Bị cáo", value=member.mention)
    embed.add_field(name="Lý do", value=reason)
    embed.add_field(name="Người gửi", value=ctx.author.mention)
    
    files = [await a.to_file() for a in ctx.message.attachments] if ctx.message.attachments else []
    view = ReportReviewView(ctx.author.id, member)
    await report_channel.send(embed=embed, files=files, view=view)
    await ctx.send(f"✅ Đã báo cáo {member.display_name}!", delete_after=5)

@bot.command()
async def bxh(ctx):
    users = await db.users.find().sort("mp", -1).to_list(100) 
    if not users: return await ctx.send("Chưa có ai trên bảng xếp hạng.")

    rankings = {"a_than": [], "god": [], "pro": [], "thuong": []}
    
    for u in users:
        member = ctx.guild.get_member(u["_id"])
        name = member.display_name if member else f"ID: {u['_id']}"
        mp = u.get("mp", 0)
        
        # Trang trí danh hiệu cực đã
        title_decor = ""
        if u.get("title_visible", True) and u.get("active_title"):
            title_decor = f" | ✧༺ {u['active_title'].title()} ༻✧"
            
        text = f"**{name}** - {mp} MP {title_decor}"
        
        if mp >= 100000: rankings["a_than"].append(text)
        elif mp >= 50000: rankings["god"].append(text)
        elif mp >= 10000: rankings["pro"].append(text)
        else: rankings["thuong"].append(text)

    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG MP SERVER 🏆", color=discord.Color.gold())
    if rankings["a_than"]: embed.add_field(name="👑 Á Thần (100k+ MP)", value="\n".join(rankings["a_than"]), inline=False)
    if rankings["god"]: embed.add_field(name="⚡ God (50k - 99k MP)", value="\n".join(rankings["god"]), inline=False)
    if rankings["pro"]: embed.add_field(name="⚔️ Pro (10k - 49k MP)", value="\n".join(rankings["pro"]), inline=False)
    if rankings["thuong"]: embed.add_field(name="🌱 Thường (< 10k MP)", value="\n".join(rankings["thuong"]), inline=False)

    await ctx.send(embed=embed)

# Các lệnh admin giữ nguyên nhưng được gọi chung hàm update logic mới
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
    if os.getenv("DISCORD_TOKEN"): bot.run(os.getenv("DISCORD_TOKEN"))

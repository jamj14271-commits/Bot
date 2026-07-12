import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import motor.motor_asyncio
import certifi
import random
import json  # Thêm thư viện đọc file JSON
from keep_alive import keep_alive

# ================= CẤU HÌNH CƠ BẢN ================= #
ADMIN_CHANNEL_ID = 1525386498739015800  
REPORT_CHANNEL_ID = 1525662263502176306

DIFFICULTY_MP = {
    "easy": 5, "normal": 10, "hard": 25, "harder": 50, "insane": 100,
    "easy demon": 250, "medium demon": 500, "hard demon": 1000,
    "insane demon": 5000, "extreme demon": 10000 
}

TITLES_DATA = {
    "chiến binh try hard": 152548454364,
    "chiến binh đã tốt nghiệp": 152548544903,
    "pro": 152548997972,
    "vua try hard": 152549103370,
    "vua hardest": 152549140941,
    "vua cày điểm": 152549739299
}

# ================= KHỞI TẠO BOT ==================== #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

db_client = None
db = None

@bot.event
async def on_ready():
    global db_client, db
    print(f'Đang kết nối database...')
    mongo_uri = os.getenv('MONGO_URI') 
    db_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri, tlsCAFile=certifi.where())
    db = db_client['gd_database']
    print(f'Bot {bot.user} đã sẵn sàng hoạt động!')

# ================= ANTI-SPAM ================= #
@bot.event
async def on_message(message):
    if message.author == bot.user: return
    bad_words = ["discord.gg/", "free nitro", "hack gem", "giftcode", "hack blox"]
    content_lower = message.content.lower()
    for word in bad_words:
        if word in content_lower:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention}, không được gửi link lạ vi phạm!", delete_after=5)
                return 
            except discord.Forbidden: pass
    await bot.process_commands(message)

async def get_user_mp(user_id):
    user = await db.users.find_one({"_id": user_id})
    return user["mp"] if user else 0

async def add_user_mp(user_id, amount):
    await db.users.update_one({"_id": user_id}, {"$inc": {"mp": amount}}, upsert=True)

# ================= UI CLASSES ================= #
class ReportActionModal(Modal):
    def __init__(self, action_type, reporter_id, reported_mention, message_to_edit):
        title = 'Lý do duyệt và xử lý' if action_type == 'approve' else 'Lý do từ chối'
        super().__init__(title=title)
        self.action_type, self.reporter_id, self.reported_mention, self.message_to_edit = action_type, reporter_id, reported_mention, message_to_edit
        self.reason = TextInput(label='Nhập lý do / Ghi chú:', style=discord.TextStyle.paragraph)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reporter = await bot.fetch_user(self.reporter_id)
        admin_mention, reason_text = interaction.user.mention, self.reason.value
        embed = self.message_to_edit.embeds[0]
        dm_embed = discord.Embed(timestamp=interaction.message.created_at)

        if self.action_type == 'approve':
            embed.title, embed.color = "✅ BÁO CÁO ĐÃ XỬ LÝ", discord.Color.green()
            dm_embed.title, dm_embed.color = "✅ BÁO CÁO CỦA BẠN ĐÃ ĐƯỢC XỬ LÝ", discord.Color.green()
            dm_embed.description = f"Admin đã xử lý vi phạm của {self.reported_mention}."
        else:
            embed.title, embed.color = "❌ BÁO CÁO BỊ TỪ CHỐI", discord.Color.dark_gray()
            dm_embed.title, dm_embed.color = "❌ BÁO CÁO BỊ TỪ CHỐI", discord.Color.red()
            dm_embed.description = f"Báo cáo của bạn về {self.reported_mention} bị từ chối."

        dm_embed.add_field(name="Ghi chú từ Admin:", value=reason_text, inline=False)
        embed.add_field(name="Người xử lý:", value=admin_mention, inline=False)
        embed.add_field(name="Ghi chú của Admin:", value=reason_text, inline=False)
        await self.message_to_edit.edit(embed=embed, view=None)
        await interaction.response.send_message("Đã ghi nhận!", ephemeral=True)
        if reporter:
            try: await reporter.send(embed=dm_embed)
            except: pass

class ReportReviewView(View):
    def __init__(self, reporter_id, reported_mention):
        super().__init__(timeout=None)
        self.reporter_id, self.reported_mention = reporter_id, reported_mention
    @discord.ui.button(label="Duyệt và xử lý", style=discord.ButtonStyle.green, custom_id="btn_rep_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ReportActionModal('approve', self.reporter_id, self.reported_mention, interaction.message))
    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_rep_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ReportActionModal('reject', self.reporter_id, self.reported_mention, interaction.message))

class RejectModal(Modal, title='Lí do từ chối'):
    reason = TextInput(label='Nhập lí do', style=discord.TextStyle.paragraph)
    def __init__(self, user_id, message_to_edit):
        super().__init__()
        self.user_id, self.message_to_edit = user_id, message_to_edit
    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        if user:
            try: await user.send(f"❌ Yêu cầu duyệt của bạn bị từ chối.\n**Lí do:** {self.reason.value}")
            except: pass 
        await self.message_to_edit.edit(content=f"❌ **Đã từ chối** bài của <@{self.user_id}>\nNgười duyệt: {interaction.user.mention}\nLý do: {self.reason.value}", view=None, embeds=[])
        await interaction.response.send_message("Đã từ chối.", ephemeral=True)

class ReviewView(View):
    def __init__(self, user_id, req_type, item_name, reward_value):
        super().__init__(timeout=None)
        self.user_id, self.req_type, self.item_name, self.reward_value = user_id, req_type, item_name, reward_value

    @discord.ui.button(label="Duyệt", style=discord.ButtonStyle.green, custom_id="btn_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        user, guild = await bot.fetch_user(self.user_id), interaction.guild
        member = guild.get_member(self.user_id)
        msg_user, msg_admin = "", ""

        if self.req_type == "mp":
            await add_user_mp(self.user_id, self.reward_value)
            msg_user = f"🎉 Level **{self.item_name.title()}** được duyệt. Cộng **{self.reward_value} Mp**!"
            msg_admin = f"✅ **Đã duyệt** cộng {self.reward_value} Mp cho <@{self.user_id}>."
        elif self.req_type == "role":
            role = guild.get_role(self.reward_value)
            if role and member:
                await member.add_roles(role)
                msg_user = f"🏆 Bạn đã nhận danh hiệu **{role.name}**!"
                msg_admin = f"✅ **Đã duyệt** cấp danh hiệu **{role.name}** cho <@{self.user_id}>."
            else: msg_admin = "⚠️ Lỗi danh hiệu/người dùng."
        
        if user and msg_user:
            try: await user.send(msg_user)
            except: pass
        await interaction.message.edit(content=f"{msg_admin}\nNgười duyệt: {interaction.user.mention}", view=None, embeds=[])
        await interaction.response.send_message("Thành công!", ephemeral=True)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RejectModal(self.user_id, interaction.message))

# ================= COMMANDS ================= #
@bot.command(name="menu", aliases=["helpme", "hdsd"])
async def bot_menu(ctx):
    embed = discord.Embed(title="📜 DANH SÁCH LỆNH CỦA BOT", color=discord.Color.blue())
    embed.add_field(name="🎮 Lệnh Cho Người Chơi", value=(
        "**`!duyet <độ khó hoặc tên danh hiệu>`**\n"
        "**`!dexuatlevel <độ khó> <tầm trung/dễ/khó> <điểm yếu>`** (Hoặc `!dx`)\n"
        "**`!bxh`** | **`!report @người_chơi <lý do>`**"
    ), inline=False)
    if ctx.author.guild_permissions.administrator:
        embed.add_field(name="🛠️ Lệnh Admin", value="`!setmp @user <số>`\n`!addmp @user <số>`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="dexuatlevel", aliases=["dx"])
async def recommend_level(ctx, *, query: str = None):
    if not query:
        return await ctx.send("❌ Ví dụ: `!dx hard demon dễ` hoặc `!dx extreme demon tầm trung né wave`")
    
    query = query.lower()
    
    # ĐỌC DỮ LIỆU TỰ ĐỘNG TỪ FILE LEVELS.JSON
    try:
        with open("levels.json", "r", encoding="utf-8") as f:
            level_db = json.load(f)
    except FileNotFoundError:
        return await ctx.send("❌ Lỗi: Hệ thống chưa tìm thấy file dữ liệu `levels.json` trên host!")
    except Exception as e:
        return await ctx.send(f"❌ Lỗi cấu trúc file dữ liệu: {e}")

    # 1. Lọc độ khó
    target_diff = None
    for diff in ["easy demon", "medium demon", "hard demon", "insane demon", "extreme demon"]:
        if diff in query:
            target_diff = diff
            break
    if not target_diff: return await ctx.send("❌ Vui lòng nhập đúng độ khó Demon cần tìm.")

    # 2. Lọc sub-difficulty
    target_sub = None
    if "tầm trung" in query or "trung bình" in query or "mid" in query: target_sub = "tầm trung"
    elif "khó" in query or "hard" in query: target_sub = "khó"
    elif "dễ" in query or "easy" in query: target_sub = "dễ"

    # 3. Lọc kỹ năng né
    bad_keywords = ["tệ", "yếu", "kém", "ngu", "không giỏi", "sợ", "ghét", "né"]
    all_skills = ["wave", "ship", "ufo", "ball", "spider", "memory", "timing", "nerve", "bossfight", "fast", "straight fly"]
    skills_to_avoid = [s for s in all_skills if s in query and any(b in query for b in bad_keywords)]

    # 4. Tìm kiếm trong Database JSON
    matched_levels = []
    for level in level_db:
        if level["diff"] != target_diff: continue
        if target_sub and level["sub"] != target_sub: continue
        if any(skill in level["skills"] for skill in skills_to_avoid): continue
        matched_levels.append(level)

    if not matched_levels:
        return await ctx.send("🤔 Không tìm thấy level nào trong file dữ liệu khớp 100% với yêu cầu này.")

    chosen_levels = random.sample(matched_levels, min(2, len(matched_levels)))
    embed = discord.Embed(title="🎯 ĐỀ XUẤT LEVEL CHO BẠN", color=discord.Color.green())
    desc = f"Phân loại: **{target_diff.title()}**"
    if target_sub: desc += f" - Cỡ **{target_sub.upper()}**"
    if skills_to_avoid: desc += f"\n(Né kỹ năng: {', '.join(skills_to_avoid)})"
    embed.description = desc
    
    for lvl in chosen_levels:
        embed.add_field(name=f"🎮 {lvl['name']}", value=f"Độ phụ: **{lvl['sub'].title()}**\nKỹ năng: {', '.join(lvl['skills']).title()}", inline=False)
    embed.set_footer(text="Chúc bạn phá đảo thành công! 😉")
    await ctx.send(embed=embed)

@bot.command(name="setmp")
@commands.has_permissions(administrator=True)
async def set_mp(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None: return ctx.send("❌ Cú pháp sai.")
    await db.users.update_one({"_id": member.id}, {"$set": {"mp": max(0, amount)}}, upsert=True)
    await ctx.send(f"✅ Chỉnh sửa thành công cho {member.mention}.")

@bot.command(name="addmp")
@commands.has_permissions(administrator=True)
async def add_mp_cmd(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None: return
    await add_user_mp(member.id, amount)
    await ctx.send(f"✅ Đã xử lý điểm cho {member.mention}.")

@bot.command(name="report")
async def report_user(ctx, member: discord.Member = None, *, reason: str = None):
    try: await ctx.message.delete()
    except: pass 
    if not member or not reason: return
    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="🚨 BÁO CÁO VI PHẠM 🚨", color=discord.Color.red(), timestamp=ctx.message.created_at)
        embed.add_field(name="Bị tố cáo:", value=member.mention).add_field(name="Lý do:", value=reason)
        files = [await a.to_file() for a in ctx.message.attachments]
        await channel.send(embed=embed, files=files, view=ReportReviewView(ctx.author.id, member.mention))

@bot.command()
async def duyet(ctx, *, yeu_cau: str = None):
    if not yeu_cau: return
    yeu_cau = yeu_cau.lower()
    if yeu_cau not in DIFFICULTY_MP and yeu_cau not in TITLES_DATA: return
    if not ctx.message.attachments: return
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if admin_channel:
        embed = discord.Embed(title="💎 YÊU CẦU DUYỆT BÀI", color=discord.Color.blue()).add_field(name="Gửi bởi", value=ctx.author.mention).add_field(name="Mục", value=yeu_cau.title())
        embed.set_image(url=ctx.message.attachments[0].url)
        await admin_channel.send(embed=embed, view=ReviewView(ctx.author.id, "role" if yeu_cau in TITLES_DATA else "mp", yeu_cau, TITLES_DATA[yeu_cau] if yeu_cau in TITLES_DATA else DIFFICULTY_MP[yeu_cau]))

@bot.command()
async def bxh(ctx):
    users = await db.users.find().sort("mp", -1).to_list(length=100) 
    if not users: return
    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG MP 🏆", color=discord.Color.gold())
    lines = [f"**{ctx.guild.get_member(u['_id']).display_name if ctx.guild.get_member(u['_id']) else u['_id']}** - {u['mp']} Mp" for u in users]
    embed.description = "\n".join(lines[:15])
    await ctx.send(embed=embed)

keep_alive()  
bot.run(os.getenv('DISCORD_TOKEN'))

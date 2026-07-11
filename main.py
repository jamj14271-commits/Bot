import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import motor.motor_asyncio
import certifi

# ================= CẤU HÌNH CƠ BẢN ================= #
# ID kênh duyệt bài 
ADMIN_CHANNEL_ID = 1525386498739015800  

# Bảng Mp theo độ khó
DIFFICULTY_MP = {
    "easy": 5, "normal": 10, "hard": 25, "harder": 50, "insane": 100,
    "easy demon": 250, "medium demon": 500, "hard demon": 1000,
    "insane demon": 5000, "extreme": 10000
}

# Dữ liệu ID Danh hiệu
TITLES_DATA = {
    "chiến binh try hard": 152548454364,
    "chiến binh đã tốt nghiệp": 152548544903,
    "pro": 152548997972,
    "vua try hard": 152549103370,
    "vua hardest": 152549140941,
    "vua cày điểm": 152549739299
}
# =================================================== #

# ================= KHỞI TẠO BOT ==================== #
# (Dòng này đã được đưa lên trên để sửa lỗi NameError)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ================= DATABASE ======================== #
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

# Hàm hỗ trợ Database
async def get_user_mp(user_id):
    user = await db.users.find_one({"_id": user_id})
    return user["mp"] if user else 0

async def add_user_mp(user_id, amount):
    await db.users.update_one({"_id": user_id}, {"$inc": {"mp": amount}}, upsert=True)

# ================= GIAO DIỆN NÚT BẤM ================= #
class RejectModal(Modal, title='Lí do từ chối'):
    reason = TextInput(label='Nhập lí do', style=discord.TextStyle.paragraph, placeholder="Ví dụ: Video bị lag, chưa đủ điều kiện beat hardest...")

    def __init__(self, user_id, message_to_edit):
        super().__init__()
        self.user_id = user_id
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        if user:
            try:
                await user.send(f"❌ Yêu cầu duyệt của bạn đã bị từ chối.\n**Lí do:** {self.reason.value}")
            except:
                pass 
        
        await self.message_to_edit.edit(content=f"❌ **Đã từ chối** bài của <@{self.user_id}>\nNgười duyệt: {interaction.user.mention}\nLý do: {self.reason.value}", view=None, embeds=[])
        await interaction.response.send_message("Đã gửi thông báo từ chối.", ephemeral=True)

class ReviewView(View):
    def __init__(self, user_id, req_type, item_name, reward_value):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.req_type = req_type          # "mp" hoặc "role"
        self.item_name = item_name        # Tên độ khó hoặc tên danh hiệu
        self.reward_value = reward_value  # Số MP hoặc ID Role

    @discord.ui.button(label="Duyệt", style=discord.ButtonStyle.green, custom_id="btn_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        user = await bot.fetch_user(self.user_id)
        guild = interaction.guild
        member = guild.get_member(self.user_id)

        msg_user = ""
        msg_admin = ""

        # NẾU LÀ DUYỆT ĐỂ LẤY MP
        if self.req_type == "mp":
            await add_user_mp(self.user_id, self.reward_value)
            msg_user = f"🎉 Chúc mừng! Level **{self.item_name.title()}** của bạn đã được duyệt. Bạn được cộng **{self.reward_value} Mp**!"
            msg_admin = f"✅ **Đã duyệt** cộng {self.reward_value} Mp cho <@{self.user_id}>."
        
        # NẾU LÀ DUYỆT ĐỂ CẤP DANH HIỆU
        elif self.req_type == "role":
            role = guild.get_role(self.reward_value)
            if role and member:
                await member.add_roles(role)
                msg_user = f"🏆 Đỉnh quá! Video của bạn đủ điều kiện và bạn đã chính thức nhận danh hiệu **{role.name}**!"
                msg_admin = f"✅ **Đã duyệt** cấp danh hiệu **{role.name}** cho <@{self.user_id}>."
            else:
                msg_admin = "⚠️ **Lỗi:** Không tìm thấy Danh hiệu hoặc người dùng trong server để cấp."
        
        # Gửi tin nhắn cho người dùng
        if user and msg_user:
            try:
                await user.send(msg_user)
            except:
                pass
                
        # Cập nhật lại tin nhắn trong kênh Admin
        await interaction.message.edit(content=f"{msg_admin}\nNgười duyệt: {interaction.user.mention}", view=None, embeds=[])
        await interaction.response.send_message("Duyệt thành công!", ephemeral=True)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        modal = RejectModal(self.user_id, interaction.message)
        await interaction.response.send_modal(modal)

# ================= CÁC LỆNH BOT ================= #

@bot.command()
async def duyet(ctx, *, yeu_cau: str = None):
    if not yeu_cau:
        return await ctx.send("Vui lòng nhập: `!duyet [độ khó]` (lấy MP) hoặc `!duyet [danh hiệu]` (nhận danh hiệu)")
    
    yeu_cau = yeu_cau.lower()
    is_mp = yeu_cau in DIFFICULTY_MP
    is_role = yeu_cau in TITLES_DATA

    if not is_mp and not is_role:
        return await ctx.send("❌ Yêu cầu không hợp lệ. Vui lòng kiểm tra lại tên độ khó hoặc danh hiệu.")
    
    if not ctx.message.attachments:
        return await ctx.send("📸 Bạn phải gửi kèm video/ảnh minh chứng!")

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if not admin_channel:
        return await ctx.send("Lỗi: Không tìm thấy kênh Admin.")
        
    attachment_url = ctx.message.attachments[0].url

    # TỰ ĐỘNG PHÂN LOẠI MÀU SẮC ĐỂ ADMIN DỄ PHÂN BIỆT
    if is_role:
        # Danh hiệu: Màu Vàng Gold
        embed = discord.Embed(title="⭐ YÊU CẦU CẤP DANH HIỆU", color=discord.Color.gold())
        reward_name = "Danh hiệu"
        reward_value = yeu_cau.title()
        req_type = "role"
        reward_id = TITLES_DATA[yeu_cau]
    else:
        # MP: Màu Xanh Dương
        embed = discord.Embed(title="💎 YÊU CẦU CỘNG MP", color=discord.Color.blue())
        reward_name = "Số MP"
        reward_value = f"{DIFFICULTY_MP[yeu_cau]} Mp"
        req_type = "mp"
        reward_id = DIFFICULTY_MP[yeu_cau]

    embed.add_field(name="Người gửi", value=ctx.author.mention, inline=True)
    embed.add_field(name="Yêu cầu", value=yeu_cau.title(), inline=True)
    embed.add_field(name="Loại thưởng", value=reward_name, inline=True)
    embed.add_field(name="Phần thưởng", value=reward_value, inline=False)
    embed.set_image(url=attachment_url)

    view = ReviewView(ctx.author.id, req_type, yeu_cau, reward_id)
    await admin_channel.send(embed=embed, view=view)
    await ctx.send("✅ Yêu cầu đã được gửi đến Admin. Chờ duyệt nhé!")

@bot.command()
async def bxh(ctx):
    users = await db.users.find().sort("mp", -1).to_list(length=100) 
    if not users:
        return await ctx.send("Hiện tại chưa có ai trên bảng xếp hạng.")

    thuong, pro, god, a_than = [], [], [], []
    
    for u in users:
        user_obj = ctx.guild.get_member(u["_id"])
        name = user_obj.display_name if user_obj else f"ID: {u['_id']}"
        mp = u["mp"]
        text = f"**{name}** - {mp} Mp"
        
        if mp >= 100000: a_than.append(text)
        elif mp >= 50000: god.append(text)
        elif mp >= 10000: pro.append(text)
        else: thuong.append(text)

    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG MP SERVER 🏆", color=discord.Color.gold())
    
    if a_than:
        embed.add_field(name="👑 Á Thần (100,000+ Mp)", value="\n".join(a_than), inline=False)
    if god:
        embed.add_field(name="⚡ God (50,000 - 99,999 Mp)", value="\n".join(god), inline=False)
    if pro:
        embed.add_field(name="🔥 Pro (10,000 - 49,999 Mp)", value="\n".join(pro), inline=False)
    if thuong:
        embed.add_field(name="🌱 Thường (0 - 9,999 Mp)", value="\n".join(thuong), inline=False)

    await ctx.send(embed=embed)

bot.run(os.getenv('DISCORD_TOKEN'))
    

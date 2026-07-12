import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import json
import motor.motor_asyncio
import certifi
import google.generativeai as genai
from keep_alive import keep_alive

# ================= CẤU HÌNH CƠ BẢN ================= #
ADMIN_CHANNEL_ID = 1525386498739015800  
REPORT_CHANNEL_ID = 1525662263502176306
WELCOME_CHANNEL_ID = 1525492114564317204  # Thay bằng ID kênh chào mừng của server bạn

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

# Cấu hình Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
# =================================================== #

# ================= KHỞI TẠO BOT ==================== #
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

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

# ================= TỰ ĐỘNG HƯỚNG DẪN NEWBIE ================= #
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
        embed.add_field(name="💎 Nhận MP & Danh Hiệu", value="Dùng lệnh `!duyet [độ khó]` kèm video/ảnh để admin duyệt và cấp Mp / Danh hiệu.", inline=False)
        embed.add_field(name="🤖 Xin Đề Xuất Level", value="Bí ý tưởng? Hãy gõ `!dexuatlevel` để AI gợi ý level phù hợp với kỹ năng của bạn.", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Chúc bạn có những giây phút leo rank vui vẻ!")
        
        await channel.send(content=member.mention, embed=embed)

# ================= ANTI-SPAM ================= #
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    bad_words = ["discord.gg/", "free nitro", "hack gem", "giftcode", "hack blox"]
    content_lower = message.content.lower()
    
    for word in bad_words:
        if word in content_lower:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention}, bạn không được gửi link lạ hoặc từ ngữ vi phạm vào server!", delete_after=5)
                return 
            except discord.Forbidden:
                pass

    await bot.process_commands(message)

# ================= CÁC HÀM CƠ SỞ DỮ LIỆU ================= #
async def get_user_mp(user_id):
    user = await db.users.find_one({"_id": user_id})
    return user["mp"] if user else 0

async def add_user_mp(user_id, amount):
    await db.users.update_one({"_id": user_id}, {"$inc": {"mp": amount}}, upsert=True)

# ================= GIAO DIỆN NÚT BẤM REPORT ================= #
class ReportActionModal(Modal):
    def __init__(self, action_type, reporter_id, reported_mention, message_to_edit):
        title = 'Lý do duyệt và xử lý' if action_type == 'approve' else 'Lý do từ chối'
        super().__init__(title=title)
        
        self.action_type = action_type
        self.reporter_id = reporter_id
        self.reported_mention = reported_mention
        self.message_to_edit = message_to_edit

        self.reason = TextInput(
            label='Nhập lý do / Ghi chú:',
            style=discord.TextStyle.paragraph,
            placeholder="Ví dụ: Đã ban 7 ngày do dùng hack..." if action_type == 'approve' else "Bằng chứng chưa rõ ràng..."
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reporter = await bot.fetch_user(self.reporter_id)
        admin_mention = interaction.user.mention
        reason_text = self.reason.value

        embed = self.message_to_edit.embeds[0]
        dm_embed = discord.Embed(timestamp=interaction.message.created_at)

        if self.action_type == 'approve':
            embed.title = "✅ BÁO CÁO ĐÃ XỬ LÝ"
            embed.color = discord.Color.green()
            dm_embed.title = "✅ BÁO CÁO CỦA BẠN ĐÃ ĐƯỢC XỬ LÝ"
            dm_embed.color = discord.Color.green()
            dm_embed.description = f"Cảm ơn bạn đã báo cáo. Admin đã xử lý vi phạm của {self.reported_mention}."
            dm_embed.add_field(name="Ghi chú từ Admin:", value=reason_text, inline=False)
        else:
            embed.title = "❌ BÁO CÁO BỊ TỪ CHỐI"
            embed.color = discord.Color.dark_gray()
            dm_embed.title = "❌ BÁO CÁO BỊ TỪ CHỐI"
            dm_embed.color = discord.Color.red()
            dm_embed.description = f"Rất tiếc, báo cáo của bạn về {self.reported_mention} không được duyệt."
            dm_embed.add_field(name="Lý do từ Admin:", value=reason_text, inline=False)

        embed.add_field(name="Người xử lý:", value=admin_mention, inline=False)
        embed.add_field(name="Ghi chú của Admin:", value=reason_text, inline=False)

        await self.message_to_edit.edit(embed=embed, view=None)
        await interaction.response.send_message("Đã ghi nhận kết quả xử lý!", ephemeral=True)
        
        if reporter:
            try:
                await reporter.send(embed=dm_embed)
            except discord.Forbidden:
                pass

class ReportReviewView(View):
    def __init__(self, reporter_id, reported_mention):
        super().__init__(timeout=None)
        self.reporter_id = reporter_id
        self.reported_mention = reported_mention

    @discord.ui.button(label="Duyệt và xử lý", style=discord.ButtonStyle.green, custom_id="btn_rep_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: Button):
        modal = ReportActionModal('approve', self.reporter_id, self.reported_mention, interaction.message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_rep_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        modal = ReportActionModal('reject', self.reporter_id, self.reported_mention, interaction.message)
        await interaction.response.send_modal(modal)

# ================= GIAO DIỆN NÚT BẤM DUYỆT BÀI ================= #
class RejectModal(Modal, title='Lí do từ chối'):
    reason = TextInput(label='Nhập lí do', style=discord.TextStyle.paragraph, placeholder="Ví dụ: Video bị lag, không thấy rõ gameplay...")

    def __init__(self, user_id, message_to_edit):
        super().__init__()
        self.user_id = user_id
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        user = await bot.fetch_user(self.user_id)
        if user:
            try:
                await user.send(f"❌ Yêu cầu duyệt của bạn đã bị từ chối.\n**Lí do:** {self.reason.value}")
            except discord.Forbidden:
                pass 
        
        await self.message_to_edit.edit(content=f"❌ **Đã từ chối** bài của <@{self.user_id}>\nNgười duyệt: {interaction.user.mention}\nLý do: {self.reason.value}", view=None, embeds=[])
        await interaction.response.send_message("Đã gửi thông báo từ chối.", ephemeral=True)

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

        msg_user = ""
        msg_admin = ""

        if self.req_type == "mp":
            await add_user_mp(self.user_id, self.reward_value)
            msg_user = f"🎉 Chúc mừng! Level **{self.item_name.title()}** của bạn đã được duyệt. Bạn được cộng **{self.reward_value} Mp**!"
            msg_admin = f"✅ **Đã duyệt** cộng {self.reward_value} Mp cho <@{self.user_id}>."
        elif self.req_type == "role":
            role = guild.get_role(self.reward_value)
            if role and member:
                await member.add_roles(role)
                msg_user = f"🏆 Đỉnh quá! Video của bạn đủ điều kiện và bạn đã chính thức nhận danh hiệu **{role.name}**!"
                msg_admin = f"✅ **Đã duyệt** cấp danh hiệu **{role.name}** cho <@{self.user_id}>."
            else:
                msg_admin = "⚠️ **Lỗi:** Không tìm thấy Danh hiệu hoặc người dùng."
        
        if user and msg_user:
            try:
                await user.send(msg_user)
            except discord.Forbidden:
                pass
                
        await interaction.message.edit(content=f"{msg_admin}\nNgười duyệt: {interaction.user.mention}", view=None, embeds=[])
        await interaction.response.send_message("Duyệt thành công!", ephemeral=True)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: Button):
        modal = RejectModal(self.user_id, interaction.message)
        await interaction.response.send_modal(modal)
        # ================= CÁC LỆNH BOT (COMMANDS) ================= #

@bot.command()
async def menu(ctx):
    embed = discord.Embed(title="📚 BẢNG HƯỚNG DẪN SỬ DỤNG LỆNH", color=discord.Color.blurple())
    
    embed.add_field(
        name="1️⃣ Gửi bài Duyệt (MP / Danh hiệu)",
        value="`!duyet [độ khó/tên danh hiệu]`\n*Ví dụ: `!duyet hard demon` hoặc `!duyet pro`*\n(Lưu ý: Phải đính kèm file ảnh/video chứng minh)",
        inline=False
    )
    embed.add_field(
        name="2️⃣ Xin AI Đề xuất Level",
        value="`!dexuatlevel [độ khó] [dễ/tầm trung/khó] [né/cần] [điểm yếu/mạnh]`\n*Ví dụ: `!dexuatlevel \"Hard Demon\" dễ cần \"luyện tập wave\"`*\n*(Mẹo: Dùng ngoặc kép `\" \"` nếu cụm từ có dấu cách)*",
        inline=False
    )
    embed.add_field(
        name="3️⃣ Tố cáo người chơi vi phạm",
        value="`!report @người_chơi [lý do]`\n*Ví dụ: `!report @abc dùng hack speed`*\n(Lưu ý: Nên kèm theo ảnh/video bằng chứng)",
        inline=False
    )
    embed.add_field(
        name="4️⃣ Bảng Xếp Hạng",
        value="`!bxh` - Xem top các tay to nhiều MP nhất server.",
        inline=False
    )
    embed.set_footer(text="Nếu gặp lỗi, vui lòng liên hệ Admin server!")
    
    await ctx.send(embed=embed)

@bot.command(name="setmp")
@commands.has_permissions(administrator=True)
async def set_mp(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None:
        return await ctx.send("❌ Sai cú pháp! Dùng: `!setmp @người_chơi số_điểm`")
    if amount < 0:
        return await ctx.send("❌ Số Mp không thể nhỏ hơn 0.")
    
    await db.users.update_one({"_id": member.id}, {"$set": {"mp": amount}}, upsert=True)
    await ctx.send(f"✅ Đã chỉnh sửa! {member.mention} hiện có **{amount}** Mp.")

@bot.command(name="addmp")
@commands.has_permissions(administrator=True)
async def add_mp_cmd(ctx, member: discord.Member = None, amount: int = None):
    if member is None or amount is None:
        return await ctx.send("❌ Sai cú pháp! Dùng: `!addmp @người_chơi số_điểm` (Có thể dùng số âm để trừ, ví dụ: -50)")
    
    await add_user_mp(member.id, amount)
    new_mp = await get_user_mp(member.id)
    action = "cộng thêm" if amount > 0 else "trừ đi"
    await ctx.send(f"✅ Đã {action} **{abs(amount)}** Mp cho {member.mention}. Tổng Mp hiện tại: **{new_mp}**.")

@set_mp.error
@add_mp_cmd.error
async def admin_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn không có quyền Administrator để dùng lệnh này!", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Sai cú pháp hoặc bạn chưa tag đúng người. Hãy kiểm tra lại!", delete_after=5)

@bot.command(name="report")
async def report_user(ctx, member: discord.Member = None, *, reason: str = None):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass 

    if not member or not reason:
        await ctx.send("❌ Sai cú pháp! Dùng: `!report @tên_người_chơi lý do kèm bằng chứng`", delete_after=5)
        return

    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    if report_channel:
        embed = discord.Embed(title="🚨 BÁO CÁO VI PHẠM MỚI 🚨", color=discord.Color.red(), timestamp=ctx.message.created_at)
        embed.add_field(name="Kẻ bị tố cáo:", value=member.mention, inline=False)
        embed.add_field(name="Lý do & Bằng chứng:", value=reason, inline=False)
        embed.add_field(name="Người tố cáo:", value=ctx.author.mention, inline=False)

        files = []
        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                files.append(await attachment.to_file())

        view = ReportReviewView(ctx.author.id, member.mention)
        await report_channel.send(embed=embed, files=files, view=view)
        
        await ctx.send(f"✅ Đã ghi nhận báo cáo đối với {member.display_name}. Hệ thống sẽ sớm xử lý!", delete_after=5)
    else:
        await ctx.send("❌ Lỗi hệ thống: Không tìm thấy kênh Report! (Vui lòng kiểm tra lại quyền của Bot)", delete_after=5)

@bot.command()
async def duyet(ctx, *, yeu_cau: str = None):
    if not yeu_cau:
        return await ctx.send("Vui lòng nhập độ khó hoặc tên danh hiệu!\nVí dụ: `!duyet hard demon` (lấy MP) hoặc `!duyet pro` (nhận danh hiệu)")
    
    yeu_cau = yeu_cau.lower()
    is_mp = yeu_cau in DIFFICULTY_MP
    is_role = yeu_cau in TITLES_DATA

    if not is_mp and not is_role:
        return await ctx.send("❌ Yêu cầu không hợp lệ. Vui lòng gõ đúng độ khó (vd: hard demon) hoặc tên danh hiệu (vd: chiến binh try hard).")
    
    if not ctx.message.attachments:
        return await ctx.send("📸 Bạn phải gửi kèm theo video gameplay hoặc ảnh chứng minh!")

    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if not admin_channel:
        return await ctx.send("Lỗi: Không tìm thấy kênh Admin.")

    attachment_url = ctx.message.attachments[0].url

    if is_role:
        embed = discord.Embed(title="⭐ YÊU CẦU CẤP DANH HIỆU", color=discord.Color.gold())
        reward_name = "Danh hiệu"
        reward_value = yeu_cau.title()
        req_type = "role"
        reward_id = TITLES_DATA[yeu_cau]
    else:
        embed = discord.Embed(title="💎 YÊU CẦU CỘNG MP", color=discord.Color.blue())
        reward_name = "Số MP"
        reward_value = f"{DIFFICULTY_MP[yeu_cau]} Mp"
        req_type = "mp"
        reward_id = DIFFICULTY_MP[yeu_cau]

    embed.add_field(name="Người gửi", value=ctx.author.mention, inline=True)
    embed.add_field(name="Yêu cầu", value=yeu_cau.title(), inline=True)
    embed.add_field(name="Loại thưởng", value=reward_name, inline=True)
    embed.add_field(name="Phần thưởng dự kiến", value=reward_value, inline=False)
    embed.set_image(url=attachment_url)
    embed.add_field(name="Link File/Video", value=attachment_url, inline=False)

    view = ReviewView(ctx.author.id, req_type, yeu_cau, reward_id)
    await admin_channel.send(embed=embed, view=view)
    await ctx.send("✅ Đã gửi yêu cầu và video cho Admin kiểm tra. Bạn chờ kết quả nhé!")

@bot.command()
async def dexuatlevel(ctx, do_kho: str = None, phan_loai: str = None, yeu_cau: str = None, *, ky_nang: str = None):
    if not all([do_kho, phan_loai, yeu_cau, ky_nang]):
        embed = discord.Embed(title="❌ Sai cú pháp lệnh Đề Xuất", color=discord.Color.red())
        embed.description = "**Cách dùng đúng:**\n`!dexuatlevel [độ khó] [dễ/tầm trung/khó] [né/cần] [kỹ năng]`\n\n**Ví dụ:**\n`!dexuatlevel \"Hard Demon\" dễ cần \"luyện tập wave và ship\"`\n`!dexuatlevel \"Easy Demon\" khó né \"các đoạn memory dài\"`"
        return await ctx.send(embed=embed)
    
    await ctx.send("⏳ *Đang phân tích dữ liệu và tìm level phù hợp cho bạn...*")
    
    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Tôi đang chơi Geometry Dash. Hãy đề xuất cho tôi DUY NHẤT 1 level thuộc độ khó {do_kho} ở mức {phan_loai} của độ khó đó. Tôi muốn {yeu_cau} {ky_nang}. Trả lời thật ngắn gọn: Tên level, người tạo, ID (nếu có thể), và giải thích 2-3 câu tại sao nó hợp với tôi."
            
            response = model.generate_content(prompt)
            
            embed = discord.Embed(title="🤖 Gemini Đề Xuất Cho Bạn", description=response.text, color=discord.Color.green())
            embed.set_footer(text="Được tạo tự động bởi AI (Google Gemini)")
            return await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Lỗi Gemini API: {e}")
            pass 

    try:
        with open("levels_fallback.json", "r", encoding="utf-8") as f:
            levels_db = json.load(f)
            
        suggested_level = None
        for lvl in levels_db:
            if lvl["do_kho"].lower() == do_kho.lower() and lvl["phan_loai"].lower() == phan_loai.lower():
                suggested_level = lvl
                break
                
        if suggested_level:
            embed = discord.Embed(title="📁 Đề Xuất Từ Thư Viện", color=discord.Color.orange())
            embed.add_field(name="Tên Level", value=f"**{suggested_level['name']}** by {suggested_level['creator']}", inline=False)
            embed.add_field(name="ID", value=suggested_level.get('id', 'Không rõ'), inline=True)
            embed.add_field(name="Mô tả", value=suggested_level['description'], inline=False)
            embed.set_footer(text="Hệ thống AI tạm bận, sử dụng dữ liệu gợi ý cục bộ.")
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Hiện tại AI đang quá tải và thư viện cục bộ chưa có level nào khớp hoàn toàn với yêu cầu của bạn. Hãy thử đổi từ khóa nhé!")

    except FileNotFoundError:
        await ctx.send("❌ Hệ thống AI hiện không khả dụng và file dữ liệu dự phòng (`levels_fallback.json`) không tồn tại.")

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
        
        if mp >= 100000:
            a_than.append(text)
        elif mp >= 50000:
            god.append(text)
        elif mp >= 10000:
            pro.append(text)
        else:
            thuong.append(text)

    embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG MP SERVER 🏆", color=discord.Color.gold())
    
    if a_than:
        embed.add_field(name="👑 Á Thần (100,000+ Mp)", value="\n".join(a_than), inline=False)
    if god:
        embed.add_field(name="⚡ God (50,000 - 99,999 Mp)", value="\n".join(god), inline=False)
    if pro:
        embed.add_field(name="⚔️ Pro (10,000 - 49,999 Mp)", value="\n".join(pro), inline=False)
    if thuong:
        embed.add_field(name="🌱 Thường (< 10,000 Mp)", value="\n".join(thuong), inline=False)

    await ctx.send(embed=embed)

# ================= CHẠY BOT ================= #
if __name__ == "__main__":
    # Kích hoạt web server để giữ bot online 24/7 (nếu bạn dùng Uptimerobot / Render)
    keep_alive() 
    
    # Lấy token từ biến môi trường
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Lỗi: Không tìm thấy DISCORD_TOKEN trong biến môi trường!")
            

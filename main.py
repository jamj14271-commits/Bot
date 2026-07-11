import discord
from discord.ext import commands
import os

# 1. KHỞI TẠO INTENTS (QUAN TRỌNG)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 2. KHỞI TẠO BOT (Phải có dòng này TRƯỚC các lệnh command)
bot = commands.Bot(command_prefix='!', intents=intents)

# 3. CÁC LỆNH COMMAND (Dán đoạn code !duyet của bạn vào đây)
@bot.command()
async def duyet(ctx, *, yeu_cau: str = None):
    # ... (Toàn bộ code !duyet của bạn để ở đây) ...
    # ... (Giữ nguyên đoạn code bạn vừa gửi mình) ...

# 4. CHẠY BOT (Luôn đặt ở cuối file)
bot.run(os.getenv('DISCORD_TOKEN'))
    embed.add_field(name="Yêu cầu", value=yeu_cau.title(), inline=True)
    embed.add_field(name="Loại thưởng", value=reward_name, inline=True)
    embed.add_field(name="Phần thưởng", value=reward_value, inline=False)
    embed.set_image(url=attachment_url)

    view = ReviewView(ctx.author.id, req_type, yeu_cau, reward_id)
    await admin_channel.send(embed=embed, view=view)
    await ctx.send("✅ Yêu cầu đã được gửi đến Admin. Chờ duyệt nhé!")
  

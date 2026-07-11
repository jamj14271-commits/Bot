# CẬP NHẬT PHẦN LỆNH !DUYỆT ĐỂ ADMIN DỄ NHÌN
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
    attachment_url = ctx.message.attachments[0].url

    # TỰ ĐỘNG PHÂN LOẠI MÀU SẮC ĐỂ ADMIN DỄ PHÂN BIỆT
    if is_role:
        # Danh hiệu: Màu Vàng Gold (Sang chảnh, dễ thấy nhất)
        embed = discord.Embed(title="⭐ YÊU CẦU CẤP DANH HIỆU", color=discord.Color.gold())
        reward_name = "Danh hiệu"
        reward_value = yeu_cau.title()
        req_type = "role"
        reward_id = TITLES_DATA[yeu_cau]
    else:
        # MP: Màu Xanh Dương (Chuẩn cho việc cày cuốc)
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
  

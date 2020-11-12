from datetime import datetime, timedelta, timezone
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import discord
from discord.ext import tasks
import re
from dispander import dispand
import async_timeout
import aiohttp
import json
import settings

TOKEN = settings.TOKEN
intents = discord.Intents.all()
client = discord.Client(intents=intents)
jst = timezone(timedelta(hours=9), 'JST')
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

mildom_status = {}
mention_dict = {484103635895058432: '<@&718449500729114664>', 484103660742115363: '<@&718449761409302580>',
                484104086472491020: '<@&718450891744870530>', 484104317410738177: '<@&718450954613162015>',
                484104150959783936: '<@&718451051102994473>', 484104415612239872: '<@&718451257332858920>',
                484104516934041615: '<@&718451718106382417>', 571440864761741325: '<@&718451311393243139>',
                647688309325168651: '<@&718451366699466753>', 484103980440354821: '<@&718451434684809308>'}

mildom_list = [['10105254', '484103635895058432', '<@&718449500729114664>', 'KUN'],
               ['10724334', '484104317410738177', '<@&718450954613162015>', 'Tanaka90'],
               ['10116311', '571440864761741325', '<@&718451311393243139>', 'Sovault'],
               ['10080489', '484104415612239872', '<@&718451257332858920>', 'まんさや']]

reaction_dict = {'01kun': 'L-KUN', '05tnk90': 'L-tn90', '06exam': 'L-EXAM', '11sova': 'L-Sova', '04riki': 'L-rikito',
                 '02mav': 'L-MAV', '07sayaA': 'L-saya', '08delfin': 'L-fiN', '10abo': 'L-abo', '03ryu': 'L-Ryu'}

emoji_list = ['<:01kun:503956099343581185>', '<:02mav:503956138404872202>', '<:04riki:503956260006133760>',
              '<:05tnk90:503956313110478849>', '<:06exam:503956340939685888>', '<:07sayaA:503956355602972685>',
              '<:08delfin:503956370714787872>', '<:11sova:530672411574534154>', '<:10abo:537845803247730690>',
              '<:03ryu:503956243417792543>']
archive = {}
auto_notify_message = {}
latest_live_link = ''
reaction_id = 731559319354605589
mildom_count = 0
live_status = 'first'


@tasks.loop(seconds=15)
async def mildom_archive():
    global mildom_count
    print('check mildom')
    mildom_count = mildom_count + 1
    if mildom_count == 4:
        get_archive = True
        mildom_count = 0
    else:
        get_archive = False
    for val in mildom_list:
        user_id = val[0]
        mention_role = val[2]
        name = val[3]
        ch = client.get_channel(int(val[1]))
        msg_id = auto_notify_message[int(user_id)]
        msg = await ch.fetch_message(msg_id)
        await mildom_check(user_id=user_id,
                           channel=ch,
                           mention_role=mention_role,
                           mildom_name=name, msg=msg)
        if get_archive:
            await get_mildom_archive(user_id=user_id, msg=msg)


@tasks.loop(seconds=60)
async def openrec_exam_every_30sec():
    global live_status, latest_live_link
    dt_now = datetime.now(jst)
    start_year = dt_now.year - 1
    today_year = dt_now.year
    today_month = dt_now.month
    today_day = dt_now.day
    download_url = "https://www.openrec.tv/viewapp/api/v3/get_movie_list?start_date=" + str(
        start_year) + "%2F01%2F01&end_date=" + str(today_year) + "%2F" + str(today_month) + "%2F" + str(
        today_day) + "&upload_type=0&movie_sort_type=UD&movie_sort_direction=1&game_id=&tag=&recxuser_id=19580443" \
                     "&date_status=all&Uuid=914F0026-1056-CA80-42A8-E8738D0FEDE4&Token" \
                     "=313b054f4b052ac6701856aa639fd3fcbfe63ab7&Random=OLROWOKRVNNUNZPUEZCS&page_number=1&list_limit" \
                     "=40&list_offset=0"
    content = await request(url=download_url)
    if '"onair_status":"1"' in content:
        print('Exam-on-live')
        live_list = re.findall('"identify_id":"[a-zA-Z0-9!-/:-@¥[-`{-~]{11}","comment":"', content)
        latest_live = live_list[-1]
        latest_live_link = 'https://www.openrec.tv/live/' + latest_live[-24:-13]
        live_list.clear()
        if live_status == 'false':
            await client.get_channel(484104150959783936).send(
                "<@&718451051102994473> EXAMさんが配信を開始しました。\n" + latest_live_link)
            live_status = 'true'
        elif live_status == 'first':
            live_status = 'true'
    else:
        print('Exam-not-live')
        if live_status == 'true':
            live_status = 'false'
            try:
                msg_ch = client.get_channel(484104150959783936)
                msg = ''
                async for msg_history in msg_ch.history():
                    if re.search(r'`\[\d+]`', msg_history.content) is None:
                        msg = msg_history
                        break
                    else:
                        continue
                await msg.edit(content='［終了］' + msg.content)
            except NameError:
                print('メッセージが存在しません')
        elif live_status == 'first':
            live_status = 'false'


@client.event
async def on_ready():
    f = drive.CreateFile({'id': '1nsBAxrZTnI_o4UskEjZqlDgAZ75aHOUq'})
    f.GetContentFile('log.txt')
    for value_list in mildom_list:
        user_id = value_list[0]
        channel_id = value_list[1]
        channel = client.get_channel(int(channel_id))
        msg = None
        async for msg_history in channel.history():
            if msg_history.author.id == 718034684533145605:
                if re.search(r'`\[\d+]`', msg_history.content) is None:
                    msg = msg_history
                    break
        auto_notify_message[int(user_id)] = msg.id
    mildom_archive.start()
    openrec_exam_every_30sec.start()
    print('ready')


@client.event
async def on_message(message):
    # メンション
    if message.channel.id in mention_dict:
        if message.author == client.user:
            return
        await notify_mention(message=message)
    # Bot除外
    if message.author.bot:
        return
    # DM機能
    if message.guild is None:
        await dm(message=message)
    # リアクションロール
    if message.content.startswith("!reactionrole"):
        if message.author.id != 295208852712849409:
            return
        for emoji in emoji_list:
            await message.add_reaction(emoji)
    # Expand
    await dispand(message)


@client.event
async def on_raw_reaction_add(payload):
    message_id = payload.message_id
    if message_id == reaction_id:
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, client.guilds)
        if payload.emoji.name in reaction_dict:
            role_name = reaction_dict.get(payload.emoji.name)
            role = discord.utils.get(guild.roles, name=role_name)
        else:
            role = discord.utils.get(guild.roles, name=payload.emoji.name)

        if role is not None:
            member = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
            thisbot = discord.utils.find(lambda m: m.id == 718034684533145605, guild.members)
            if member == thisbot:
                return
            if member is not None:
                await member.add_roles(role)

            else:
                print("Member not found")

        else:
            print("Role not found")


@client.event
async def on_raw_reaction_remove(payload):
    message_id = payload.message_id
    if message_id == reaction_id:
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, client.guilds)

        if payload.emoji.name in reaction_dict:
            role_name = reaction_dict.get(payload.emoji.name)
            role = discord.utils.get(guild.roles, name=role_name)

        else:
            role = discord.utils.get(guild.roles, name=payload.emoji.name)

        if role is not None:
            member = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
            this_bot = client.user
            if member == this_bot:
                return
            if member is not None:
                await member.remove_roles(role)

            else:
                print("Member not found")

        else:
            print("Role not found")


@client.event
async def on_raw_message_edit(payload):
    ch = client.get_channel(payload.channel_id)
    edited_message_id = payload.message_id
    edited_msg = await ch.fetch_message(edited_message_id)
    text_mod = url_replace(text=edited_msg.content)
    if edited_msg.author.id == 718034684533145605:
        return
    async for bot_message in ch.history():
        if str(edited_message_id) in bot_message.content and bot_message.author.id == 718034684533145605:
            await bot_message.edit(
                content=mention_dict.get(edited_msg.channel.id) + '\n' + text_mod + '\n`[' + str(edited_message_id) + ']`')
        break
    print('message edited')


@client.event
async def on_raw_message_delete(payload):
    ch = client.get_channel(payload.channel_id)
    message_id = payload.message_id
    async for fetch_message in ch.history():
        if str(message_id) not in fetch_message.content:
            continue
        if fetch_message.author.id != 718034684533145605:
            continue
        await fetch_message.delete()
        break
    print('message deleted')


async def get_mildom_archive(user_id, msg):
    """
    アーカイブ取得関数
    """
    if '［アーカイブ］' in msg.content:
        return
    url = "https://cloudac.mildom.com/nonolive/videocontent/profile/playbackList?user_id=" + user_id
    r = await request(url=url)
    mildom_dict = json.loads(r)
    v_id = mildom_dict['body'][0]['v_id']
    archive_url = 'https://www.mildom.com/playback/' + user_id + '?v_id=' + v_id
    old_archive = archive.get(user_id)
    if old_archive is None:
        archive[user_id] = archive_url
        return
    if old_archive != archive_url:
        unix_time = mildom_dict['body'][0]['publish_time']
        if len(msg.embeds) == 0:
            return
        embed = msg.embeds[0]
        embed.title = '［アーカイブ］'+mildom_dict['body'][0]['title']
        embed.url = archive_url
        await msg.edit(embed=embed)
    archive[user_id] = archive_url
    return


async def mildom_check(user_id, channel, mention_role, mildom_name, msg):
    """
    配信状況チェック関数化
    """
    url = "https://cloudac.mildom.com/nonolive/gappserv/user/profileV2?user_id=" + user_id + "&__platform=web"
    r = await request(url=url)
    mildom_dict = json.loads(r)
    anchor_live = mildom_dict['body']['user_info']['anchor_live']
    # 配信中の場合
    if anchor_live == 11:
        if mildom_status.get(user_id) == 'offline':
            avatar_url = mildom_dict['body']['user_info']['avatar']
            title = mildom_dict['body']['user_info']['anchor_intro']
            thumbnail_url = mildom_dict['body']['user_info']['pic']
            embed = discord.Embed(title=title, url='https://mildom.com/'+user_id, color=discord.Colour.blue())
            embed.set_thumbnail(url=thumbnail_url)
            embed.set_author(name=mildom_name, icon_url=avatar_url)
            notify_message = await channel.send(mention_role + ' ' + mildom_name + 'さんが配信を開始しました。', embed=embed)
            auto_notify_message[int(user_id)] = notify_message.id
        mildom_status[user_id] = 'online'

    # 配信中ではない場合
    else:
        if mildom_status.get(user_id) == 'online':
            if '［終了］' not in msg.content:
                await msg.edit(content='［終了］' + msg.content)
        mildom_status[user_id] = 'offline'


async def dm(message):
    if message.content == '人数':
        server = discord.utils.get(client.guilds, id=484102468524048395)
        await message.channel.send(len(server.members))
    if message.content == 'status' or message.content == '配信状況' or message.content == '配信':
        embed = discord.Embed(title="配信状況一覧", description="このBotが取得している配信者の配信状況一覧です。",
                              color=discord.Colour.blue())
        for item in mildom_list:
            name = item[3]
            user_id = item[0]
            status = mildom_status.get(user_id)
            if status == 'online':
                status_message = '[配信中](https://www.mildom.com/' + user_id + ')'
            elif status == 'offline':
                status_message = '配信していません'
            else:
                status_message = '取得に失敗しました。製作者(Alpaca#8032)までお問い合わせ下さい。'
            embed.add_field(name=name + 'さん',
                            value=status_message, inline=False)
        if live_status == 'true':
            embed.add_field(name='EXAMさん',
                            value='[配信中](' + latest_live_link + ')', inline=False)
        else:
            embed.add_field(name='EXAMさん',
                            value='配信していません', inline=False)

        await message.channel.send(embed=embed)
    if message.content == 'log' or message.content == 'ログ':
        if message.author.id == 295208852712849409 or message.author.id == 539910964724891719:
            filepath = 'log.txt'
            title = 'log.txt'
            file = drive.CreateFile(
                {'id': '1nsBAxrZTnI_o4UskEjZqlDgAZ75aHOUq', 'title': title, 'mimeType': 'text/plain'})
            file.SetContentFile(filepath)
            file.Upload()
            print('upload-complete')
            await message.channel.send(
                'ログをアップロードしました。'
                '\nリンク：https://drive.google.com/file/d/1nsBAxrZTnI_o4UskEjZqlDgAZ75aHOUq/view?usp=sharing')


async def notify_mention(message):
    dt_now = datetime.now(jst)
    with open('log.txt', 'a') as f:
        content = '時刻：' + str(
            dt_now) + ' 送信者：' + message.author.name + ' チャンネル：' + message.channel.name + ' メッセージ：' + message.content
        print(content, file=f)
    text_mod = url_replace(text=message.content)
    await message.channel.send(
        mention_dict.get(message.channel.id) + '\n' + text_mod + '\n`[' + str(message.id) + ']`')


def url_replace(text):
    if 'http' in text:
        pattern = r"https?://[\w/:%#\$&\?\(\)~\.=\+\-]+"
        url_list = re.findall(pattern, text)
        text_mod = text
        for url in url_list:
            if ('<' + url + '>') in text:
                continue
            text_mod = text_mod.replace(url, "<" + url + ">")
    else:
        text_mod = text
    return text_mod


async def fetch(session, url):
    with async_timeout.timeout(10):
        async with session.get(url) as response:
            return await response.text()


async def request(url):
    async with aiohttp.ClientSession() as session:
        body = await fetch(session, url)
        return body


client.run(TOKEN)

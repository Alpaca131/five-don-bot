import asyncio
import feedparser
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import aiohttp
import async_timeout
import discord
import sentry_sdk
from aiolimiter import AsyncLimiter
from discord.ext import tasks
from dispander import dispand

import settings

TOKEN = settings.TOKEN
DSN = settings.SENTRY_DSN
intents = discord.Intents.all()
client = discord.Client(intents=intents)
sentry_sdk.init(
    DSN,
    traces_sample_rate=1.0
)
jst = timezone(timedelta(hours=9), 'JST')
server_join_ratelimit = AsyncLimiter(time_period=10, max_rate=10)
invite_link_ratelimit = AsyncLimiter(time_period=3600, max_rate=2)
url_ratelimit = AsyncLimiter(time_period=60, max_rate=4)
mildom_status = {}
heart_beat = {}
mention_dict = {484103635895058432: '<@&718449500729114664>', 484103660742115363: '<@&718449761409302580>',
                484104086472491020: '<@&718450891744870530>', 484104317410738177: '<@&718450954613162015>',
                484104150959783936: '<@&718451051102994473>', 484104415612239872: '<@&718451257332858920>',
                484104516934041615: '<@&718451718106382417>', 571440864761741325: '<@&718451311393243139>',
                647688309325168651: '<@&718451366699466753>', 484103980440354821: '<@&718451434684809308>'}

mildom_list = [['10105254', '484103635895058432', '<@&718449500729114664>', 'KUN'],
               ['10724334', '484104317410738177', '<@&718450954613162015>', 'Tanaka90'],
               ['10116311', '571440864761741325', '<@&718451311393243139>', 'Sovault'],
               ['10080489', '484104415612239872', '<@&718451257332858920>', 'まんさや']]
"""
KUN
tanaka90
rikito
EXAM
saya
Sovault
abobo
delfin
mavnyan
ryunyan
"""
youtube_ch_id_list = {'UCGjV4bsC43On-YuiLZcfL0w': 541259764357922837,
                      'UCE2PvzXYbNdLUEgdCIrkQqw': 541679922867994641,
                      'UC0Z60kCcQ8VIk5c29sPS9Jw': 541679834040893441,
                      'UC0VoI57B2_63MErt_1QBpxA': 541680011006967818,
                      'UCk-m-OXRVEXUolSWtmY56oA': 541680078896234499,
                      'UC-8IQG9ldD4C5NNeMpBIkXw': 571441032097693736,
                      'UC7R9svaqJMU_FsMlkMTEf2Q': 647688423255179285,
                      'UCy41m_l93UNEQK-TFQ7YRSg': 541680146512609280,
                      'UCXCoqJeKIfPBHkugSFNCGew': 541679468775997460,
                      'UCQH8DfT8RtqzgGMRRjhMmbw': 541679741141516308,
                      }

latest_v_ids = {}

reaction_dict = {'01kun': 'L-KUN', '05tnk90': 'L-tn90', '06exam': 'L-EXAM', '11sova': 'L-Sova', '04riki': 'L-rikito',
                 '02mav': 'L-MAV', '07sayaA': 'L-saya', '08delfin': 'L-fiN', '10abo': 'L-abo', '03ryu': 'L-Ryu'}

emoji_list = ['<:01kun:503956099343581185>', '<:02mav:503956138404872202>', '<:04riki:503956260006133760>',
              '<:05tnk90:503956313110478849>', '<:06exam:503956340939685888>', '<:07sayaA:503956355602972685>',
              '<:08delfin:503956370714787872>', '<:11sova:530672411574534154>', '<:10abo:537845803247730690>',
              '<:03ryu:503956243417792543>']
archive = {}
auto_notify_message = {}
mute_role = None
latest_live_link = ''
reaction_id = 731559319354605589
mildom_count = 0
regex_discord_message_url = (
    r'https://(ptb.|canary.)?discord(app)?.com/channels/'
    '[0-9]{18}/[0-9]{18}/[0-9]{18}'
)
sent_url_list = {}
live_status = 'first'
log_path = 'home/alpaca-data/five-don-bot-log/log.txt'


@tasks.loop(minutes=1)
async def check_process_running():
    global mildom_count
    if time.time() - heart_beat['mildom'] > 35:
        mildom_count = 0
        del heart_beat['mildom']
        for i in mildom_list:
            user_id = i[0]
            mildom_status[user_id] = 'offline'
        mildom_archive.restart()
    elif time.time() - heart_beat['openrec'] > 65:
        del heart_beat['openrec']
        openrec_exam_every_30sec.restart()
    else:
        return


@tasks.loop(minutes=5)
async def reset_sent_url_list():
    sent_url_list.clear()


@tasks.loop(seconds=20)
async def mildom_archive():
    global mildom_count
    print('check mildom')
    heart_beat['mildom'] = time.time()
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
        await mildom_check_live(user_id=user_id,
                                channel=ch,
                                mention_role=mention_role,
                                mildom_name=name, msg=msg)
        if get_archive:
            await mildom_check_archive(user_id=user_id, msg=msg)


@tasks.loop(seconds=60)
async def openrec_exam_every_30sec():
    global live_status, latest_live_link
    heart_beat['openrec'] = time.time()
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
                mentioned_role = msg.role_mentions[0]
                msg.content = msg.content.replace(f'<@&{mentioned_role.id}>', '')
                await msg.edit(content='［終了］' + msg.content)
            except NameError:
                print('メッセージが存在しません')
        elif live_status == 'first':
            live_status = 'false'


@tasks.loop(minutes=5)
async def check_youtube():
    for yt_ch_id in youtube_ch_id_list:
        r = feedparser.parse(f'https://www.youtube.com/feeds/videos.xml?channel_id={yt_ch_id}')
        discord_ch = client.get_channel(youtube_ch_id_list[yt_ch_id])
        latest_v_id = r['entries'][0]['id'][9:]
        stored_v_id = latest_v_ids.get(yt_ch_id)
        if stored_v_id is None:
            latest_v_ids[yt_ch_id] = latest_v_id
        elif stored_v_id != latest_v_id:
            await discord_ch.send(f'動画がUPされました。\nhttps://www.youtube.com/watch?v={latest_v_id}')
            latest_v_ids[yt_ch_id] = latest_v_id


@client.event
async def on_ready():
    global mute_role
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
    # 暫定的にWelcomeロールに設定
    mute_role = discord.utils.get(client.get_guild(484102468524048395).roles, id=734047235574071304)
    mildom_archive.start()
    openrec_exam_every_30sec.start()
    reset_sent_url_list.start()
    await asyncio.sleep(2)
    check_process_running.start()
    print('ready')


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    await invite_link_detection(message)
    await url_detection(message)
    # メンション
    if message.channel.id in mention_dict:
        await notify_mention(message=message)
    # Bot除外
    if message.author.bot:
        return
    # DM機能
    if message.guild is None:
        await dm(message=message)
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
            this_bot = client.user
            if member == this_bot:
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
                content=mention_dict.get(edited_msg.channel.id) + '\n' + text_mod + '\n`[' + str(
                    edited_message_id) + ']`')
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


@client.event
async def on_member_join(member):
    if server_join_ratelimit.has_capacity(1):
        print(member.display_name + ' JOINED')
    else:
        await member.add_roles(mute_role)
        await client.get_user(539910964724891719).send('This user might be a spammer.\nID: ' + str(member.id))
        await client.get_user(295208852712849409).send('このユーザーはスパムかもしれません。10秒間に10人以上がサーバーに参加しました。```\n'
                                                       'ID: ' + str(member.id) + '\n名前: ' + member.display_name + '```')
    await server_join_ratelimit.acquire(1)


async def mildom_check_archive(user_id, msg):
    """
    アーカイブチェック
    """
    # エラーの原因が判明するまでの応急処置
    try:
        if '［アーカイブ］' in msg.content:
            return
        v_id, title = await mildom_get_playback(user_id)
        if v_id is None:
            return
        archive_url = 'https://www.mildom.com/playback/' + user_id + '?v_id=' + str(v_id)
        old_archive = archive.get(user_id)
        if old_archive is None:
            archive[user_id] = archive_url
            return
        if old_archive != archive_url:
            if len(msg.embeds) == 0:
                return
            embed = msg.embeds[0]
            embed.title = '［アーカイブ］' + title
            embed.url = archive_url
            await msg.edit(embed=embed)
        archive[user_id] = archive_url
        return
    except Exception as e:
        print(e)


async def mildom_check_live(user_id, channel, mention_role, mildom_name, msg):
    """
    配信状況チェック
    """
    # エラーの原因が判明するまでの応急処置
    try:
        r = await mildom_get_user(user_id)
        if r is None:
            return
        anchor_live = r['anchor_live']
        # 配信中の場合
        if anchor_live == 11:
            if mildom_status.get(user_id) == 'offline':
                embed = discord.Embed(title=r['live_title'],
                                      url='https://mildom.com/' + user_id,
                                      color=discord.Colour.blue())
                embed.set_thumbnail(url=r['thumbnail_url'])
                embed.set_author(name=mildom_name,
                                 icon_url=r['avatar_url'])
                notify_message = await channel.send(mention_role + ' ' + mildom_name + 'さんが配信を開始しました。',
                                                    embed=embed)
                auto_notify_message[int(user_id)] = notify_message.id
            mildom_status[user_id] = 'online'

        # 配信中ではない場合
        else:
            if mildom_status.get(user_id) == 'online':
                content: str = msg.content
                mentioned_role = msg.role_mentions[0]
                if '［終了］' not in content:
                    content = content.replace(f'<@&{mentioned_role.id}>', '')
                    await msg.edit(content='［終了］' + content)
            mildom_status[user_id] = 'offline'
    except Exception as e:
        await client.get_channel(742064458939105321).send(str(e))


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
            await message.channel.send(file=log_path)


async def notify_mention(message):
    text_mod = url_replace(text=message.content)
    await message.channel.send(
        mention_dict.get(message.channel.id) + '\n' + text_mod + '\n`[' + str(message.id) + ']`')
    dt_now = datetime.now(jst)
    with open(log_path, 'a') as f:
        content = '時刻：' + str(
            dt_now) + ' 送信者：' + message.author.name + ' チャンネル：' + message.channel.name + ' メッセージ：' + message.content
        print(content, file=f)


async def auto_ban(message):
    if message.channel.id == 790003241621651496:
        user_id = int(message.content)
        user = client.fetch_user(user_id)
        guild = client.get_guild(484102468524048395)
        if user not in guild.members:
            await guild.ban(user=user, reason='Auto BAN')
        else:
            print('This user is in the guild.')


async def invite_link_detection(message):
    invite_link_list = re.findall(r'discord.gg/[a-zA-Z0-9]+', message.content)
    if invite_link_list:
        if invite_link_ratelimit.has_capacity(len(invite_link_list)):
            await invite_link_ratelimit.acquire(len(invite_link_list))
        else:
            await message.channel.send('Discordの招待URLは1時間に2回までしか投稿できません。招待リンクを削除して再投稿してみて下さい。\nメッセージを削除しました。')
            await message.delete()


async def url_detection(message):
    if 'http' in message.content:
        pattern = r"https?://[\w/:%#\$&\?\(\)~\.=\+\-]+"
        all_url_list = re.findall(pattern, message.content)
        message_url_list = re.findall(regex_discord_message_url, message.content)
        url_list = list(set(all_url_list) - set(message_url_list))
        if url_list:
            deleted = False
            if url_ratelimit.has_capacity(len(url_list)):
                await url_ratelimit.acquire(len(url_list))
            else:
                bot_message = await message.channel.send('URLの送りすぎです。時間をあけて再度お試し下さい。\nメッセージを削除しました。')
                await message.delete()
                await asyncio.sleep(3)
                await bot_message.delete()
                deleted = True
            for url in url_list:
                if url in sent_url_list:
                    sent_url_list[url] = sent_url_list[url] + 1
                    if sent_url_list[url] >= 3:
                        if not deleted:
                            bot_message = await message.channel.send('同じURLの送りすぎです。時間をあけて再度お試し下さい。\nメッセージを削除しました。')
                            await message.delete()
                            await asyncio.sleep(3)
                            await bot_message.delete()
                            deleted = True
                else:
                    sent_url_list[url] = 1


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


async def mildom_get_user(user_id):
    # noinspection PyBroadException
    try:
        url = f"https://cloudac.mildom.com/nonolive/gappserv/user/profileV2?user_id={user_id}&__platform=web"
        r = await request(url)
        api_response = json.loads(r)
        anchor_live = api_response['body']['user_info']['anchor_live']
        avatar_url = api_response['body']['user_info']['avatar']
        live_title = api_response['body']['user_info']['anchor_intro']
        thumbnail_url = api_response['body']['user_info']['pic']
        data_dict = {'anchor_live': anchor_live,
                     'live_title': live_title,
                     'avatar_url': avatar_url,
                     'thumbnail_url': thumbnail_url}
        return data_dict
    except Exception as e:
        await client.get_user(539910964724891719).send(str(e))
        logging.error(msg=f'mildom user API error: {e}')
        return None


async def mildom_get_playback(user_id):
    # noinspection PyBroadException
    try:
        url = f"https://cloudac.mildom.com/nonolive/videocontent/profile/playbackList?user_id={user_id}"
        r = await request(url)
        local_dict = json.loads(r)
        v_id = local_dict['body'][0]['v_id']
        title = local_dict['body'][0]['title']
        return v_id, title
    except Exception as e:
        await client.get_user(539910964724891719).send(str(e))
        logging.error(msg='mildom playback API error: ' + str(e))
        return None, None


client.run(TOKEN)

# usstock-bot

I built this for my own US-stock chat. It watches three Chinese financial wires (Jin10, Wallstreetcn, Eastmoney), picks out the items that are actually about US stocks, posts them to a Telegram channel, and babysits the linked discussion group on the side.

One file, stdlib only. `python3 usstock_bot.py` and it runs. Anything personal — token, group IDs, whitelist — lives in `config.json`, so copy `config.example.json`, fill it in, done.

## How the news side works

It polls the three wires about every 60 seconds. Deciding what counts as "US stock news" is just keyword tables at the top of the file: index/macro anchors, company names (Chinese names included), earnings terms, US policy names. Those lists are my editorial taste, you will want to edit them.

Dedup is three layers, because the same flash arrives from all three wires with different wording:

- content fingerprint for exact copies
- 24h text similarity (≥ 0.88) for reworded copies
- event-level anchors, so three takes on the same earnings print still post once

Long analysis pieces, numbered listicles and "click here for more" teasers get dropped. The channel only gets flash items. Broadcast targets are chat IDs in `targets.txt`, one per line; if the bot is made admin of a channel it also registers that channel by itself.

## Moderation notes (learned the hard way)

- Promo links and TG invite links are deleted, warnings accumulate, third warning is a 1-hour mute. Banwords are a plain text file, one word per line.
- Admins are NOT exempt from the flood and link rules. That was deliberate — an admin forwarding junk into the group caused a duplicate mess once.
- Duplicate-checking only applies to channel forwards landing in the group. Members' own posts are not checked, people repeat themselves, that's fine.
- Kicks and bans get reported to the owner by DM, with the group name attached.
- There is a whitelist for a helper bot the group relies on (a search bot): its own messages skip moderation, links pointing at it don't count as promo, and inline results sent through it are exempt from link deletion. Banwords still apply to it.
- Reply to a message with `/mute`, `/unmute`, `/kick` or `/ban` to act on its author. `/rules` posts the group rules.

In private chat, anyone can send `/news` for the latest matched flashes, or ask for a one-time invite link to the group.

## Running it

Get a token from @BotFather and save it into its own file (chmod 600) — the config points at that file, the token itself is never in the config or the code. The bot needs to be admin in both the channel and the group (delete messages, restrict members, invite links).

```bash
python3 usstock_bot.py   # foreground first, check it behaves
```

For a permanent install I use systemd:

```ini
[Unit]
Description=usstock-bot
After=network-online.target

[Service]
WorkingDirectory=/opt/usstock-bot
ExecStart=/usr/bin/python3 /opt/usstock-bot/usstock_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

State (seen item IDs, fingerprints, warning counts) sits in `state.json` next to the script and creates itself.

## Config keys worth knowing

| Key | What it does |
| --- | --- |
| `token_file` | File holding the bot token |
| `owner_ids` | User IDs treated as owners/admins everywhere |
| `report_to` | Who gets kick/ban reports by DM (0 = off) |
| `group_id` | Discussion group; invite links are made for this group |
| `group_labels` | Group ID → name, used in reports |
| `bot_id` | The bot's own user ID (the part before the colon in the token) |
| `whitelisted_user_ids` / `whitelisted_bot_usernames` | The helper-bot exemption described above |
| `banwords_file` | Banword list path |

The full set is in `config.example.json`.

One caveat: the three wires are unofficial web endpoints. Every now and then Jin10 reshuffles its API and the matching `fetch_*` function needs a five-minute fix. UI strings are Chinese literals in the file; replace them if your group speaks something else.

MIT license, see LICENSE.

---

## 中文版

自己有个美股群，就写了这个机器人：盯金十、华尔街见闻、东方财富三个快讯源，把真正跟美股有关的挑出来发到频道，顺带管一下绑定的讨论群。

单文件、纯标准库，`python3 usstock_bot.py` 就能跑。token、群 ID、白名单这些个人设置全在 `config.json` 里，复制 `config.example.json` 填好就行，源码里不写死任何东西。

### 新闻这边怎么筛

大约每 60 秒轮询一次三个源。什么算「美股相关」就是文件开头几张关键词表：大盘和宏观锚点、公司名（带中文名）、财报词、美国政策人名。这几张表是我的口味，你用肯定要改。

去重做了三层，因为同一条快讯三个源都会发、措辞还不一样：正文指纹挡完全重复的，24 小时相似度（≥0.88）挡改写的，最后一层按事件锚点合并——同一场财报三个源写三遍，频道里只出现一次。长篇分析、编号要点、引流预告一律拦掉，频道只进快讯体。

播报目标写在 `targets.txt`，一行一个 chat ID；机器人被设为频道管理员后也会自动把那个频道登记进来。

### 群管的几个决定（都是踩坑踩出来的）

- 广告和引流链接自动删，警告累计 3 次禁言 1 小时，违禁词是单独的文本文件一行一词
- 管理员不豁免刷屏和链接规则——这是故意的，之前有管理员往群里转垃圾，重复帖删到手软
- 重复检测只针对频道转发进群的消息，成员自己说话不查，人重复自己很正常
- 踢人、封禁之后会私聊给号主发一份报告，带群名
- 给群里在用的搜索机器人留了白名单：它本人的消息不删、指向它的链接不算引流、经它发出的搜索结果豁免链接删除，但违禁词照样管它
- 回复某人的消息发 `/mute`、`/unmute`、`/kick`、`/ban` 就能处理他；`/rules` 发群规

私聊里任何人发 `/news` 能看最新命中的快讯，发「进群」领一次性邀请链接。

### 跑起来

找 @BotFather 建机器人，token 单独存一个文件（权限 600），config 里只写文件路径。机器人要在频道和群里都是管理员（删消息、限制成员、邀请链接三个权限）。

先前台跑一遍看没问题，再用 systemd 常驻（unit 示例在英文版里，路径换成你自己的）。运行状态（看过的快讯 ID、指纹、警告次数）存在同目录的 `state.json`，自动生成。

配置项主要就这些：`token_file`（token 文件）、`owner_ids`（号主 ID）、`report_to`（踢人报告发给谁，0 为关）、`group_id`（讨论群）、`bot_id`（机器人自己的 ID，看 token 冒号前那段）、`whitelisted_user_ids` / `whitelisted_bot_usernames`（白名单）、`banwords_file`（词表路径）。全集看 `config.example.json`。

丑话说前面：三个源都是非官方网页接口，金十隔段时间就会改一次接口，对应的 `fetch_*` 函数得跟着修五分钟。界面文案是中文字符串，群里不用中文的话自己替换。

MIT，见 LICENSE。

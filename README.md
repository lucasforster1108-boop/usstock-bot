# usstock-bot

A Telegram bot that broadcasts US-stock news flashes to a channel and moderates its discussion group: **pure Python standard library, single file, zero third-party dependencies** — `python3 usstock_bot.py` and it runs. All personal settings live in one `config.json`; the source contains no group/channel IDs, no admin IDs and no secrets.

## Features

**News broadcasting**
- Polls three public Chinese-language financial wires (Jin10, Wallstreetcn, Eastmoney) every ~60 seconds
- A relevance filter keeps only US-stock items: index/macro anchors, listed companies, earnings, US policy, institutional research (keyword lists are plain constants at the top of the file — edit them to retarget the filter)
- Three-layer deduplication: content fingerprint, 24h text similarity (≥ 0.88), and event-level anchor matching, so the same story from three wires posts once
- Targets are chat IDs in `targets.txt` (one per line); when the bot is added as a channel admin, it registers that channel automatically
- Long analysis pieces, list-style digests and teaser posts are filtered out; only flash-style items are pushed

**Group moderation**
- Promo/TG-link deletion, banword file (one word per line), flood detection (6 messages / 30 s)
- Warnings accumulate; the 3rd warning mutes for 1 hour. Admins are **not** exempt from the flood/link rules
- Duplicate detection for messages forwarded from channels (exact + fuzzy match)
- Reply-based admin commands: `/mute`, `/unmute`, `/kick`, `/ban`, `/rules`
- Kicks and bans are reported to the owner in private chat
- Configurable whitelist for a helper bot the group relies on (e.g. a search bot): its own messages skip moderation, links pointing at it are not treated as promo, and inline results sent via it are exempt from link deletion (banwords still apply)
- New members get a welcome message with the group rules

**Private chat**
- `/news` (or 「新闻」/「快讯」): the latest matched flashes, for anyone
- 「进群」: a one-time invite link to the discussion group

## Deployment

1. **Create the bot and store the token**: talk to @BotFather, `/newbot`, save the token into a file of its own, e.g. `/root/.usstock-bot_token` (chmod 600). Add the bot to your channel and discussion group as admin (it needs message deletion, member restriction and invite-link permissions).
2. **Configure**: `cp config.example.json config.json` and fill in your own values (see the table below); `cp banwords.example.txt banwords.txt` and edit the word list. Put your broadcast channel's ID (or leave the file empty and let the bot auto-register the channel) into `targets.txt`, one ID per line.
3. **Run** in the foreground first to check it works:

   ```bash
   python3 usstock_bot.py
   ```

   For permanent operation use systemd (adjust the paths):

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

   Save as `/etc/systemd/system/usstock-bot.service`, then `systemctl enable --now usstock-bot`.

Runtime state (seen item IDs, fingerprints, warnings, pending notices) is kept in `state.json` next to the script and is created automatically.

## Configuration (config.json)

| Key | Description |
| --- | --- |
| `token_file` | Path to the file containing the bot token. The token never goes into config or code. |
| `owner_ids` | Telegram user IDs treated as owners: they get the owner `/start` behaviour, count as admins everywhere, and their private `/news` is answered with priority handling. |
| `report_to` | User ID that receives kick/ban reports. `0` disables reports. |
| `group_id` | The discussion group ID; one-time invite links are created for this group. |
| `group_labels` | Map of group ID (as string) → display name, used in kick/ban reports. |
| `bot_id` | The bot's own Telegram user ID (ask @userinfobot with your bot, or read it from the token prefix). |
| `whitelisted_user_ids` | User/bot IDs exempt from moderation (see Features). |
| `whitelisted_bot_usernames` | Bot usernames (without `@`) whose t.me links are not counted as promo links. |
| `banwords_file` | Banword list file, resolved relative to the script directory. |

## Notes

- UI strings are in Chinese (the bot was built for a Chinese-language community); they are plain string literals in `usstock_bot.py` and can be replaced freely.
- The news sources are public web endpoints of Jin10 / Wallstreetcn / Eastmoney; if a source changes its API the corresponding `fetch_*` function needs adjusting.
- This is a template: the keyword lists (anchors, companies, policy terms) encode one community's editorial choices — review and adapt them before use.

## Custom development

Fields, filters, thresholds and texts are all adjustable. If your community needs a custom flow (different news sources, extra moderation rules, integrations), a customized or hosted version can be arranged — contact the author.

## License

MIT, see [LICENSE](LICENSE).

---

## 中文版

一个 Telegram 机器人：把美股快讯播报到频道，同时管理绑定的讨论群。**纯 Python 标准库、单文件、零第三方依赖**，`python3 usstock_bot.py` 就能跑。所有个人设置都在一个 `config.json` 里，源码不写死任何群/频道 ID、管理员 ID 或密钥。

### 功能

**快讯播报**
- 每约 60 秒轮询三个公开中文财经快讯源（金十、华尔街见闻、东方财富）
- 相关性过滤只保留美股内容：大盘/宏观锚点、上市公司、财报、美国政策、机构研报（关键词表是文件顶部的普通常量，可自行增删以调整口径）
- 三层去重：正文指纹、24 小时文本相似度（≥ 0.88）、事件级锚点匹配，同一条新闻三个源发来只发一次
- 播报目标是 `targets.txt` 里的 chat ID（一行一个）；机器人被拉进频道设为管理员后会自动登记该频道
- 长篇分析、编号要点类、引流预告类内容会被拦下，只推快讯体

**群管理**
- 广告/引流链接自动删、违禁词文件（一行一词）、刷屏检测（30 秒 6 条）
- 警告累计，第 3 次禁言 1 小时；管理员也不豁免刷屏/链接规则
- 频道转发消息的重复检测（精确 + 模糊匹配）
- 回复式管理员命令：`/mute`、`/unmute`、`/kick`、`/ban`、`/rules`
- 踢人/封禁后私聊报告号主
- 可配置白名单（给群里依赖的辅助机器人，如搜索机器人）：其本人消息整条豁免删帖，指向它的链接不算引流，经它发出的内联结果豁免链接删除（违禁词不豁免）
- 新人进群自动发欢迎语 + 群规

**私聊**
- `/news`（或发「新闻」/「快讯」）：最新命中的快讯，所有人可用
- 发「进群」：领讨论群的一次性邀请链接

### 部署三步

1. **建机器人拿 token**：在 Telegram 里找 @BotFather 发 `/newbot`，把 token 单独存成一个文件，例如 `/root/.usstock-bot_token`（权限 600）。把机器人拉进你的频道和讨论群并设为管理员（需要删消息、限制成员、邀请链接权限）。
2. **填配置**：`cp config.example.json config.json` 按下表改成你自己的值；`cp banwords.example.txt banwords.txt` 改词表。播报频道 ID 写进 `targets.txt`（一行一个；也可以留空，等机器人进频道后自动登记）。
3. **启动**：先前台试跑确认无误：

   ```bash
   python3 usstock_bot.py
   ```

   正式常驻用 systemd（示例 unit，把路径换成你的实际路径）：

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

   存为 `/etc/systemd/system/usstock-bot.service` 后 `systemctl enable --now usstock-bot`。

运行状态（已见快讯 ID、指纹、警告次数、待删提示）保存在同目录的 `state.json`，自动生成，不用管。

### 配置项说明（config.json）

| 键 | 说明 |
| --- | --- |
| `token_file` | 存放 Bot Token 的文件路径。token 不写进 config、更不写进代码。 |
| `owner_ids` | 号主的 TG 数字 ID 列表：走号主版 `/start`、在任何群里都视为管理员。 |
| `report_to` | 接收踢人/封禁报告的用户 ID；填 0 关闭报告。 |
| `group_id` | 讨论群 ID，一次性邀请链接就是给这个群生成的。 |
| `group_labels` | 群 ID（字符串）→ 显示名的映射，用于踢人/封禁报告。 |
| `bot_id` | 机器人自己的 TG 数字 ID（可用 @userinfobot 查，或看 token 冒号前一段）。 |
| `whitelisted_user_ids` | 豁免群管的用户/机器人 ID 列表（见功能说明）。 |
| `whitelisted_bot_usernames` | 机器人用户名（不带 `@`）列表，指向它们的 t.me 链接不算引流。 |
| `banwords_file` | 违禁词文件路径（相对路径按脚本所在目录解析）。 |

### 说明

- 界面文案为中文，在 `usstock_bot.py` 里都是普通字符串，可自行替换。
- 新闻源是金十 / 华尔街见闻 / 东方财富的公开网页接口；源方改接口时需相应调整对应的 `fetch_*` 函数。
- 这是模板：关键词表（锚点、公司、政策词）体现的是一个社区的编辑口径，使用前请按自己的需要审阅调整。

### 定制开发

字段、过滤口径、阈值、文案都能自己改。如果你的社区有特殊流程（换新闻源、加群管规则、和其他系统打通等），需要定制版或代部署，可联系作者获取付费定制服务。

### License

MIT，见 [LICENSE](LICENSE)。

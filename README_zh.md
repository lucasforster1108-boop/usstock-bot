# usstock-bot

[English](README.md) | 简体中文

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

先前台跑一遍看没问题，再用 systemd 常驻（路径换成你自己的）：

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
运行状态（看过的快讯 ID、指纹、警告次数）存在同目录的 `state.json`，自动生成。

配置项主要就这些：`token_file`（token 文件）、`owner_ids`（号主 ID）、`report_to`（踢人报告发给谁，0 为关）、`group_id`（讨论群）、`bot_id`（机器人自己的 ID，看 token 冒号前那段）、`whitelisted_user_ids` / `whitelisted_bot_usernames`（白名单）、`banwords_file`（词表路径）。全集看 `config.example.json`。

丑话说前面：三个源都是非官方网页接口，金十隔段时间就会改一次接口，对应的 `fetch_*` 函数得跟着修五分钟。界面文案是中文字符串，群里不用中文的话自己替换。

MIT，见 LICENSE。

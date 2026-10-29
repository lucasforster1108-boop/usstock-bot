# usstock-bot

English | [简体中文](README_zh.md)

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

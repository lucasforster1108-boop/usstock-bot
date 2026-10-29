#!/usr/bin/env python3
# usstock_bot.py - US-stock news broadcaster + discussion-group moderation bot.
# - Polls three public Chinese-language financial news wires (Jin10, Wallstreetcn,
#   Eastmoney) every ~60 seconds and pushes items that match a US-stock relevance
#   filter to the chats listed in targets.txt (one chat id per line; channels go here).
# - Moderates the discussion group: promo/link deletion, banwords, flood control,
#   warnings -> 1h mute, reply-based admin commands, kick/ban reports to the owner.
# - Private chat: /news on demand for anyone; one-time group invite links.
# Pure Python standard library, single file. Every personal setting (bot token
# file, owner ids, group/channel ids, whitelist) lives in config.json - copy
# config.example.json and fill in your own values. No ids or secrets in code.
import json, os, re, time, html, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, 'config.json')
STATE = os.path.join(BASE, 'state.json')
TARGETS = os.path.join(BASE, 'targets.txt')

DEFAULT_CONFIG = {
    'token_file': '',
    'owner_ids': [],
    'report_to': 0,
    'group_id': 0,
    'group_labels': {},
    'bot_id': 0,
    'whitelisted_user_ids': [],
    'whitelisted_bot_usernames': [],
    'banwords_file': 'banwords.txt',
}

def _deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst

def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding='utf-8') as f:
            _deep_merge(cfg, json.load(f))
    return cfg

CFG = load_config()

def _load_token():
    path = CFG.get('token_file') or ''
    if path and os.path.exists(path):
        return open(path).read().strip()
    raise SystemExit('Bot token not found: set "token_file" in config.json to a file containing your bot token.')

TOKEN = _load_token()
API = f'https://api.telegram.org/bot{TOKEN}'
FEED = 'https://www.jin10.com/flash_newest.js'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
OWNER_IDS = {int(x) for x in CFG.get('owner_ids') or []}

ANCHORS = [
    '美股','道琼斯','费城半导体','中概股','纳斯达克','纳指','道指','标普','纽交所','华尔街','OPEC','欧佩克','EIA',
    '美联储','鲍威尔','FOMC','国会','参议院','众议院','美国商务部','美国财政部','美国政府','贸易代表办公室','美债','美国国债','美元指数','美国CPI','美国非农','美国就业','美国经济','特朗普','美国总统','白宫','马斯克','贝森特','美国财长','财政部长','耶伦','卢特尼克','商务部长',
]
COMPANIES = [
    '英伟达','美光','闪迪','海力士','迈威尔','康宁','应用材料','英特尔','博通','高通','AMD','超微半导体',
    '特斯拉','苹果公司','微软','谷歌','亚马逊','Meta','奈飞','甲骨文','台积电',
    '西部数据','希捷','拉姆研究','科磊','Palantir','礼来','伯克希尔',
    '沃尔玛','好市多','家得宝','宝洁','强生','联合健康','Visa','万事达','埃克森美孚','雪佛龙',
    '波音','可口可乐','百事','迪士尼','思科','赛富时','优步','星巴克','耐克','麦当劳','戴尔','超微电脑','美国运通',
]
EARN = ['财报','业绩','季报','年报','营收','盈利','指引']
KR_GATE = ['韩国','韩股','KOSPI','三星']
RISES = ['大涨','拉升','暴涨','涨超','飙升','创新高','历史新高','领涨','涨幅扩大']
POLICY = ['关税','出口管制','实体清单','制裁','禁令','法案','减税','税改','补贴','加征','贸易协议','债务上限','政府关门','稀土']
ACTORS = ['美国','华盛顿','中国','对华','商务部','财政部','白宫','国会']
INST = ['高盛','摩根士丹利','大摩','花旗','美银','美国银行','瑞银','野村','汇丰','巴克莱','德意志银行','富国银行','杰富瑞','伯恩斯坦']
SCOPE = ['美国','美股','美联储','美元','美债','中国','对华','韩国','韩股','KOSPI','海力士','三星','日本','日股','日经','铠侠','台湾','台股','台积电','黄金','金价','原油','油价','OPEC','欧佩克']
WATCH = ['英伟达','苹果']
MOVES = ['拉升','跳水','暴涨','暴跌','大涨','大跌','涨超','跌超','涨幅扩大','跌幅扩大','飙升','重挫','闪崩','创新高','历史新高','涨停','跌停','转涨','转跌','领涨','领跌']

def log(msg):
    print(time.strftime('%F %T'), msg, flush=True)

def api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f'{API}/{method}', data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def send(chat_id, text):
    try:
        return api('sendMessage', chat_id=chat_id, text=text).get('ok', False)
    except Exception as e:
        log(f'send fail {chat_id}: {e}')
        return False

REPORT_TO = int(CFG.get('report_to') or 0)
GROUP_LABEL = {int(k): v for k, v in (CFG.get('group_labels') or {}).items()}

def report_kick(lines):
    if not REPORT_TO:
        return
    send(REPORT_TO, '\n'.join(lines))

def who_of(u):
    w = (u or {}).get('first_name') or '用户'
    if (u or {}).get('username'):
        w += ' (@' + u['username'] + ')'
    return w

def fetch_feed():
    req = urllib.request.Request(f'{FEED}?t={int(time.time())}', headers=UA)
    with urllib.request.urlopen(req, timeout=12) as r:
        raw = r.read().decode('utf-8', 'ignore')
    m = re.search(r'=\s*(\[.*\])\s*;?\s*$', raw, re.S)
    return json.loads(m.group(1))


def fp_of(content):
    import hashlib
    norm = re.sub(r'[\s\W_]+', '', content or '')[:120]
    return hashlib.sha1(norm.encode('utf-8')).hexdigest()

def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))

def fetch_wscn():
    d = _get_json('https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&client=pc&limit=30')
    out = []
    for it in (d.get('data') or {}).get('items') or []:
        ts = it.get('display_time') or 0
        t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts)) if ts else ''
        out.append({'id': 'wscn-' + str(it.get('id')), 'time': t, 'important': 0,
                    'data': {'content': it.get('content_text') or ''}})
    return out

def fetch_em():
    d = _get_json('https://np-listapi.eastmoney.com/comm/web/getFastNewsList?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=30&req_trace=1',
                  {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://kuaixun.eastmoney.com/'})
    out = []
    for it in (d.get('data') or {}).get('fastNewsList') or []:
        out.append({'id': 'em-' + str(it.get('code')), 'time': it.get('showTime') or '', 'important': 0,
                    'data': {'content': it.get('summary') or it.get('title') or ''}})
    return out

def fetch_all():
    items = []
    for fn in (fetch_feed, fetch_wscn, fetch_em):
        try:
            items.extend(fn())
        except Exception as e:
            log('source fail %s: %s' % (fn.__name__, e))
    items.sort(key=lambda x: x.get('time', ''), reverse=True)
    return items


def norm_text(content):
    return re.sub(r'[\s\W_]+', '', content or '')[:400]

def is_dup(content, recent):
    import difflib
    n = norm_text(content)
    if len(n) < 25:
        return False
    now = int(time.time())
    for r in recent:
        if now - r.get('ts', 0) > 86400:
            continue
        t = r.get('t', '')
        if not t or abs(len(t) - len(n)) > max(len(t), len(n)) * 0.35:
            continue
        if difflib.SequenceMatcher(None, n, t).ratio() >= 0.88:
            return True
    return False

_ALIAS = {
    'NVIDIA': ['nvidia', '英伟达', 'nvda'], 'TESLA': ['tesla', '特斯拉'],
    'MICROSOFT': ['microsoft', '微软', 'msft'], 'AMAZON': ['amazon', '亚马逊', 'amzn'],
    'GOOGLE': ['google', 'alphabet', '谷歌', 'googl'], 'NETFLIX': ['netflix', '奈飞'],
    'TSMC': ['tsmc', '台积电'], 'MICRON': ['micron', '美光'],
    'BROADCOM': ['broadcom', '博通', 'avgo'], 'QUALCOMM': ['qualcomm', '高通', 'qcom'],
    'INTEL': ['intel', '英特尔', 'intc'], 'ORACLECO': ['oracle', '甲骨文', 'orcl'],
    'APPLE': ['apple', '苹果', 'aapl'], 'WALMART': ['walmart', '沃尔玛'],
    'DISNEY': ['disney', '迪士尼'], 'BOEING': ['boeing', '波音'],
    'STARBUCKS': ['starbucks', '星巴克'], 'NIKE': ['nike', '耐克'],
    'CISCO': ['cisco', '思科'], 'DELL': ['dell', '戴尔'], 'UBER': ['uber', '优步'],
    'EXXON': ['exxon', '埃克森美孚'], 'CHEVRON': ['chevron', '雪佛龙'],
    'MCDONALDS': ['mcdonald', '麦当劳'], 'SKHYNIX': ['hynix', '海力士'],
    'SAMSUNG': ['samsung', '三星'], 'SANDISK': ['sandisk', '闪迪'],
    'MARVELL': ['marvell', '迈威尔'], 'CORNING': ['corning', '康宁'],
    'APPMAT': ['applied materials', '应用材料'], 'WDC': ['western digital', '西部数据'],
    'SEAGATE': ['seagate', '希捷'], 'PALANTIR': ['palantir', 'pltr'],
    'LILLY': ['eli lilly', '礼来'], 'BERKSHIRE': ['berkshire', '伯克希尔'],
    'COSTCO': ['costco', '好市多'], 'HOMEDEPOT': ['home depot', '家得宝'],
    'PG': ['procter', '宝洁'], 'JNJ': ['johnson', '强生'],
    'UNH': ['unitedhealth', '联合健康'], 'VISA': ['visa'],
    'MASTERCARD': ['mastercard', '万事达'], 'COKE': ['coca-cola', '可口可乐'],
    'PEPSI': ['pepsi', '百事'], 'SALESFORCE': ['salesforce', '赛富时'],
    'AMEX': ['american express', '美国运通'], 'SUPERMICRO': ['super micro', '超微电脑'],
    'LAM': ['lam research', '拉姆研究'], 'KLA': ['kla', '科磊'],
    'META': ['meta'], 'AMD': ['amd', '超微半导体'],
}
_STOP = {'THE', 'AND', 'WILL', 'INC', 'CORP', 'CO', 'LTD', 'PLC', 'SAID', 'SAYS',
         'NEW', 'FOR', 'WITH', 'FROM', 'ITS', 'ARE', 'HAS', 'PER', 'IN', 'ON',
         'AT', 'TO', 'OF', 'A', 'AN', 'IS', 'IT', 'AS', 'BY', 'OR', 'BE'}

def event_anchors(content):
    low = (content or '').lower()
    out = set()
    for canon, aliases in _ALIAS.items():
        if any(a in low for a in aliases):
            out.add('C:' + canon)
    for name in COMPANIES + ANCHORS:
        if name.lower() in low:
            out.add('C:' + name)
    for tok in re.findall(r'[A-Za-z][A-Za-z0-9\-\.]{2,}', content or ''):
        t = tok.upper().rstrip('.')
        if t.endswith('.O') or t.endswith('.N'):
            t = t[:-2]
        if t in _STOP or len(t) < 3:
            continue
        out.add('T:' + t)
        flat = t.replace('-', '').replace('.', '')
        if flat != t:
            out.add('T:' + flat)
    return out

def event_dup(anchors, events):
    if not anchors:
        return False
    comp = {a for a in anchors if a.startswith('C:')}
    if not comp and len(anchors) < 3:
        return False
    now = int(time.time())
    for e in events:
        if now - e.get('ts', 0) > 5400:
            continue
        ea = set(e.get('a', []))
        if not ea:
            continue
        inter = len(anchors & ea)
        if not inter:
            continue
        j = inter / len(anchors | ea)
        if j >= 0.5:
            return True
        ecomp = {a for a in ea if a.startswith('C:')}
        if comp and comp == ecomp and j >= 0.35:
            return True
    return False

def clean(t):
    s = html.unescape(re.sub(r'<[^>]+>', '', t or '')).strip()
    s = re.sub(r'^金十数据\d+月\d+日讯[，,]?', '', s).strip()
    return s


def is_analysis(c):
    return len(re.findall(r'(?:^|[。\n])\s*[1-9][\.、]', c)) >= 2

TEASER_BLOCK = ['专属文章', '盯盘神器', '市场深谈']

def matched(content):
    if is_analysis(content):
        return False
    if any(b in content for b in TEASER_BLOCK):
        return False
    if content.count('北京时间') >= 3 or '日程安排' in content or '总统行程' in content:
        return False
    if re.search(r'点击(查看|阅读)\s*(\.\.\.|…)', content) or re.search(r'点击(查看|阅读)\s*$', content):
        return False
    if content.startswith('【') and '点击阅读' in content and len(content) < 220:
        return False
    if len(content) > 1200:
        return False
    if len(content) > 350 and not any(k in content for k in INST) and '研报' not in content:
        return False
    low = content.lower()
    if any(k.lower() in low for k in ANCHORS) or any(k.lower() in low for k in COMPANIES):
        return True
    if any(k in content for k in INST) and (any(s in content for s in SCOPE) or any(e in content for e in EARN)):
        return True
    if any(w in content for w in KR_GATE) and any(r in content for r in RISES):
        return True
    if '苹果' in content and any(e in content for e in EARN):
        return True
    if any(w in content for w in POLICY) and any(a in content for a in ACTORS):
        return True
    return False

def fmt(it):
    return clean(it['data'].get('content', ''))

def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {'offset': 0, 'seen': []}

def save_state(st):
    st['seen'] = st['seen'][-300:]
    json.dump(st, open(STATE, 'w'))

def targets():
    try:
        ids = []
        for line in open(TARGETS):
            line = line.strip()
            if line and int(line) not in ids:
                ids.append(int(line))
        return ids
    except FileNotFoundError:
        return []


# ---------------- group moderation ----------------
BOT_ID = int(CFG.get('bot_id') or 0)
GROUP_ID = int(CFG.get('group_id') or 0)
# Whitelisted bot/user IDs (e.g. a search bot the group relies on): their own
# messages skip the moderation chain entirely, and links pointing at a
# whitelisted bot username are not counted as promo links.
WHITELIST_IDS = {int(x) for x in CFG.get('whitelisted_user_ids') or []}
WHITELIST_NAMES = [str(x).lstrip('@').lower() for x in CFG.get('whitelisted_bot_usernames') or []]
PROMO = ['带单','喊单','返佣','包赚','稳赚','杀猪盘','博彩','赌场','招嫖','约炮','代实名','刷单','彩金','免费开户送','高额回报','稳赚不赔','内幕消息','老师带你','跟单信号']
RULES_TEXT = '📋 群规\n1) 只聊美股相关：大盘、个股、财报、政策、机构观点\n2) 禁广告、引流、外链推广（t.me 等）\n3) 禁刷屏、重复发帖、人身攻击\n4) 违者：删帖+警告，3 次警告禁言 1 小时'
_admin_cache = {}
_spam_win = {}
_dup_win = {}
_dup_hist = {}

def banwords():
    try:
        return [l.strip() for l in open(os.path.join(BASE, CFG.get('banwords_file') or 'banwords.txt'), encoding='utf-8') if l.strip()]
    except Exception:
        return []

def is_admin(cid, uid):
    if uid in OWNER_IDS:
        return True
    key = (cid, uid)
    now = time.time()
    if key in _admin_cache and now - _admin_cache[key][1] < 300:
        return _admin_cache[key][0]
    ok = False
    try:
        r = api('getChatMember', chat_id=cid, user_id=uid)
        ok = (r.get('result') or {}).get('status') in ('creator', 'administrator')
    except Exception:
        ok = False
    _admin_cache[key] = (ok, now)
    return ok

def _perms(can_send):
    return json.dumps({'can_send_messages': can_send, 'can_send_media_messages': can_send,
                       'can_send_other_messages': can_send, 'can_send_polls': can_send,
                       'can_add_web_page_previews': can_send, 'can_invite_users': True,
                       'can_pin_messages': False, 'can_change_info': False})

def restrict(cid, uid, can_send, until=0):
    try:
        api('restrictChatMember', chat_id=cid, user_id=uid, permissions=_perms(can_send), until_date=until)
        return True
    except Exception as e:
        log(f'restrict fail {cid}/{uid}: {e}')
        return False

def del_msg(cid, mid):
    try:
        api('deleteMessage', chat_id=cid, message_id=mid)
    except Exception:
        pass

def notice(st, cid, text, ttl=90):
    try:
        r = api('sendMessage', chat_id=cid, text=text)
        mid = (r.get('result') or {}).get('message_id')
        if mid:
            st.setdefault('temp', []).append({'chat': cid, 'msg': mid, 'at': int(time.time()) + ttl})
    except Exception as e:
        log(f'notice fail: {e}')

def greet_new_members(st, msg):
    cid = msg['chat']['id']
    for user in msg.get('new_chat_members') or []:
        if user.get('is_bot'):
            continue
        uid = user['id']
        name = user.get('first_name') or '新朋友'
        try:
            api('sendMessage', chat_id=cid,
                text=f'欢迎 {name} 加入！\n\n' + RULES_TEXT)
        except Exception as e:
            log(f'greet send fail: {e}')
        log(f'greeted {cid}/{uid}')

def handle_callback(cq, st):
    try:
        data = cq.get('data') or ''
        if not data.startswith('vf:'):
            return
        uid_target = int(data[3:])
        frm = cq.get('from') or {}
        msg = cq.get('message') or {}
        cid = (msg.get('chat') or {}).get('id')
        if frm.get('id') != uid_target:
            api('answerCallbackQuery', callback_query_id=cq['id'], text='只能由本人点击验证', show_alert=True)
            return
        restrict(cid, uid_target, True)
        key = f'{cid}:{uid_target}'
        pend = st.setdefault('pending', {})
        if key in pend:
            if pend[key].get('msg'):
                del_msg(cid, pend[key]['msg'])
            del pend[key]
        api('answerCallbackQuery', callback_query_id=cq['id'], text='验证通过，欢迎加入！')
        notice(st, cid, f'✅ {frm.get("first_name") or "新朋友"} 已通过验证，欢迎加入讨论！', 60)
        log(f'verified {cid}/{uid_target}')
    except Exception as e:
        log(f'callback error: {e}')

def mod_sweep(st):
    changed = False
    now = int(time.time())
    pend = st.setdefault('pending', {})
    if pend:
        # Legacy cleanup: new-member verification has been removed, so drop any
        # residual pending entries WITHOUT kicking; delete the stale verify
        # prompt and lift any lingering join restriction.
        for key in list(pend.keys()):
            entry = pend.pop(key)
            changed = True
            try:
                cid_s, uid_s = key.split(':')
                cid2, uid2 = int(cid_s), int(uid_s)
            except Exception:
                continue
            if entry.get('msg'):
                del_msg(cid2, entry['msg'])
            restrict(cid2, uid2, True)
            log(f'verify abolished: dropped pending {key} (no kick)')
    temp = st.setdefault('temp', [])
    keep = []
    for t in temp:
        if now >= t.get('at', 0):
            del_msg(t['chat'], t['msg'])
            changed = True
        else:
            keep.append(t)
    st['temp'] = keep
    return changed

def detect_violation(msg, text, links_ok=False):
    low = (text or '').lower()
    # Whitelist: links pointing at a whitelisted bot itself are not TG promo
    # links (other t.me links still count).
    for _wn in WHITELIST_NAMES:
        low = re.sub(r'(?:t\.me|telegram\.me)/' + re.escape(_wn) + r'(?![a-z0-9_])(\?\S*)?', '', low)
    ents = (msg.get('entities') or []) + (msg.get('caption_entities') or [])
    has_tme = 't.me/' in low or 'telegram.me/' in low or 'joinchat' in low
    has_url = has_tme or ('http://' in low or 'https://' in low or 'www.' in low or any(e.get('type') in ('url', 'text_link') for e in ents))
    words = PROMO + banwords()
    hit = next((w for w in words if w in (text or '')), None)
    if hit:
        return f'广告/违禁内容（{hit}）'
    if has_tme and not links_ok:
        return '外链引流（TG 链接）'
    return None

def handle_group_message(msg, st):
    cid = msg['chat']['id']
    if msg.get('new_chat_members'):
        greet_new_members(st, msg)
        return
    if msg.get('left_chat_member'):
        uid = msg['left_chat_member'].get('id')
        st.setdefault('pending', {}).pop(f'{cid}:{uid}', None)
        return
    frm = msg.get('from') or {}
    uid = frm.get('id')
    if not uid or uid == BOT_ID or msg.get('sender_chat'):
        return
    if uid in WHITELIST_IDS:
        return  # Whitelist: a whitelisted bot's own messages skip the whole moderation chain (no delete, no warn)
    _via_wl = (msg.get('via_bot') or {}).get('id') in WHITELIST_IDS
    # Whitelist: inline results sent via a whitelisted bot are bot-generated
    # (via_bot cannot be forged): links in them are exempt like the bot's own
    # messages, but PROMO/banwords still apply (never exempt).
    text = (msg.get('text') or msg.get('caption') or '').strip()
    # admin commands (reply-based)
    if text.startswith(('/mute', '/kick', '/ban', '/unmute', '/rules')) and is_admin(cid, uid):
        if text.startswith('/rules'):
            notice(st, cid, RULES_TEXT, 180)
            return
        rep = msg.get('reply_to_message') or {}
        target = (rep.get('from') or {}).get('id')
        if not target:
            notice(st, cid, '用法：回复对方任意一条消息，再发命令。', 60)
            return
        if text.startswith('/mute'):
            restrict(cid, target, False, int(time.time()) + 3600)
            notice(st, cid, '🔇 已禁言 1 小时。', 60)
        elif text.startswith('/unmute'):
            restrict(cid, target, True)
            notice(st, cid, '🔊 已解除禁言。', 60)
        elif text.startswith('/kick'):
            try:
                api('banChatMember', chat_id=cid, user_id=target)
                api('unbanChatMember', chat_id=cid, user_id=target)
            except Exception as e:
                log(f'kick cmd fail: {e}')
            notice(st, cid, '👋 已移出本群。', 60)
            _adm = (msg.get('from') or {}).get('first_name') or '管理员'
            report_kick(['👋 踢人报告', '群：' + GROUP_LABEL.get(cid, str(cid)), f'用户：{who_of(rep.get("from"))}（{target}）', f'原因：管理员 {_adm} 手动踢出（可重新加入）'])
        elif text.startswith('/ban'):
            try:
                api('banChatMember', chat_id=cid, user_id=target)
            except Exception as e:
                log(f'ban cmd fail: {e}')
            notice(st, cid, '🚫 已封禁。', 60)
            _adm = (msg.get('from') or {}).get('first_name') or '管理员'
            report_kick(['🚫 封禁报告', '群：' + GROUP_LABEL.get(cid, str(cid)), f'用户：{who_of(rep.get("from"))}（{target}）', f'原因：管理员 {_adm} 手动封禁（不可再进群）'])
        return
    # spam windows (admins not exempt, owner rule 2026-10-27)
    now = time.time()
    key = (cid, uid)
    win = [t for t in _spam_win.get(key, []) if now - t < 30]
    win.append(now)
    _spam_win[key] = win
    violation = detect_violation(msg, text, links_ok=_via_wl)
    if not violation and not _via_wl and len(win) >= 6:
        violation = '刷屏'
    _fwd_chat = None
    _sc = msg.get('sender_chat') or {}
    _ffc = msg.get('forward_from_chat') or {}
    _fo = msg.get('forward_origin') or {}
    if _sc.get('type') == 'channel':
        _fwd_chat = _sc.get('id')
    elif _ffc.get('type') == 'channel':
        _fwd_chat = _ffc.get('id')
    elif _fo.get('type') == 'channel':
        _fwd_chat = (_fo.get('chat') or {}).get('id')
    if not violation and text and _fwd_chat is not None:
        norm = re.sub(r'[^\w]+', '', text.lower())
        if norm:
            hkey = (cid, 'fwd', _fwd_chat)
            hist = [(t0, s0) for (t0, s0) in _dup_hist.get(hkey, []) if now - t0 < 300]
            is_dup = False
            for _t0, prev in hist:
                if prev == norm:
                    is_dup = True
                    break
                if len(prev) >= 8 and len(norm) >= 8:
                    import difflib
                    if difflib.SequenceMatcher(None, prev, norm).ratio() >= 0.85:
                        is_dup = True
                        break
            hist.append((now, norm))
            _dup_hist[hkey] = hist[-20:]
            if is_dup:
                violation = '重复刷屏'
    if violation:
        del_msg(cid, msg['message_id'])
        wkey = f'{cid}:{uid}'
        warns = st.setdefault('warns', {})
        n = warns.get(wkey, 0) + 1
        name = frm.get('first_name') or '成员'
        if n >= 3:
            warns[wkey] = 0
            restrict(cid, uid, False, int(time.time()) + 3600)
            notice(st, cid, f'⚠️ {name} 第 3 次违规（{violation}），已禁言 1 小时。')
        else:
            warns[wkey] = n
            notice(st, cid, f'⚠️ {name} 的消息已被删除（{violation}），第 {n} 次警告，满 3 次禁言 1 小时。')
        log(f'violation {cid}/{uid}: {violation} warn={n}')

def handle_public_private(msg, st):
    chat_id = msg['chat']['id']
    text = (msg.get('text') or '').strip()
    if text.startswith('/start'):
        send(chat_id, '我是美股快讯播报机器人。\n- 发 /news：最新美股相关快讯\n- 发「进群」：拿讨论群的一次性邀请链接\n绑定的频道会自动播报符合规则的美股快讯。')
    elif '进群' in text or text.startswith('/join'):
        try:
            r = api('createChatInviteLink', chat_id=GROUP_ID, member_limit=1, name='via-bot')
            link = (r.get('result') or {}).get('invite_link')
            if link:
                send(chat_id, '这是你的一次性进群链接（只能用一次）：\n' + link)
            else:
                send(chat_id, '暂时生成不了链接，请直接从频道点进讨论群。')
        except Exception as e:
            log(f'invite fail: {e}')
            send(chat_id, '暂时生成不了链接（机器人邀请权限未开），请直接从频道点进讨论群。')
    elif text.startswith('/news') or '新闻' in text or '快讯' in text:
        _send_latest(chat_id, 5)
    else:
        send(chat_id, '我负责播报美股快讯。发 /news 看最新快讯，发「进群」进讨论群。')

def main():
    st = load_state()
    seen = st['seen']
    fps = st.setdefault('fps', [])
    st.setdefault('warns', {}); st.setdefault('pending', {}); st.setdefault('temp', [])
    recent = st.setdefault('recent', [])
    events = st.setdefault('events', [])
    if not seen:
        try:
            items = fetch_feed()
            seen = [it['id'] for it in items]
            st['seen'] = seen
            save_state(st)
            log(f'seeded {len(seen)} flash ids')
        except Exception as e:
            log(f'seed failed: {e}')
    last_poll = 0
    while True:
        try:
            if mod_sweep(st):
                save_state(st)
        except Exception as e:
            log(f'sweep error: {e}')
        # 1) handle owner commands (long poll, short timeout)
        try:
            resp = api('getUpdates', offset=st['offset'], timeout=5)
            for u in resp.get('result', []):
                st['offset'] = u['update_id'] + 1
                mcm = u.get('my_chat_member')
                if mcm:
                    c2 = mcm.get('chat', {})
                    ns = (mcm.get('new_chat_member') or {}).get('status')
                    if ns in ('member', 'administrator') and c2.get('type') == 'channel' and c2.get('id'):
                        if c2['id'] not in targets():
                            with open(TARGETS, 'a') as f:
                                f.write(str(c2['id']) + '\n')
                            log('registered target %s (%s)' % (c2['id'], c2.get('title', '')))
                            send(c2['id'], '✅ 美股快讯播报已接入：符合规则的美股快讯（大盘/公司/财报/政策/机构观点）会自动发到这里。')
                    save_state(st)
                cq = u.get('callback_query')
                if cq:
                    handle_callback(cq, st)
                msg = u.get('message') or {}
                chat = msg.get('chat', {})
                frm = msg.get('from', {})
                text = (msg.get('text') or '').strip()
                if chat.get('type') == 'private' and frm.get('id') in OWNER_IDS and text:
                    if text.startswith('/start'):
                        send(chat['id'], '我是美股快讯播报机器人。\n- 发 /news 给你最新几条美股相关快讯\n- 频道建好、把我拉进去设为管理员后，我会自动往频道播报快讯\n先给你发几条最新的：')
                        _send_latest(chat['id'], 3)
                    elif text.startswith('/news') or '新闻' in text or '快讯' in text:
                        _send_latest(chat['id'], 5)
                    else:
                        send(chat['id'], '我只负责播报，不聊天。发 /news 看最新美股快讯。')
                elif chat.get('type') in ('group', 'supergroup'):
                    handle_group_message(msg, st)
                elif chat.get('type') == 'private' and text:
                    handle_public_private(msg, st)
                save_state(st)
        except Exception as e:
            log(f'updates error: {e}')
        # 2) every ~60s: fetch feed, auto-push matched new items to targets
        now = time.time()
        if now - last_poll >= 60:
            last_poll = now
            tgs = targets()
            if tgs:
                try:
                    items = fetch_all()
                    new = [it for it in items if it['id'] not in seen]
                    new.sort(key=lambda x: x['time'])
                    for it in new:
                        seen.append(it['id'])
                        c = clean(it['data'].get('content', ''))
                        if matched(c):
                            f = fp_of(c)
                            if f not in fps and not is_dup(c, recent):
                                ea = event_anchors(c)
                                if event_dup(ea, events):
                                    log(f'event dup blocked: {c[:60]}')
                                else:
                                    fps.append(f)
                                    recent.append({'t': norm_text(c), 'ts': int(time.time())})
                                    if ea:
                                        events.append({'ts': int(time.time()), 'a': sorted(ea)})
                                    for t in tgs:
                                        send(t, fmt(it))
                    if new:
                        st['seen'] = seen
                        st['fps'] = fps[-800:]
                        st['recent'] = recent[-200:]
                        st['events'] = [e for e in events if int(time.time()) - e.get('ts', 0) < 10800][-300:]
                        events[:] = st['events']
                        save_state(st)
                except Exception as e:
                    log(f'feed error: {e}')
        time.sleep(2)

def _send_latest(chat_id, n):
    try:
        items = fetch_all()
        hits = []
        used = set()
        for it in items:
            c = clean(it['data'].get('content', ''))
            f = fp_of(c)
            if matched(c) and f not in used:
                used.add(f)
                hits.append(it)
            if len(hits) >= n:
                break
        if not hits:
            send(chat_id, '暂时没有新的美股相关快讯。')
            return
        for it in reversed(hits):
            send(chat_id, fmt(it))
    except Exception as e:
        send(chat_id, f'快讯源暂时拉不到：{e}')

if __name__ == '__main__':
    main()

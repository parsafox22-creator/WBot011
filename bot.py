import os,json,time,uuid,shutil,re,ast,sys,tempfile,html
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup,InlineKeyboardButton
from dotenv import load_dotenv
load_dotenv()
VERSION='31.0.0'
TOKEN=os.getenv('BOT_TOKEN','')
ADMIN_ID=int(os.getenv('ADMIN_ID','7278007788') or 7278007788)
OWNER_ID=7278007788
DATA_FILE='data.json'; BACKUP_DIR='backups'
os.makedirs(BACKUP_DIR,exist_ok=True)
bot=telebot.TeleBot(TOKEN,parse_mode='HTML'); states={}
DEFAULT={'users':{},'packs':{},'orders':{},'tickets':{},'deposits':{},'discounts':{},'referral_rewards':{},'private_threads':{},'private_chats':{},'admins':{},'settings':{'welcome_text':'به ربات خوش آمدید','guide_text':'راهنما تنظیم نشده است.','rules_text':'قوانین تنظیم نشده است.','free_config':'', 'card_number':'','card_holder':'','min_deposit':50000,'admin_link':'','force_join':False,'channel_id':'','channel_link':'','bot_enabled':True,'referral_enabled':True,'referral_percent':10,'referral_max_rewards':1}}
def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def load():
    if not os.path.exists(DATA_FILE): return json.loads(json.dumps(DEFAULT))
    try:
        d=json.load(open(DATA_FILE,encoding='utf-8'))
    except: return json.loads(json.dumps(DEFAULT))
    for k,v in DEFAULT.items(): d.setdefault(k,json.loads(json.dumps(v)))
    for k,v in DEFAULT['settings'].items(): d['settings'].setdefault(k,v)
    d.setdefault('admins',{})
    return d
def save(d):
    t=DATA_FILE+'.tmp'; json.dump(d,open(t,'w',encoding='utf-8'),ensure_ascii=False,indent=2); os.replace(t,DATA_FILE)
def backup(tag):
    if os.path.exists(DATA_FILE):
        p=f'{BACKUP_DIR}/data_{tag}_{int(time.time())}.json'; shutil.copy2(DATA_FILE,p); return p
def code(prefix,col):
    while True:
        c=f'{prefix}-{uuid.uuid4().hex[:8].upper()}'
        if c not in col:return c
def user(d,uid,tg=None):
    uid=str(uid); u=d['users'].setdefault(uid,{'balance':0,'username':(tg.username if tg and tg.username else 'بدون نام'),'first_name':(tg.first_name if tg else ''),'crv_code':f'crv-{uid}','orders':[],'hidden_packs':[],'blocked':False,'blocked_until':None,'restrictions':{},'created_at':now()})
    for k,v in {'balance':0,'orders':[],'hidden_packs':[],'blocked':False,'blocked_until':None,'restrictions':{},'crv_code':f'crv-{uid}','referrer_id':None,'referral_reward_claimed':False}.items():u.setdefault(k,v)
    d.setdefault('referral_rewards',{})
    return u
def get_referral_link(ref_uid):
    try:
        me=bot.get_me()
        return f'https://t.me/{me.username}?start=ref_{ref_uid}'
    except:
        return ''
def apply_referral_reward(d,o):
    try:
        s=d.get('settings',{})
        if not s.get('referral_enabled',True): return 0
        buyer_id=str(o.get('user_id')); buyer=d.get('users',{}).get(buyer_id)
        if not buyer: return 0
        ref_id=str(buyer.get('referrer_id') or '')
        if not ref_id or ref_id==buyer_id: return 0
        ref=d.get('users',{}).get(ref_id)
        if not ref: return 0
        max_rewards=max(1,int(s.get('referral_max_rewards',1)))
        rewards_for_buyer=sum(1 for x in d.get('referral_rewards',{}).values() if str(x.get('referred_user_id',''))==buyer_id)
        if rewards_for_buyer>=max_rewards: return 0
        amount=int(o.get('amount',0)); percent=max(0,min(100,int(s.get('referral_percent',10))))
        reward=amount*percent//100
        if reward<=0: return 0
        ref['balance']=int(ref.get('balance',0))+reward
        rid=code('REF',d.setdefault('referral_rewards',{}))
        d['referral_rewards'][rid]={'code':rid,'referrer_id':ref_id,'referred_user_id':buyer_id,'order_code':o.get('code'),'amount':amount,'reward':reward,'percent':percent,'created_at':now()}
        o['referral_reward_code']=rid; o['referral_reward']=reward; o['referral_rewarded_at']=now()
        # Backward-compatible flag: true after at least one referral reward.
        buyer['referral_reward_claimed']=True
        return reward
    except Exception:
        return 0
def real(o): return str(o.from_user.id)
def eff(o):
    r=real(o); return states.get(r,{}).get('ghost_target',r) if owner(r) else r

PERMISSIONS={
 'panel':'🛠 ورود به پنل مدیریت','card':'💳 تغییر کارت','min':'💰 تغییر حداقل واریز','referral':'👥 مدیریت رفرال',
 'packs_view':'📦 مشاهده بسته‌ها','packs_add':'➕ افزودن بسته','packs_edit':'✏️ ویرایش بسته‌ها','packs_delete':'🗑 حذف بسته‌ها','packs_sale':'⏯ روشن/خاموش فروش',
 'discounts':'🎟 مدیریت تخفیف','users':'👥 مشاهده کاربران','broadcast':'📢 پیام همگانی','private':'💬 پیام خصوصی','backup':'💾 بکاپ','export':'📦 دریافت ZIP','import':'🗃 نصب DB','reset':'♻️ ریست DB',
 'ghost':'👻 Ghost','restrict':'🚫 مسدود/محدود','tickets':'🎫 تیکت‌ها','link':'🔗 لینک PV','guide':'📚 راهنما','join':'📢 عضویت اجباری','welcome':'📝 خوش‌آمد','bot_toggle':'⏯ روشن/خاموش ربات','update':'📥 آپدیت Python',
 'wallet':'💰 مدیریت موجودی','wallet_add':'➕ افزایش موجودی کیف پول','wallet_subtract':'➖ کاهش موجودی کیف پول','wallet_requests':'💳 مدیریت درخواست‌های افزایش موجودی','orders':'🛍 مدیریت سفارش‌ها','order_reapprove':'✅ تایید مجدد سفارش رد شده','deposits':'💳 مدیریت واریزها','admin_manage':'👑 مدیریت ادمین‌ها','stats':'📊 آمار','user_edit':'✏️ ویرایش اطلاعات کاربران','user_delete':'🗑 حذف/پاکسازی کاربران','private_close':'🔒 بستن چت خصوصی','ticket_close':'🔒 بستن تیکت','ticket_delete':'🗑 حذف تیکت','pack_restore':'♻️ بازگردانی بسته','system':'⚙️ تنظیمات سیستمی','user_lookup':'🔎 استعلام کاربر','free_config':'🎁 تنظیم کانفیگ رایگان','rules':'📜 تنظیم قوانین'
}

def owner(uid): return str(uid) == str(OWNER_ID)
def admin(uid):
    uid=str(uid)
    if owner(uid): return True
    try:
        a=load().get('admins',{}).get(uid,{})
        return bool(a.get('active',False))
    except Exception: return False

def can(uid,perm):
    if owner(uid): return True
    if not admin(uid): return False
    a=load().get('admins',{}).get(str(uid),{})
    return bool(a.get('permissions',{}).get(perm,False) or a.get('permissions',{}).get('all',False))

def admin_name(uid):
    if owner(uid): return 'مالک اصلی'
    return load().get('admins',{}).get(str(uid),{}).get('name',str(uid))

def audit(actor,action,details=''):
    if owner(actor) or not admin(actor): return
    try:
        text=f'🔔 <b>فعالیت ادمین</b>\n\n👤 ادمین: <code>{actor}</code>\n🏷 نام: {admin_name(actor)}\n🕒 {now()}\n\n📌 <b>{action}</b>'
        if details: text += f'\n\n📝 {details}'
        bot.send_message(ADMIN_ID,text)
    except Exception: pass

def callback_perm(data):
    if data in ('admin','back_admin','main','developer','ghost_exit','private_cancel','join_check'): return 'panel'
    if data.startswith(('lookup_','dev_lookup')): return 'user_lookup'
    if data=='a_admins' or data.startswith(('admin_add','admin_manage:','admin_perm:','admin_toggle:','admin_remove:')): return 'admin_manage'
    if data.startswith('a_packs') or data.startswith(('p_add','p_edit:')): return 'packs_view' if data=='a_packs' else ('packs_add' if data=='p_add' else 'packs_edit')
    if data.startswith(('p_del:','p_del_yes:')): return 'packs_delete'
    if data.startswith(('pack_sale','sale_toggle:')): return 'packs_sale'
    mp={'a_orders':'orders','a_card':'card','a_min':'min','a_referral':'referral','a_discount':'discounts','a_users':'users','a_broadcast':'broadcast','a_private':'private','a_backup':'backup','a_export':'export','a_import':'import','a_reset':'reset','a_ghost':'ghost','a_restrict':'restrict','a_tickets':'tickets','a_link':'link','a_guide':'guide','a_join':'join','a_welcome':'welcome','a_bot':'bot_toggle','a_update':'update','ghost_balance':'wallet','deposit':'deposits','a_stats':'stats','a_free_config':'free_config','a_rules':'rules'}
    if data in mp:return mp[data]
    if data in ('a_wallet_requests','a_deposits'): return 'wallet_requests'
    if data=='a_wallet_add': return 'wallet_add'
    if data.startswith(('private_reply:','private_close:')): return 'private_close' if data.startswith('private_close:') else 'private'
    if data.startswith(('ticket_admin:','ticket_reply:')): return 'tickets'
    if data.startswith(('ticket_close:','ticket_close_yes:')): return 'ticket_close'
    if data.startswith(('ticket_delete:','ticket_delete_yes:')): return 'ticket_delete'
    if data.startswith(('ghost_pack:','ghost_edit:','ghost_delete_confirm:','ghost_delete_yes:')): return 'ghost'
    if data.startswith(('ghost_deleted','ghost_restore:')): return 'pack_restore'
    if data.startswith('order_reapprove:'): return 'order_reapprove'
    if data.startswith('order_receipt:'): return 'orders'
    if data.startswith(('order_','adm_')): return 'orders'
    if data.startswith(('dep_ok:','dep_no:','dep_reapprove:','dep_view:','dep_receipt:','deps_status:')): return 'wallet_requests'
    if data.startswith('ghost_balance_add'): return 'wallet_add'
    if data.startswith('ghost_balance_sub'): return 'wallet_subtract'
    if data.startswith(('block_','limit_','unlimit:')): return 'restrict'
    if data.startswith(('user_edit:','user_del:')): return 'user_edit'
    return 'panel'

def wait_perm(w):
    return {'private_target':'private','private_message':'private','private_user_message':'private','private_admin_message':'private','ghost':'ghost','restrict':'restrict','duration':'restrict','ghost_pack_edit':'ghost','ticket_answer':'tickets','ticket_admin_reply':'tickets','ticket_user_reply':'tickets','p_full_add':'packs_add','p_full_edit':'packs_edit','p_name':'packs_add','p_price':'packs_add','p_volume':'packs_add','p_duration':'packs_add','p_desc':'packs_add','p_json':'packs_edit','card':'card','min':'min','link':'link','guide':'guide','welcome':'welcome','broadcast':'broadcast','join':'join','import':'import','update_py':'update','discount':'discounts','discount_apply':'discounts','dep_amount':'deposits','vpn':'orders','track':'orders','vpn':'orders','admin_add':'admin_manage','admin_perm':'admin_manage','admin_remove':'admin_manage','ghost_balance_add':'wallet_add','ghost_balance_sub':'wallet_subtract','wallet_target':'wallet_add','lookup_user':'user_lookup','lookup_duration':'user_lookup','lookup_private_message':'user_lookup'}.get(w,'panel')

def expired(x):
    if x is None:return False
    try:return float(x)<=time.time()
    except:return False
def blocked(u):
    if not u.get('blocked'):return False
    if u.get('blocked_until') is not None and expired(u['blocked_until']): u['blocked']=False;u['blocked_until']=None;return False
    return True
def limited(u,k):
    x=u.get('restrictions',{}).get(k)
    if not x:return False
    if x!='permanent' and expired(x):u['restrictions'].pop(k,None);return False
    return True
def joined(uid,d):
    s=d['settings']; ch=s.get('channel_id') or ''
    if not s.get('force_join') or not ch:return True
    try:return bot.get_chat_member(ch,int(uid)).status in ('creator','administrator','member')
    except:return False
def gate(m):
    if admin(m.from_user.id):return True
    d=load()
    if not d['settings'].get('bot_enabled', True):
        bot.send_message(m.chat.id,'⏸ ربات موقتاً خاموش است. لطفاً بعداً دوباره تلاش کنید.')
        return False
    u=user(d,m.from_user.id,m.from_user)
    if blocked(u):save(d);bot.send_message(m.chat.id,'⛔ حساب شما مسدود است.');return False
    if d['settings'].get('force_join') and not joined(m.from_user.id,d):
        mk=InlineKeyboardMarkup(); link=d['settings'].get('channel_link')
        if link:mk.add(InlineKeyboardButton('📢 عضویت در کانال',url=link))
        mk.add(InlineKeyboardButton('✅ بررسی عضویت',callback_data='join_check'));bot.send_message(m.chat.id,'🔒 ابتدا در کانال اطلاع‌رسانی عضو شوید.',reply_markup=mk);return False
    return True
def menu(uid,ghost=False):
    m=InlineKeyboardMarkup(row_width=2)
    m.add(InlineKeyboardButton('🛍 خرید بسته',callback_data='buy'))
    m.add(InlineKeyboardButton('💰 اعتبار من',callback_data='bal'),InlineKeyboardButton('📦 بسته‌های من',callback_data='packs'),InlineKeyboardButton('🎁 کانفیگ رایگان',callback_data='free'),InlineKeyboardButton('🔍 رهگیری سفارش',callback_data='track'),InlineKeyboardButton('⚙️ اطلاعات حساب',callback_data='info'),InlineKeyboardButton('📚 راهنما',callback_data='guide'),InlineKeyboardButton('📜 قوانین',callback_data='rules'),InlineKeyboardButton('📞 ارتباط با ما',callback_data='contact'))
    if ghost:
        m.add(InlineKeyboardButton('💰 مدیریت موجودی کاربر',callback_data='ghost_balance'))
        m.add(InlineKeyboardButton('📦 مدیریت بسته‌های کاربر',callback_data='packs'))
        m.add(InlineKeyboardButton('❌ خروج Ghost',callback_data='ghost_exit'))
    elif admin(uid):
        m.add(InlineKeyboardButton('🛠 مدیریت',callback_data='admin'))
        if owner(uid): m.add(InlineKeyboardButton('👨‍💻 مدیریت دولوپر',callback_data='developer'))
    m.add(InlineKeyboardButton('دعوت دوستان 👥',callback_data='referral'))
    return m
def show(c,t,m=None):
    try:bot.edit_message_text(t,c.message.chat.id,c.message.message_id,reply_markup=m)
    except:bot.send_message(c.message.chat.id,t,reply_markup=m)
@bot.message_handler(commands=['admin'])
def admin_command(m):
    if not admin(m.from_user.id):
        bot.reply_to(m, f'⛔ دسترسی ندارید.\nشناسه فعلی شما: <code>{m.from_user.id}</code>')
        return
    show_admin_panel(m)

@bot.message_handler(commands=['develop'])
def develop_command(m):
    if not owner(m.from_user.id):
        bot.reply_to(m, '⛔ این بخش فقط برای مالک اصلی ربات است.')
        return
    show_developer_panel(m)

def show_developer_panel(m):
    if not owner(m.from_user.id): return
    mkr=InlineKeyboardMarkup(row_width=2)
    mkr.add(InlineKeyboardButton('👑 مدیریت ادمین‌ها',callback_data='dev_admins'))
    mkr.add(InlineKeyboardButton('🔎 دسترسی استعلام کاربران',callback_data='dev_lookup'))
    mkr.add(InlineKeyboardButton('🛠 پنل مدیریت',callback_data='admin'))
    mkr.add(InlineKeyboardButton('🔙 بازگشت',callback_data='main'))
    chat_id = m.chat.id if hasattr(m,'chat') else m.message.chat.id
    bot.send_message(chat_id,'👨‍💻 <b>مدیریت دولوپر</b>\n\nاین بخش فقط برای مالک اصلی ربات قابل دسترسی است.',reply_markup=mkr)

def build_admin_keyboard(uid):
    # تنها منبع ساخت کیبورد پنل مدیریت؛ بنابراین /admin، دکمه مدیریت و «بازگشت»
    # دقیقاً یک لیست یکسان از امکانات را نمایش می‌دهند.
    mkr=InlineKeyboardMarkup(row_width=2)
    uid=str(uid)
    if owner(uid):
        mkr.add(InlineKeyboardButton('👑 مدیریت ادمین‌ها',callback_data='a_admins'))
    items=[
        ('🛍 مدیریت سفارش‌ها','a_orders','orders'),
        ('➕ افزایش موجودی کیف پول','a_wallet_add','wallet_add'),
        ('💳 مدیریت افزایش موجودی','a_wallet_requests','wallet_requests'),
        ('💳 تغییر شماره کارت','a_card','card'),
        ('💰 حداقل واریز','a_min','min'),
        ('👥 مدیریت رفرال','a_referral','referral'),
        ('📦 بسته‌ها','a_packs','packs_view'),
        ('🎟 کد تخفیف','a_discount','discounts'),
        ('👥 کاربران','a_users','users'),
        ('🔎 استعلام کاربر','a_lookup','user_lookup'),
        ('📊 داشبورد و آمار','a_stats','stats'),
        ('📢 همگانی','a_broadcast','broadcast'),
        ('💬 پیام خصوصی','a_private','private'),
        ('💾 بکاپ','a_backup','backup'),
        ('📦 دریافت ZIP کامل ربات','a_export','export'),
        ('🗃 نصب DB','a_import','import'),
        ('♻️ ریست DB','a_reset','reset'),
        ('👻 Ghost','a_ghost','ghost'),
        ('🚫 مسدود/محدود','a_restrict','restrict'),
        ('🎫 تیکت‌ها','a_tickets','tickets'),
        ('🔗 لینک PV','a_link','link'),
        ('📚 تغییر راهنما','a_guide','guide'),
        ('🎁 تنظیم کانفیگ رایگان','a_free_config','free_config'),
        ('📜 تنظیم قوانین','a_rules','rules'),
        ('📢 عضویت اجباری','a_join','join'),
        ('📝 خوش‌آمد','a_welcome','welcome'),
        ('⏯ روشن/خاموش ربات','a_bot','bot_toggle'),
        ('📥 آپدیت Python','a_update','update')
    ]
    for label,cb,perm in items:
        if can(uid,perm):
            mkr.add(InlineKeyboardButton(label,callback_data=cb))
    return mkr

def _resolve_lookup_user(d, query):
    q = str(query or '').strip()
    if not q:
        return None
    if q.isdigit():
        uid = str(int(q))
        if uid in d.get('users', {}):
            return uid
    ql = q.lower()
    for uid, uu in d.get('users', {}).items():
        if str(uu.get('crv_code', '')).lower() == ql:
            return str(uid)
    return None

def _telegram_user_snapshot(uid, stored):
    """Refresh safe Telegram account fields when Bot API can see the user."""
    info = {
        'first_name': str(stored.get('first_name', '') or ''),
        'last_name': str(stored.get('last_name', '') or ''),
        'username': str(stored.get('username', '') or ''),
    }
    try:
        chat = bot.get_chat(int(uid))
        if getattr(chat, 'first_name', None) is not None:
            info['first_name'] = str(chat.first_name or '')
        if getattr(chat, 'last_name', None) is not None:
            info['last_name'] = str(chat.last_name or '')
        if getattr(chat, 'username', None) is not None:
            info['username'] = str(chat.username or '')
        return info, None
    except Exception as e:
        return info, str(e)

def _lookup_status_text(uu):
    if blocked(uu):
        until = uu.get('blocked_until')
        if until is None:
            return '🚫 مسدود دائم'
        try:
            return f'⏱ مسدود موقت تا {datetime.fromtimestamp(float(until)).strftime("%Y-%m-%d %H:%M:%S")}'
        except Exception:
            return '⏱ مسدود موقت'
    rs = uu.get('restrictions', {}) or {}
    active = []
    labels = {'orders': 'سفارش', 'deposits': 'واریز'}
    for key, value in rs.items():
        if value == 'permanent':
            active.append('🚫 ' + labels.get(key, key))
        elif value is not None and not expired(value):
            try:
                active.append(f'⏱ {labels.get(key, key)} تا {datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")}')
            except Exception:
                active.append('⏱ ' + labels.get(key, key))
    return '🟢 بدون محدودیت' if not active else ' | '.join(active)

def _lookup_text(d, uid, tg=None):
    uu = d.get('users', {}).get(str(uid), {})
    info = tg or {
        'first_name': str(uu.get('first_name', '') or ''),
        'last_name': str(uu.get('last_name', '') or ''),
        'username': str(uu.get('username', '') or ''),
    }
    name = ' '.join(x for x in [info.get('first_name', ''), info.get('last_name', '')] if x).strip() or 'ثبت نشده'
    username = ('@' + info['username'].lstrip('@')) if info.get('username') else 'ندارد'
    orders = [o for o in d.get('orders', {}).values() if str(o.get('user_id')) == str(uid)]
    deposits = [x for x in d.get('deposits', {}).values() if str(x.get('user_id')) == str(uid)]
    tickets = [t for t in d.get('tickets', {}).values() if str(t.get('user_id')) == str(uid)]
    private_chats = [x for x in d.get('private_chats', {}).values() if str(x.get('user_id')) == str(uid)]
    open_tickets = sum(1 for x in tickets if x.get('status') == 'open')
    closed_tickets = sum(1 for x in tickets if x.get('status') == 'closed')
    open_private = sum(1 for x in private_chats if x.get('status') == 'open')
    ref = uu.get('referrer_id') or '-'
    return (
        f'🔎 <b>استعلام کامل کاربر</b>\n\n'
        f'👤 نام تلگرام: <b>{html.escape(name)}</b>\n'
        f'🔗 یوزرنیم: <b>{html.escape(username)}</b>\n'
        f'🆔 Telegram ID: <code>{html.escape(str(uid))}</code>\n'
        f'🔑 CRV: <code>{html.escape(str(uu.get("crv_code", "-")))}</code>\n\n'
        f'💰 موجودی: <b>{int(uu.get("balance", 0)):,} تومان</b>\n'
        f'📌 وضعیت: <b>{html.escape(_lookup_status_text(uu))}</b>\n'
        f'📅 تاریخ ثبت: <code>{html.escape(str(uu.get("created_at", "-")))}</code>\n'
        f'👥 معرف: <code>{html.escape(str(ref))}</code>\n\n'
        f'🛍 تعداد سفارش‌ها: <b>{len(orders)}</b>\n'
        f'💳 تعداد واریزها: <b>{len(deposits)}</b>\n'
        f'🎫 تیکت‌ها: <b>{len(tickets)}</b> (باز: {open_tickets} | بسته: {closed_tickets})\n'
        f'💬 چت خصوصی: <b>{len(private_chats)}</b> (باز: {open_private})\n'
        f'📦 بسته‌های کاربر: <b>{len(uu.get("orders", []))}</b>'
    )

def _lookup_keyboard(uid):
    uid = str(uid)
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton('🚫 مسدود / محدود', callback_data='lookup_restrict:' + uid),
        InlineKeyboardButton('🔓 رفع مسدود / محدودیت', callback_data='lookup_unlimit:' + uid),
    )
    m.add(
        InlineKeyboardButton('👻 Ghost', callback_data='lookup_ghost:' + uid),
        InlineKeyboardButton('💬 پیام خصوصی', callback_data='lookup_private:' + uid),
    )
    m.add(InlineKeyboardButton('🔄 بروزرسانی استعلام', callback_data='lookup_refresh:' + uid))
    m.add(InlineKeyboardButton('🔴 بازگشت به پنل مدیریت', callback_data='back_admin'))
    return m

def _lookup_restrict_keyboard(uid):
    uid = str(uid)
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton('🚫 مسدود دائم', callback_data='lookup_block_perm:' + uid),
        InlineKeyboardButton('⏱ مسدود موقت', callback_data='lookup_block_temp:' + uid),
        InlineKeyboardButton('🛍 محدودیت سفارش', callback_data='lookup_limit_orders:' + uid),
        InlineKeyboardButton('💰 محدودیت واریز', callback_data='lookup_limit_deposits:' + uid),
        InlineKeyboardButton('🔓 رفع همه محدودیت‌ها', callback_data='lookup_unlimit:' + uid),
        InlineKeyboardButton('🔙 برگشت به استعلام', callback_data='lookup_refresh:' + uid),
    )

def show_admin_panel(m):
    mkr=build_admin_keyboard(m.from_user.id)
    bot.send_message(m.chat.id,'🛠 <b>پنل مدیریت</b>\n🛍 <b>مدیریت سفارش‌ها</b> در صورت داشتن دسترسی در همین پنل نمایش داده می‌شود.',reply_markup=mkr)

@bot.message_handler(commands=['start'])
def start(m):
    raw=str(getattr(m,'text','') or '').split()
    start_arg=raw[1].strip() if len(raw)>1 else ''
    ref_id=start_arg[4:].strip() if start_arg.startswith('ref_') and start_arg[4:].strip().isdigit() else None
    d0=load(); is_new=str(m.from_user.id) not in d0.get('users',{})
    if not gate(m):return
    d=load(); uid=eff(m); u=user(d,uid,m.from_user if uid==real(m) else None)
    if is_new and uid==real(m) and ref_id and ref_id!=uid and ref_id in d.get('users',{}):
        u['referrer_id']=str(ref_id)
    save(d)
    ghost=admin(real(m)) and states.get(real(m),{}).get('ghost_target')
    if ghost:
        t=f'👻 <b>Ghost</b>\n🆔 <code>{uid}</code>\n🔑 CRV: <code>{u["crv_code"]}</code>\n👤 @{u.get("username","بدون نام")}\n💰 {int(u.get("balance",0)):,} تومان\n📦 سفارش‌ها: {len(u.get("orders",[]))}'
    else:
        t=d['settings'].get('welcome_text','به ربات خوش آمدید')+'\n\nاطلاعات شما نزد ما محفوظ است 💖'
    bot.send_message(m.chat.id,t,reply_markup=menu(real(m),bool(ghost)))

# Dedicated owner/developer callbacks are registered BEFORE the catch-all callback handler.
# This prevents the generic permission/router logic from swallowing the developer menu.
@bot.callback_query_handler(func=lambda c: c.data in ('developer','dev_admins','a_admins','admin_add','dev_lookup') or c.data.startswith(('admin_manage:','admin_perm:','admin_toggle:','admin_remove:','dev_lookup_toggle:')))
def owner_developer_callback(c):
    r = str(c.from_user.id)
    if not owner(r):
        bot.answer_callback_query(c.id, '⛔ فقط مالک اصلی دسترسی دارد.', show_alert=True)
        return
    try:
        d = load()
        data = c.data
        bot.answer_callback_query(c.id)

        if data == 'developer':
            show_developer_panel(c)
            return

        if data == 'dev_lookup':
            m = InlineKeyboardMarkup(row_width=1)
            admins = d.get('admins', {})
            if not admins:
                m.add(InlineKeyboardButton('— ادمینی وجود ندارد —', callback_data='dev_admins'))
            else:
                for aid, a in admins.items():
                    enabled = bool(a.get('permissions', {}).get('user_lookup', False) or a.get('permissions', {}).get('all', False))
                    label = ('🟢' if enabled else '🔴') + f' {a.get("name", aid)} | {aid}'
                    m.add(InlineKeyboardButton(label, callback_data='dev_lookup_toggle:' + str(aid)))
            m.add(InlineKeyboardButton('🔙 بازگشت به دولوپر', callback_data='back_developer'))
            show(c, '🔎 <b>دسترسی استعلام کاربران</b>\n\nبرای هر ادمین، با زدن دکمه می‌توانید دسترسی «استعلام کاربر» را روشن یا خاموش کنید.', m)
            return

        if data.startswith('dev_lookup_toggle:'):
            aid = data.split(':', 1)[1]
            a = d.get('admins', {}).get(aid)
            if not a:
                bot.answer_callback_query(c.id, 'ادمین پیدا نشد.', show_alert=True)
                return
            perms = a.setdefault('permissions', {})
            perms['user_lookup'] = not bool(perms.get('user_lookup', False))
            save(d)
            enabled = perms['user_lookup']
            bot.answer_callback_query(c.id, 'دسترسی فعال شد ✅' if enabled else 'دسترسی غیرفعال شد 🔴')
            m = InlineKeyboardMarkup(row_width=1)
            for xaid, xa in d.get('admins', {}).items():
                xenabled = bool(xa.get('permissions', {}).get('user_lookup', False) or xa.get('permissions', {}).get('all', False))
                m.add(InlineKeyboardButton(('🟢' if xenabled else '🔴') + f' {xa.get("name", xaid)} | {xaid}', callback_data='dev_lookup_toggle:' + str(xaid)))
            m.add(InlineKeyboardButton('🔙 بازگشت به دولوپر', callback_data='back_developer'))
            show(c, '🔎 <b>دسترسی استعلام کاربران</b>\n\n🟢 فعال = ادمین می‌تواند استعلام بگیرد.\n🔴 غیرفعال = دسترسی ندارد.', m)
            return

        if data in ('a_admins', 'dev_admins'):
            m = InlineKeyboardMarkup(row_width=2)
            m.add(InlineKeyboardButton('➕ افزودن ادمین', callback_data='admin_add'))
            for aid, a in d.get('admins', {}).items():
                status = '🟢' if a.get('active', False) else '🔴'
                m.add(InlineKeyboardButton(f'{status} {a.get("name", aid)} | {aid}', callback_data='admin_manage:' + str(aid)))
            m.add(InlineKeyboardButton('🔴 بازگشت', callback_data='back_developer'))
            show(c, '👑 <b>مدیریت ادمین‌ها</b>\n\nفقط مالک اصلی می‌تواند ادمین اضافه، حذف یا محدودیت‌ها را تغییر دهد.', m)
            return

        if data == 'admin_add':
            states[r] = {'wait': 'admin_add'}
            m = InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 لغو', callback_data='dev_admins'))
            show(c, '➕ <b>افزودن ادمین</b>\n\nآیدی عددی Telegram ادمین جدید را ارسال کنید:', m)
            return

        if data.startswith('admin_manage:'):
            aid = data.split(':', 1)[1]
            a = d.get('admins', {}).get(aid)
            if not a:
                bot.answer_callback_query(c.id, 'ادمین پیدا نشد.', show_alert=True)
                return
            m = InlineKeyboardMarkup(row_width=2)
            m.add(InlineKeyboardButton(('🟢 فعال' if a.get('active') else '🔴 غیرفعال'), callback_data='admin_toggle:' + aid),
                  InlineKeyboardButton('🗑 حذف ادمین', callback_data='admin_remove:' + aid))
            for key, label in PERMISSIONS.items():
                if key == 'admin_manage':
                    continue
                val = bool(a.get('permissions', {}).get(key, False))
                m.add(InlineKeyboardButton(('✅ ' if val else '⬜ ') + label, callback_data=f'admin_perm:{aid}:{key}'))
            m.add(InlineKeyboardButton('🔴 بازگشت', callback_data='dev_admins'))
            show(c, f'👤 <b>مدیریت ادمین</b>\n🆔 <code>{aid}</code>\n🏷 {a.get("name", "-")}\nوضعیت: {"فعال 🟢" if a.get("active") else "غیرفعال 🔴"}\n\nدسترسی‌ها را تک‌به‌تک روشن/خاموش کنید.', m)
            return

        if data.startswith('admin_perm:'):
            _, aid, key = data.split(':', 2)
            a = d.get('admins', {}).get(aid)
            if not a or key not in PERMISSIONS:
                bot.answer_callback_query(c.id, 'اطلاعات ادمین معتبر نیست.', show_alert=True)
                return
            a.setdefault('permissions', {})[key] = not bool(a.get('permissions', {}).get(key, False))
            save(d)
            show(c, f'👤 <b>مدیریت ادمین</b>\n🆔 <code>{aid}</code>', InlineKeyboardMarkup().add(
                InlineKeyboardButton('⚙️ مدیریت دسترسی‌ها', callback_data='admin_manage:' + aid),
                InlineKeyboardButton('🔴 بازگشت', callback_data='dev_admins')))
            return

        if data.startswith('admin_toggle:'):
            aid = data.split(':', 1)[1]
            a = d.get('admins', {}).get(aid)
            if not a:
                bot.answer_callback_query(c.id, 'ادمین پیدا نشد.', show_alert=True)
                return
            a['active'] = not bool(a.get('active'))
            save(d)
            show(c, '✅ وضعیت ادمین تغییر کرد.', InlineKeyboardMarkup().add(
                InlineKeyboardButton('⚙️ ادامه', callback_data='admin_manage:' + aid),
                InlineKeyboardButton('🔴 بازگشت', callback_data='dev_admins')))
            return

        if data.startswith('admin_remove:'):
            aid = data.split(':', 1)[1]
            if aid not in d.get('admins', {}):
                bot.answer_callback_query(c.id, 'ادمین پیدا نشد.', show_alert=True)
                return
            d['admins'].pop(aid, None)
            save(d)
            show(c, '🗑 ادمین حذف شد.', InlineKeyboardMarkup().add(InlineKeyboardButton('👑 مدیریت ادمین‌ها', callback_data='dev_admins')))
            return
    except Exception as e:
        try:
            bot.answer_callback_query(c.id, '❌ خطا در مدیریت ادمین‌ها؛ جزئیات برای مالک ارسال شد.', show_alert=True)
            bot.send_message(OWNER_ID, f'❌ <b>خطای مدیریت دولوپر</b>\n<code>{str(e)[:1500]}</code>')
        except Exception:
            pass

@bot.callback_query_handler(func=lambda c:True)
def cb(c):
    if c.data=='join_check':
        d=load();ok=joined(c.from_user.id,d);bot.answer_callback_query(c.id,'عضویت تأیید شد ✅' if ok else 'هنوز عضو نیستید',show_alert=not ok)
        if ok:show(c,'✅ عضویت تأیید شد.',menu(str(c.from_user.id)));return
    if not admin(c.from_user.id):
        d=load()
        if not d['settings'].get('bot_enabled', True):
            bot.answer_callback_query(c.id,'⏸ ربات موقتاً خاموش است.',show_alert=True);return
        u=user(d,eff(c),c.from_user)
        if blocked(u):bot.answer_callback_query(c.id,'حساب مسدود است.',show_alert=True);return
        if d['settings'].get('force_join') and not joined(c.from_user.id,d):bot.answer_callback_query(c.id,'ابتدا عضو کانال شوید.',show_alert=True);return
    d=load();r=real(c);uid=eff(c);u=user(d,uid,c.from_user)

    if admin(r) and not owner(r):
        perm=callback_perm(c.data)
        if not can(r,perm):
            bot.answer_callback_query(c.id,'⛔ این دسترسی برای شما فعال نیست.',show_alert=True);return
        audit(r,'اجرای عملیات',f'دکمه: <code>{c.data}</code> | دسترسی: <code>{perm}</code>')

    # Owner/developer callbacks are handled by owner_developer_callback above.
    if c.data == 'a_packs' and admin(r):
        m=InlineKeyboardMarkup(row_width=2)
        m.add(InlineKeyboardButton('➕ افزودن بسته',callback_data='p_add'))
        for pid,p in d.get('packs',{}).items():
            m.add(InlineKeyboardButton(f'✏️ {p.get("name",pid)}',callback_data='p_edit:'+pid),
                  InlineKeyboardButton('🗑 حذف',callback_data='p_del:'+pid))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'))
        show(c,'📦 <b>مدیریت بسته‌ها</b>\n\nیک بسته را برای ویرایش انتخاب کنید یا حذف کنید:',m)
        bot.answer_callback_query(c.id)
        return

    if c.data == 'a_discount' and admin(r):
        m=InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton('➕ ساخت کد تخفیف',callback_data='discount_add'))
        for dc,v in d.get('discounts',{}).items():
            m.add(InlineKeyboardButton(f'🎟 {dc} | {v.get("percent",0)}% | {v.get("used",0)}/{v.get("limit",0) or "∞"}',callback_data='discount_info:'+dc))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'))
        show(c,'🎟 <b>مدیریت کدهای تخفیف</b>',m)
        bot.answer_callback_query(c.id)
        return

    if c.data == 'a_stats' and admin(r):
        # Compact management dashboard: all values are calculated from the
        # current local DB, so it works identically on Railway and Termux.
        now_dt = datetime.now()
        today = now_dt.date()
        week_start = today - timedelta(days=6)

        def parse_dt(v):
            try:
                return datetime.strptime(str(v), '%Y-%m-%d %H:%M:%S')
            except Exception:
                return None

        users = d.get('users', {})
        orders = d.get('orders', {})
        deposits = d.get('deposits', {})
        tickets = d.get('tickets', {})
        private_chats = d.get('private_chats', {})

        def is_today(v):
            x = parse_dt(v)
            return bool(x and x.date() == today)

        def is_week(v):
            x = parse_dt(v)
            return bool(x and week_start <= x.date() <= today)

        total_users = len(users)
        new_today = sum(1 for u0 in users.values() if is_today(u0.get('created_at')))
        new_week = sum(1 for u0 in users.values() if is_week(u0.get('created_at')))
        active_service_users = sum(
            1 for u0 in users.values()
            if any(str(oc) in orders and orders[str(oc)].get('status') in ('approved', 'delivered')
                   for oc in u0.get('orders', []))
        )

        open_tickets = sum(1 for t0 in tickets.values() if t0.get('status') == 'open')
        ticket_waiting_admin = sum(1 for t0 in tickets.values()
                                   if t0.get('status') == 'open' and t0.get('turn') == 'admin')
        ticket_waiting_user = sum(1 for t0 in tickets.values()
                                  if t0.get('status') == 'open' and t0.get('turn') == 'user')

        open_private = sum(1 for ch0 in private_chats.values() if ch0.get('status') == 'open')
        private_waiting_admin = sum(1 for ch0 in private_chats.values()
                                    if ch0.get('status') == 'open' and ch0.get('turn') == 'admin')

        pending_orders = sum(1 for o0 in orders.values() if o0.get('status') == 'pending')
        approved_orders = sum(1 for o0 in orders.values() if o0.get('status') in ('approved', 'delivered'))
        today_orders = sum(1 for o0 in orders.values() if is_today(o0.get('created_at')))
        week_orders = sum(1 for o0 in orders.values() if is_week(o0.get('created_at')))
        today_sales = sum(int(o0.get('amount', 0) or 0) for o0 in orders.values()
                          if is_today(o0.get('created_at')) and o0.get('status') in ('approved', 'delivered'))
        week_sales = sum(int(o0.get('amount', 0) or 0) for o0 in orders.values()
                         if is_week(o0.get('created_at')) and o0.get('status') in ('approved', 'delivered'))

        pending_deposits = sum(1 for x0 in deposits.values() if x0.get('status') == 'pending')
        today_deposits = sum(int(x0.get('amount', 0) or 0) for x0 in deposits.values()
                             if is_today(x0.get('created_at')) and x0.get('status') == 'approved')
        week_deposits = sum(int(x0.get('amount', 0) or 0) for x0 in deposits.values()
                            if is_week(x0.get('created_at')) and x0.get('status') == 'approved')

        total_wallet = sum(int(u0.get('balance', 0) or 0) for u0 in users.values())
        alerts = []
        if open_tickets:
            alerts.append(f'🎫 {open_tickets} تیکت باز')
        if ticket_waiting_admin:
            alerts.append(f'🔴 {ticket_waiting_admin} تیکت منتظر پاسخ ادمین')
        if private_waiting_admin:
            alerts.append(f'💬 {private_waiting_admin} پیام خصوصی منتظر پاسخ ادمین')
        if pending_orders:
            alerts.append(f'🛒 {pending_orders} سفارش در انتظار بررسی')
        if pending_deposits:
            alerts.append(f'💳 {pending_deposits} واریز در انتظار بررسی')
        alert_text = '\n'.join('• ' + z for z in alerts) if alerts else '• مورد فوری برای بررسی وجود ندارد. ✅'

        text = (
            '📊 <b>داشبورد مدیریت</b> <code>30</code>\n'
            f'🕒 بروزرسانی: <code>{now()}</code>\n\n'
            '👥 <b>کاربران</b>\n'
            f'• کل کاربران: <b>{total_users:,}</b>\n'
            f'• کاربران جدید امروز: <b>{new_today:,}</b>\n'
            f'• کاربران جدید ۷ روز اخیر: <b>{new_week:,}</b>\n'
            f'• کاربران دارای سرویس تأییدشده: <b>{active_service_users:,}</b>\n\n'
            '💰 <b>مالی</b>\n'
            f'• موجودی کل کیف پول‌ها: <b>{total_wallet:,} تومان</b>\n'
            f'• فروش تأییدشده امروز: <b>{today_sales:,} تومان</b>\n'
            f'• فروش تأییدشده ۷ روز اخیر: <b>{week_sales:,} تومان</b>\n'
            f'• شارژ تأییدشده امروز: <b>{today_deposits:,} تومان</b>\n'
            f'• شارژ تأییدشده ۷ روز اخیر: <b>{week_deposits:,} تومان</b>\n\n'
            '🛒 <b>سفارش‌ها</b>\n'
            f'• سفارش‌های امروز: <b>{today_orders:,}</b>\n'
            f'• سفارش‌های ۷ روز اخیر: <b>{week_orders:,}</b>\n'
            f'• سفارش‌های تأیید/تحویل‌شده: <b>{approved_orders:,}</b>\n'
            f'• در انتظار بررسی: <b>{pending_orders:,}</b>\n\n'
            '🎫 <b>پشتیبانی</b>\n'
            f'• تیکت باز: <b>{open_tickets:,}</b>\n'
            f'• منتظر پاسخ ادمین: <b>{ticket_waiting_admin:,}</b>\n'
            f'• منتظر پاسخ کاربر: <b>{ticket_waiting_user:,}</b>\n'
            f'• چت خصوصی باز: <b>{open_private:,}</b>\n\n'
            '🔔 <b>هشدارهای مدیریتی</b>\n'
            f'{alert_text}'
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton('🔎 استعلام کاربر', callback_data='a_lookup'),
            InlineKeyboardButton('🎫 تیکت‌های باز', callback_data='a_tickets'),
        )
        kb.add(
            InlineKeyboardButton('💬 پیام خصوصی', callback_data='a_private'),
            InlineKeyboardButton('💳 واریزهای در انتظار', callback_data='a_wallet_requests'),
        )
        kb.add(
            InlineKeyboardButton('🛒 سفارش‌ها', callback_data='a_orders'),
            InlineKeyboardButton('🔄 بروزرسانی داشبورد', callback_data='a_stats'),
        )
        kb.add(InlineKeyboardButton('🔴 بازگشت به پنل مدیریت', callback_data='back_admin'))
        show(c, text, kb)
        bot.answer_callback_query(c.id, 'داشبورد بروزرسانی شد ✅')
        return

    if c.data == 'a_export' and admin(r):
        try:
            import zipfile
            base=os.path.dirname(os.path.abspath(__file__))
            stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
            export_path=os.path.join(base,f'Bot_full_{stamp}.zip')
            excluded_dirs={'__pycache__','.git'}
            excluded_files={'.env'}
            with zipfile.ZipFile(export_path,'w',zipfile.ZIP_DEFLATED) as zf:
                for dirpath,dirnames,filenames in os.walk(base):
                    dirnames[:]=[x for x in dirnames if x not in excluded_dirs]
                    for fn in filenames:
                        if fn in excluded_files or fn.startswith('.bot_update_') or fn==os.path.basename(export_path) or fn.lower().endswith('.zip'):
                            continue
                        full=os.path.join(dirpath,fn)
                        zf.write(full,os.path.relpath(full,base))
            with open(export_path,'rb') as f:
                bot.send_document(ADMIN_ID,f,caption='📦 فایل کامل ربات آماده شد.\n💾 شامل کد، دیتابیس، requirements و فایل‌های لازم است.\n🔐 .env و توکن داخل فایل قرار نگرفته‌اند.')
            os.remove(export_path)
            bot.answer_callback_query(c.id,'ZIP کامل ربات ارسال شد ✅')
        except Exception as e:
            bot.answer_callback_query(c.id,'ساخت ZIP ناموفق بود.',show_alert=True)
            bot.send_message(ADMIN_ID,f'❌ خطا در ساخت ZIP: {e}')
        return

    if c.data == 'a_update' and admin(r):
        states[r]={'wait':'update_py'}
        m=InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'))
        show(c,'📥 <b>آپدیت ربات</b>\n\nفایل Python نسخه جدید را به صورت <b>Document</b> ارسال کنید.\n\nقبل از جایگزینی:\n• از bot.py فعلی بکاپ گرفته می‌شود.\n• Syntax فایل جدید بررسی می‌شود.\n• <b>data.json و .env دست‌نخورده می‌مانند.</b>\n• در صورت موفقیت، ربات خودکار Restart می‌شود.',m)
        bot.answer_callback_query(c.id)
        return

    if c.data=='back_developer':
        states[r] = {}
        show(c, '👨‍💻 <b>مدیریت دولوپر</b>\n\nاین بخش فقط برای مالک اصلی ربات قابل دسترسی است.', InlineKeyboardMarkup().add(InlineKeyboardButton('👑 مدیریت ادمین‌ها', callback_data='dev_admins'), InlineKeyboardButton('🛠 پنل مدیریت', callback_data='admin'), InlineKeyboardButton('🔙 بازگشت', callback_data='main')))
        return
    if c.data=='back_main':
        states[r]={};show(c,'✨ WhiteLineVPN ✨',menu(r,bool(admin(r) and states.get(r,{}).get('ghost_target'))));return
    if c.data=='back_admin' and admin(r):
        states[r]={}
        show(c,'🛠 <b>پنل مدیریت</b>\n🆔 Admin ID: <code>'+str(ADMIN_ID)+'</code>',build_admin_keyboard(r));return
    if c.data=='main':show(c,'✨ WhiteLineVPN ✨',menu(r,bool(admin(r) and states.get(r,{}).get('ghost_target'))))
    elif c.data=='referral':
        link=get_referral_link(real(c))
        if not link:
            show(c,'❌ ساخت لینک دعوت موقتاً امکان‌پذیر نیست.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
            return
        refs=[x for x in d.get('users',{}).values() if str(x.get('referrer_id',''))==str(uid)]
        claimed=sum(1 for x in refs if x.get('referral_reward_claimed'))
        total_reward=sum(int(x.get('reward',0)) for x in d.get('referral_rewards',{}).values() if str(x.get('referrer_id',''))==str(uid))
        text=(f'👥 <b>دعوت دوستان</b>\n\n🔗 لینک اختصاصی شما:\n<code>{link}</code>\n\n'
              f'👤 دعوت‌شده‌ها: <b>{len(refs)}</b>\n🎁 هدیه‌های دریافت‌شده: <b>{claimed}</b>\n'
              f'💰 مجموع هدیه دریافتی: <b>{total_reward:,} تومان</b>\n\n'
              f'با خرید موفق هر دعوت‌شده، <b>{int(d["settings"].get("referral_percent",10))}% مبلغ خرید</b> به کیف پول شما اضافه می‌شود.\n'
              f'⚠️ افزایش موجودی کیف پول شامل هدیه نمی‌شود؛ فقط خرید موفق حساب می‌شود و حداکثر <b>{int(d["settings"].get("referral_max_rewards",1))} بار</b> برای هر دعوت‌شده پاداش پرداخت می‌شود.')
        show(c,text,InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data=='buy':
        if limited(u,'orders'):bot.answer_callback_query(c.id,'ثبت سفارش محدود شده.',show_alert=True);return
        m=InlineKeyboardMarkup();
        for pid,p in d['packs'].items():
            if p.get('active',True):m.add(InlineKeyboardButton(f'📦 {p.get("name","")} {p.get("volume","")} {p.get("duration","")} {int(p.get("price",0)):,} تومان',callback_data='pack:'+pid))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main'));show(c,'📦 بسته مورد نظر را انتخاب کنید:',m)
    elif c.data.startswith('pack:'):
        pid=c.data[5:];p=d['packs'].get(pid)
        if not p:return
        m=InlineKeyboardMarkup();m.add(InlineKeyboardButton('🎟 اعمال کد تخفیف',callback_data='discount_use:'+pid),InlineKeyboardButton('🛍 خرید',callback_data='checkout:'+pid),InlineKeyboardButton('🔴 بازگشت',callback_data='buy'));show(c,f'📦 <b>{p.get("name")}</b>\n💰 {int(p.get("price",0)):,} تومان\n📐 {p.get("volume","-")}\n⏳ {p.get("duration","-")}\n📝 {p.get("desc","-")}',m)
    elif c.data.startswith('discount_use:'):
        pid=c.data.split(':',1)[1];states[r]={'wait':'discount_apply','pid':pid};show(c,'🎟 کد تخفیف را وارد کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='pack:'+pid)))
    elif c.data.startswith('checkout:'):

        pid=c.data[9:];p=d['packs'].get(pid);price=int(p.get('price',0));co=states.get(r,{}).get('checkout',{});amount=int(co.get('amount',price));dc=co.get('discount_code','');states.setdefault(r,{})['checkout']={'pid':pid,'amount':amount,'original_price':price,'discount_code':dc};m=InlineKeyboardMarkup().add(InlineKeyboardButton('💰 کیف پول',callback_data='wallet:'+pid),InlineKeyboardButton('💳 کارت به کارت',callback_data='card:'+pid));m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='pack:'+pid));text=f'💰 مبلغ: <b>{amount:,} تومان</b>' if amount==price or not dc else f'💰 مبلغ اصلی: <s>{price:,} تومان</s>\n🎟 تخفیف: <b>{price-amount:,} تومان</b>\n💰 مبلغ نهایی: <b>{amount:,} تومان</b>';show(c,text+'\nروش پرداخت:',m)
    elif c.data.startswith('wallet:'):
        if limited(u,'orders'):bot.answer_callback_query(c.id,'ثبت سفارش محدود شده.',show_alert=True);return
        pid=c.data[7:];amount=int(states.get(r,{}).get('checkout',{}).get('amount',d['packs'].get(pid,{}).get('price',0)))
        if int(u.get('balance',0))<amount:bot.answer_callback_query(c.id,'موجودی کافی نیست.',show_alert=True);return
        # برداشت کیف پول قبل از ایجاد سفارش، برای جلوگیری از ثبت چند سفارش با یک موجودی
        u['balance']-=amount
        dc=states.get(r,{}).get('checkout',{}).get('discount_code')
        if dc and dc in d.get('discounts',{}):d['discounts'][dc]['used']=int(d['discounts'][dc].get('used',0))+1
        oc=code('ORD',d['orders'])
        d['orders'][oc]={'code':oc,'user_id':uid,'pack_id':pid,'amount':amount,'payment_method':'wallet','payment_status':'paid','status':'pending','discount_code':dc or None,'created_at':now()}
        u['orders'].append(oc)
        mk=InlineKeyboardMarkup().add(InlineKeyboardButton('✅ تایید',callback_data='adm_approve:'+oc),InlineKeyboardButton('❌ رد و استرداد',callback_data='adm_reject:'+oc))
        save(d)
        bot.send_message(ADMIN_ID,f'🛍 <b>سفارش کیف پول جدید</b>\n🆔 {oc}\nکاربر: <code>{uid}</code>\nCRV: <code>{u["crv_code"]}</code>\nبسته: {d["packs"][pid]["name"]}\n💰 مبلغ: {amount:,} تومان\n💳 مبلغ از کیف پول مشتری کسر شده است.',reply_markup=mk)
        show(c,f'✅ سفارش ثبت شد\n🆔 <code>{oc}</code>\n💰 مبلغ از کیف پول شما کسر شد و پس از بررسی ارسال می‌شود.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data.startswith('card:'):
        pid=c.data[5:];amount=int(states.get(r,{}).get('checkout',{}).get('amount',d['packs'].get(pid,{}).get('price',0)));states[r]={'wait':'order_receipt','pid':pid,'amount':amount,'discount_code':states.get(r,{}).get('checkout',{}).get('discount_code','')};s=d['settings'];show(c,f'💳 شماره کارت: <code>{s.get("card_number","")}</code>\n👤 {s.get("card_holder","")}\n💰 {amount:,} تومان\n\n📥 عکس رسید را ارسال کنید.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='checkout:'+pid)))
    elif c.data=='ghost_balance' and admin(r) and states.get(r,{}).get('ghost_target'):
        target=states[r]['ghost_target'];gu=d['users'].get(target)
        if not gu: bot.answer_callback_query(c.id,'❌ کاربر Ghost پیدا نشد.',show_alert=True);return
        bm=InlineKeyboardMarkup(row_width=2)
        bm.add(InlineKeyboardButton('➕ افزایش موجودی',callback_data='ghost_balance_add'),InlineKeyboardButton('➖ کاهش موجودی',callback_data='ghost_balance_sub'))
        bm.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main'))
        show(c,f'👻 <b>مدیریت موجودی</b>\nکاربر: <code>{target}</code>\n💰 موجودی فعلی: <b>{int(gu.get("balance",0)):,} تومان</b>',bm)
    elif c.data=='bal':
        bm=InlineKeyboardMarkup(row_width=2)
        if admin(r) and states.get(r,{}).get('ghost_target'):
            bm.add(InlineKeyboardButton('➕ افزایش موجودی',callback_data='ghost_balance_add'),InlineKeyboardButton('➖ کاهش موجودی',callback_data='ghost_balance_sub'))
        else: bm.add(InlineKeyboardButton('➕ افزایش موجودی',callback_data='deposit'))
        bm.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main'))
        show(c,f'💰 موجودی: <b>{int(u.get("balance",0)):,} تومان</b>\nحداقل واریز: {int(d["settings"].get("min_deposit",0)):,}',bm)
    elif c.data=='deposit':
        if limited(u,'deposits'):bot.answer_callback_query(c.id,'افزایش موجودی محدود شده.',show_alert=True);return
        states[r]={'wait':'dep_amount'};show(c,'💵 مبلغ واریز را به تومان وارد کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data=='packs':
        rows=[];m=InlineKeyboardMarkup(row_width=1)
        ghost_active=admin(r) and bool(states.get(r,{}).get('ghost_target'))
        for oc in u.get('orders',[]):
            if oc in u.get('hidden_packs',[]):
                continue
            o=d['orders'].get(oc,{})
            if o.get('status') in ('approved','delivered'):
                p=d['packs'].get(o.get('pack_id'),{})
                rows.append((oc,p,o))
                if ghost_active:
                    m.add(InlineKeyboardButton(f'✏️ {p.get("name", "بسته")} | {oc}',callback_data='ghost_pack:'+oc))
                else:
                    m.add(InlineKeyboardButton(f'📦 {p.get("name", "بسته")} | {oc}',callback_data='pack_view:'+oc))
        if ghost_active:
            deleted=[oc for oc in u.get('hidden_packs',[]) if oc in d.get('orders',{})]
            if deleted:
                m.add(InlineKeyboardButton(f'🗑 حذف شده‌ها ({len(deleted)})',callback_data='ghost_deleted'))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main'))
        show(c,'📦 <b>بسته‌های من</b>\n\nبرای مشاهده مشخصات، بسته موردنظر را انتخاب کنید.' if rows else '📦 <b>بسته‌های من</b>\n\nبسته‌ای ندارید.',m)
    elif c.data.startswith('pack_view:'):
        oc=c.data[10:]
        if oc not in u.get('orders',[]) or oc in u.get('hidden_packs',[]):
            bot.answer_callback_query(c.id,'❌ این بسته در دسترس نیست.',show_alert=True);return
        o=d['orders'].get(oc,{})
        if o.get('status') not in ('approved','delivered'):
            bot.answer_callback_query(c.id,'❌ این بسته هنوز قابل مشاهده نیست.',show_alert=True);return
        p=d['packs'].get(o.get('pack_id'),{})
        m=InlineKeyboardMarkup(row_width=1)
        m.add(InlineKeyboardButton('🗑 حذف این بسته',callback_data='hide_confirm:'+oc))
        m.add(InlineKeyboardButton('🔴 بازگشت به بسته‌های من',callback_data='packs'))
        show(c,f'📦 <b>مشخصات بسته</b>\n\n🏷 نام: <b>{p.get("name", "-")}</b>\n🆔 سفارش: <code>{oc}</code>\n📐 حجم: {p.get("volume", "-")}\n⏳ مدت: {p.get("duration", "-")}\n📝 توضیحات: {p.get("desc", "-")}\n\n🔗 <b>مشخصات/لینک:</b>\n<code>{o.get("config") or "ثبت نشده"}</code>',m)
    elif c.data.startswith('hide_confirm:'):
        oc=c.data[13:]
        if oc not in u.get('orders',[]) or oc in u.get('hidden_packs',[]):
            bot.answer_callback_query(c.id,'❌ این بسته در دسترس نیست.',show_alert=True);return
        o=d['orders'].get(oc,{})
        p=d['packs'].get(o.get('pack_id'),{})
        m=InlineKeyboardMarkup(row_width=2)
        m.add(InlineKeyboardButton('✅ بله، حذف کن',callback_data='hide_yes:'+oc),InlineKeyboardButton('❌ لغو',callback_data='pack_view:'+oc))
        show(c,f'⚠️ <b>مطمئنی می‌خواهی این بسته را حذف کنی؟</b>\n\n📦 {p.get("name", "-")}\n🆔 <code>{oc}</code>\n\nبا حذف، بسته فقط از بخش «بسته‌های من» شما مخفی می‌شود.',m)
    elif c.data.startswith('hide_yes:'):
        oc=c.data[9:]
        if oc not in u.get('orders',[]) or oc in u.get('hidden_packs',[]):
            bot.answer_callback_query(c.id,'❌ این بسته قبلاً حذف شده یا در دسترس نیست.',show_alert=True);return
        o=d['orders'].get(oc,{})
        p=d['packs'].get(o.get('pack_id'),{})
        u.setdefault('hidden_packs',[]).append(oc)
        save(d)
        try:
            bot.send_message(ADMIN_ID,f'🗑 <b>حذف بسته توسط کاربر</b>\n\n👤 کاربر: <code>{uid}</code>\n🔑 CRV: <code>{u.get("crv_code", "")}</code>\n📦 بسته: {p.get("name", "-")}\n🆔 سفارش: <code>{oc}</code>\n\nℹ️ بسته از «بسته‌های من» کاربر مخفی شد.')
        except Exception:
            pass
        bot.answer_callback_query(c.id,'بسته با موفقیت حذف شد ✅')
        show(c,'✅ بسته از «بسته‌های من» حذف شد.',InlineKeyboardMarkup().add(InlineKeyboardButton('📦 بسته‌های من',callback_data='packs'),InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data == 'ghost_deleted' and admin(r) and states.get(r,{}).get('ghost_target'):
        target=str(states[r].get('ghost_target'));gu=d['users'].get(target,{})
        m=InlineKeyboardMarkup(row_width=1)
        deleted=[oc for oc in gu.get('hidden_packs',[]) if oc in d.get('orders',{}) and str(d['orders'][oc].get('user_id'))==target]
        for oc in deleted:
            o=d['orders'].get(oc,{});p=d['packs'].get(o.get('pack_id'),{})
            m.add(InlineKeyboardButton(f'♻️ {p.get("name","بسته")} | {oc}',callback_data='ghost_restore:'+oc))
        m.add(InlineKeyboardButton('🔴 بازگشت به بسته‌های من',callback_data='packs'))
        show(c,'🗑 <b>بسته‌های حذف‌شده کاربر</b>\n\nبرای بازگردانی، بسته موردنظر را انتخاب کنید.',m)
    elif c.data.startswith('ghost_restore:') and admin(r) and states.get(r,{}).get('ghost_target'):
        oc=c.data[14:];target=str(states[r].get('ghost_target'));gu=d['users'].get(target,{});o=d['orders'].get(oc,{})
        if str(o.get('user_id'))!=target or oc not in gu.get('hidden_packs',[]):
            bot.answer_callback_query(c.id,'❌ بسته حذف‌شده پیدا نشد.',show_alert=True);return
        gu['hidden_packs'].remove(oc);save(d)
        bot.answer_callback_query(c.id,'بسته بازگردانی شد ✅');show(c,'♻️ بسته با موفقیت بازگردانی شد.',InlineKeyboardMarkup().add(InlineKeyboardButton('📦 بسته‌های من',callback_data='packs')))
    elif c.data.startswith('ghost_pack:') and admin(r) and states.get(r,{}).get('ghost_target'):
        oc=c.data[11:];o=d['orders'].get(oc,{}) ;target=str(states[r].get('ghost_target'))
        if str(o.get('user_id'))!=target or o.get('status') not in ('approved','delivered'):
            bot.answer_callback_query(c.id,'❌ بسته متعلق به کاربر Ghost نیست.',show_alert=True);return
        p=d['packs'].get(o.get('pack_id'),{});m=InlineKeyboardMarkup(row_width=2)
        m.add(InlineKeyboardButton('✏️ ویرایش مشخصات',callback_data='ghost_edit:'+oc),InlineKeyboardButton('🗑 حذف بسته',callback_data='ghost_delete_confirm:'+oc))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='packs'))
        show(c,f'📦 <b>مدیریت بسته کاربر</b>\n📦 {p.get("name","")}\n🆔 سفارش: <code>{oc}</code>\n\nمشخصات/لینک فعلی:\n<code>{o.get("config") or "ثبت نشده"}</code>',m)
    elif c.data.startswith('ghost_edit:') and admin(r) and states.get(r,{}).get('ghost_target'):
        oc=c.data[11:];target=str(states[r].get('ghost_target'));o=d['orders'].get(oc,{})
        if str(o.get('user_id'))!=target or o.get('status') not in ('approved','delivered'):
            bot.answer_callback_query(c.id,'❌ بسته معتبر نیست.',show_alert=True);return
        p=d['packs'].get(o.get('pack_id'),{});states[r]={'ghost_target':target,'wait':'ghost_pack_edit','order':oc}
        show(c,f'✏️ <b>ویرایش بسته کاربر</b>\n📦 {p.get("name","")}\n🆔 سفارش: <code>{oc}</code>\n\nمشخصات/لینک فعلی:\n<code>{o.get("config") or "ثبت نشده"}</code>\n\n📥 مشخصات جدید را در یک پیام ارسال کنید.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='ghost_pack:'+oc)))
    elif c.data.startswith('ghost_delete_confirm:') and admin(r) and states.get(r,{}).get('ghost_target'):
        oc=c.data[len('ghost_delete_confirm:'):];target=str(states[r].get('ghost_target'));o=d['orders'].get(oc,{})
        if str(o.get('user_id'))!=target or oc not in d['users'].get(target,{}).get('orders',[]):
            bot.answer_callback_query(c.id,'❌ بسته معتبر نیست.',show_alert=True);return
        p=d['packs'].get(o.get('pack_id'),{});m=InlineKeyboardMarkup(row_width=2)
        m.add(InlineKeyboardButton('✅ بله، حذف کن',callback_data='ghost_delete_yes:'+oc),InlineKeyboardButton('❌ لغو',callback_data='ghost_pack:'+oc))
        show(c,f'⚠️ <b>حذف بسته در Ghost</b>\n\nمطمئنی می‌خواهی این بسته را حذف کنی؟\n📦 {p.get("name","-")}\n🆔 <code>{oc}</code>',m)
    elif c.data.startswith('ghost_delete_yes:') and admin(r) and states.get(r,{}).get('ghost_target'):
        oc=c.data[len('ghost_delete_yes:'):];target=str(states[r].get('ghost_target'));gu=d['users'].get(target,{});o=d['orders'].get(oc,{})
        if str(o.get('user_id'))!=target or oc not in gu.get('orders',[]):
            bot.answer_callback_query(c.id,'❌ بسته معتبر نیست.',show_alert=True);return
        if oc not in gu.setdefault('hidden_packs',[]): gu['hidden_packs'].append(oc)
        save(d)
        bot.answer_callback_query(c.id,'بسته حذف شد ✅');show(c,'🗑 بسته از بسته‌های کاربر حذف شد.',InlineKeyboardMarkup().add(InlineKeyboardButton('📦 بسته‌های من',callback_data='packs')))
    elif c.data.startswith('hide:'):
        oc=c.data[5:]
        if oc in u.get('orders',[]) and oc not in u.setdefault('hidden_packs',[]):u['hidden_packs'].append(oc);save(d)
        bot.answer_callback_query(c.id,'از فهرست حذف شد.');show(c,'📦 بسته‌های من',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))

    elif c.data=='ghost_balance_add' and admin(r) and states.get(r,{}).get('ghost_target'):
        states[r]['wait']='ghost_balance_add'; bot.send_message(c.message.chat.id,'➕ مبلغ افزایش موجودی را به تومان وارد کنید:')
    elif c.data=='ghost_balance_sub' and admin(r) and states.get(r,{}).get('ghost_target'):
        states[r]['wait']='ghost_balance_sub'; bot.send_message(c.message.chat.id,'➖ مبلغ کاهش موجودی را به تومان وارد کنید:')
    elif c.data=='info':show(c,f'⚙️ اطلاعات حساب\n🔑 CRV: <code>{u["crv_code"]}</code>\n🆔 ID: <code>{uid}</code>\n👤 @{u.get("username","بدون نام")}\n💰 {int(u.get("balance",0)):,} تومان\n📦 سفارش: {len(u.get("orders",[]))}',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data=='track':states[r]={'wait':'track'};show(c,'🔍 کد سفارش را ارسال کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data=='guide':show(c,d['settings'].get('guide_text','راهنما تنظیم نشده.'),InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data=='rules':show(c,d['settings'].get('rules_text','قوانین تنظیم نشده است.'),InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data=='free':
        fc=d['settings'].get('free_config','').strip()
        text='🎁 <b>کانفیگ رایگان</b>\n\n'+(html.escape(fc) if fc else 'در حال حاضر کانفیگ رایگان تنظیم نشده است.')
        show(c,text,InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main')))
    elif c.data=='contact':
        m=InlineKeyboardMarkup(row_width=1)
        m.add(
            InlineKeyboardButton('🎫 ثبت تیکت',callback_data='ticket_new'),
            InlineKeyboardButton('🔎 پیگیری تیکت',callback_data='ticket_track'),
            InlineKeyboardButton('📁 تیکت‌های بسته‌شده',callback_data='ticket_closed')
        )
        admin_link=d['settings'].get('admin_link','').strip()
        if admin_link:
            m.add(InlineKeyboardButton('💬 ارتباط مستقیم با ادمین',url=admin_link))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_main'))
        show(c,'📞 <b>ارتباط با ما</b>\n\nیکی از گزینه‌های زیر را انتخاب کنید:',m)
    elif c.data=='ticket_new':states[r]={'wait':'ticket_subject'};show(c,'🎫 موضوع تیکت را بنویسید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='contact')))
    elif c.data=='ticket_track':states[r]={'wait':'ticket_track'};show(c,'🔎 کد تیکت را وارد کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='contact')))
    elif c.data.startswith('ticket_reply:'):
        tc=c.data.split(':',1)[1];t=d.get('tickets',{}).get(tc,{})
        if not t or str(t.get('user_id'))!=str(uid) or t.get('status')!='open':
            bot.answer_callback_query(c.id,'❌ این تیکت بسته شده یا پیدا نشد.',show_alert=True);return
        if t.get('turn','admin')!='user':
            bot.answer_callback_query(c.id,'⏳ فعلاً منتظر پاسخ ادمین باشید.',show_alert=True);return
        states[r]={'wait':'ticket_user_reply','ticket':tc}
        show(c,f'↩️ <b>پاسخ به تیکت {tc}</b>\nموضوع: {t.get("subject","-")}\n\n📥 متن پاسخ خود را ارسال کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 لغو',callback_data='contact')))
    elif c.data=='ticket_closed':
        ts=[t for t in d['tickets'].values() if str(t.get('user_id'))==str(uid) and t.get('status')=='closed'];show(c,'📁 تیکت‌های بسته‌شده\n\n'+('\n\n'.join(f'<code>{t["code"]}</code>\nموضوع: {t.get("subject")}\nآخرین پاسخ: {t.get("answer") or "-"}' for t in ts) if ts else 'موردی نیست.'),InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='contact')))
    elif c.data=='admin' and admin(r):
        show(c,'🛠 <b>پنل مدیریت</b>\n🆔 Admin ID: <code>'+str(ADMIN_ID)+'</code>',build_admin_keyboard(r))
    elif c.data=='a_wallet_add' and admin(r):
        if not can(r,'wallet_add'):
            bot.answer_callback_query(c.id,'⛔ دسترسی افزایش موجودی کیف پول برای شما فعال نیست.',show_alert=True);return
        states[r]={'wait':'wallet_target'}
        show(c,'➕ <b>افزایش موجودی کیف پول</b>\n\nآیدی عددی کاربر یا CRV او را ارسال کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data in ('a_deposits','a_wallet_requests') and admin(r):
        if not can(r,'wallet_requests'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت واریزها برای شما فعال نیست.',show_alert=True);return
        m=InlineKeyboardMarkup(row_width=1)
        deps=d.get('deposits',{})
        counts={k:sum(1 for x in deps.values() if x.get('status')==k) for k in ('pending','approved','rejected')}
        m.add(InlineKeyboardButton(f'⏳ واریزهای در انتظار تایید ({counts["pending"]})',callback_data='deps_status:pending:0'))
        m.add(InlineKeyboardButton(f'✅ واریزهای تایید شده ({counts["approved"]})',callback_data='deps_status:approved:0'))
        m.add(InlineKeyboardButton(f'❌ واریزهای رد شده ({counts["rejected"]})',callback_data='deps_status:rejected:0'))
        m.add(InlineKeyboardButton('🔴 پنل مدیریت',callback_data='back_admin'))
        show(c,'💳 <b>مدیریت واریزها / شارژ کیف پول</b>\n\nهر شارژ یک شناسه اختصاصی مانند <code>DEP-XXXXXXXX</code> دارد و قابل رهگیری است.',m)
    elif c.data.startswith('deps_status:') and admin(r):
        if not can(r,'wallet_requests'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت درخواست‌های افزایش موجودی برای شما فعال نیست.',show_alert=True);return
        parts=c.data.split(':'); status=parts[1]; page=int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 0
        labels={'pending':'در انتظار تایید','approved':'تایید شده','rejected':'رد شده'}
        m=InlineKeyboardMarkup(row_width=1)
        items=[x for x in d.get('deposits',{}).values() if x.get('status')==status]
        items.sort(key=lambda z:z.get('created_at',''),reverse=True)
        page_size=20; start=page*page_size; page_items=items[start:start+page_size]
        for x in page_items:
            m.add(InlineKeyboardButton(f'{x.get("code")} | کاربر {x.get("user_id")} | {int(x.get("amount",0)):,} تومان',callback_data='dep_view:'+str(x.get('code'))))
        if not items:m.add(InlineKeyboardButton('— موردی نیست —',callback_data='a_wallet_requests'))
        nav=[]
        if page>0: nav.append(InlineKeyboardButton('⬅️ قبلی',callback_data=f'deps_status:{status}:{page-1}'))
        if start+page_size<len(items): nav.append(InlineKeyboardButton('➡️ بعدی',callback_data=f'deps_status:{status}:{page+1}'))
        if nav: m.row(*nav)
        m.add(InlineKeyboardButton('🔙 مدیریت افزایش موجودی',callback_data='a_wallet_requests'),InlineKeyboardButton('🔴 پنل مدیریت',callback_data='back_admin'))
        show(c,f'📋 <b>واریزهای {labels.get(status,status)}</b>\n\nشناسه هر واریز قابل استفاده در رهگیری است:',m)
    elif c.data.startswith('dep_view:') and admin(r):
        if not can(r,'wallet_requests'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت واریزها برای شما فعال نیست.',show_alert=True);return
        dc=c.data.split(':',1)[1];x=d.get('deposits',{}).get(dc)
        if not x:
            bot.answer_callback_query(c.id,'❌ واریز پیدا نشد.',show_alert=True);return
        uu=d.get('users',{}).get(str(x.get('user_id')),{});st=x.get('status','-')
        sf={'pending':'⏳ در انتظار تایید','approved':'✅ تایید شده','rejected':'❌ رد شده'}.get(st,st)
        m=InlineKeyboardMarkup(row_width=2)
        if st=='pending':
            m.add(InlineKeyboardButton('✅ تایید',callback_data='dep_ok:'+dc),InlineKeyboardButton('❌ رد',callback_data='dep_no:'+dc))
        elif st=='rejected' and can(r,'wallet_requests'):
            m.add(InlineKeyboardButton('♻️ تایید مجدد درخواست رد شده',callback_data='dep_reapprove:'+dc))
        if x.get('receipt_file_id'):
            m.add(InlineKeyboardButton('🧾 مشاهده رسید',callback_data='dep_receipt:'+dc))
        m.add(InlineKeyboardButton('🔙 لیست افزایش موجودی',callback_data='deps_status:'+st+':0'),InlineKeyboardButton('🔴 مدیریت افزایش موجودی',callback_data='a_wallet_requests'))
        actor=x.get('approved_by') or x.get('rejected_by') or x.get('admin_id') or '-'
        show(c,f'💳 <b>جزئیات درخواست افزایش موجودی</b>\n\n🆔 شناسه اختصاصی: <code>{dc}</code>\n👤 کاربر: <code>{x.get("user_id")}</code>\n🔑 CRV: <code>{uu.get("crv_code","")}</code>\n👤 نام کاربری: @{uu.get("username","بدون نام") if uu.get("username") not in ("","بدون نام") else "بدون نام"}\n💰 مبلغ: <b>{int(x.get("amount",0)):,} تومان</b>\n💳 روش: {x.get("payment_method","کارت به کارت")}\n📌 وضعیت: <b>{sf}</b>\n🕒 ثبت: {x.get("created_at","-")}\n🕒 تایید: {x.get("approved_at","-")}\n🕒 رد: {x.get("rejected_at","-")}\n👨‍💼 اپراتور: <code>{actor}</code>\n📝 توضیح: {x.get("note","-")}',m)
    elif c.data=='a_orders' and admin(r):
        m=InlineKeyboardMarkup(row_width=1)
        orders=d.get('orders',{})
        counts={k:sum(1 for o in orders.values() if o.get('status')==k) for k in ('approved','pending','rejected')}
        m.add(InlineKeyboardButton(f'✅ سفارش‌های تایید شده ({counts["approved"]})',callback_data='orders_status:approved'))
        m.add(InlineKeyboardButton(f'⏳ سفارش‌های در انتظار تایید ({counts["pending"]})',callback_data='orders_status:pending'))
        m.add(InlineKeyboardButton(f'❌ سفارش‌های رد شده ({counts["rejected"]})',callback_data='orders_status:rejected'))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'))
        show(c,'🛍 <b>مدیریت سفارش‌ها</b>\n\nوضعیت سفارش‌ها را انتخاب کنید:',m)
    elif c.data.startswith('orders_status:') and admin(r):
        status=c.data.split(':',1)[1]
        labels={'approved':'تایید شده','pending':'در انتظار تایید','rejected':'رد شده'}
        m=InlineKeyboardMarkup(row_width=1)
        items=[o for o in d.get('orders',{}).values() if o.get('status')==status]
        items.sort(key=lambda z:z.get('created_at',''),reverse=True)
        for o in items[:100]:
            p=d.get('packs',{}).get(o.get('pack_id'),{})
            m.add(InlineKeyboardButton(f'{o.get("code")} | {p.get("name","بسته")} | {int(o.get("amount",0)):,} تومان',callback_data='order_view:'+str(o.get('code'))))
        if not items: m.add(InlineKeyboardButton('— موردی نیست —',callback_data='a_orders'))
        m.add(InlineKeyboardButton('🔙 مدیریت سفارش‌ها',callback_data='a_orders'),InlineKeyboardButton('🔴 پنل مدیریت',callback_data='back_admin'))
        show(c,f'📋 <b>سفارش‌های {labels.get(status,status)}</b>\n\nبرای مشاهده جزئیات، سفارش را انتخاب کنید:',m)
    elif c.data.startswith('order_view:') and admin(r):
        oc=c.data.split(':',1)[1];o=d.get('orders',{}).get(oc)
        if not o:
            bot.answer_callback_query(c.id,'❌ سفارش پیدا نشد.',show_alert=True);return
        p=d.get('packs',{}).get(o.get('pack_id'),{});uu=d.get('users',{}).get(str(o.get('user_id')),{});status=o.get('status','-')
        status_fa={'approved':'✅ تایید شده','pending':'⏳ در انتظار تایید','rejected':'❌ رد شده','delivered':'📦 تحویل شده'}.get(status,status)
        m=InlineKeyboardMarkup(row_width=2)
        if status=='pending':
            m.add(InlineKeyboardButton('✅ تایید',callback_data='adm_approve:'+oc),InlineKeyboardButton('❌ رد',callback_data='adm_reject:'+oc))
        elif status=='rejected' and can(r,'order_reapprove'):
            m.add(InlineKeyboardButton('♻️ تایید مجدد سفارش رد شده',callback_data='order_reapprove:'+oc))
        if o.get('payment_method')=='card' and o.get('receipt_file_id'):
            m.add(InlineKeyboardButton('🧾 مشاهده رسید پرداخت',callback_data='order_receipt:'+oc))
        m.add(InlineKeyboardButton('🔙 لیست سفارش‌ها',callback_data='orders_status:'+status),InlineKeyboardButton('🔴 مدیریت سفارش‌ها',callback_data='a_orders'))
        text=(f'🛍 <b>جزئیات سفارش</b>\n\n🆔 سفارش: <code>{oc}</code>\n👤 کاربر: <code>{o.get("user_id")}</code>\n🔑 CRV: <code>{uu.get("crv_code","")}</code>\n📦 بسته: {p.get("name","-")}\n💰 مبلغ: {int(o.get("amount",0)):,} تومان\n💳 روش پرداخت: {o.get("payment_method","-")}\n📌 وضعیت: <b>{status_fa}</b>\n🕒 {o.get("created_at","-")}')
        show(c,text,m)
    elif c.data.startswith('order_receipt:') and admin(r):
        if not can(r,'orders'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت سفارش‌ها برای شما فعال نیست.',show_alert=True);return
        oc=c.data.split(':',1)[1];o=d.get('orders',{}).get(oc)
        if not o:
            bot.answer_callback_query(c.id,'❌ سفارش پیدا نشد.',show_alert=True);return
        if o.get('payment_method')!='card' or not o.get('receipt_file_id'):
            bot.answer_callback_query(c.id,'🧾 رسیدی برای این سفارش ثبت نشده است.',show_alert=True);return
        try:
            bot.send_photo(r,o['receipt_file_id'],caption=f'🧾 <b>رسید پرداخت سفارش</b>\n🆔 سفارش: <code>{oc}</code>\n👤 کاربر: <code>{o.get("user_id")}</code>\n💰 مبلغ: {int(o.get("amount",0)):,} تومان')
            bot.answer_callback_query(c.id,'🧾 رسید پرداخت ارسال شد.')
        except Exception:
            bot.answer_callback_query(c.id,'❌ ارسال رسید ناموفق بود.',show_alert=True)
        return
    elif c.data.startswith('order_reapprove:') and admin(r):
        oc=c.data.split(':',1)[1]
        if not can(r,'order_reapprove'):
            bot.answer_callback_query(c.id,'⛔ دسترسی تایید مجدد سفارش رد شده برای شما فعال نیست.',show_alert=True);return
        o=d.get('orders',{}).get(oc)
        if not o:
            bot.answer_callback_query(c.id,'❌ سفارش پیدا نشد.',show_alert=True);return
        if o.get('status')!='rejected':
            bot.answer_callback_query(c.id,'⚠️ فقط سفارش رد شده را می‌توان دوباره تایید کرد.',show_alert=True);return
        # Wallet orders were refunded on rejection; charge again when re-approved.
        if o.get('payment_method')=='wallet' and int(o.get('refunded_amount',0))>0:
            target=d.get('users',{}).get(str(o.get('user_id')))
            amount=int(o.get('amount',0))
            if not target or int(target.get('balance',0))<amount:
                bot.answer_callback_query(c.id,'❌ موجودی کاربر برای تایید مجدد این سفارش کافی نیست.',show_alert=True);return
            target['balance']=int(target.get('balance',0))-amount
            o['refunded_amount']=0
            o['recharged_for_reapproval_at']=now()
        o['status']='approved';o['payment_status']='paid';o['approved_at']=now();o['reapproved_at']=now();o['reapproved_by']=str(r)
        reward=apply_referral_reward(d,o)
        save(d)
        try:
            bot.send_message(int(o.get('user_id')),f'✅ <b>سفارش شما دوباره تایید شد.</b>\n\n🆔 سفارش: <code>{oc}</code>\n📦 بسته: {d.get("packs",{}).get(o.get("pack_id"),{}).get("name","-")}\n\n📥 سفارش توسط مدیریت تایید شد و در حال تکمیل است.')
        except Exception: pass
        bot.send_message(ADMIN_ID,f'📌 <b>تایید مجدد سفارش</b>\n🆔 سفارش: <code>{oc}</code>\n👤 کاربر: <code>{o.get("user_id")}</code>\n👨‍💼 انجام‌دهنده: <code>{r}</code>' + (f'\n🎁 پاداش رفرال: {reward:,} تومان' if reward else ''))
        audit(r,'تایید مجدد سفارش رد شده',f'سفارش: <code>{oc}</code> | کاربر: <code>{o.get("user_id")}</code>')
        bot.answer_callback_query(c.id,'✅ سفارش دوباره تایید شد و کاربر مطلع شد.',show_alert=True)
        # The normal VPN/config flow remains available to the admin who re-approved it.
        states[r]={'wait':'vpn','order':oc}
        show(c,f'✅ سفارش <code>{oc}</code> دوباره تایید شد.\n\n📥 حالا مشخصات کانفیگ را در همین چت ارسال کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🛍 مدیریت سفارش‌ها',callback_data='a_orders')))
    elif c.data=='a_referral' and admin(r):
        s=d['settings']
        enabled=s.get('referral_enabled',True)
        percent=max(0,min(100,int(s.get('referral_percent',10))))
        max_rewards=max(1,int(s.get('referral_max_rewards',1)))
        m=InlineKeyboardMarkup(row_width=2)
        m.add(InlineKeyboardButton('🟢 روشن' if enabled else '🔴 خاموش',callback_data='ref_toggle'))
        m.add(InlineKeyboardButton(f'📊 درصد: {percent}%',callback_data='ref_percent'),InlineKeyboardButton(f'🔢 دفعات: {max_rewards}',callback_data='ref_times'))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'))
        show(c,f'👥 <b>مدیریت رفرال</b>\n\nوضعیت: {"روشن 🟢" if enabled else "خاموش 🔴"}\nدرصد پاداش: <b>{percent}%</b>\nدفعات پاداش برای هر دعوت‌شده: <b>{max_rewards}</b>\n\nدفعات پیش‌فرض ۱ است؛ یعنی فقط اولین خرید موفق هر دعوت‌شده شامل پاداش می‌شود.',m)
    elif c.data=='ref_toggle' and admin(r):
        d['settings']['referral_enabled']=not d['settings'].get('referral_enabled',True);save(d)
        show(c,f'👥 رفرال: {"روشن 🟢" if d["settings"]["referral_enabled"] else "خاموش 🔴"}',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_referral')))
    elif c.data=='ref_percent' and admin(r):
        states[r]={'wait':'ref_percent'};show(c,'📊 درصد پاداش رفرال را ارسال کنید.\nمثال: 10',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_referral')))
    elif c.data=='ref_times' and admin(r):
        states[r]={'wait':'ref_times'};show(c,'🔢 تعداد دفعات دریافت پاداش برای هر دعوت‌شده را ارسال کنید.\nمثال: 1\n\n۱ یعنی فقط اولین خرید موفق؛ 2 یعنی دو خرید موفق اول.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_referral')))
    elif c.data=='a_card' and admin(r):
        states[r]={'wait':'card'};show(c,'💳 اطلاعات کارت را در یک پیام بفرستید با این قالب:\nشماره کارت | نام صاحب کارت',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data=='a_join' and admin(r):
        s=d['settings'];m=InlineKeyboardMarkup().add(InlineKeyboardButton('🟢 روشن' if s.get('force_join') else '⚪ خاموش',callback_data='join_toggle'),InlineKeyboardButton('✏️ تنظیم کانال',callback_data='join_setup'),InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'));show(c,f'📢 عضویت اجباری\nوضعیت: {"روشن 🟢" if s.get("force_join") else "خاموش ⚪"}\nشناسه: {s.get("channel_id","")}\nلینک: {s.get("channel_link","")}',m)
    elif c.data=='join_toggle' and admin(r):
        d['settings']['force_join']=not d['settings'].get('force_join',False);save(d);show(c,f'📢 عضویت اجباری: {"روشن 🟢" if d["settings"]["force_join"] else "خاموش ⚪"}',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data=='join_setup' and admin(r):
        states[r]={'wait':'join'};show(c,'📢 اطلاعات کانال را در دو خط بفرستید:\nخط اول: @channel یا -100...\nخط دوم: لینک عضویت',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_join')))
    elif c.data=='a_bot' and admin(r):
        d['settings']['bot_enabled']=not d['settings'].get('bot_enabled',True);save(d);show(c,f'⏯ وضعیت ربات: {"روشن 🟢" if d["settings"]["bot_enabled"] else "خاموش 🔴"}',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data=='a_discount' and admin(r):
        m=InlineKeyboardMarkup().add(InlineKeyboardButton('➕ ساخت کد تخفیف','discount_add'))
        for dc,v in d.get('discounts',{}).items():
            m.add(InlineKeyboardButton(f'🎟 {dc} | {v.get("percent",0)}% | {v.get("used",0)}/{v.get("limit",0) or "∞"}',callback_data='discount_info:'+dc))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'));show(c,'🎟 مدیریت کدهای تخفیف:',m)
    elif c.data=='discount_add' and admin(r):
        states[r]={'wait':'discount'};show(c,'🎟 کد تخفیف را در یک پیام با قالب زیر بفرستید:\nCODE | درصد تخفیف | محدودیت استفاده | مدت اعتبار به دقیقه\n\nبرای محدودیت یا زمان نامحدود عدد 0 بگذارید.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_discount')))
    elif c.data.startswith('discount_info:') and admin(r):
        dc=c.data.split(':',1)[1];v=d.get('discounts',{}).get(dc,{});show(c,f'🎟 <b>{dc}</b>\nدرصد: {v.get("percent",0)}%\nاستفاده: {v.get("used",0)} / {v.get("limit",0) or "∞"}\nاعتبار: {"نامحدود" if not v.get("expires_at") else datetime.fromtimestamp(v["expires_at"]).strftime("%Y-%m-%d %H:%M")}',InlineKeyboardMarkup().add(InlineKeyboardButton('🗑 حذف',callback_data='discount_del:'+dc),InlineKeyboardButton('🔴 بازگشت',callback_data='a_discount')))
    elif c.data.startswith('discount_del:') and admin(r):
        dc=c.data.split(':',1)[1];d.get('discounts',{}).pop(dc,None);save(d);show(c,'✅ کد تخفیف حذف شد.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_discount')))
    elif c.data in ('a_min','a_link','a_guide','a_rules','a_free_config','a_welcome','a_broadcast','a_ghost','a_restrict','a_import') and admin(r):
        mp={'a_card':('card','💳 اطلاعات کارت را در یک پیام با قالب: شماره کارت | نام صاحب کارت'),'a_min':('min','حداقل واریز جدید:'),'a_link':('link','لینک PV ادمین:'),'a_guide':('guide','راهنمای جدید:'),'a_rules':('rules','قوانین جدید:'),'a_free_config':('free_config','کانفیگ رایگان جدید را ارسال کنید (متن یا لینک):'),'a_welcome':('welcome','متن خوش‌آمد جدید:'),'a_broadcast':('broadcast','متن پیام همگانی:'),'a_ghost':('ghost','CRV یا Telegram ID کاربر:'),'a_restrict':('restrict','CRV یا Telegram ID کاربر:'),'a_import':('import','فایل JSON را به صورت Document ارسال کنید.'),'a_join':('join','دو خط بفرستید: شناسه کانال (@channel یا -100...) و لینک عضویت')};w,t=mp[c.data];states[r]={'wait':w};show(c,t,InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data=='a_lookup' and admin(r):
        states[r]={'wait':'lookup_user'}
        show(c,'🔎 <b>استعلام کاربر</b>\n\nCRV یا Telegram ID عددی کاربر را ارسال کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data=='a_packs' and admin(r):
        m=InlineKeyboardMarkup().add(InlineKeyboardButton('➕ افزودن بسته','p_add'))
        for pid,p in d['packs'].items():
            m.add(InlineKeyboardButton(f'✏️ {p.get("name")} ({pid})',callback_data='p_edit:'+pid),InlineKeyboardButton('🗑 حذف',callback_data='p_del:'+pid))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'));show(c,'📦 مدیریت بسته‌ها:',m)
    elif c.data=='p_add' and admin(r):
        states[r]={'wait':'p_full_add'};show(c,'➕ مشخصات بسته را در یک پیام و دقیقاً با قالب زیر بفرستید:\nنام | قیمت | حجم | مدت | توضیحات',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_packs')))
    elif c.data.startswith('p_edit:') and admin(r):
        pid=c.data[7:];p=d['packs'].get(pid)
        if not p: bot.answer_callback_query(c.id,'بسته پیدا نشد.',show_alert=True); return
        states[r]={'wait':'p_full_edit','pid':pid};show(c,f'✏️ مشخصات جدید بسته را دقیقاً با قالب زیر بفرستید:\nنام | قیمت | حجم | مدت | توضیحات\n\nمقدار فعلی:\n{p.get("name","")} | {p.get("price",0)} | {p.get("volume","")} | {p.get("duration","")} | {p.get("desc","")}',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_packs')))
    elif c.data.startswith('p_del:') and admin(r):
        pid=c.data[6:];p=d['packs'].get(pid,{})
        m=InlineKeyboardMarkup().add(InlineKeyboardButton('⚠️ تایید حذف',callback_data='p_del_yes:'+pid),InlineKeyboardButton('لغو',callback_data='a_packs'));show(c,f'حذف بسته «{p.get("name",pid)}»؟',m)
    elif c.data.startswith('p_del_yes:') and admin(r):
        pid=c.data[10:];d['packs'].pop(pid,None);save(d);show(c,'✅ بسته کاملاً حذف شد.',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='a_packs')))
    elif c.data=='a_users' and admin(r):show(c,'👥 کاربران: '+str(len(d['users']))+'\n\n'+'\n'.join(f'{x["crv_code"]} | {k} | {int(x.get("balance",0)):,}' for k,x in list(d['users'].items())[-50:]),InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data=='a_backup' and admin(r):
        backup('manual');bot.send_document(ADMIN_ID,open(DATA_FILE,'rb'),caption='💾 پشتیبان دیتابیس')
    elif c.data=='a_reset' and admin(r):show(c,'⚠️ همه کاربران، سفارش‌ها، تیکت‌ها و موجودی‌ها حذف می‌شوند. ادامه؟',InlineKeyboardMarkup().add(InlineKeyboardButton('⚠️ تایید ریست',callback_data='reset_yes'),InlineKeyboardButton('لغو',callback_data='admin')))
    elif c.data=='reset_yes' and admin(r):backup('before_reset');save(json.loads(json.dumps(DEFAULT)));show(c,'♻️ دیتابیس ریست شد.',InlineKeyboardMarkup().add(InlineKeyboardButton('مدیریت',callback_data='admin')))
    elif c.data.startswith('lookup_') and admin(r):
        target = c.data.split(':', 1)[1] if ':' in c.data else ''
        if target not in d.get('users', {}):
            bot.answer_callback_query(c.id, '❌ کاربر پیدا نشد.', show_alert=True)
            return
        if c.data.startswith('lookup_refresh:'):
            tg, _ = _telegram_user_snapshot(target, d['users'][target])
            uu = d['users'][target]
            uu['first_name'] = tg.get('first_name', uu.get('first_name', ''))
            uu['last_name'] = tg.get('last_name', uu.get('last_name', ''))
            uu['username'] = tg.get('username', uu.get('username', 'بدون نام')) or 'بدون نام'
            save(d)
            bot.answer_callback_query(c.id, 'اطلاعات بروزرسانی شد ✅')
            show(c, _lookup_text(d, target, tg), _lookup_keyboard(target))
        elif c.data.startswith('lookup_restrict:'):
            show(c, f'🚫 <b>مدیریت محدودیت کاربر</b>\n\n🆔 <code>{target}</code>\n🔑 CRV: <code>{html.escape(str(d["users"][target].get("crv_code", "-")))}</code>\n\nنوع عملیات را انتخاب کنید:', _lookup_restrict_keyboard(target))
        elif c.data.startswith('lookup_block_perm:'):
            uu = d['users'][target]
            uu['blocked'] = True; uu['blocked_until'] = None
            save(d); audit(r, 'مسدود کردن کاربر از استعلام', f'کاربر: <code>{target}</code>')
            bot.answer_callback_query(c.id, 'کاربر به‌صورت دائم مسدود شد ✅')
            show(c, _lookup_text(d, target), _lookup_keyboard(target))
        elif c.data.startswith('lookup_block_temp:'):
            states[r] = {'wait':'lookup_duration', 'target':target, 'lookup_action':'block'}
            show(c, f'⏱ <b>مسدودیت موقت</b>\n\nکاربر: <code>{target}</code>\nمدت را به دقیقه ارسال کنید:', InlineKeyboardMarkup().add(InlineKeyboardButton('🔙 برگشت', callback_data='lookup_refresh:'+target)))
        elif c.data.startswith('lookup_limit_orders:') or c.data.startswith('lookup_limit_deposits:'):
            action = 'orders' if c.data.startswith('lookup_limit_orders:') else 'deposits'
            uu = d['users'][target]
            uu.setdefault('restrictions', {})[action] = 'permanent'
            save(d); audit(r, 'اعمال محدودیت کاربر از استعلام', f'کاربر: <code>{target}</code> | نوع: <code>{action}</code>')
            bot.answer_callback_query(c.id, 'محدودیت اعمال شد ✅')
            show(c, _lookup_text(d, target), _lookup_keyboard(target))
        elif c.data.startswith('lookup_unlimit:'):
            uu = d['users'][target]
            uu['blocked'] = False; uu['blocked_until'] = None; uu['restrictions'] = {}
            save(d); audit(r, 'رفع محدودیت کاربر از استعلام', f'کاربر: <code>{target}</code>')
            bot.answer_callback_query(c.id, 'همه محدودیت‌ها رفع شد 🔓')
            show(c, _lookup_text(d, target), _lookup_keyboard(target))
        elif c.data.startswith('lookup_ghost:'):
            states[r] = {'ghost_target':target}
            bot.answer_callback_query(c.id, 'Ghost فعال شد 👻')
            bot.send_message(c.message.chat.id, f'👻 Ghost برای کاربر <code>{target}</code> فعال شد.\n🔑 CRV: <code>{html.escape(str(d["users"][target].get("crv_code", "-")))}</code>\n\nحالا /start را بزنید.')
        elif c.data.startswith('lookup_private:'):
            states[r] = {'wait':'lookup_private_message', 'private_target':target}
            show(c, f'💬 <b>پیام خصوصی به کاربر</b>\n\n👤 کاربر: <code>{target}</code>\n🔑 CRV: <code>{html.escape(str(d["users"][target].get("crv_code", "-")))}</code>\n\n📥 متن پیام را ارسال کنید:', InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 لغو', callback_data='private_cancel')))
        return

    elif c.data=='a_private' and admin(r):
        states[r]={'wait':'private_target'}
        show(c,'💬 <b>پیام خصوصی به کاربر</b>\n\nCRV یا Telegram ID کاربر را ارسال کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data.startswith('private_reply:'):
        key=c.data.split(':',1)[1]
        th=d.get('private_threads',{}).get(str(key),{})
        chat_id=str(th.get('chat_id','')) if th else ''
        # New messages use the stable PV chat code directly. Keep old message-id
        # callbacks working for conversations created by version 27.0.
        if not chat_id:
            chat_id=str(key)
            chat=d.get('private_chats',{}).get(chat_id,{})
            if not chat and str(key).isdigit():
                old=d.get('private_threads',{}).get(str(key),{})
                chat_id=str(old.get('chat_id',''))
        chat=d.get('private_chats',{}).get(chat_id,{})
        if not chat or chat.get('status')!='open':
            bot.answer_callback_query(c.id,'❌ این گفتگو دیگر قابل پاسخ نیست.',show_alert=True);return
        if admin(r):
            if chat.get('admin_id') and str(chat.get('admin_id'))!=str(r) and str(r)!=str(OWNER_ID):
                bot.answer_callback_query(c.id,'⛔ این گفتگوی خصوصی برای ادمین دیگری است.',show_alert=True);return
            if chat.get('turn')!='admin':
                bot.answer_callback_query(c.id,'⏳ فعلاً منتظر پاسخ کاربر باشید.',show_alert=True);return
            parent=str(chat.get('last_message_id',''))
            th=d.get('private_threads',{}).get(parent,{})
            states[r]={'wait':'private_admin_message','private_chat':chat_id,'private_parent':parent}
            bot.answer_callback_query(c.id)
            bot.send_message(c.message.chat.id,'↩️ <b>پاسخ ادمین</b>\n\n📨 پاسخ به پیام:\n'+str(th.get('text',''))[:1200]+'\n\n📥 متن پاسخ را ارسال کنید:',reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 لغو',callback_data='private_cancel')))
        elif str(c.from_user.id)==str(chat.get('user_id')):
            if chat.get('turn')!='user':
                bot.answer_callback_query(c.id,'⏳ لطفاً منتظر پاسخ ادمین باشید.',show_alert=True);return
            parent=str(chat.get('last_message_id',''))
            th=d.get('private_threads',{}).get(parent,{})
            states[r]={'wait':'private_user_message','private_chat':chat_id,'private_parent':parent}
            bot.answer_callback_query(c.id)
            bot.send_message(c.message.chat.id,'↩️ <b>پاسخ شما</b>\n\n📨 پاسخ به پیام:\n'+str(th.get('text',''))[:1200]+'\n\n📥 متن پاسخ را ارسال کنید:',reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 لغو',callback_data='private_cancel')))
    elif c.data.startswith('private_close:') and admin(r):
        key=c.data.split(':',1)[1]
        chat_id=str(key)
        chat=d.get('private_chats',{}).get(chat_id,{})
        if not chat and str(key).isdigit():
            old=d.get('private_threads',{}).get(str(key),{})
            chat_id=str(old.get('chat_id',''))
            chat=d.get('private_chats',{}).get(chat_id,{})
        if not chat or chat.get('status')!='open':
            bot.answer_callback_query(c.id,'این چت قبلاً بسته شده است.',show_alert=True);return
        if chat.get('admin_id') and str(chat.get('admin_id'))!=str(r) and str(r)!=str(OWNER_ID):
            bot.answer_callback_query(c.id,'⛔ این گفتگو برای ادمین دیگری است.',show_alert=True);return
        chat['status']='closed';chat['closed_at']=now();chat['closed_by']=str(r);save(d);states[r]={}
        bot.answer_callback_query(c.id,'چت بسته شد ✅')
        show(c,'🔒 <b>چت خصوصی بسته شد.</b>',InlineKeyboardMarkup().add(InlineKeyboardButton('💬 پیام خصوصی جدید',callback_data='a_private'),InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
        try: bot.send_message(int(chat.get('user_id')),f'🔒 <b>گفتگوی خصوصی بسته شد.</b>\n\nاین گفتگو توسط مدیریت بسته شد.')
        except Exception: pass
    elif c.data=='private_cancel':
        states[r]={};bot.answer_callback_query(c.id,'لغو شد.');bot.send_message(c.message.chat.id,'❌ پاسخ لغو شد.')
    elif c.data=='a_tickets' and admin(r):
        m=InlineKeyboardMarkup(row_width=1)
        for t in sorted(d.get('tickets',{}).values(), key=lambda z:z.get('created_at',''), reverse=True):
            if t.get('status')!='closed':
                m.add(InlineKeyboardButton(f'🎫 {t.get("code")} | {str(t.get("subject",""))[:35]}',callback_data='ticket_admin:'+str(t.get('code'))))
        if not any(t.get('status')!='closed' for t in d.get('tickets',{}).values()):
            m.add(InlineKeyboardButton('— تیکت بازی وجود ندارد —',callback_data='a_tickets'))
        m.add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin'));show(c,'🎫 <b>تیکت‌های باز و در جریان:</b>\n\nبا انتخاب هر تیکت، پاسخ دهید یا آن را ببندید.',m)
    elif c.data.startswith('ticket_admin:') and admin(r):
        tc=c.data.split(':',1)[1];t=d.get('tickets',{}).get(tc,{})
        if not t or t.get('status')!='open': bot.answer_callback_query(c.id,'❌ تیکت باز پیدا نشد.',show_alert=True);return
        msgs=t.get('messages',[]);last=msgs[-1] if msgs else {'sender':'user','text':t.get('message','')}
        if t.get('turn','admin')!='admin':
            status='⏳ منتظر پاسخ کاربر'
        else: status='🟢 نوبت ادمین'
        states[r]={'wait':'ticket_admin_reply','ticket':tc}
        kb=InlineKeyboardMarkup(row_width=2).add(InlineKeyboardButton('↩️ پاسخ',callback_data='ticket_admin:'+tc),InlineKeyboardButton('🔒 بستن تیکت',callback_data='ticket_close:'+tc))
        show(c,f'🎫 <b>{tc}</b>\n👤 کاربر: <code>{t.get("user_id")}</code>\nموضوع: {t.get("subject","-")}\nوضعیت: {status}\n\nآخرین پیام ({last.get("sender","user")}):\n{str(last.get("text", ""))[:2500]}\n\n📥 متن پاسخ را ارسال کنید:',kb)
    elif c.data.startswith('ticket_close:') and admin(r):
        tc=c.data.split(':',1)[1];t=d.get('tickets',{}).get(tc,{})
        if not t or t.get('status')!='open': bot.answer_callback_query(c.id,'این تیکت قبلاً بسته شده است.',show_alert=True);return
        t['status']='closed';t['closed_at']=now();t['closed_by']=str(r);save(d);states[r]={}
        try: bot.send_message(int(t.get('user_id')),f'🔒 <b>تیکت شما بسته شد.</b>\n\n🎫 شناسه: <code>{tc}</code>\n📌 موضوع: {t.get("subject","-")}\n\nاین تیکت توسط مدیریت بسته شد و ادامه پاسخ‌گویی در آن امکان‌پذیر نیست.')
        except Exception: pass
        bot.answer_callback_query(c.id,'🔒 تیکت بسته شد.',show_alert=True)
        show(c,f'🔒 تیکت <code>{tc}</code> بسته شد.',InlineKeyboardMarkup().add(InlineKeyboardButton('🎫 تیکت‌های باز',callback_data='a_tickets'),InlineKeyboardButton('🔴 پنل مدیریت',callback_data='back_admin')))
    elif c.data=='ghost_exit' and admin(r):states[r]={};show(c,'👻 از Ghost خارج شدید.',menu(r))
    elif c.data.startswith('adm_approve:') and admin(r):
        oc=c.data[12:];o=d['orders'].get(oc)
        if not o:
            bot.answer_callback_query(c.id,'❌ سفارش پیدا نشد.',show_alert=True);return
        if o.get('status')!='pending':
            bot.answer_callback_query(c.id,'⚠️ این سفارش قبلاً بررسی شده است.',show_alert=True);return
        o['status']='approved';o['payment_status']='paid';o['approved_at']=now();reward=apply_referral_reward(d,o);save(d)
        states[r]={'wait':'vpn','order':oc}
        bot.answer_callback_query(c.id,'✅ سفارش تایید شد؛ کانفیگ را ارسال کنید.')
        if reward:
            inviter_id=str(d['users'][str(o.get('user_id'))].get('referrer_id'))
            try: bot.send_message(int(inviter_id),f'🎁 <b>هدیه دعوت</b>\nبه‌خاطر اولین خرید موفق دعوت‌شده شما، <b>{reward:,} تومان</b> به کیف پولتان اضافه شد.\n🆔 سفارش: <code>{oc}</code>')
            except: pass
            bot.send_message(ADMIN_ID,f'👥 <b>پاداش دعوت ثبت شد</b>\nسفارش: <code>{oc}</code>\nمعرف: <code>{inviter_id}</code>\n🎁 مبلغ: {reward:,} تومان')
        show(c,f'✅ سفارش <code>{oc}</code> تایید شد.\n\n📥 حالا مشخصات کانفیگ را در همین چت ارسال کنید:',InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 بازگشت',callback_data='back_admin')))
    elif c.data.startswith('adm_reject:') and admin(r):
        oc=c.data[11:];o=d['orders'].get(oc)
        if not o:
            bot.answer_callback_query(c.id,'❌ سفارش پیدا نشد.',show_alert=True);return
        if o.get('status')!='pending':
            bot.answer_callback_query(c.id,'⚠️ این سفارش قبلاً بررسی شده است.',show_alert=True);return
        o['status']='rejected';o['payment_status']='refunded' if o.get('payment_method')=='wallet' else 'rejected'
        refund=0
        if o.get('payment_method')=='wallet':
            target=d['users'].get(str(o.get('user_id')))
            if target is not None:
                refund=int(o.get('amount',0));target['balance']=int(target.get('balance',0))+refund
                o['refunded_amount']=refund;o['refunded_at']=now()
        dc=o.get('discount_code')
        if dc and dc in d.get('discounts',{}) and d['discounts'][dc].get('used',0)>0:d['discounts'][dc]['used']-=1
        save(d)
        bot.send_message(o['user_id'],f'❌ سفارش <code>{oc}</code> رد شد.' + (f'\n\n💰 مبلغ {refund:,} تومان به کیف پول شما مسترد شد.' if refund else ''))
        bot.answer_callback_query(c.id,'❌ سفارش رد شد و در صورت پرداخت کیف پول، وجه مسترد شد.',show_alert=True)
        try: bot.edit_message_reply_markup(c.message.chat.id,c.message.message_id,reply_markup=None)
        except: pass
        bot.send_message(ADMIN_ID,f'📌 <b>نتیجه بررسی سفارش {oc}</b>\n❌ رد شد' + (f'\n💰 استرداد: {refund:,} تومان' if refund else ''))
    elif c.data.startswith('dep_ok:') and admin(r):
        if not can(r,'wallet_requests'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت درخواست‌های افزایش موجودی برای شما فعال نیست.',show_alert=True);return
        dc=c.data[7:];x=d['deposits'].get(dc)
        if not x: bot.answer_callback_query(c.id,'❌ رسید پیدا نشد.',show_alert=True);return
        if x.get('status')!='pending': bot.answer_callback_query(c.id,'⚠️ این رسید قبلاً بررسی شده است.',show_alert=True);return
        d['users'][x['user_id']]['balance']+=int(x['amount']);x['status']='approved';x['approved_at']=now();x['approved_by']=str(r);save(d)
        bot.send_message(x['user_id'],f'✅ رسید واریز <code>{dc}</code> تایید شد و {int(x["amount"]):,} تومان به کیف پول شما اضافه شد.')
        bot.answer_callback_query(c.id,f'✅ رسید {dc} تایید شد.',show_alert=True)
        try: bot.edit_message_caption((c.message.caption or '')+'\n\n✅ <b>تایید شد.</b>',c.message.chat.id,c.message.message_id)
        except: pass
        bot.send_message(ADMIN_ID,f'📌 <b>نتیجه رسید {dc}</b>\n✅ تایید شد.\n💰 {int(x["amount"]):,} تومان به موجودی کاربر اضافه شد.')
    elif c.data.startswith('dep_receipt:') and admin(r):
        if not can(r,'wallet_requests'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت درخواست‌های افزایش موجودی برای شما فعال نیست.',show_alert=True);return
        dc=c.data[12:];x=d.get('deposits',{}).get(dc)
        if not x or not x.get('receipt_file_id'):
            bot.answer_callback_query(c.id,'🧾 رسیدی برای این درخواست ثبت نشده است.',show_alert=True);return
        try:
            bot.send_photo(r,x['receipt_file_id'],caption=f'🧾 <b>رسید افزایش موجودی</b>\n🆔 <code>{dc}</code>\n👤 کاربر: <code>{x.get("user_id")}</code>\n💰 مبلغ: {int(x.get("amount",0)):,} تومان')
            bot.answer_callback_query(c.id,'🧾 رسید ارسال شد.')
        except Exception:
            bot.answer_callback_query(c.id,'❌ ارسال رسید ناموفق بود.',show_alert=True)
        return
    elif c.data.startswith('dep_reapprove:') and admin(r):
        if not can(r,'wallet_requests'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت درخواست‌های افزایش موجودی برای شما فعال نیست.',show_alert=True);return
        dc=c.data[14:];x=d.get('deposits',{}).get(dc)
        if not x: bot.answer_callback_query(c.id,'❌ درخواست پیدا نشد.',show_alert=True);return
        if x.get('status')!='rejected': bot.answer_callback_query(c.id,'⚠️ فقط درخواست ردشده قابل تایید مجدد است.',show_alert=True);return
        d['users'][str(x['user_id'])]['balance']=int(d['users'][str(x['user_id'])].get('balance',0))+int(x['amount'])
        x['status']='approved';x['approved_at']=now();x['approved_by']=str(r);x['reapproved_by']=str(r);x['reapproved_at']=now()
        save(d)
        bot.send_message(x['user_id'],f'✅ درخواست افزایش موجودی <code>{dc}</code> که قبلاً رد شده بود، دوباره تایید شد و {int(x["amount"]):,} تومان به کیف پول شما اضافه شد.')
        bot.answer_callback_query(c.id,f'✅ {dc} تایید مجدد شد.',show_alert=True)
        try: bot.edit_message_reply_markup(c.message.chat.id,c.message.message_id,reply_markup=None)
        except: pass
        return
    elif c.data.startswith('dep_no:') and admin(r):
        if not can(r,'wallet_requests'):
            bot.answer_callback_query(c.id,'⛔ دسترسی مدیریت درخواست‌های افزایش موجودی برای شما فعال نیست.',show_alert=True);return
        dc=c.data[7:];x=d['deposits'].get(dc)
        if not x: bot.answer_callback_query(c.id,'❌ رسید پیدا نشد.',show_alert=True);return
        if x.get('status')!='pending': bot.answer_callback_query(c.id,'⚠️ این رسید قبلاً بررسی شده است.',show_alert=True);return
        x['status']='rejected';x['rejected_at']=now();x['rejected_by']=str(r);save(d)
        bot.send_message(x['user_id'],f'❌ رسید واریز <code>{dc}</code> رد شد و مبلغی به کیف پول اضافه نشد.')
        bot.answer_callback_query(c.id,f'❌ رسید {dc} رد شد.',show_alert=True)
        try: bot.edit_message_caption((c.message.caption or '')+'\n\n❌ <b>رد شد.</b>',c.message.chat.id,c.message.message_id)
        except: pass
        bot.send_message(ADMIN_ID,f'📌 <b>نتیجه رسید {dc}</b>\n❌ رد شد.')
    elif c.data.startswith(('block_perm:','block_temp:','limit_orders:','limit_deposits:','unlimit:')) and admin(r):
        action,target=c.data.split(':',1);u2=d['users'].get(target)
        if not u2:return
        if action=='block_perm':u2['blocked']=True;u2['blocked_until']=None;save(d);bot.answer_callback_query(c.id,'مسدود دائم شد.')
        elif action=='unlimit':u2['blocked']=False;u2['blocked_until']=None;u2['restrictions']={};save(d);bot.answer_callback_query(c.id,'محدودیت‌ها رفع شد.')
        else:states[r]={'wait':'duration','target':target,'action':('block' if action=='block_temp' else 'orders' if action=='limit_orders' else 'deposits')};bot.send_message(ADMIN_ID,'⏱ مدت به دقیقه:')
@bot.message_handler(content_types=['photo'])
def photo(m):
    r=real(m);st=states.get(r,{})
    if st.get('wait') not in ('order_receipt','dep_receipt'):return
    d=load();uid=eff(m);u=user(d,uid,m.from_user)
    if st['wait']=='order_receipt':
        oc=code('ORD',d['orders']);dc=st.get('discount_code');
        if dc and dc in d.get('discounts',{}):d['discounts'][dc]['used']=int(d['discounts'][dc].get('used',0))+1
        d['orders'][oc]={'code':oc,'user_id':uid,'pack_id':st['pid'],'amount':int(st['amount']),'payment_method':'card','payment_status':'receipt_pending','status':'pending','receipt_file_id':m.photo[-1].file_id,'discount_code':dc or None,'created_at':now()};u['orders'].append(oc);mk=InlineKeyboardMarkup().add(InlineKeyboardButton('✅ تایید',callback_data='adm_approve:'+oc),InlineKeyboardButton('❌ رد',callback_data='adm_reject:'+oc));cap=f'🔔 سفارش {oc}\nکاربر {uid}\nCRV {u["crv_code"]}\nمبلغ {int(st["amount"]):,}';save(d);bot.send_photo(ADMIN_ID,m.photo[-1].file_id,caption=cap,reply_markup=mk);bot.reply_to(m,f'✅ رسید ثبت شد. کد سفارش: <code>{oc}</code>')
    else:
        dc=code('DEP',d['deposits']);d['deposits'][dc]={'code':dc,'tracking_id':dc,'user_id':uid,'amount':int(st['amount']),'status':'pending','payment_method':'card_to_card','source':'user_request','receipt_file_id':m.photo[-1].file_id,'created_at':now()};mk=InlineKeyboardMarkup().add(InlineKeyboardButton('✅ تایید',callback_data='dep_ok:'+dc),InlineKeyboardButton('❌ رد',callback_data='dep_no:'+dc));save(d);bot.send_photo(ADMIN_ID,m.photo[-1].file_id,caption=f'💰 واریز {dc}\nکاربر {uid}\nمبلغ {int(st["amount"]):,}',reply_markup=mk);bot.reply_to(m,f'✅ رسید ثبت شد. شناسه رهگیری شارژ کیف پول: <code>{dc}</code>')
    states[r]={}
@bot.message_handler(content_types=['document'])
def doc(m):
    r=real(m); st=states.get(r,{})
    if not admin(r):
        return
    wait=st.get('wait')

    if wait=='update_py':
        name=(m.document.file_name or '').lower()
        if not name.endswith('.py'):
            bot.reply_to(m,'❌ فقط فایل Python با پسوند .py ارسال کنید.')
            return
        temp_path=None
        try:
            file_info=bot.get_file(m.document.file_id)
            raw=bot.download_file(file_info.file_path)
            source=raw.decode('utf-8-sig')
            # Syntax check without executing the uploaded code.
            ast.parse(source, filename=m.document.file_name)

            current=os.path.abspath(__file__)
            base=os.path.dirname(current)
            backup_dir=os.path.join(base,'backups')
            os.makedirs(backup_dir,exist_ok=True)
            stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
            py_backup=os.path.join(backup_dir,f'bot_{stamp}.py')
            data_backup=os.path.join(backup_dir,f'data_{stamp}.json')
            if os.path.exists(current): shutil.copy2(current,py_backup)
            if os.path.exists(DATA_FILE): shutil.copy2(DATA_FILE,data_backup)

            fd,temp_path=tempfile.mkstemp(prefix='.bot_update_',suffix='.py',dir=base)
            with os.fdopen(fd,'w',encoding='utf-8',newline='') as f: f.write(source)
            os.replace(temp_path,current)
            temp_path=None
            states[r]={}
            bot.send_message(m.chat.id,'✅ فایل جدید معتبر بود و جایگزین شد.\n💾 بکاپ bot.py و دیتابیس قبلی ذخیره شد.\n🔄 ربات در حال Restart است...')
            # data.json is deliberately not replaced. The new code loads the existing DB.
            os.execv(sys.executable,[sys.executable,current])
        except SyntaxError as e:
            if temp_path and os.path.exists(temp_path): os.remove(temp_path)
            bot.reply_to(m,f'❌ Syntax فایل جدید مشکل دارد؛ هیچ تغییری اعمال نشد.\nخط {e.lineno}: {e.msg}')
        except Exception as e:
            if temp_path and os.path.exists(temp_path): os.remove(temp_path)
            bot.reply_to(m,f'❌ آپدیت انجام نشد و نسخه فعلی حفظ شد.\n{e}')
        return

    if wait!='import':
        return
    if not (m.document.file_name or '').lower().endswith('.json'):
        bot.reply_to(m,'❌ فقط JSON.')
        return
    try:
        raw=bot.download_file(bot.get_file(m.document.file_id).file_path)
        new=json.loads(raw.decode())
        if not all(isinstance(new.get(k),dict) for k in ('users','packs','orders')):
            raise ValueError('ساختار نامعتبر')
        for k,v in DEFAULT.items(): new.setdefault(k,json.loads(json.dumps(v)))
        for k,v in DEFAULT['settings'].items(): new['settings'].setdefault(k,v)
        backup('before_import'); save(new); states[r]={}
        bot.reply_to(m,'✅ دیتابیس نصب شد و بکاپ دیتابیس قبلی ذخیره شد.')
    except Exception as e:
        bot.reply_to(m,f'❌ {e}')

# Dedicated handler for adding admins.
# It is intentionally registered before the generic state/text handlers so a plain
# numeric Telegram ID is always consumed by the admin-add flow.
@bot.message_handler(func=lambda m: owner(m.from_user.id) and states.get(str(m.from_user.id), {}).get('wait') == 'admin_add', content_types=['text'])
def handle_admin_add_text(m):
    r = real(m)
    x = (m.text or '').strip()
    if not x.isdigit() or int(x) <= 0:
        bot.reply_to(m, '❌ آیدی باید یک عدد معتبر Telegram باشد. دوباره ارسال کنید:')
        return
    aid = str(int(x))
    if aid == str(OWNER_ID):
        bot.reply_to(m, '❌ آیدی مالک اصلی قابل افزودن به عنوان ادمین نیست.')
        return
    d = load()
    if aid in d.get('admins', {}):
        states[r] = {}
        bot.reply_to(m, f'⚠️ ادمین <code>{aid}</code> از قبل در لیست ادمین‌ها وجود دارد.')
        return
    d.setdefault('admins', {})[aid] = {
        'name': f'Admin {aid}',
        'active': True,
        'permissions': {},
        'created_at': now(),
        'created_by': str(OWNER_ID)
    }
    save(d)
    states[r] = {}
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton('⚙️ تنظیم دسترسی‌ها', callback_data='admin_manage:' + aid),
        InlineKeyboardButton('👑 مدیریت ادمین‌ها', callback_data='dev_admins')
    )
    bot.reply_to(m, f'✅ ادمین <code>{aid}</code> با موفقیت اضافه شد.\n\nهمه دسترسی‌ها در ابتدا خاموش هستند؛ دسترسی‌های موردنیاز را فعال کنید.', reply_markup=kb)

@bot.message_handler(func=lambda m: bool(m.reply_to_message) and str(m.reply_to_message.message_id) in load().get('private_threads',{}), content_types=['text'])
def private_reply(m):
    """Backward-compatible reply-to-message support for private conversations.
    Button replies are the primary flow; this handler also makes Telegram's
    native Reply action work reliably for old and new messages.
    """
    d=load(); r=real(m); mid=str(m.reply_to_message.message_id)
    th=d.get('private_threads',{}).get(mid,{})
    chat_id=str(th.get('chat_id','')); chat=d.get('private_chats',{}).get(chat_id,{})
    if not chat or chat.get('status')!='open' or str(chat.get('last_message_id'))!=mid:
        return
    is_admin=admin(r); is_user=str(r)==str(chat.get('user_id'))
    if not (is_admin or is_user): return
    expected='admin' if is_admin else 'user'
    if chat.get('turn')!=expected:
        bot.reply_to(m,'⏳ فعلاً نوبت پاسخ طرف مقابل است.'); return
    # Route it through the same stateful engine as the inline button flow.
    states[r]={'wait':'private_admin_message' if is_admin else 'private_user_message',
               'private_chat':chat_id,'private_parent':mid}
    bot.reply_to(m,'📥 متن پاسخ را ارسال کنید.\n🔴 برای لغو از دکمه لغو استفاده کنید:',
                 reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('🔴 لغو',callback_data='private_cancel')))


# Dedicated package text handler.
# Package add/edit used to share the generic state handler; on some Telegram
# updates that made the input appear to be ignored. Keep this flow isolated so
# the package message is always consumed by the package state.
def _normalize_digits(value):
    table = str.maketrans(
        '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
        '01234567890123456789'
    )
    return value.translate(table)

def _parse_package_text(value):
    # Remove bidi/zero-width control characters that Telegram can include in
    # Persian/Arabic text, normalize line breaks, and keep "|" as the delimiter.
    value = re.sub(r'[\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff]', '', value or '')
    value = value.replace('\r', ' ').replace('\n', ' ')
    parts = [z.strip() for z in value.split('|', 4)]
    if len(parts) != 5:
        return None, '❌ قالب صحیح:\nنام | قیمت | حجم | مدت | توضیحات'
    name, price_text, volume, duration, desc = parts
    if not name:
        return None, '❌ نام بسته نمی‌تواند خالی باشد.'
    if not price_text:
        return None, '❌ قیمت بسته را وارد کنید.'
    price_text = _normalize_digits(price_text).replace(',', '').replace('٬', '').replace('،', '').replace(' ', '')
    if not price_text.isdigit():
        return None, '❌ قیمت باید فقط عدد باشد. مثال: 2950000'
    price = int(price_text)
    if price < 0:
        return None, '❌ قیمت نامعتبر است.'
    if not volume:
        return None, '❌ حجم بسته نمی‌تواند خالی باشد.'
    if not duration:
        return None, '❌ مدت بسته نمی‌تواند خالی باشد.'
    if not desc:
        return None, '❌ توضیحات بسته نمی‌تواند خالی باشد.'
    return {
        'name': name,
        'price': price,
        'volume': volume,
        'duration': duration,
        'desc': desc,
        'active': True
    }, None

@bot.message_handler(
    func=lambda m: str(m.from_user.id) in states
    and states[str(m.from_user.id)].get('wait') in ('p_full_add', 'p_full_edit'),
    content_types=['text']
)
def handle_package_text(m):
    r = real(m)
    st = states.get(r, {})
    w = st.get('wait')
    if w not in ('p_full_add', 'p_full_edit'):
        return

    # Only admins/owner may use package management.
    if not admin(r):
        states[r] = {}
        bot.reply_to(m, '⛔ دسترسی به مدیریت بسته‌ها ندارید.')
        return

    raw = (m.text or '').strip()
    pnew, error = _parse_package_text(raw)
    if error:
        bot.reply_to(
            m,
            error + '\n\nنمونه:\n04 مولتی لوکیشن | 2950000 | 100 گیگ | یک ماهه | '
                   'مخصوص استفاده سبک تا سنگین'
        )
        return

    d = load()
    if w == 'p_full_add':
        pid = 'P' + uuid.uuid4().hex[:6].upper()
        d.setdefault('packs', {})[pid] = pnew
        msg = f'✅ بسته جدید با موفقیت اضافه شد: <code>{pid}</code>'
    else:
        pid = str(st.get('pid', ''))
        if pid not in d.get('packs', {}):
            states[r] = {}
            bot.reply_to(m, '❌ بسته موردنظر دیگر وجود ندارد. دوباره از مدیریت بسته‌ها انتخاب کنید.')
            return
        d['packs'][pid] = pnew
        msg = f'✅ مشخصات بسته <code>{pid}</code> با موفقیت ویرایش شد.'

    save(d)
    states[r] = {}
    bot.reply_to(m, msg)

@bot.message_handler(func=lambda m: str(m.from_user.id) in states and states[str(m.from_user.id)].get('wait') is not None)
def text(m):
    r=real(m);st=states[r];w=st['wait'];d=load();uid=eff(m);u=user(d,uid,m.from_user);x=(m.text or '').strip()
    if admin(r) and not owner(r):
        perm=wait_perm(w)
        if not can(r,perm):
            states[r]={};bot.reply_to(m,'⛔ این دسترسی برای شما فعال نیست.');return
        audit(r,'دریافت/اجرای عملیات متنی',f'نوع: <code>{w}</code> | متن: <code>{x[:500]}</code>')
    if w=='admin_add' and owner(r):
        if not x.isdigit() or int(x)<=0:
            bot.reply_to(m,'❌ آیدی باید یک عدد معتبر Telegram باشد.');return
        aid=str(int(x))
        if aid==str(ADMIN_ID): bot.reply_to(m,'❌ این آیدی مالک اصلی است.');return
        d.setdefault('admins',{})[aid]={'name':f'Admin {aid}','active':True,'permissions':{},'created_at':now(),'created_by':str(ADMIN_ID)}
        save(d);states[r]={};audit(r,'افزودن ادمین',f'ادمین جدید: <code>{aid}</code>');
        show_text=InlineKeyboardMarkup().add(InlineKeyboardButton('⚙️ تنظیم دسترسی‌ها',callback_data='admin_manage:'+aid),InlineKeyboardButton('👑 مدیریت ادمین‌ها',callback_data='a_admins'))
        bot.reply_to(m,f'✅ ادمین <code>{aid}</code> اضافه شد.\n\nهمه دسترسی‌ها در ابتدا خاموش هستند؛ حالا دسترسی‌های موردنیاز را فعال کنید.',reply_markup=show_text);return
    if w=='lookup_user':
        target = _resolve_lookup_user(d, x)
        if not target:
            bot.reply_to(m, '❌ کاربر پیدا نشد. فقط CRV یا Telegram ID عددیِ کاربری که در ربات ثبت شده را وارد کنید:')
            return
        tg, _ = _telegram_user_snapshot(target, d['users'][target])
        uu = d['users'][target]
        uu['first_name'] = tg.get('first_name', uu.get('first_name', ''))
        uu['last_name'] = tg.get('last_name', uu.get('last_name', ''))
        uu['username'] = tg.get('username', uu.get('username', 'بدون نام')) or 'بدون نام'
        save(d); states[r] = {}
        audit(r, 'استعلام کاربر', f'کاربر: <code>{target}</code> | CRV: <code>{html.escape(str(uu.get("crv_code", "-")))}</code>')
        bot.reply_to(m, _lookup_text(d, target, tg), reply_markup=_lookup_keyboard(target))
        return
    if w=='lookup_duration':
        target = str(st.get('target',''))
        action = st.get('lookup_action')
        if target not in d.get('users',{}) or action != 'block':
            states[r] = {}; bot.reply_to(m, '❌ عملیات استعلام منقضی شده است.'); return
        try:
            minutes = int(_normalize_digits(x).replace(',', '').replace('٬', '').replace(' ', ''))
            if minutes <= 0: raise ValueError
        except Exception:
            bot.reply_to(m, '❌ مدت نامعتبر است. یک عدد مثبت بر حسب دقیقه ارسال کنید.'); return
        d['users'][target]['blocked'] = True
        d['users'][target]['blocked_until'] = time.time() + minutes * 60
        save(d); states[r] = {}
        audit(r, 'مسدودیت موقت کاربر از استعلام', f'کاربر: <code>{target}</code> | دقیقه: <code>{minutes}</code>')
        bot.reply_to(m, f'✅ کاربر <code>{target}</code> به مدت {minutes:,} دقیقه مسدود شد.', reply_markup=_lookup_keyboard(target))
        return
    if w=='lookup_private_message':
        target = str(st.get('private_target',''))
        if target not in d.get('users',{}):
            states[r] = {}; bot.reply_to(m, '❌ کاربر پیدا نشد.'); return
        if not x:
            bot.reply_to(m, '❌ متن پیام خصوصی نمی‌تواند خالی باشد.'); return
        chat_id = code('PV', d.setdefault('private_chats', {}))
        try:
            safe = html.escape(x)
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton('↩️ پاسخ', callback_data=f'private_reply:{chat_id}'))
            sent = bot.send_message(int(target), f'💬 <b>پیام خصوصی از مدیریت</b>\n\n{safe}', reply_markup=kb)
            d['private_chats'][chat_id] = {'user_id':target,'admin_id':str(r),'status':'open','turn':'user','last_message_id':str(sent.message_id),'created_at':now()}
            d.setdefault('private_threads', {})[str(sent.message_id)] = {'chat_id':chat_id,'user_id':target,'admin_id':str(r),'created_at':now(),'sender':'admin','text':x}
            save(d); states[r] = {}
            bot.reply_to(m, f'✅ پیام خصوصی برای <code>{target}</code> ارسال شد.\n🆔 گفتگوی خصوصی: <code>{chat_id}</code>', reply_markup=_lookup_keyboard(target))
        except Exception as e:
            states[r] = {}
            bot.reply_to(m, f'❌ ارسال پیام خصوصی انجام نشد.\nجزئیات: <code>{html.escape(str(e))[:700]}</code>')
        return

    if w=='private_target':
        target=x if x in d['users'] else next((z for z,v in d['users'].items() if v.get('crv_code','').lower()==x.lower()),None)
        if not target:
            bot.reply_to(m,'❌ کاربر پیدا نشد. CRV یا Telegram ID را بررسی کنید.');return
        states[r]={'wait':'private_message','private_target':target}
        tu=d['users'][target]
        bot.reply_to(m,f'👤 کاربر: <code>{target}</code>\n🔑 CRV: <code>{tu.get("crv_code","")}</code>\n\n📥 متن پیام خصوصی را ارسال کنید:')
        return
    if w=='private_message':
        target=str(st.get('private_target',''))
        if target not in d.get('users',{}):
            states[r]={};bot.reply_to(m,'❌ کاربر پیدا نشد.');return
        if not x:
            bot.reply_to(m,'❌ متن پیام خصوصی نمی‌تواند خالی باشد.');return
        # Create a stable conversation ID BEFORE sending the message. The
        # callback never depends on a Telegram message_id/edit operation.
        chat_id=code('PV',d.setdefault('private_chats',{}))
        try:
            safe=html.escape(x)
            kb=InlineKeyboardMarkup().add(InlineKeyboardButton('↩️ پاسخ',callback_data=f'private_reply:{chat_id}'))
            sent=bot.send_message(int(target),f'💬 <b>پیام خصوصی از مدیریت</b>\n\n{safe}',reply_markup=kb)
            d.setdefault('private_chats',{})[chat_id]={'user_id':target,'admin_id':str(r),'status':'open','turn':'user','last_message_id':str(sent.message_id),'created_at':now()}
            d.setdefault('private_threads',{})[str(sent.message_id)]={'chat_id':chat_id,'user_id':target,'admin_id':str(r),'created_at':now(),'sender':'admin','text':x}
            save(d);states[r]={}
            bot.reply_to(m,f'✅ پیام خصوصی برای <code>{target}</code> ارسال شد.\n🆔 گفتگوی خصوصی: <code>{chat_id}</code>\n📌 کاربر با دکمه «پاسخ» می‌تواند پاسخ دهد.')
        except Exception as e:
            states[r]={}
            bot.reply_to(m,f'❌ ارسال پیام خصوصی انجام نشد.\nجزئیات: <code>{html.escape(str(e))[:700]}</code>')
        return
    if w in ('private_user_message','private_admin_message'):
        chat_id=str(st.get('private_chat','')); parent=str(st.get('private_parent',''))
        chat=d.get('private_chats',{}).get(chat_id,{})
        th=d.get('private_threads',{}).get(parent,{})
        if not chat or chat.get('status')!='open':
            states[r]={};bot.reply_to(m,'❌ این گفتگوی خصوصی بسته یا منقضی شده است.');return
        is_admin_side=(w=='private_admin_message' and admin(r))
        is_user_side=(w=='private_user_message' and str(r)==str(chat.get('user_id')))
        if not (is_admin_side or is_user_side):
            states[r]={};bot.reply_to(m,'⛔ این پاسخ متعلق به شما نیست.');return
        expected='admin' if is_admin_side else 'user'
        if chat.get('turn')!=expected:
            states[r]={};bot.reply_to(m,'⏳ فعلاً نوبت پاسخ طرف مقابل است.');return
        if not x:
            bot.reply_to(m,'❌ متن پاسخ نمی‌تواند خالی باشد.');return
        parent_text=str(th.get('text',''))
        try:
            safe_x=html.escape(x); safe_parent=html.escape(parent_text[:1200])
            if is_user_side:
                admin_id=int(chat.get('admin_id') or ADMIN_ID)
                text_out=f'💬 <b>پاسخ کاربر به پیام خصوصی</b>\n\n👤 کاربر: <code>{r}</code>\n🔑 CRV: <code>{html.escape(str(d.get("users",{}).get(str(r),{}).get("crv_code", "")))}</code>\n\n↩️ <b>پاسخ به پیام:</b>\n{safe_parent}\n\n📝 <b>متن پاسخ:</b>\n{safe_x}'
                sent=bot.send_message(admin_id,text_out,reply_markup=InlineKeyboardMarkup(row_width=2).add(InlineKeyboardButton('↩️ پاسخ',callback_data=f'private_reply:{chat_id}'),InlineKeyboardButton('🔒 بستن چت',callback_data=f'private_close:{chat_id}')))
                new_id=str(sent.message_id)
                d.setdefault('private_threads',{})[new_id]={'chat_id':chat_id,'user_id':chat['user_id'],'admin_id':str(chat.get('admin_id') or ADMIN_ID),'created_at':now(),'sender':'user','text':x,'reply_to_message_id':parent}
                chat['last_message_id']=new_id;chat['turn']='admin';save(d);states[r]={}
                bot.reply_to(m,'✅ پاسخ شما برای مدیریت ارسال شد.\n⏳ حالا منتظر پاسخ ادمین باشید.')
            else:
                user_id=int(chat['user_id'])
                text_out=f'📨 <b>پاسخ ادمین به پیام شما</b>\n\n↩️ <b>پاسخ به پیام:</b>\n{safe_parent}\n\n📝 <b>متن پاسخ ادمین:</b>\n{safe_x}'
                sent=bot.send_message(user_id,text_out,reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton('↩️ پاسخ',callback_data=f'private_reply:{chat_id}')))
                new_id=str(sent.message_id)
                d.setdefault('private_threads',{})[new_id]={'chat_id':chat_id,'user_id':chat['user_id'],'admin_id':str(r),'created_at':now(),'sender':'admin','text':x,'reply_to_message_id':parent}
                chat['last_message_id']=new_id;chat['turn']='user';save(d);states[r]={}
                bot.reply_to(m,'✅ پاسخ برای کاربر ارسال شد.')
        except Exception as e:
            bot.reply_to(m,f'❌ ارسال پاسخ انجام نشد.\nجزئیات: <code>{html.escape(str(e))[:700]}</code>')
        return
    if w=='ghost_pack_edit':
        target=str(st.get('ghost_target',''));oc=str(st.get('order',''))
        o=d['orders'].get(oc,{})
        if not target or target!=str(o.get('user_id')) or target not in d['users'] or o.get('status') not in ('approved','delivered'):
            states[r]={};bot.reply_to(m,'❌ دسترسی یا بسته معتبر نیست.');return
        o['config']=x;o['config_updated_at']=now();o['config_updated_by']=str(ADMIN_ID);save(d);states[r]={'ghost_target':target}
        bot.reply_to(m,f'✅ مشخصات/لینک بسته <code>{oc}</code> در حالت Ghost تغییر کرد.')
        try:
            bot.send_message(int(target),f'🔄 مشخصات بسته <code>{oc}</code> توسط مدیریت به‌روزرسانی شد.\n\n<code>{x}</code>')
        except Exception: pass
        return
    if w=='discount_apply':
        dc=x.upper();v=d.get('discounts',{}).get(dc);pid=st.get('pid')
        valid=bool(v)
        if valid and v.get('expires_at') and expired(v['expires_at']):valid=False
        if valid and v.get('limit',0) and int(v.get('used',0))>=int(v['limit']):valid=False
        if not valid:bot.reply_to(m,'❌ کد تخفیف نامعتبر، منقضی یا تمام‌شده است.');return
        price=int(d['packs'][pid].get('price',0));pct=max(0,min(100,int(v.get('percent',0))));amount=max(0,price-(price*pct//100));states[r]={'checkout':{'pid':pid,'amount':amount,'original_price':price,'discount_code':dc}}
        kb=InlineKeyboardMarkup().add(InlineKeyboardButton('🛍 تکمیل خرید',callback_data='checkout:'+pid),InlineKeyboardButton('🔴 بازگشت',callback_data='pack:'+pid))
        bot.reply_to(m,f'✅ کد تخفیف اعمال شد: {pct}%\n💰 مبلغ نهایی: {amount:,} تومان\n\n👇 برای ادامه خرید روی دکمه زیر بزنید:',reply_markup=kb)
        try:
            uname='@'+m.from_user.username if getattr(m.from_user,'username',None) else 'بدون یوزرنیم'
            admin_text=(f'🎟 <b>کد تخفیف توسط کاربر وارد شد</b>\n👤 کاربر: <code>{r}</code>\n🔗 Username: {html.escape(uname)}\n🔑 CRV: <code>{html.escape(str(d.get("users",{}).get(str(r),{}).get("crv_code","")))}</code>\n📦 بسته: {html.escape(str(d["packs"][pid].get("name","")))}\n🎟 کد: <code>{html.escape(dc)}</code>\n📌 تخفیف: <b>{pct}%</b>\n💰 مبلغ اصلی: <b>{price:,} تومان</b>\n💵 مبلغ نهایی: <b>{amount:,} تومان</b>')
            bot.send_message(ADMIN_ID,admin_text)
        except Exception:
            pass
        return
    if w=='discount':
        try:
            parts=[z.strip() for z in x.split('|')];dc=parts[0].upper();pct=int(parts[1]);limit=int(parts[2]);mins=int(parts[3]);
            if not dc or not (0<=pct<=100) or limit<0 or mins<0:raise ValueError
            d.setdefault('discounts',{})[dc]={'percent':pct,'limit':limit,'used':0,'expires_at':(time.time()+mins*60 if mins else None),'created_at':now()};save(d);states[r]={};bot.reply_to(m,f'✅ کد {dc} با تخفیف {pct}% ساخته شد.')
        except:bot.reply_to(m,'❌ قالب نامعتبر. CODE | درصد | محدودیت | دقیقه')
        return
    if w=='wallet_target':
        q=x.strip()
        target=None
        if q.isdigit() and q in d.get('users',{}):
            target=q
        else:
            target=next((uid for uid,uu in d.get('users',{}).items() if str(uu.get('crv_code','')).lower()==q.lower()),None)
        if not target:
            bot.reply_to(m,'❌ کاربر با این ID یا CRV پیدا نشد. دوباره ارسال کنید:')
            return
        if not can(r,'wallet_add'):
            states[r]={};bot.reply_to(m,'⛔ دسترسی افزایش موجودی کیف پول برای شما فعال نیست.');return
        states[r]={'ghost_target':target,'wait':'ghost_balance_add'}
        bot.reply_to(m,f'👤 کاربر انتخاب شد: <code>{target}</code>\n🔑 CRV: <code>{d["users"][target].get("crv_code","")}</code>\n💰 موجودی فعلی: {int(d["users"][target].get("balance",0)):,} تومان\n\n➕ مبلغ افزایش موجودی را به تومان ارسال کنید:')
        return
    if w=='dep_amount':
        try:a=int(x.replace(',',''))
        except:bot.reply_to(m,'❌ مبلغ نامعتبر');return
        if a<int(d['settings']['min_deposit']):bot.reply_to(m,f'❌ حداقل {int(d["settings"]["min_deposit"]):,} تومان');return
        st.update(wait='dep_receipt',amount=a);states[r]=st;bot.send_message(m.chat.id,f'💳 کارت: <code>{d["settings"]["card_number"]}</code>\n👤 {d["settings"]["card_holder"]}\n💰 {a:,} تومان\n📥 رسید را ارسال کنید.')
    elif w=='track':
        o=d['orders'].get(x) or d['deposits'].get(x)
        if not o:bot.reply_to(m,'❌ کد پیدا نشد.');return
        owner_user=d['users'].get(o.get('user_id'),{});p=d['packs'].get(o.get('pack_id'),{})
        track_kb=None
        if admin(r) and o.get('status')=='rejected' and can(r,'order_reapprove') and x in d.get('orders',{}):
            track_kb=InlineKeyboardMarkup().add(InlineKeyboardButton('♻️ تایید مجدد سفارش رد شده',callback_data='order_reapprove:'+x))
        if admin(r) and x in d.get('orders',{}) and o.get('payment_method')=='card' and o.get('receipt_file_id') and can(r,'orders'):
            if track_kb is None: track_kb=InlineKeyboardMarkup()
            track_kb.add(InlineKeyboardButton('🧾 مشاهده رسید پرداخت',callback_data='order_receipt:'+x))
        bot.reply_to(m,f'🔍 کد: <code>{x}</code>\n👤 کاربر: <code>{o.get("user_id")}</code>\n🔑 CRV: <code>{owner_user.get("crv_code","")}</code>\n📦 {p.get("name", "واریز کیف پول")}\n💰 {int(o.get("amount",0)):,}\n💳 {o.get("payment_method","کارت به کارت")}\n📌 وضعیت: {o.get("status",o.get("payment_status"))}\n🕒 {o.get("created_at")}',reply_markup=track_kb)
        states[r]={}
    elif w=='ticket_subject':
        st.update(wait='ticket_msg',subject=x);states[r]=st;bot.reply_to(m,'📝 متن تیکت:')
    elif w=='ticket_msg':
        tc=code('TKT',d['tickets']);
        t={'code':tc,'user_id':uid,'subject':st['subject'],'message':x,'answer':'','status':'open','turn':'admin','created_at':now(),'messages':[{'sender':'user','user_id':str(uid),'text':x,'created_at':now()}]}
        d['tickets'][tc]=t;save(d);states[r]={}
        safe_sub=html.escape(str(st.get('subject','-')));safe_x=html.escape(x);safe_tc=html.escape(tc);safe_crv=html.escape(str(u.get('crv_code','')))
        kb=InlineKeyboardMarkup(row_width=2).add(InlineKeyboardButton('↩️ پاسخ',callback_data='ticket_admin:'+tc),InlineKeyboardButton('🔒 بستن تیکت',callback_data='ticket_close:'+tc))
        try:
            bot.send_message(ADMIN_ID,f'🎫 <b>تیکت جدید</b>\n\n🆔 شناسه: <code>{safe_tc}</code>\n👤 کاربر: <code>{uid}</code>\n🔑 CRV: <code>{safe_crv}</code>\n📌 موضوع: {safe_sub}\n\n📝 متن تیکت:\n{safe_x}',reply_markup=kb)
        except Exception as e:
            # Keep the ticket saved even if admin delivery temporarily fails.
            bot.reply_to(m,f'⚠️ تیکت ثبت شد اما ارسال اعلان به مدیریت ناموفق بود.\nشناسه: <code>{safe_tc}</code>\nخطا: <code>{html.escape(str(e))[:500]}</code>')
            return
        bot.reply_to(m,f'✅ تیکت شما با موفقیت ثبت شد.\n\n🎫 شناسه: <code>{safe_tc}</code>\n📌 موضوع: {safe_sub}\n🟢 وضعیت: باز و در جریان\n\nبه محض پاسخ مدیریت، پاسخ برای شما ارسال می‌شود.')
    elif w=='ticket_track':
        t=d['tickets'].get(x)
        if not t or not (str(t.get('user_id'))==str(uid) or admin(r)):
            bot.reply_to(m,'❌ تیکت پیدا نشد.')
        else:
            msgs=t.get('messages',[]);last=msgs[-1].get('text','') if msgs else t.get('answer','')
            bot.reply_to(m,f'🎫 <b>{x}</b>\n📌 موضوع: {t.get("subject","-")}\n📍 وضعیت: {"🟢 باز و در جریان" if t.get("status")=="open" else "🔒 بسته"}\n\nآخرین پیام:\n{last}')
        states[r]={}
    elif w=='card':
        parts=[z.strip() for z in x.split('|',1)]
        if len(parts)!=2 or not parts[0] or not parts[1]:bot.reply_to(m,'❌ قالب صحیح: شماره کارت | نام صاحب کارت');return
        d['settings']['card_number']=parts[0];d['settings']['card_holder']=parts[1];save(d);states[r]={};bot.reply_to(m,'✅ شماره کارت و نام صاحب کارت با موفقیت تغییر کرد.')
    elif w=='ref_percent':
        try:
            v=int(x.replace('%','').strip())
            if not 0<=v<=100: raise ValueError
            d['settings']['referral_percent']=v;save(d);states[r]={};bot.reply_to(m,f'✅ درصد رفرال روی {v}% تنظیم شد.')
        except: bot.reply_to(m,'❌ درصد نامعتبر است. عددی بین 0 تا 100 وارد کنید.')
    elif w=='ref_times':
        try:
            v=int(x.strip())
            if v<1: raise ValueError
            d['settings']['referral_max_rewards']=v;save(d);states[r]={};bot.reply_to(m,f'✅ دفعات رفرال روی {v} بار برای هر دعوت‌شده تنظیم شد.')
        except: bot.reply_to(m,'❌ تعداد نامعتبر است. عدد صحیح بزرگ‌تر از صفر وارد کنید.')
    elif w=='min':
        try:d['settings']['min_deposit']=int(x.replace(',',''));save(d);states[r]={};bot.reply_to(m,'✅ حداقل واریز تغییر کرد.')
        except:bot.reply_to(m,'❌ مبلغ نامعتبر')
    elif w=='link':
        link=x.strip()
        if link.startswith('@'):
            link='https://t.me/'+link[1:]
        elif not link.startswith(('https://t.me/','http://t.me/','tg://')):
            bot.reply_to(m,'❌ لینک معتبر نیست. مثال: https://t.me/YourUsername یا @YourUsername')
            return
        d['settings']['admin_link']=link
        save(d);states[r]={};bot.reply_to(m,'✅ لینک PV تغییر کرد.')
    elif w=='guide':d['settings']['guide_text']=x;save(d);states[r]={};bot.reply_to(m,'✅ راهنما تغییر کرد.')
    elif w=='rules':d['settings']['rules_text']=x;save(d);states[r]={};bot.reply_to(m,'✅ قوانین تغییر کرد.')
    elif w=='free_config':d['settings']['free_config']=x;save(d);states[r]={};bot.reply_to(m,'✅ کانفیگ رایگان تغییر کرد.')
    elif w=='welcome':d['settings']['welcome_text']=x;save(d);states[r]={};bot.reply_to(m,'✅ متن خوش‌آمد تغییر کرد.')
    elif w in ('ghost_balance_add','ghost_balance_sub'):
        needed_perm='wallet_add' if w=='ghost_balance_add' else 'wallet_subtract'
        if not can(r,needed_perm):
            states[r]={};bot.reply_to(m,'⛔ دسترسی این عملیات برای شما فعال نیست.');return
        try: amount=int(x.replace(',','').replace('٬','').replace(' ',''))
        except: bot.reply_to(m,'❌ مبلغ نامعتبر است.'); return
        target=st.get('ghost_target')
        if not target or target not in d['users']: bot.reply_to(m,'❌ کاربر Ghost پیدا نشد.'); return
        old=int(d['users'][target].get('balance',0))
        if w=='ghost_balance_sub' and amount>old: bot.reply_to(m,'❌ موجودی کاربر کافی نیست.'); return
        d['users'][target]['balance']=old+amount if w=='ghost_balance_add' else old-amount
        dc=None
        if w=='ghost_balance_add':
            dc=code('DEP',d.setdefault('deposits',{}))
            d['deposits'][dc]={
                'code':dc,'tracking_id':dc,'user_id':target,'amount':amount,
                'status':'approved','payment_method':'admin_manual','source':'admin_manual',
                'admin_id':str(r),'approved_by':str(r),'approved_at':now(),'created_at':now(),
                'receipt_file_id':None,'note':'افزایش موجودی دستی توسط ادمین'
            }
        save(d); states[r]={'ghost_target':target}
        bot.reply_to(m,f'✅ موجودی کاربر {target} به {int(d["users"][target]["balance"]):,} تومان تغییر کرد.' + (f'\n🆔 شناسه افزایش: <code>{dc}</code>' if dc else ''))
    elif w=='broadcast':
        if not x:
            bot.reply_to(m,'❌ متن پیام همگانی نمی‌تواند خالی باشد.');return
        safe=html.escape(x)
        ids=list(d.get('users',{}).keys())
        n=0;failed=0;blocked=0
        for z in ids:
            try:
                bot.send_message(int(z),safe,disable_web_page_preview=True)
                n+=1
                # Small pacing prevents Telegram flood-limit failures on larger DBs.
                if n % 25 == 0: time.sleep(0.7)
            except Exception as e:
                failed+=1
                msg=str(e).lower()
                if 'blocked' in msg or 'chat not found' in msg or 'user is deactivated' in msg:
                    blocked+=1
        states[r]={}
        bot.reply_to(m,f'📢 <b>نتیجه پیام همگانی</b>\n\n👥 کل کاربران: {len(ids)}\n✅ ارسال موفق: {n}\n❌ ناموفق: {failed}\n🚫 مسدود/غیرفعال: {blocked}')
    elif w=='ghost':
        target=x if x in d['users'] else next((z for z,v in d['users'].items() if v.get('crv_code','').lower()==x.lower()),None)
        if not target and x in d.get('admins',{}): target=x
        if target: states[r]={'ghost_target':target}; bot.reply_to(m,f'👻 Ghost فعال شد. /start را بزنید.')
        else:bot.reply_to(m,'❌ کاربر پیدا نشد.')
    elif w=='restrict':
        target=x if x in d['users'] else next((z for z,v in d['users'].items() if v.get('crv_code','').lower()==x.lower()),None)
        if not target:bot.reply_to(m,'❌ کاربر پیدا نشد.');return
        mk=InlineKeyboardMarkup().add(InlineKeyboardButton('🚫 دائم',callback_data='block_perm:'+target),InlineKeyboardButton('⏱ موقت',callback_data='block_temp:'+target),InlineKeyboardButton('🛍 محدودیت سفارش',callback_data='limit_orders:'+target),InlineKeyboardButton('💰 محدودیت واریز',callback_data='limit_deposits:'+target),InlineKeyboardButton('🔓 رفع همه',callback_data='unlimit:'+target));bot.reply_to(m,'نوع محدودیت:',reply_markup=mk);states[r]={}
    elif w=='duration':
        try:minutes=int(x);until=time.time()+minutes*60
        except:bot.reply_to(m,'❌ دقیقه نامعتبر');return
        uu=d['users'][st['target']];
        if st['action']=='block':uu['blocked']=True;uu['blocked_until']=until
        else:uu['restrictions'][st['action']]=until
        save(d);states[r]={};bot.reply_to(m,'✅ محدودیت زمانی اعمال شد.')
    elif w in ('ticket_answer','ticket_admin_reply','ticket_user_reply'):
        tc=str(st.get('ticket',''));t=d.get('tickets',{}).get(tc)
        if not t or t.get('status')!='open':
            states[r]={};bot.reply_to(m,'❌ این تیکت بسته شده یا پیدا نشد.');return
        if not x:
            bot.reply_to(m,'❌ متن پاسخ نمی‌تواند خالی باشد.');return
        is_admin_side=w in ('ticket_answer','ticket_admin_reply')
        try:
            if is_admin_side:
                if not admin(r) or t.get('turn','admin')!='admin':
                    bot.reply_to(m,'⏳ فعلاً منتظر پاسخ کاربر باشید.');return
                # Send first; only mutate DB after Telegram accepts the message.
                safe_x=html.escape(x); safe_sub=html.escape(str(t.get('subject','-'))); safe_tc=html.escape(tc)
                kb=InlineKeyboardMarkup().add(InlineKeyboardButton('↩️ پاسخ به ادمین',callback_data=f'ticket_reply:{tc}'))
                bot.send_message(int(t['user_id']),f'📨 <b>پاسخ ادمین به تیکت شما</b>\n\n🎫 شناسه تیکت: <code>{safe_tc}</code>\n📌 موضوع: {safe_sub}\n\n📝 متن پاسخ ادمین:\n{safe_x}\n\n🟢 وضعیت: تیکت همچنان باز و در جریان است.',reply_markup=kb)
                t['answer']=x;t['last_admin_at']=now();t['turn']='user'
                t.setdefault('messages',[]).append({'sender':'admin','admin_id':str(r),'text':x,'created_at':now()})
                save(d);states[r]={}
                bot.reply_to(m,f'✅ پاسخ ادمین به تیکت <code>{safe_tc}</code> برای کاربر ارسال شد.\n🟢 تیکت همچنان باز است.')
            else:
                if str(r)!=str(t.get('user_id')) or t.get('turn','admin')!='user':
                    bot.reply_to(m,'⏳ فعلاً منتظر پاسخ ادمین باشید.');return
                safe_x=html.escape(x);safe_sub=html.escape(str(t.get('subject','-')));safe_tc=html.escape(tc)
                crv=html.escape(str(d.get('users',{}).get(str(r),{}).get('crv_code','')))
                kb=InlineKeyboardMarkup(row_width=2).add(InlineKeyboardButton('↩️ پاسخ',callback_data=f'ticket_admin:{tc}'),InlineKeyboardButton('🔒 بستن تیکت',callback_data=f'ticket_close:{tc}'))
                bot.send_message(int(ADMIN_ID),f'💬 <b>پاسخ کاربر به تیکت</b>\n\n🎫 شناسه تیکت: <code>{safe_tc}</code>\n👤 کاربر: <code>{r}</code>\n🔑 CRV: <code>{crv}</code>\n📌 موضوع: {safe_sub}\n\n📝 متن پاسخ کاربر:\n{safe_x}\n\n🟢 وضعیت: تیکت باز و در جریان است.',reply_markup=kb)
                t['turn']='admin';t.setdefault('messages',[]).append({'sender':'user','user_id':str(r),'text':x,'created_at':now()})
                save(d);states[r]={}
                bot.reply_to(m,f'✅ پاسخ شما به تیکت <code>{safe_tc}</code> برای مدیریت ارسال شد.\n⏳ حالا منتظر پاسخ ادمین باشید.')
        except Exception as e:
            bot.reply_to(m,f'❌ ارسال پاسخ انجام نشد؛ وضعیت تیکت تغییر نکرد.\nجزئیات: <code>{html.escape(str(e))[:700]}</code>')
        return
    elif w=='vpn':
        o=d['orders'].get(st['order'])
        if not o: bot.reply_to(m,'❌ سفارش پیدا نشد.');states[r]={};return
        if o.get('status') not in ('approved','pending'): bot.reply_to(m,'⚠️ این سفارش قبلاً نهایی شده است.');states[r]={};return
        o['status']='delivered';o['payment_status']='paid';o['config']=x;o['delivered_at']=now();save(d)
        bot.send_message(o['user_id'],f'🎉 سفارش <code>{o["code"]}</code> تایید و تحویل شد.\n\n<code>{x}</code>')
        states[r]={};bot.reply_to(m,f'✅ کانفیگ سفارش <code>{o["code"]}</code> با موفقیت برای مشتری ارسال شد.')
    elif w=='join':
        ls=x.splitlines();
        if len(ls)>=2:d['settings']['channel_id']=ls[0].strip();d['settings']['channel_link']=ls[1].strip();d['settings']['force_join']=True;save(d);states[r]={};bot.reply_to(m,'✅ عضویت اجباری روشن و کانال تنظیم شد.')
    elif w=='p_name':st['p']['name']=x;st['wait']='p_price';states[r]=st;bot.reply_to(m,'قیمت:')
    elif w=='p_price':
        try:st['p']['price']=int(x.replace(',',''));st['wait']='p_volume';states[r]=st;bot.reply_to(m,'حجم:')
        except:bot.reply_to(m,'❌ قیمت نامعتبر')
    elif w=='p_volume':st['p']['volume']=x;st['wait']='p_duration';states[r]=st;bot.reply_to(m,'مدت:')
    elif w=='p_duration':st['p']['duration']=x;st['wait']='p_desc';states[r]=st;bot.reply_to(m,'توضیحات:')
    elif w=='p_desc':st['p']['desc']=x;st['p']['active']=True;pid='P'+uuid.uuid4().hex[:6].upper();d['packs'][pid]=st['p'];save(d);states[r]={};bot.reply_to(m,f'✅ بسته ساخته شد: {pid}')
    elif w=='p_json':
        try:d['packs'][st['pid']]=json.loads(x);save(d);states[r]={};bot.reply_to(m,'✅ بسته ویرایش شد.')
        except Exception as e:bot.reply_to(m,f'❌ JSON نامعتبر: {e}')
if __name__=='__main__':
    print(f'Bot 28.0 lookup-update is running... Owner ID: {OWNER_ID}');bot.infinity_polling(skip_pending=True)

"""
Премиум-эмодзи Telegram.

Все эмодзи оформляются HTML-тегом <tg-emoji emoji-id="...">⚙️</tg-emoji>.
Юзер с Telegram Premium увидит кастомные иконки, остальные — fallback emoji.

В кнопках (InlineKeyboardButton) используется поле icon_custom_emoji_id.
"""

# ─── HTML-обёртки для текста сообщений ──────────────────────────────────────

def e(emoji_id: str, fallback: str) -> str:
    """Возвращает HTML-тег премиум-эмодзи с fallback-символом."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# ─── Идентификаторы премиум-эмодзи ──────────────────────────────────────────
ID_SETTINGS         = "5870982283724328568"
ID_PROFILE          = "5870994129244131212"
ID_PEOPLE           = "5870772616305839506"
ID_PERSON_CHECK     = "5891207662678317861"
ID_PERSON_X         = "5893192487324880883"
ID_FILE             = "5870528606328852614"
ID_SMILE            = "5870764288364252592"
ID_GRAPH_UP         = "5870930636742595124"
ID_STATS            = "5870921681735781843"
ID_HOUSE            = "5873147866364514353"
ID_LOCK_CLOSED      = "6037249452824072506"
ID_LOCK_OPEN        = "6037496202990194718"
ID_MEGAPHONE        = "6039422865189638057"
ID_CHECK            = "5870633910337015697"
ID_CROSS            = "5870657884844462243"
ID_PENCIL           = "5870676941614354370"
ID_TRASH            = "5870875489362513438"
ID_DOWN             = "5893057118545646106"
ID_PAPERCLIP        = "6039451237743595514"
ID_LINK             = "5769289093221454192"
ID_INFO             = "6028435952299413210"
ID_BOT              = "6030400221232501136"
ID_EYE              = "6037397706505195857"
ID_EYE_HIDDEN       = "6037243349675544634"
ID_SEND             = "5963103826075456248"
ID_DOWNLOAD         = "6039802767931871481"
ID_BELL             = "6039486778597970865"
ID_GIFT             = "6032644646587338669"
ID_CLOCK            = "5983150113483134607"
ID_PARTY            = "6041731551845159060"
ID_FONT             = "5870801517140775623"
ID_WRITE            = "5870753782874246579"
ID_MEDIA            = "6035128606563241721"
ID_GEO              = "6042011682497106307"
ID_WALLET           = "5769126056262898415"
ID_BOX              = "5884479287171485878"
ID_CRYPTO           = "5260752406890711732"
ID_CALENDAR         = "5890937706803894250"
ID_TAG              = "5886285355279193209"
ID_TIME_PASSED      = "5775896410780079073"
ID_APPS             = "5778672437122045013"
ID_BRUSH            = "6050679691004612757"
ID_ADD_TEXT         = "5771851822897566479"
ID_RESIZE           = "5778479949572738874"
ID_MONEY            = "5904462880941545555"
ID_SEND_MONEY       = "5890848474563352982"
ID_RECEIVE_MONEY    = "5879814368572478751"
ID_CODE             = "5940433880585605708"
ID_LOADING          = "5345906554510012647"


# ─── Текстовые токены ──────────────────────────────────────────────────────
SETTINGS        = e(ID_SETTINGS,        "⚙️")
PROFILE         = e(ID_PROFILE,         "👤")
PEOPLE          = e(ID_PEOPLE,          "👥")
PERSON_CHECK    = e(ID_PERSON_CHECK,    "👤")
PERSON_X        = e(ID_PERSON_X,        "👤")
FILE            = e(ID_FILE,            "📁")
SMILE           = e(ID_SMILE,           "🙂")
GRAPH_UP        = e(ID_GRAPH_UP,        "📊")
STATS           = e(ID_STATS,           "📊")
HOUSE           = e(ID_HOUSE,           "🏘")
LOCK_CLOSED     = e(ID_LOCK_CLOSED,     "🔒")
LOCK_OPEN       = e(ID_LOCK_OPEN,       "🔓")
MEGAPHONE       = e(ID_MEGAPHONE,       "📣")
CHECK           = e(ID_CHECK,           "✅")
CROSS           = e(ID_CROSS,           "❌")
PENCIL          = e(ID_PENCIL,          "🖋")
TRASH           = e(ID_TRASH,           "🗑")
DOWN            = e(ID_DOWN,            "📰")
PAPERCLIP       = e(ID_PAPERCLIP,       "📎")
LINK            = e(ID_LINK,            "🔗")
INFO            = e(ID_INFO,            "ℹ")
BOT             = e(ID_BOT,             "🤖")
EYE             = e(ID_EYE,             "👁")
EYE_HIDDEN      = e(ID_EYE_HIDDEN,      "👁")
SEND            = e(ID_SEND,            "⬆")
DOWNLOAD        = e(ID_DOWNLOAD,        "⬇")
BELL            = e(ID_BELL,            "🔔")
GIFT            = e(ID_GIFT,            "🎁")
CLOCK           = e(ID_CLOCK,           "⏰")
PARTY           = e(ID_PARTY,           "🎉")
FONT            = e(ID_FONT,            "🔗")
WRITE           = e(ID_WRITE,           "✍")
MEDIA           = e(ID_MEDIA,           "🖼")
GEO             = e(ID_GEO,             "📍")
WALLET          = e(ID_WALLET,          "👛")
BOX             = e(ID_BOX,             "📦")
CRYPTO          = e(ID_CRYPTO,          "👾")
CALENDAR        = e(ID_CALENDAR,        "📅")
TAG             = e(ID_TAG,             "🏷")
TIME_PASSED     = e(ID_TIME_PASSED,     "🕓")
APPS            = e(ID_APPS,            "📦")
BRUSH           = e(ID_BRUSH,           "🖌")
ADD_TEXT        = e(ID_ADD_TEXT,        "🔡")
RESIZE          = e(ID_RESIZE,          "↔")
MONEY           = e(ID_MONEY,           "🪙")
SEND_MONEY      = e(ID_SEND_MONEY,      "🪙")
RECEIVE_MONEY   = e(ID_RECEIVE_MONEY,   "🏧")
CODE            = e(ID_CODE,            "🔨")
LOADING         = e(ID_LOADING,         "🔄")
BACK            = "◁"

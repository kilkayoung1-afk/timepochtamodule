 # meta developer: @Kilka_Young
# scope: hikka_only

__version__ = (4, 0, 0)

import asyncio
import io
import gzip
import json
import random
import string

from telethon.tl import functions, types
from telethon.tl.types import MessageEntityCustomEmoji

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen

from .. import loader, utils

MAX_ITEMS = 90


def gen_name():
    return "mypig_" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))


# ─── TEXT → SHAPES ─────────────────────────────────────────────

def text_to_shapes(text, font_path, scale=0.1):
    font = TTFont(font_path)
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()

    shapes = []
    x_offset = 0

    for ch in text:
        glyph_name = cmap.get(ord(ch))
        if not glyph_name:
            x_offset += 50
            continue

        glyph = gs[glyph_name]
        pen = RecordingPen()
        glyph.draw(pen)

        verts = []

        for op, pts in pen.value:
            if op == "moveTo":
                x, y = pts[0]
                verts.append([x * scale + x_offset, -y * scale])
            elif op == "lineTo":
                x, y = pts[0]
                verts.append([x * scale + x_offset, -y * scale])

        if verts:
            shapes.append({
                "ty": "sh",
                "ks": {
                    "a": 0,
                    "k": {
                        "v": verts,
                        "i": [[0, 0]] * len(verts),
                        "o": [[0, 0]] * len(verts),
                        "c": True
                    }
                }
            })

        x_offset += glyph.width * scale

    return shapes


# ─── REPLACE TEXT ─────────────────────────────────────────────

def replace_text_tgs(data, text):
    raw = gzip.decompress(data)
    lottie = json.loads(raw.decode())

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    shapes = text_to_shapes(text, font_path)

    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("ty") == "gr" and "it" in obj:
                obj["it"] = shapes + [x for x in obj["it"] if x.get("ty") != "sh"]
                return True
            for v in obj.values():
                if walk(v):
                    return True
        elif isinstance(obj, list):
            for i in obj:
                if walk(i):
                    return True
        return False

    walk(lottie)

    return gzip.compress(json.dumps(lottie).encode())


# ─── MODULE ───────────────────────────────────────────────────

@loader.tds
class MyPigAIGod(loader.Module):
    """mypigAI GOD — генерация текста в TGS"""

    strings = {"name": "mypigAI GOD"}

    def __init__(self):
        self.sessions = {}

    async def _get_docs(self, message):
        reply = await message.get_reply_message()
        if not reply:
            return []

        result = []

        for ent in (reply.entities or []):
            if isinstance(ent, MessageEntityCustomEmoji):
                docs = await self._client(
                    functions.messages.GetCustomEmojiDocumentsRequest(
                        document_id=[ent.document_id]
                    )
                )
                if docs:
                    result.append(docs[0])

        return result

    async def _upload(self, buf, doc):
        file = await self._client.upload_file(buf)

        media = types.InputMediaUploadedDocument(
            file=file,
            mime_type=doc.mime_type,
            attributes=[
                types.DocumentAttributeFilename(file_name="sticker.tgs"),
                types.DocumentAttributeCustomEmoji(alt="✨")
            ],
        )

        res = await self._client(
            functions.messages.UploadMediaRequest(peer="me", media=media)
        )

        return types.InputStickerSetItem(
            document=types.InputDocument(
                id=res.document.id,
                access_hash=res.document.access_hash,
                file_reference=res.document.file_reference,
            ),
            emoji="✨",
        )

    async def _create(self, call, uid):
        s = self.sessions[uid]

        docs = s["docs"]
        text = s["text"]

        while len(docs) < MAX_ITEMS:
            docs += docs
        docs = docs[:MAX_ITEMS]

        me = await self._client.get_me()
        short_name = gen_name() + "_by_" + (me.username or "user")

        items = []

        for i, doc in enumerate(docs):
            try:
                data = await self._client.download_media(doc, bytes)

                if doc.mime_type == "application/x-tgsticker":
                    new_data = replace_text_tgs(data, text)
                    buf = io.BytesIO(new_data)
                else:
                    continue

                item = await self._upload(buf, doc)
                items.append(item)

            except:
                pass

            if i % 5 == 0:
                await call.edit(f"⏳ {i+1}/90")

            await asyncio.sleep(0.03)

        await self._client(
            functions.stickers.CreateStickerSetRequest(
                user_id=me.id,
                title=f"{text} Pack",
                short_name=short_name,
                stickers=items,
                emojis=True,
            )
        )

        link = f"https://t.me/addemoji/{short_name}"

        await call.edit(f"✅ Готово!\n\n🔗 {link}")

        self.sessions.pop(uid, None)

    @loader.command()
    async def piggod(self, message):
        """Создать текстовый TGS пак"""

        docs = await self._get_docs(message)

        if not docs:
            await utils.answer(message, "❌ Ответь на эмодзи")
            return

        uid = message.sender_id
        self.sessions[uid] = {"docs": docs, "text": None}

        await message.delete()

        await self.inline.form(
            text="✍️ Введи текст:",
            reply_markup=[
                [{"text": "Ввести", "input": "Текст", "handler": self._set_text, "args": (uid,)}]
            ],
            message=message
        )

    async def _set_text(self, call, value, uid):
        self.sessions[uid]["text"] = value.strip()

        await call.edit(
            "🚀 Создать пак?",
            reply_markup=[
                [{"text": "Создать", "callback": self._start, "args": (uid,)}]
            ]
        )

    async def _start(self, call, uid):
        await call.edit("⏳ Генерация...")
        asyncio.create_task(self._create(call, uid))
# ╔══════════════════════════════════════════════════════════════════╗
# ║ 🐷 PiggyPack ║
# ║ Автоматическая генерация паков на 90 стикеров/эмодзи ║
# ╚══════════════════════════════════════════════════════════════════╝
# meta developer: @Kilka_Young
# scope: hikka_only
# scope: hikka_min 1.6.3
# requires: Pillow fonttools

__version__ = (1, 0, 0)

import asyncio
import colorsys
import gzip
import io
import json
import re
from typing import Any, Dict

from PIL import Image
from telethon.tl import functions, types
from telethon.tl.types import (
    DocumentAttributeSticker,
    DocumentAttributeCustomEmoji,
    InputStickerSetEmpty,
    Message,
    MessageEntityCustomEmoji,
)

from .. import loader, utils

# Премиум эмодзи для красивого интерфейса
PE = {
    "ok": "5870633910337015697",
    "err": "5870657884844462243",
    "pig": "5422894157141549420", # Замените на ID нужного вам эмодзи свинки, если есть
    "pack": "5778672437122045013",
    "palette": "5870676941614354370",
    "link": "5769289093221454192",
    "clock": "5983150113483134607",
    "sticker": "5886285355279193209",
}

def pe(emoji: str, eid: str) -> str:
    return f'<emoji document_id="{eid}">{emoji}</emoji>'

def hex_to_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def get_gradient_hex(iteration: int, total: int = 90) -> str:
    """Генерирует HEX цвет по кругу (HSV) для создания градиента из 90 оттенков."""
    r, g, b = colorsys.hsv_to_rgb(iteration / total, 0.85, 0.95)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

def tint_image(img: Image.Image, hex_color: str) -> Image.Image:
    r, g, b = hex_to_rgb(hex_color)
    img = img.convert("RGBA")
    data = img.load()
    for y in range(img.height):
        for x in range(img.width):
            ro, go, bo, ao = data[x, y]
            if ao > 0:
                gray = int(0.299 * ro + 0.587 * go + 0.114 * bo)
                data[x, y] = (int(r * gray / 255), int(g * gray / 255), int(b * gray / 255), ao)
    return img

def tint_lottie(lottie_json: dict, hex_color: str) -> dict:
    r, g, b = hex_to_rgb(hex_color)
    nr, ng, nb = r / 255, g / 255, b / 255

    def _walk(obj):
        if isinstance(obj, dict):
            if "c" in obj and isinstance(obj["c"], dict) and "k" in obj["c"]:
                k = obj["c"]["k"]
                if isinstance(k, list) and len(k) >= 3 and isinstance(k[0], (int, float)):
                    gray = 0.299 * k[0] + 0.587 * k[1] + 0.114 * k[2]
                    obj["c"]["k"] = [nr * gray, ng * gray, nb * gray] + (k[3:] or [1.0])
                elif isinstance(k, list):
                    for kf in k:
                        if isinstance(kf, dict) and "s" in kf:
                            s = kf["s"]
                            if isinstance(s, list) and len(s) >= 3:
                                gray = 0.299 * s[0] + 0.587 * s[1] + 0.114 * s[2]
                                kf["s"] = [nr * gray, ng * gray, nb * gray] + (s[3:] or [1.0])
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
    _walk(lottie_json)
    return lottie_json

async def recolor_document(client, doc, hex_color: str) -> io.BytesIO:
    data = await client.download_media(doc, bytes)
    mime = getattr(doc, "mime_type", "")
    if mime == "application/x-tgsticker":
        raw = gzip.decompress(data)
        lottie = json.loads(raw)
        lottie = tint_lottie(lottie, hex_color)
        compressed = gzip.compress(json.dumps(lottie).encode())
        buf = io.BytesIO(compressed)
        buf.name = "sticker.tgs"
    else:
        img = Image.open(io.BytesIO(data)).convert("RGBA").resize((512, 512), Image.LANCZOS)
        img = tint_image(img, hex_color)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", lossless=True)
        buf.seek(0)
        buf.name = "sticker.webp"
        buf.seek(0)
    return buf

def validate_short_name(name: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_]{1,64}", name))

async def _upload_sticker_item(client, me_entity, uploaded_file, mime: str, emoji_str: str, is_emoji_pack: bool):
    if is_emoji_pack:
        sticker_attr = types.DocumentAttributeCustomEmoji(
            alt=emoji_str, stickerset=types.InputStickerSetEmpty(), free=False, text_color=False,
        )
    else:
        sticker_attr = types.DocumentAttributeSticker(
            alt=emoji_str, stickerset=types.InputStickerSetEmpty(),
        )
    
    file_name = "sticker.tgs" if mime == "application/x-tgsticker" else "sticker.webp"
    
    media = types.InputMediaUploadedDocument(
        file=uploaded_file, mime_type=mime,
        attributes=[types.DocumentAttributeFilename(file_name=file_name), sticker_attr],
    )
    result = await client(functions.messages.UploadMediaRequest(peer=me_entity, media=media))
    real_doc = result.document
    return types.InputStickerSetItem(
        document=types.InputDocument(
            id=real_doc.id, access_hash=real_doc.access_hash, file_reference=real_doc.file_reference,
        ),
        emoji=emoji_str,
    )

@loader.tds
class PiggyPackMod(loader.Module):
    """Генератор паков из 90 стикеров/эмодзи. Канал: @mypigAI"""

    strings = {"name": "PiggyPack"}

    def __init__(self):
        self._sessions: Dict[int, Dict[str, Any]] = {}

    @loader.command()
    async def pigpack(self, message: Message):
        """Ответьте на стикер/премиум эмодзи, чтобы сгенерировать пак из 90 вариаций"""
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, pe("❌", PE["err"]) + " Ответьте на стикер или премиум эмодзи.")
            return

        target_doc = None

        if reply.sticker:
            target_doc = reply.sticker
        else:
            for ent in (reply.entities or []):
                if isinstance(ent, MessageEntityCustomEmoji):
                    emoji_docs = await self._client(
                        functions.messages.GetCustomEmojiDocumentsRequest(document_id=[ent.document_id])
                    )
                    if emoji_docs:
                        target_doc = emoji_docs[0]
                        break

        if not target_doc:
            await utils.answer(message, pe("❌", PE["err"]) + " Не найден стикер или премиум эмодзи.")
            return

        uid = message.sender_id
        self._sessions[uid] = {
            "doc": target_doc,
            "target_type": None,
            "pack_name": None,
            "step": "type",
            "total_items": 90
        }

        await message.delete()
        await self.inline.form(text=self._step_text(uid), reply_markup=self._step_markup(uid), message=message)

    def _step_text(self, uid: int) -> str:
        s = self._sessions[uid]
        step = s["step"]
        if step == "type":
            return (pe("🐷", PE.get("pig", PE["sticker"])) + " <b>mypigAI | Генератор Паков</b>\n\n"
                    "Вы выбрали базовый элемент. Что мы будем создавать (90 шт.)?")
        if step == "name":
            type_label = "эмодзи" if s["target_type"] == "emoji" else "стикеров"
            return (pe("🏷", PE["sticker"]) + f" <b>Введите название для пака {type_label}</b>\n\n"
                    "Введите короткое имя (латиница, цифры, _).")
        return pe("⏰", PE["clock"]) + " <b>Генерация пака (90 элементов)...</b>\n\nЭто может занять некоторое время."

    def _step_markup(self, uid: int):
        s = self._sessions[uid]
        step = s["step"]
        if step == "type":
            return [[
                {"text": "Стикеры (90 шт)", "icon_custom_emoji_id": PE["sticker"], "callback": self._cb_set_type, "args": (uid, "sticker")},
                {"text": "Эмодзи (90 шт)", "icon_custom_emoji_id": PE["pack"], "callback": self._cb_set_type, "args": (uid, "emoji")},
            ]]
        if step == "name":
            return [[{"text": "Ввести название", "icon_custom_emoji_id": PE["palette"], "input": "Введите short_name (a-z, 0-9, _)", "handler": self._input_name, "args": (uid,)}]]
        return []

    async def _cb_set_type(self, call, uid: int, pack_type: str):
        s = self._sessions.get(uid)
        if not s:
            await call.answer("Сессия устарела.", show_alert=True); return
        s["target_type"] = pack_type
        s["step"] = "name"
        await call.edit(text=self._step_text(uid), reply_markup=self._step_markup(uid))

    async def _input_name(self, call, value: str, uid: int):
        s = self._sessions.get(uid)
        if not s:
            await call.answer("Сессия устарела.", show_alert=True); return
        clean = value.strip().lower()
        if not validate_short_name(clean):
            await call.answer("Только a-z, 0-9, _ (1-64 символа).", show_alert=True); return
        
        me = await self._client.get_me()
        s["pack_name"] = clean + "_by_" + (me.username or "userbot")
        s["step"] = "processing"
        
        await call.edit(text=self._step_text(uid))
        asyncio.ensure_future(self._do_generate(call, uid))

    async def _do_generate(self, call, uid: int):
        s = self._sessions[uid]
        doc = s["doc"]
        pack_name = s["pack_name"]
        pack_type = s["target_type"]
        total = s["total_items"]
        
        me = await self._client.get_me()
        me_entity = await self._client.get_input_entity("me")
        input_stickers = []

        # Защита от флуда и спама редактированиями
        for i in range(total):
            try:
                # Получаем цвет из градиента
                color = get_gradient_hex(i, total)
                buf = await recolor_document(self._client, doc, color)
                uploaded = await self._client.upload_file(buf, file_name=buf.name)
                
                mime = getattr(doc, "mime_type", "image/webp")
                emoji_str = "🐷"
                
                item = await _upload_sticker_item(self._client, me_entity, uploaded, mime, emoji_str, pack_type == "emoji")
                input_stickers.append(item)
            except Exception as e:
                pass # Пропускаем ошибки отдельных фреймов/стикеров

            # Обновляем UI каждые 5 стикеров, чтобы не получить лимит на редактирование
            if i % 5 == 0 or i == total - 1:
                bar = "█" * int((i + 1) / total * 10) + "░" * (10 - int((i + 1) / total * 10))
                pct = int((i + 1) / total * 100)
                try:
                    await call.edit(text=(
                        pe("⏰", PE["clock"]) + " <b>Генерация 90 элементов...</b>\n\n"
                        f"<code>[{bar}]</code> {pct}%\n"
                        f"Обработано: <b>{i + 1}/{total}</b>\n\n"
                        "<i>Powered by @mypigAI</i>"
                    ))
                except:
                    pass
            
            await asyncio.sleep(0.1) # Задержка во избежание FloodWait

        try:
            if not input_stickers:
                raise ValueError("Не удалось сгенерировать элементы")
            
            is_emojis = (pack_type == "emoji")
            await self._client(functions.stickers.CreateStickerSetRequest(
                user_id=me.id,
                title=f"Piggy {pack_type.capitalize()} Pack",
                short_name=pack_name,
                stickers=input_stickers,
                emojis=is_emojis,
            ))
            pack_link = f"https://t.me/{'addemoji' if is_emojis else 'addstickers'}/{pack_name}"
            
        except Exception as e:
            await call.edit(text=pe("❌", PE["err"]) + f" <b>Ошибка:</b>\n<code>{str(e)}</code>"); return

        type_label = "Стикерпак" if pack_type == "sticker" else "Эмодзи-пак"
        await call.edit(
            text=(pe("✅", PE["ok"]) + " <b>Успешно сгенерировано!</b>\n\n"
                  f"{pe('🐷', PE.get('pig', PE['sticker']))} {type_label} на 90 элементов создан.\n"
                  f"{pe('📦', PE['pack'])} Градиентная заливка применена.\n\n"
                  f"{pe('🔗', PE['link'])} <a href=\"{pack_link}\">{pack_link}</a>\n\n"
                  "<b>Владелец:</b> @Kilka_Young\n<b>Канал:</b> https://t.me/mypigAI"),
            reply_markup=[[{"text": "Открыть пак", "icon_custom_emoji_id": PE["link"], "url": pack_link}]],
        )
        self._sessions.pop(uid, None)

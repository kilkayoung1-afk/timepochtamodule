# meta developer: @Kilka_Young
# meta desc: NFT Gift → Lottie/TGS с кастомным текстом
# scope: hikka_only
# requires: aiohttp fonttools

import gzip
import html
import io
import json
import logging
import os
import re
from urllib.parse import quote, urlparse

import aiohttp
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    InputStickerSetEmpty,
    Message,
)

from .. import loader, utils

logger = logging.getLogger(__name__)


__version__ = (1, 0, 0)

NFT_LINK_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/nft/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
FRAGMENT_LINK_RE = re.compile(
    r"(?:https?://)?(?:fragment\.com|nft\.fragment\.com)/gift/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
DIRECT_LOTTIE_RE = re.compile(
    r"https?://[^\s<>\"']+?/gift/([A-Za-z0-9_-]+)\.lottie\.json",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>\"']+")


@loader.tds
class NFTGiftLottie(loader.Module):
    """Скачивает Lottie NFT-подарка Telegram и добавляет свой текст."""

    strings = {
        "name": "NFTGiftLottie",
        "usage": (
            "🎁 <b>Использование:</b>\n"
            "<code>.nftgift ссылка | текст</code> — отправить .tgs\n"
            "<code>.nftlottie ссылка | текст</code> — отправить .lottie.json\n\n"
            "Если текст не указан, будет: <code>{default}</code>"
        ),
        "loading": "⏳ <b>Загружаю NFT-подарок...</b>",
        "bad_link": "❌ <b>Не нашёл ссылку/slug NFT-подарка.</b>\n\n{usage}",
        "download_error": "❌ <b>Не удалось скачать Lottie:</b> <code>{error}</code>",
        "invalid_lottie": "❌ <b>Fragment вернул невалидный Lottie JSON.</b>",
        "sending": "📤 <b>Отправляю анимацию...</b>",
        "done": (
            "🎁 <b>NFT Gift Lottie</b>\n"
            "🔗 Slug: <code>{slug}</code>\n"
            "📝 Текст: <code>{text}</code>"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_text",
                "Создал: @Kilka_Young",
                lambda: "Текст по умолчанию для NFT Gift анимации",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "font_size",
                42,
                lambda: "Размер текста",
                validator=loader.validators.Integer(minimum=12, maximum=96),
            ),
            loader.ConfigValue(
                "text_y",
                438,
                lambda: "Позиция текста по Y на холсте 512x512",
                validator=loader.validators.Integer(minimum=0, maximum=512),
            ),
            loader.ConfigValue(
                "font_path",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                lambda: "Путь к TTF/OTF шрифту для векторного текста",
                validator=loader.validators.String(),
            ),
        )

    @staticmethod
    def _safe_filename(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "gift"

    @staticmethod
    def _is_url(value: str) -> bool:
        try:
            parsed = urlparse(value)
        except ValueError:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _usage(self) -> str:
        return self.strings["usage"].format(
            default=html.escape(self.config["default_text"])
        )

    async def _get_invocation_text(self, message: Message) -> str:
        args = utils.get_args_raw(message).strip()
        if args:
            return args

        if message.is_reply:
            reply = await message.get_reply_message()
            if reply and reply.raw_text:
                return reply.raw_text.strip()

        return ""

    def _extract_lottie_source(self, raw: str) -> tuple[str | None, str | None, str]:
        raw = raw.strip()
        if not raw:
            return None, None, ""

        link_part, separator, text_part = raw.partition("|")
        parts = link_part.strip().split(maxsplit=1)
        candidate = parts[0] if parts else ""
        custom_text = text_part.strip()

        if not separator and len(parts) > 1:
            custom_text = parts[1].strip()

        custom_text = custom_text or self.config["default_text"]

        for regex in (DIRECT_LOTTIE_RE, NFT_LINK_RE, FRAGMENT_LINK_RE):
            match = regex.search(candidate) or regex.search(raw)
            if match:
                slug = match.group(1)
                if regex is DIRECT_LOTTIE_RE:
                    url_match = URL_RE.search(candidate) or URL_RE.search(raw)
                    url = url_match.group(0) if url_match else None
                    return slug, url, custom_text
                return slug, self._lottie_url(slug), custom_text

        if self._is_url(candidate) and candidate.endswith(".lottie.json"):
            slug = self._safe_filename(candidate.rsplit("/", 1)[-1].replace(".lottie.json", ""))
            return slug, candidate, custom_text

        if re.fullmatch(r"[A-Za-z0-9_-]+-\d+", candidate):
            return candidate, self._lottie_url(candidate), custom_text

        return None, None, custom_text

    @staticmethod
    def _lottie_url(slug: str) -> str:
        return f"https://nft.fragment.com/gift/{quote(slug, safe='')}.lottie.json"

    async def _download_lottie(self, url: str) -> dict:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=20) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                data = await response.json(content_type=None)

        if not isinstance(data, dict) or "layers" not in data:
            raise ValueError("not a Lottie animation")

        return data

    @staticmethod
    def _path_shape(path: dict, name: str) -> dict:
        return {
            "ty": "sh",
            "nm": name,
            "ix": 1,
            "ks": {"a": 0, "k": path, "ix": 2},
            "mn": "ADBE Vector Shape - Group",
            "hd": False,
        }

    @staticmethod
    def _fill(color: list[float], name: str) -> dict:
        return {
            "ty": "fl",
            "nm": name,
            "c": {"a": 0, "k": color, "ix": 4},
            "o": {"a": 0, "k": 100, "ix": 5},
            "r": 1,
            "bm": 0,
            "mn": "ADBE Vector Graphic - Fill",
            "hd": False,
        }

    @staticmethod
    def _stroke(color: list[float], width: int, name: str) -> dict:
        return {
            "ty": "st",
            "nm": name,
            "c": {"a": 0, "k": color, "ix": 3},
            "o": {"a": 0, "k": 100, "ix": 4},
            "w": {"a": 0, "k": width, "ix": 5},
            "lc": 2,
            "lj": 2,
            "bm": 0,
            "mn": "ADBE Vector Graphic - Stroke",
            "hd": False,
        }

    def _text_to_shapes(self, text: str) -> list[dict]:
        from fontTools.pens.basePen import BasePen
        from fontTools.ttLib import TTFont

        font_path = self.config["font_path"]
        if not os.path.exists(font_path):
            raise FileNotFoundError(font_path)

        font = TTFont(font_path)
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap()
        hmtx = font["hmtx"].metrics
        units = font["head"].unitsPerEm
        scale = self.config["font_size"] / units

        class LottiePathPen(BasePen):
            def __init__(self, glyphs, glyph_scale, dx, baseline):
                super().__init__(glyphs)
                self.scale = glyph_scale
                self.dx = dx
                self.baseline = baseline
                self.paths = []
                self.path = None

            def _map(self, point):
                return [round(self.dx + point[0] * self.scale, 3), round(self.baseline - point[1] * self.scale, 3)]

            @staticmethod
            def _zero():
                return [0, 0]

            def _moveTo(self, point):
                if self.path:
                    self.paths.append(self.path)
                mapped = self._map(point)
                self.path = {"i": [self._zero()], "o": [self._zero()], "v": [mapped], "c": False}

            def _lineTo(self, point):
                if not self.path:
                    self._moveTo(point)
                    return
                self.path["i"].append(self._zero())
                self.path["o"].append(self._zero())
                self.path["v"].append(self._map(point))

            def _curveToOne(self, point1, point2, point3):
                if not self.path:
                    self._moveTo(point3)
                    return
                start = self.path["v"][-1]
                c1 = self._map(point1)
                c2 = self._map(point2)
                end = self._map(point3)
                self.path["o"][-1] = [round(c1[0] - start[0], 3), round(c1[1] - start[1], 3)]
                self.path["i"].append([round(c2[0] - end[0], 3), round(c2[1] - end[1], 3)])
                self.path["o"].append(self._zero())
                self.path["v"].append(end)

            def _qCurveToOne(self, point1, point2):
                if not self.path:
                    self._moveTo(point2)
                    return
                start = self.path["v"][-1]
                q = self._map(point1)
                end = self._map(point2)
                c1 = [
                    start[0] + (2 * (q[0] - start[0]) / 3),
                    start[1] + (2 * (q[1] - start[1]) / 3),
                ]
                c2 = [
                    end[0] + (2 * (q[0] - end[0]) / 3),
                    end[1] + (2 * (q[1] - end[1]) / 3),
                ]
                self.path["o"][-1] = [round(c1[0] - start[0], 3), round(c1[1] - start[1], 3)]
                self.path["i"].append([round(c2[0] - end[0], 3), round(c2[1] - end[1], 3)])
                self.path["o"].append(self._zero())
                self.path["v"].append(end)

            def _closePath(self):
                if self.path:
                    self.path["c"] = True
                    self.paths.append(self.path)
                    self.path = None

            def _endPath(self):
                if self.path:
                    self.paths.append(self.path)
                    self.path = None

        safe_text = text[:80]
        lines = safe_text.splitlines() or [safe_text]
        line_height = self.config["font_size"] * 1.2
        start_y = self.config["text_y"] - (line_height * (len(lines) - 1) / 2)
        shapes = []

        for line_number, line in enumerate(lines[:3]):
            width = 0
            glyphs = []
            for char in line:
                glyph_name = cmap.get(ord(char))
                if not glyph_name:
                    glyph_name = ".notdef"
                glyphs.append(glyph_name)
                width += hmtx.get(glyph_name, hmtx.get(".notdef", (units // 2, 0)))[0] * scale

            cursor = 256 - width / 2
            baseline = start_y + line_number * line_height
            for glyph_name in glyphs:
                pen = LottiePathPen(glyph_set, scale, cursor, baseline)
                glyph_set[glyph_name].draw(pen)
                pen._endPath()
                for path in pen.paths:
                    shapes.append(self._path_shape(path, f"{glyph_name} path"))
                cursor += hmtx.get(glyph_name, hmtx.get(".notdef", (units // 2, 0)))[0] * scale

        return shapes

    def _add_text_layer(self, lottie: dict, text: str, next_index: int) -> None:
        lottie.setdefault("layers", []).append(
            {
                "ddd": 0,
                "ind": next_index,
                "ty": 5,
                "nm": "Kilka_Young text",
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100, "ix": 11},
                    "r": {"a": 0, "k": 0, "ix": 10},
                    "p": {"a": 0, "k": [256, self.config["text_y"], 0], "ix": 2},
                    "a": {"a": 0, "k": [0, 0, 0], "ix": 1},
                    "s": {"a": 0, "k": [100, 100, 100], "ix": 6},
                },
                "ao": 0,
                "t": {
                    "d": {
                        "k": [
                            {
                                "s": {
                                    "sz": [492, 96],
                                    "ps": [-246, -48],
                                    "s": self.config["font_size"],
                                    "f": "Arial",
                                    "t": text[:180],
                                    "j": 2,
                                    "tr": 0,
                                    "lh": int(self.config["font_size"] * 1.2),
                                    "ls": 0,
                                    "fc": [1, 1, 1],
                                    "sc": [0, 0, 0],
                                    "sw": 7,
                                    "of": True,
                                },
                                "t": 0,
                            }
                        ]
                    },
                    "p": {},
                    "m": {"g": 1, "a": {"a": 0, "k": [0, 0], "ix": 2}},
                },
                "ip": lottie.get("ip", 0),
                "op": lottie.get("op", 180),
                "st": 0,
                "bm": 0,
            }
        )

    def _add_text(self, lottie: dict, text: str) -> dict:
        layers = lottie.setdefault("layers", [])
        next_index = max(
            (layer.get("ind", 0) for layer in layers if isinstance(layer, dict)),
            default=0,
        ) + 1

        lottie["w"] = int(lottie.get("w") or 512)
        lottie["h"] = int(lottie.get("h") or 512)
        lottie.setdefault("fr", 60)
        lottie.setdefault("ip", 0)
        lottie.setdefault("op", 180)

        try:
            shapes = self._text_to_shapes(text)
        except Exception:
            logger.exception("Vector text generation failed")
            lottie["fonts"] = {
                "list": [
                    {
                        "fName": "Arial",
                        "fFamily": "Arial",
                        "fStyle": "Regular",
                        "ascent": 75,
                    }
                ]
            }
            self._add_text_layer(lottie, text, next_index)
            return lottie

        if not shapes:
            return lottie

        group = {
            "ty": "gr",
            "nm": "Kilka_Young vector text",
            "it": [
                *shapes,
                self._stroke([0, 0, 0, 1], 7, "Text outline"),
                self._fill([1, 1, 1, 1], "Text fill"),
                {
                    "ty": "tr",
                    "p": {"a": 0, "k": [0, 0], "ix": 2},
                    "a": {"a": 0, "k": [0, 0], "ix": 1},
                    "s": {"a": 0, "k": [100, 100], "ix": 3},
                    "r": {"a": 0, "k": 0, "ix": 6},
                    "o": {"a": 0, "k": 100, "ix": 7},
                    "sk": {"a": 0, "k": 0, "ix": 4},
                    "sa": {"a": 0, "k": 0, "ix": 5},
                    "nm": "Transform",
                },
            ],
            "np": len(shapes) + 2,
            "cix": 2,
            "bm": 0,
            "ix": 1,
            "mn": "ADBE Vector Group",
            "hd": False,
        }

        layers.append(
            {
                "ddd": 0,
                "ind": next_index,
                "ty": 4,
                "nm": "Kilka_Young vector text",
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100, "ix": 11},
                    "r": {"a": 0, "k": 0, "ix": 10},
                    "p": {"a": 0, "k": [0, 0, 0], "ix": 2},
                    "a": {"a": 0, "k": [0, 0, 0], "ix": 1},
                    "s": {"a": 0, "k": [100, 100, 100], "ix": 6},
                },
                "ao": 0,
                "shapes": [group],
                "ip": lottie.get("ip", 0),
                "op": lottie.get("op", 180),
                "st": 0,
                "bm": 0,
            }
        )
        return lottie

    @staticmethod
    def _to_json_file(lottie: dict, slug: str) -> io.BytesIO:
        payload = json.dumps(lottie, ensure_ascii=False, separators=(",", ":")).encode()
        file = io.BytesIO(payload)
        file.name = f"{NFTGiftLottie._safe_filename(slug)}.lottie.json"
        file.seek(0)
        return file

    @staticmethod
    def _to_tgs_file(lottie: dict, slug: str) -> io.BytesIO:
        payload = json.dumps(lottie, ensure_ascii=False, separators=(",", ":")).encode()
        file = io.BytesIO(gzip.compress(payload))
        file.name = f"{NFTGiftLottie._safe_filename(slug)}.tgs"
        file.seek(0)
        return file

    async def _build(self, message: Message):
        raw = await self._get_invocation_text(message)
        slug, url, text = self._extract_lottie_source(raw)
        if not slug or not url:
            await utils.answer(
                message,
                self.strings["bad_link"].format(usage=self._usage()),
            )
            return None

        await utils.answer(message, self.strings["loading"])

        try:
            lottie = await self._download_lottie(url)
            return slug, self._add_text(lottie, text), text
        except ValueError:
            await utils.answer(message, self.strings["invalid_lottie"])
        except Exception as e:
            logger.exception("NFT Gift download failed")
            await utils.answer(
                message,
                self.strings["download_error"].format(error=html.escape(str(e))),
            )
        return None

    @loader.command(
        ru_doc="[ссылка/slug] | [текст] — скачать NFT Gift как Telegram .tgs"
    )
    async def nftgiftcmd(self, message: Message):
        """[link/slug] | [text] — Download NFT Gift as Telegram .tgs"""
        result = await self._build(message)
        if result is None:
            return

        slug, lottie, text = result
        await utils.answer(message, self.strings["sending"])
        file = self._to_tgs_file(lottie, slug)

        try:
            await message.client.send_file(
                message.peer_id,
                file,
                force_document=True,
                mime_type="application/x-tgsticker",
                attributes=[
                    DocumentAttributeFilename(file_name=file.name),
                    DocumentAttributeSticker(
                        alt="🎁",
                        stickerset=InputStickerSetEmpty(),
                    ),
                ],
                reply_to=message.reply_to_msg_id,
            )
        except Exception:
            logger.exception("TGS sticker send failed, retrying as document")
            file.seek(0)
            await message.client.send_file(
                message.peer_id,
                file,
                force_document=True,
                attributes=[DocumentAttributeFilename(file_name=file.name)],
                reply_to=message.reply_to_msg_id,
            )

        await utils.answer(
            message,
            self.strings["done"].format(
                slug=html.escape(slug),
                text=html.escape(text[:180]),
            ),
        )

    @loader.command(
        ru_doc="[ссылка/slug] | [текст] — скачать NFT Gift как .lottie.json"
    )
    async def nftlottiecmd(self, message: Message):
        """[link/slug] | [text] — Download NFT Gift as .lottie.json"""
        result = await self._build(message)
        if result is None:
            return

        slug, lottie, text = result
        await utils.answer(message, self.strings["sending"])
        file = self._to_json_file(lottie, slug)

        await message.client.send_file(
            message.peer_id,
            file,
            force_document=True,
            attributes=[DocumentAttributeFilename(file_name=file.name)],
            reply_to=message.reply_to_msg_id,
        )

        await utils.answer(
            message,
            self.strings["done"].format(
                slug=html.escape(slug),
                text=html.escape(text[:180]),
            ),
        )

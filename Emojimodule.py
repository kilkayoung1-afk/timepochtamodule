# meta developer: @your_username
# scope: hikka_only
# scope: hikka_min 1.6.2

"""
Emoji Recolor Module
Advanced emoji/sticker recoloring with smooth animations
Supports WEBP, TGS (Lottie) with gradient transitions
"""

import gzip
import json
import io
import asyncio
import re
from typing import List, Tuple, Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFilter
from telethon import TelegramClient
from telethon.tl.types import (
    DocumentAttributeSticker,
    DocumentAttributeCustomEmoji,
    InputStickerSetEmpty,
    InputDocument,
)
from telethon.tl.functions.stickers import CreateStickerSetRequest
from .. import loader, utils
import logging

logger = logging.getLogger(__name__)


# ==================== UTILS ====================

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert HEX to RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_lottie(r: int, g: int, b: int) -> List[float]:
    """Convert RGB to Lottie color format (0.0 - 1.0)"""
    return [r / 255.0, g / 255.0, b / 255.0, 1.0]


def interpolate_color(
    color1: Tuple[int, int, int],
    color2: Tuple[int, int, int],
    t: float
) -> Tuple[int, int, int]:
    """
    Smooth color interpolation with ease-in-out
    t: 0.0 to 1.0
    """
    # Ease-in-out formula
    t = t * t * (3.0 - 2.0 * t)
    
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t),
    )


def interpolate_lottie_color(
    color1: List[float],
    color2: List[float],
    t: float
) -> List[float]:
    """Interpolate Lottie colors"""
    t = t * t * (3.0 - 2.0 * t)  # ease-in-out
    return [
        color1[i] + (color2[i] - color1[i]) * t
        for i in range(4)
    ]


# ==================== TGS PROCESSING ====================

class TGSProcessor:
    """Handle TGS (Lottie) animations"""
    
    @staticmethod
    def decompress(data: bytes) -> Dict[str, Any]:
        """Decompress and parse TGS"""
        try:
            decompressed = gzip.decompress(data)
            return json.loads(decompressed)
        except Exception as e:
            logger.error(f"TGS decompress error: {e}")
            return None
    
    @staticmethod
    def compress(data: Dict[str, Any]) -> bytes:
        """Compress Lottie JSON to TGS"""
        try:
            json_str = json.dumps(data, separators=(',', ':'))
            return gzip.compress(json_str.encode('utf-8'))
        except Exception as e:
            logger.error(f"TGS compress error: {e}")
            return None
    
    @staticmethod
    def find_colors(lottie_data: Dict[str, Any]) -> List[List[float]]:
        """Find all colors in Lottie JSON"""
        colors = []
        
        def traverse(obj):
            if isinstance(obj, dict):
                # Color property
                if 'c' in obj and isinstance(obj['c'], dict):
                    if 'k' in obj['c']:
                        color = obj['c']['k']
                        if isinstance(color, list) and len(color) >= 3:
                            colors.append(color)
                
                for value in obj.values():
                    traverse(value)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)
        
        traverse(lottie_data)
        return colors
    
    @staticmethod
    def recolor_with_animation(
        lottie_data: Dict[str, Any],
        target_color: List[float],
        frames: int = 15
    ) -> Dict[str, Any]:
        """
        Add smooth color animation to Lottie
        Creates keyframes for gradient transition
        """
        
        def recolor_object(obj, path=""):
            if isinstance(obj, dict):
                # Found color property
                if 'c' in obj and isinstance(obj['c'], dict):
                    if 'k' in obj['c']:
                        original_color = obj['c']['k']
                        
                        # If already animated, skip
                        if isinstance(original_color, list) and \
                           len(original_color) > 0 and \
                           isinstance(original_color[0], dict):
                            return
                        
                        # Create keyframes
                        if isinstance(original_color, list) and len(original_color) >= 3:
                            keyframes = []
                            total_frames = lottie_data.get('op', 60)  # out point
                            
                            for i in range(frames):
                                t = i / (frames - 1) if frames > 1 else 0
                                frame = int(t * total_frames)
                                
                                interpolated = interpolate_lottie_color(
                                    original_color,
                                    target_color,
                                    t
                                )
                                
                                keyframe = {
                                    "t": frame,
                                    "s": interpolated,
                                    "i": {"x": [0.42], "y": [0]},  # ease-in
                                    "o": {"x": [0.58], "y": [1]}   # ease-out
                                }
                                keyframes.append(keyframe)
                            
                            # Replace static color with animated
                            obj['c']['k'] = keyframes
                            obj['c']['a'] = 1  # animated flag
                
                # Recursively process
                for key, value in obj.items():
                    recolor_object(value, f"{path}.{key}")
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    recolor_object(item, f"{path}[{i}]")
        
        recolor_object(lottie_data)
        return lottie_data


# ==================== WEBP PROCESSING ====================

class WEBPProcessor:
    """Handle WEBP images with animation"""
    
    @staticmethod
    async def recolor_static(
        image: Image.Image,
        target_color: Tuple[int, int, int]
    ) -> Image.Image:
        """Recolor static WEBP image"""
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # Get pixels
        pixels = image.load()
        width, height = image.size
        
        # Calculate average color
        total_r, total_g, total_b = 0, 0, 0
        count = 0
        
        for x in range(width):
            for y in range(height):
                r, g, b, a = pixels[x, y]
                if a > 50:  # Skip transparent
                    total_r += r
                    total_g += g
                    total_b += b
                    count += 1
        
        if count == 0:
            return image
        
        avg_color = (total_r // count, total_g // count, total_b // count)
        
        # Recolor
        for x in range(width):
            for y in range(height):
                r, g, b, a = pixels[x, y]
                if a > 50:
                    # Calculate brightness
                    brightness = (r + g + b) / 3 / 255.0
                    
                    # Apply target color with brightness
                    new_r = int(target_color[0] * brightness)
                    new_g = int(target_color[1] * brightness)
                    new_b = int(target_color[2] * brightness)
                    
                    pixels[x, y] = (new_r, new_g, new_b, a)
        
        return image
    
    @staticmethod
    async def create_animated(
        image: Image.Image,
        target_color: Tuple[int, int, int],
        frames: int = 12
    ) -> List[Image.Image]:
        """
        Create animated WEBP with smooth color transition
        """
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        pixels = image.load()
        width, height = image.size
        
        # Calculate original average color
        total_r, total_g, total_b = 0, 0, 0
        count = 0
        
        for x in range(width):
            for y in range(height):
                r, g, b, a = pixels[x, y]
                if a > 50:
                    total_r += r
                    total_g += g
                    total_b += b
                    count += 1
        
        if count == 0:
            return [image]
        
        original_color = (total_r // count, total_g // count, total_b // count)
        
        # Generate frames
        animated_frames = []
        
        for frame_idx in range(frames):
            t = frame_idx / (frames - 1) if frames > 1 else 0
            interpolated_color = interpolate_color(original_color, target_color, t)
            
            # Create new frame
            new_frame = Image.new('RGBA', (width, height))
            new_pixels = new_frame.load()
            
            for x in range(width):
                for y in range(height):
                    r, g, b, a = pixels[x, y]
                    if a > 50:
                        brightness = (r + g + b) / 3 / 255.0
                        
                        new_r = int(interpolated_color[0] * brightness)
                        new_g = int(interpolated_color[1] * brightness)
                        new_b = int(interpolated_color[2] * brightness)
                        
                        new_pixels[x, y] = (new_r, new_g, new_b, a)
                    else:
                        new_pixels[x, y] = (r, g, b, a)
            
            animated_frames.append(new_frame)
        
        return animated_frames


# ==================== MODULE CLASS ====================

class EmojiRecolor(loader.Module):
    """
    Advanced emoji and sticker recoloring with smooth animations
    """
    
    strings = {
        "name": "EmojiRecolor",
        "processing": "<b>🎨 Processing...</b>",
        "downloading": "<b>⬇️ Downloading file...</b>",
        "recoloring": "<b>🎨 Recoloring ({}/{})</b>",
        "uploading": "<b>⬆️ Uploading...</b>",
        "done": "<b>✅ Done!</b>",
        "no_reply": "<b>❌ Reply to sticker or emoji</b>",
        "invalid_color": "<b>❌ Invalid color format. Use HEX (#FF0000)</b>",
        "error": "<b>❌ Error: {}</b>",
        "unsupported": "<b>❌ Unsupported file type</b>",
        "pack_created": "<b>✅ Pack created: {}</b>",
        "usage_emj": "<b>Usage:</b> <code>.emj [HEX color]</code> (reply to sticker/emoji)\n"
                     "<b>Example:</b> <code>.emj #FF0000</code>\n\n"
                     "<b>Presets:</b>\n"
                     "• <code>.emj red</code> - Red\n"
                     "• <code>.emj blue</code> - Blue\n"
                     "• <code>.emj green</code> - Green\n"
                     "• <code>.emj purple</code> - Purple\n"
                     "• <code>.emj gold</code> - Gold",
        "usage_emjt": "<b>Usage:</b> <code>.emjt [text]</code> (reply to TGS emoji)",
    }
    
    # Color presets
    PRESETS = {
        "red": "#FF0000",
        "blue": "#0080FF",
        "green": "#00FF00",
        "purple": "#A020F0",
        "gold": "#FFD700",
        "pink": "#FF69B4",
        "orange": "#FFA500",
        "cyan": "#00FFFF",
    }
    
    def __init__(self):
        self.tgs = TGSProcessor()
        self.webp = WEBPProcessor()
    
    async def emjcmd(self, message):
        """Recolor sticker/emoji with smooth animation"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not reply or not reply.media:
            await utils.answer(message, self.strings["no_reply"])
            return
        
        # Parse color
        if not args:
            await utils.answer(message, self.strings["usage_emj"])
            return
        
        # Check presets
        color_hex = self.PRESETS.get(args.lower(), args)
        
        # Validate HEX
        if not re.match(r'^#?[0-9A-Fa-f]{6}$', color_hex):
            await utils.answer(message, self.strings["invalid_color"])
            return
        
        target_color_rgb = hex_to_rgb(color_hex)
        target_color_lottie = rgb_to_lottie(*target_color_rgb)
        
        await utils.answer(message, self.strings["downloading"])
        
        try:
            # Download file
            file_bytes = await reply.download_media(bytes)
            
            # Detect file type
            is_tgs = file_bytes[:2] == b'\x1f\x8b'  # gzip magic number
            
            if is_tgs:
                # Process TGS
                await utils.answer(message, self.strings["recoloring"].format(1, 1))
                
                lottie_data = self.tgs.decompress(file_bytes)
                if not lottie_data:
                    await utils.answer(message, self.strings["error"].format("Invalid TGS"))
                    return
                
                # Apply animated recolor
                recolored = self.tgs.recolor_with_animation(
                    lottie_data,
                    target_color_lottie,
                    frames=15
                )
                
                # Compress back
                new_tgs = self.tgs.compress(recolored)
                
                if not new_tgs:
                    await utils.answer(message, self.strings["error"].format("Compression failed"))
                    return
                
                await utils.answer(message, self.strings["uploading"])
                
                # Upload
                await message.client.send_file(
                    message.peer_id,
                    new_tgs,
                    force_document=True,
                    attributes=[DocumentAttributeSticker(alt='🎨', stickerset=InputStickerSetEmpty())],
                    reply_to=reply.id
                )
                
                await message.delete()
            
            else:
                # Try WEBP
                try:
                    image = Image.open(io.BytesIO(file_bytes))
                except Exception as e:
                    await utils.answer(message, self.strings["unsupported"])
                    return
                
                await utils.answer(message, self.strings["recoloring"].format(1, 1))
                
                # Create animated WEBP
                frames = await self.webp.create_animated(
                    image,
                    target_color_rgb,
                    frames=12
                )
                
                # Save as animated WEBP
                output = io.BytesIO()
                frames[0].save(
                    output,
                    format='WEBP',
                    save_all=True,
                    append_images=frames[1:],
                    duration=50,  # 50ms per frame
                    loop=0,
                    quality=95
                )
                output.seek(0)
                
                await utils.answer(message, self.strings["uploading"])
                
                # Upload
                await message.client.send_file(
                    message.peer_id,
                    output.getvalue(),
                    force_document=True,
                    attributes=[DocumentAttributeSticker(alt='🎨', stickerset=InputStickerSetEmpty())],
                    reply_to=reply.id
                )
                
                await message.delete()
        
        except Exception as e:
            logger.exception("Error in emjcmd")
            await utils.answer(message, self.strings["error"].format(str(e)))
    
    async def emjtcmd(self, message):
        """Add text to TGS emoji (advanced)"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()
        
        if not args:
            await utils.answer(message, self.strings["usage_emjt"])
            return
        
        if not reply or not reply.media:
            await utils.answer(message, self.strings["no_reply"])
            return
        
        await utils.answer(message, self.strings["processing"])
        
        try:
            file_bytes = await reply.download_media(bytes)
            
            # Must be TGS
            if file_bytes[:2] != b'\x1f\x8b':
                await utils.answer(message, self.strings["unsupported"])
                return
            
            lottie_data = self.tgs.decompress(file_bytes)
            if not lottie_data:
                await utils.answer(message, self.strings["error"].format("Invalid TGS"))
                return
            
            # Add text layer (simplified version)
            # Full implementation would use fonttools to convert text to bezier curves
            # For now, we'll add a simple text shape
            
            text_layer = {
                "ty": 5,  # Text layer
                "nm": "Text",
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100},
                    "p": {"a": 0, "k": [256, 256, 0]},
                },
                "t": {
                    "d": {
                        "k": [{
                            "s": {
                                "t": args,
                                "f": "Arial",
                                "s": 100,
                                "j": 2,
                                "tr": 0,
                                "lh": 120,
                                "fc": [1, 1, 1]
                            },
                            "t": 0
                        }]
                    }
                }
            }
            
            # Add to layers
            if 'layers' in lottie_data:
                lottie_data['layers'].append(text_layer)
            
            # Compress
            new_tgs = self.tgs.compress(lottie_data)
            
            await utils.answer(message, self.strings["uploading"])
            
            await message.client.send_file(
                message.peer_id,
                new_tgs,
                force_document=True,
                attributes=[DocumentAttributeSticker(alt='📝', stickerset=InputStickerSetEmpty())],
                reply_to=reply.id
            )
            
            await message.delete()
        
        except Exception as e:
            logger.exception("Error in emjtcmd")
            await utils.answer(message, self.strings["error"].format(str(e)))
    
    async def emjinfocmd(self, message):
        """Get info about replied sticker/emoji"""
        reply = await message.get_reply_message()
        
        if not reply or not reply.media:
            await utils.answer(message, self.strings["no_reply"])
            return
        
        try:
            file_bytes = await reply.download_media(bytes)
            
            is_tgs = file_bytes[:2] == b'\x1f\x8b'
            
            info = f"<b>📊 File Info:</b>\n\n"
            info += f"<b>Size:</b> {len(file_bytes)} bytes\n"
            info += f"<b>Type:</b> {'TGS (Lottie)' if is_tgs else 'WEBP/Other'}\n"
            
            if is_tgs:
                lottie_data = self.tgs.decompress(file_bytes)
                if lottie_data:
                    info += f"<b>Frames:</b> {lottie_data.get('op', 'N/A')}\n"
                    info += f"<b>FPS:</b> {lottie_data.get('fr', 'N/A')}\n"
                    info += f"<b>Width:</b> {lottie_data.get('w', 'N/A')}\n"
                    info += f"<b>Height:</b> {lottie_data.get('h', 'N/A')}\n"
                    
                    colors = self.tgs.find_colors(lottie_data)
                    info += f"<b>Colors found:</b> {len(colors)}\n"
            
            await utils.answer(message, info)
        
        except Exception as e:
            await utils.answer(message, self.strings["error"].format(str(e)))

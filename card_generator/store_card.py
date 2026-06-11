# -*- coding: utf-8 -*-
"""机厅信息卡片生成器 - 使用Pillow绘制机厅详细信息和框体卡片"""
import os
import sys
from io import BytesIO
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 颜色配置
COLORS = {
    'primary': '#ef5e6d',
    'text': '#2c3e50',
    'text_muted': '#7f8c8d',
    'background': '#ffffff',
    'card_bg': '#ffffff',
    'border': '#e0e0e0',
    'gold': '#fec900',
    'good': '#4caf50',
    'good_minus': '#8bc34a',
    'nom': '#ff9800',
    'nom_minus': '#ff5722',
    'bad': '#f44336',
    'j_pop_bg': '#21a1ba',
    'j_pop_border_light': '#7dc5d4',
    'j_pop_border_dark': '#0c6472',
    'anime_bg': '#fe9900',
    'anime_border_light': '#ffda8f',
    'anime_border_dark': '#e55300',
    'vocaloid_bg': '#def2f1',
    'vocaloid_border_light': '#efefef',
    'vocaloid_border_dark': '#6a7b8d',
    'black': '#000000',
    'white': '#ffffff',
}

# 屏幕类型映射
SCREEN_MAP = {
    'nom': '屏幕：普通',
    'c-y': '屏幕：偏黄',
    'c-b': '屏幕：偏蓝',
    'c-p': '屏幕：偏紫',
    'streched': '屏幕：拉伸',
    'un-contrast': '屏幕：低对比度',
    'cut': '屏幕：切边',
    'bright': '屏幕：过亮',
    'dark': '屏幕：过暗',
    'hor-w': '屏幕：横白条纹',
    'hor-b': '屏幕：横黑条纹',
    'ver-w': '屏幕：竖白条纹',
    'ver-b': '屏幕：竖黑条纹',
    'blur': '屏幕：模糊'
}

# 鼓面状态到颜色的映射
DRUM_CONDITION_COLORS = {
    'gold': '#fec900',
    'good': '#4caf50',
    'good-': '#8bc34a',
    'nom': '#ff9800',
    'nom-': '#ff5722',
    'bad': '#f44336',
    '': '#9e9e9e'  # 默认/空
}

# 音量表情映射
AUDIO_EMOJI = {
    -1: '🔇',
    0: '❓',
    2: '🔈',
    4: '🔉',
    6: '🔊'
}

# 音量描述映射
AUDIO_DESC = {
    -1: '无声',
    0: '暂无信息',
    2: '小',
    4: '中',
    6: '大'
}


class StoreCardGenerator:
    """机厅信息卡片生成器"""
    
    # 卡片宽度（手机端风格，较窄）
    CARD_WIDTH = 400
    
    # 内边距
    PADDING = 16
    
    # 字体大小（调大）
    FONT_SIZE_TITLE = 28
    FONT_SIZE_SUBTITLE = 16
    FONT_SIZE_BODY = 15
    FONT_SIZE_SMALL = 15
    FONT_SIZE_TINY = 11
    FONT_SIZE_SCORE = 32  # 评分数值字体
    
    def __init__(self, static_path: str = None):
        """初始化生成器
        
        Args:
            static_path: static文件夹路径，默认为项目根目录下的static
        """
        if static_path is None:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            static_path = os.path.join(project_root, 'static')
        
        self.static_path = static_path
        self.image_path = os.path.join(static_path, 'image')
        
        # 加载图片资源
        self._load_images()
        
        # 初始化字体
        self._init_fonts()
    
    def _load_images(self):
        """加载鼓和屏幕的图片资源"""
        drum_path = os.path.join(self.image_path, 'drum.png')
        screen_path = os.path.join(self.image_path, 'screen.png')
        
        self.drum_image = Image.open(drum_path).convert('RGBA')
        self.screen_image = Image.open(screen_path).convert('RGBA')
        
        # 鼓图片原始尺寸信息
        # 原图是512px宽，CSS中background-size是256px，所以缩放比例是2x
        self.drum_scale = 2
        self.drum_sprite_width = 56.5 * self.drum_scale  # 每个鼓面的宽度（原图尺寸）
        self.drum_sprite_height = 65 * self.drum_scale   # 每个鼓面的高度（原图尺寸）
        self.drum_bg_offset = 198 * self.drum_scale      # 背景鼓面的x偏移（原图尺寸）
        
        # 屏幕图片信息
        # 原图是600px宽，CSS中background-size未指定，使用原图尺寸
        # CSS中屏幕显示尺寸是60x40，但我们需要按原图比例裁剪
        self.screen_scale = 1  # 使用原始尺寸，在绘制时缩放
        self.screen_width = 60  # CSS中的显示尺寸
        self.screen_height = 40  # CSS中的显示尺寸
    
    def _init_fonts(self):
        """初始化字体"""
        # 尝试使用系统默认中文字体
        font_paths = [
            # Windows
            'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
            'C:/Windows/Fonts/simhei.ttf',  # 黑体
            'C:/Windows/Fonts/simsun.ttc',  # 宋体
            # Linux
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            # macOS
            '/System/Library/Fonts/PingFang.ttc',
            '/Library/Fonts/Arial Unicode.ttf',
        ]
        
        self.fonts = {}
        default_font = None
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    default_font = font_path
                    break
                except:
                    continue
        
        if default_font is None:
            # 使用PIL默认字体
            default_font = None
        
        # 创建不同大小的字体
        sizes = [
            ('title', self.FONT_SIZE_TITLE),
            ('subtitle', self.FONT_SIZE_SUBTITLE),
            ('body', self.FONT_SIZE_BODY),
            ('small', self.FONT_SIZE_SMALL),
            ('tiny', self.FONT_SIZE_TINY),
            ('score', self.FONT_SIZE_SCORE),
        ]
        
        for name, size in sizes:
            if default_font:
                self.fonts[name] = ImageFont.truetype(default_font, size)
            else:
                self.fonts[name] = ImageFont.load_default()
        
        # 尝试加载粗体字体
        bold_font_paths = [
            'C:/Windows/Fonts/msyhbd.ttc',  # 微软雅黑粗体
            'C:/Windows/Fonts/simhei.ttf',  # 黑体
        ]
        self.bold_font = None
        for font_path in bold_font_paths:
            if os.path.exists(font_path):
                try:
                    self.bold_font = font_path
                    break
                except:
                    continue
    
    def _get_drum_sprite(self, condition: str, face_type: str) -> Image.Image:
        """获取鼓面精灵图
        
        Args:
            condition: 鼓面状态 ('gold', 'good', 'good-', 'nom', 'nom-', 'bad', '')
            face_type: 鼓面类型 ('x-l', 'o-l', 'o-r', 'x-r', 'drumbg')
        
        Returns:
            裁剪后的鼓面图片
        """
        # 计算x偏移（基于CSS中的background-position-x，取绝对值后乘以缩放比例）
        # CSS: background-position-x: 0px, -56.5px, -85px, -141.5px
        face_offsets = {
            'x-l': 0,
            'o-l': 56.5 * self.drum_scale,
            'x-r': 85 * self.drum_scale,
            'o-r': 141.5 * self.drum_scale,
            'drumbg': 198 * self.drum_scale
        }
        
        # 计算y偏移（基于CSS中的background-position-y，取绝对值后乘以缩放比例）
        # CSS: background-position-y: 0px, -65px, -130px, -195px, -260px, -325px
        condition_offsets = {
            'gold': 0,
            'good': 65 * self.drum_scale,
            'nom': 130 * self.drum_scale,
            'bad': 195 * self.drum_scale,
            'good-': 260 * self.drum_scale,
            'nom-': 325 * self.drum_scale,
            '': 195 * self.drum_scale  # 默认使用bad的位置
        }
        
        x_offset = face_offsets.get(face_type, 0)
        y_offset = condition_offsets.get(condition, 195 * self.drum_scale)
        
        # 裁剪图片
        box = (
            int(x_offset),
            int(y_offset),
            int(x_offset + self.drum_sprite_width),
            int(y_offset + self.drum_sprite_height)
        )
        
        return self.drum_image.crop(box)
    
    def _get_screen_sprite(self, screen_type: str) -> Image.Image:
        """获取屏幕精灵图
        
        Args:
            screen_type: 屏幕类型 ('nom', 'c-y', 'c-b', etc.)
        
        Returns:
            裁剪后的屏幕图片
        """
        # 屏幕类型到位置的映射（基于CSS background-position）
        screen_positions = {
            'nom': (-2, -2),
            'c-y': (-66, -2),
            'c-b': (-66, -46),
            'c-p': (-66, -90),
            'streched': (-130, -2),
            'un-contrast': (-194, -2),
            'cut': (-258, -2),
            'bright': (-322, -2),
            'dark': (-322, -46),
            'hor-w': (-386, -2),
            'hor-b': (-386, -46),
            'ver-w': (-386, -90),
            'ver-b': (-386, -134),
            'blur': (-450, -2),
            'big': (-514, -2),
        }
        
        x, y = screen_positions.get(screen_type, (-2, -2))
        
        box = (
            abs(x),
            abs(y),
            abs(x) + self.screen_width,
            abs(y) + self.screen_height
        )
        
        return self.screen_image.crop(box)
    
    def _draw_text_with_outline(self, draw: ImageDraw.Draw, text: str, 
                                 position: Tuple[int, int], font: ImageFont.ImageFont,
                                 text_color: str = 'white', outline_color: str = 'black',
                                 outline_width: int = 1) -> Tuple[int, int]:
        """绘制带描边的文字
        
        Returns:
            文字的宽度和高度
        """
        x, y = position
        
        # 获取文字尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 绘制描边（8个方向）
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        
        # 绘制主文字
        draw.text((x, y), text, font=font, fill=text_color)
        
        return text_width, text_height
    
    def _get_frame_class(self, drum: Dict) -> str:
        """根据鼓的track_no确定框体类型"""
        track_no = drum.get('track_no', 1)
        if track_no % 3 == 1:
            return 'j-pop'
        elif track_no % 3 == 2:
            return 'anime'
        else:
            return 'vocaloid'
    
    def _get_frame_colors(self, frame_class: str) -> Tuple[str, str, str]:
        """获取框体的颜色配置
        
        Returns:
            (背景色, 亮边框色, 暗边框色)
        """
        colors = {
            'j-pop': (COLORS['j_pop_bg'], COLORS['j_pop_border_light'], COLORS['j_pop_border_dark']),
            'anime': (COLORS['anime_bg'], COLORS['anime_border_light'], COLORS['anime_border_dark']),
            'vocaloid': (COLORS['vocaloid_bg'], COLORS['vocaloid_border_light'], COLORS['vocaloid_border_dark']),
        }
        return colors.get(frame_class, colors['j-pop'])
    
    def _draw_drum_box(self, draw: ImageDraw.Draw, drum: Dict, 
                       x: int, y: int, scale: float = 1.0, 
                       bg_color: str = '#21a1ba') -> Image.Image:
        """绘制鼓框体示意图 - 完全按照CSS样式叠加
        
        鼓面布局（从俯视图看）：
        1P侧（左侧）    2P侧（右侧）
        ┌─────┐        ┌─────┐
        │x-l  │        │  x-r│  ← 咔（上）
        │  o-l│        │o-r  │  ← 咚（下）
        └─────┘        └─────┘
        
        Args:
            draw: ImageDraw对象
            drum: 鼓的数据
            x: 左上角x坐标
            y: 左上角y坐标
            scale: 缩放比例
            bg_color: 背景颜色（根据框体类型）
        
        Returns:
            绘制好的鼓框体图片
        """
        # 鼓框体尺寸（基于CSS .drumbox）
        box_width = int(120 * scale)
        box_height = int(108 * scale)+4
        
        # 创建带背景色的图片
        # 将十六进制颜色转换为RGB
        bg_rgb = tuple(int(bg_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        drum_img = Image.new('RGBA', (box_width, box_height), bg_rgb + (255,))
        
        # 计算缩放后的尺寸（除以2是因为原图是2倍缩放）
        drum_w = int(self.drum_sprite_width * scale / self.drum_scale)
        drum_h = int(self.drum_sprite_height * scale / self.drum_scale)
        screen_w = int(self.screen_width * scale / self.screen_scale)
        screen_h = int(self.screen_height * scale / self.screen_scale)
        
        # === 1P侧（左侧）===
        # CSS: .map-drum-left { left: 0px; width: 56.5px; height: 65px; bottom: 0px; }
        # 1P侧不需要翻转
        
        # 获取1P背景鼓面（drumbg）
        p1_bg = self._get_drum_sprite('', 'drumbg')
        p1_bg = p1_bg.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        # 获取1P四个鼓面
        p1_xl = self._get_drum_sprite(drum.get('p1_x_l', ''), 'x-l')
        p1_xl = p1_xl.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        p1_ol = self._get_drum_sprite(drum.get('p1_o_l', ''), 'o-l')
        p1_ol = p1_ol.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        p1_or = self._get_drum_sprite(drum.get('p1_o_r', ''), 'o-r')
        p1_or = p1_or.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        p1_xr = self._get_drum_sprite(drum.get('p1_x_r', ''), 'x-r')
        p1_xr = p1_xr.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        # 创建1P侧的合成图 - 先画背景，再叠加四个鼓面
        # 使用alpha_composite来正确叠加透明层
        p1_composite = Image.new('RGBA', (drum_w, drum_h), (0, 0, 0, 0))
        p1_composite = Image.alpha_composite(p1_composite, p1_bg)  # 先画背景
        p1_composite = Image.alpha_composite(p1_composite, p1_xl)
        p1_composite = Image.alpha_composite(p1_composite, p1_ol)
        p1_composite = Image.alpha_composite(p1_composite, p1_or)
        p1_composite = Image.alpha_composite(p1_composite, p1_xr)
        
        # 粘贴1P侧到左侧
        left_x = 0
        left_y = box_height - drum_h
        drum_img.paste(p1_composite, (left_x, left_y), p1_composite)
        
        # === 2P侧（右侧）===
        # CSS: .map-drum-right { right: 0px; width: 56.5px; height: 65px; bottom: 0px; }
        # 2P侧使用水平翻转实现对面视角效果
        # 注意：翻转后左右位置会互换，所以需要在翻转前交换x_l/x_r和o_l/o_r
        
        # 获取2P背景鼓面
        p2_bg = self._get_drum_sprite('', 'drumbg')
        p2_bg = p2_bg.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        # 获取2P四个鼓面（交换左右位置，因为翻转后会还原）
        # p2_x_r放在x-l位置，p2_x_l放在x-r位置
        p2_xl = self._get_drum_sprite(drum.get('p2_x_r', ''), 'x-l')  # 右咔放在左位置
        p2_xl = p2_xl.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        p2_ol = self._get_drum_sprite(drum.get('p2_o_r', ''), 'o-l')  # 右咚放在左位置
        p2_ol = p2_ol.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        p2_or = self._get_drum_sprite(drum.get('p2_o_l', ''), 'o-r')  # 左咚放在右位置
        p2_or = p2_or.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        p2_xr = self._get_drum_sprite(drum.get('p2_x_l', ''), 'x-r')  # 左咔放在右位置
        p2_xr = p2_xr.resize((drum_w, drum_h), Image.Resampling.LANCZOS)
        
        # 创建2P侧的合成图 - 先画背景
        p2_composite = Image.new('RGBA', (drum_w, drum_h), (0, 0, 0, 0))
        p2_composite = Image.alpha_composite(p2_composite, p2_bg)  # 先画背景
        p2_composite = Image.alpha_composite(p2_composite, p2_xl)
        p2_composite = Image.alpha_composite(p2_composite, p2_ol)
        p2_composite = Image.alpha_composite(p2_composite, p2_or)
        p2_composite = Image.alpha_composite(p2_composite, p2_xr)
        
        # 水平翻转整个2P侧（实现对面视角）
        p2_composite = p2_composite.transpose(Image.FLIP_LEFT_RIGHT)
        
        # 粘贴2P侧到右侧
        right_x = box_width - drum_w
        right_y = box_height - drum_h
        drum_img.paste(p2_composite, (right_x, right_y), p2_composite)
        
        # === 屏幕 ===
        # CSS: .drumbox .drum-screen { width: 60px; height: 40px; left: 30px; position: absolute; }
        # 屏幕居中显示
        screen_x = (box_width - screen_w) // 2
        screen_y = int(5 * scale)-3
        
        screen_sprite = self._get_screen_sprite(drum.get('screen', 'nom'))
        screen_sprite = screen_sprite.resize((screen_w, screen_h), Image.Resampling.LANCZOS)
        drum_img.paste(screen_sprite, (screen_x, screen_y), screen_sprite)
        
        return drum_img
    
    def _draw_drum_card(self, drum: Dict, width: int) -> Image.Image:
        """绘制单个框体卡片
        
        Args:
            drum: 框体数据
            width: 卡片宽度
        
        Returns:
            框体卡片图片
        """
        # 确定框体类型
        frame_class = self._get_frame_class(drum)
        bg_color, border_light, border_dark = self._get_frame_colors(frame_class)
        
        # 卡片高度（根据内容动态计算）
        card_height = 140
        
        # 创建卡片图片
        card = Image.new('RGB', (width, card_height), COLORS['black'])
        draw = ImageDraw.Draw(card)
        
        # 绘制外边框（4px黑色背景）
        # 内部内容区域
        inner_x = 4
        inner_y = 4
        inner_width = width - 8
        inner_height = card_height - 8
        
        # 绘制内部背景
        draw.rectangle(
            [inner_x, inner_y, inner_x + inner_width, inner_y + inner_height],
            fill=bg_color
        )
        
        # 绘制立体边框效果（上左亮，下右暗）
        # 上边框（亮）
        draw.rectangle(
            [inner_x, inner_y, inner_x + inner_width, inner_y + 4],
            fill=border_light
        )
        # 左边框（亮）
        draw.rectangle(
            [inner_x, inner_y, inner_x + 4, inner_y + inner_height],
            fill=border_light
        )
        # 下边框（暗）
        draw.rectangle(
            [inner_x, inner_y + inner_height - 4, inner_x + inner_width, inner_y + inner_height],
            fill=border_dark
        )
        # 右边框（暗）
        draw.rectangle(
            [inner_x + inner_width - 4, inner_y, inner_x + inner_width, inner_y + inner_height],
            fill=border_dark
        )
        
        # 内容区域内边距
        content_x = inner_x + 8
        content_y = inner_y + 8
        content_width = inner_width - 16
        
        # 绘制鼓框体示意图（左侧）
        # 使用更大的缩放比例，让鼓示意图更醒目
        drum_scale = 1.0
        drum_img = self._draw_drum_box(draw, drum, 0, 0, drum_scale, bg_color)
        drum_width = drum_img.width
        drum_height = drum_img.height
        
        # 粘贴鼓图片（垂直居中）
        drum_y = content_y + (inner_height - 16 - drum_height) // 2
        card.paste(drum_img, (content_x, drum_y+1), drum_img)
        
        # 右侧信息区域
        info_x = content_x + drum_width + 12
        info_y = content_y + 2
        
        # 准备文字信息
        screen_text = SCREEN_MAP.get(drum.get('screen', 'nom'), '屏幕：普通')
        
        p1_audio = drum.get('p1_audio', 0)
        p2_audio = drum.get('p2_audio', 0)
        
        # 如果两侧音量相同，简化显示
        if p1_audio == p2_audio:
            audio_text = f"音量：{AUDIO_DESC.get(p1_audio, '暂无信息')}"
        else:
            audio_text = f"1P音量：{AUDIO_DESC.get(p1_audio, '暂无')} / 2P音量：{AUDIO_DESC.get(p2_audio, '暂无')}"
        
        # 备注信息（如果有）
        comm = drum.get('comm', '')
        
        # 计算可用空间
        max_text_width = content_width - drum_width - 20
        max_text_height = inner_height - 16  # 最大文字高度
        
        # 动态调整字体大小
        # 从较大的字体开始，如果文字太长就缩小
        base_font_size = 18  # 基础字体大小（比之前大）
        min_font_size = 11   # 最小字体大小
        
        # 尝试不同的字体大小
        best_font = None
        best_font_size = min_font_size
        
        for font_size in range(base_font_size, min_font_size - 1, -1):
            if self.bold_font:
                test_font = ImageFont.truetype(self.bold_font, font_size)
            else:
                test_font = ImageFont.truetype(self.fonts['body'].path, font_size) if hasattr(self.fonts['body'], 'path') else self.fonts['body']
            
            # 计算所有文字的总高度
            total_height = 0
            line_height = font_size + 10
            
            # 屏幕信息
            total_height += line_height
            
            # 音量信息
            total_height += line_height
            
            # 备注信息（如果有）- 计算自动换行后的高度
            if comm:
                comm_text = f"其他信息：{comm}"
                # 计算换行后的行数
                comm_lines = self._wrap_text_for_drum(draw, comm_text, test_font, max_text_width)
                total_height += len(comm_lines) * line_height
            
            # 检查是否适合
            if total_height <= max_text_height:
                best_font = test_font
                best_font_size = font_size
                break
        
        if best_font is None:
            best_font = self.fonts.get('body', self.fonts.get('small'))
            best_font_size = min_font_size
        
        font = best_font
        line_height = best_font_size + 10
        
        # 绘制文字（带黑色描边）
        # 屏幕信息
        self._draw_text_with_outline(
            draw, screen_text, (info_x, info_y), font,
            text_color='white', outline_color='black', outline_width=1
        )
        info_y += line_height
        
        # 音量信息
        self._draw_text_with_outline(
            draw, audio_text, (info_x, info_y), font,
            text_color='white', outline_color='black', outline_width=1
        )
        info_y += line_height
        
        # 备注信息（如果有）- 支持自动换行
        if comm:
            comm_text = f"其他信息：{comm}"
            # 自动换行
            comm_lines = self._wrap_text_for_drum(draw, comm_text, font, max_text_width)
            for line in comm_lines:
                self._draw_text_with_outline(
                    draw, line, (info_x, info_y), font,
                    text_color='white', outline_color='black', outline_width=1
                )
                info_y += line_height
        
        return card
    
    def _draw_store_header(self, store: Dict, width: int) -> Image.Image:
        """绘制机厅信息头部 - 参考手机端网页样式
        
        Args:
            store: 机厅数据
            width: 宽度
        
        Returns:
            头部信息图片
        """
        # 创建图片（先创建临时图片计算高度）
        header = Image.new('RGB', (width, 480), COLORS['background'])
        draw = ImageDraw.Draw(header)
        
        # 内边距
        padding = self.PADDING
        x = padding
        y = padding-14
        
        # 机厅名称（大字体，加粗）
        store_name = store.get('store_name', '未知机厅')
        # 使用粗体字体
        if self.bold_font:
            title_font = ImageFont.truetype(self.bold_font, self.FONT_SIZE_TITLE)
        else:
            title_font = self.fonts['title']
        draw.text((x, y), store_name, font=title_font, fill=COLORS['text'])
        
        # 获取标题宽度
        bbox = draw.textbbox((x, y), store_name, font=self.fonts['title'])
        title_width = bbox[2] - bbox[0]
        title_height = bbox[3] - bbox[1]
        
        # 状态标签（如果有）
        if store.get('available') == False:
            tag_x = x + title_width + 10
            tag_text = "已撤机"
            tag_font = self.fonts['small']
            bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
            tag_width = bbox[2] - bbox[0] + 12
            tag_height = bbox[3] - bbox[1] + 6
            
            # 绘制标签背景
            draw.rounded_rectangle(
                [tag_x, y + 5, tag_x + tag_width, y + 5 + tag_height],
                radius=4,
                fill='#eceff1'
            )
            draw.text((tag_x + 6, y + 8), tag_text, font=tag_font, fill='#546e7a')
        
        y += title_height + 12
        
        # 地区信息
        location = f"{store.get('province', '')} · {store.get('city', '')} · {store.get('district', '')}"
        draw.text((x, y), location, font=self.fonts['subtitle'], fill=COLORS['text_muted'])
        y += 28
        
        # 信息卡片背景 - 白色圆角卡片
        card_margin = 12
        card_x = card_margin
        card_y = y
        card_width = width - card_margin * 2
        
        # 计算卡片内容高度
        # 左列：地址、营业/价格/本地群（横向排列）
        # 右列：评分
        left_col_width = card_width * 0.72  # 给左侧更多空间
        right_col_width = card_width * 0.40
        
        # 卡片内边距
        inner_padding = 16
        cx = card_x + inner_padding
        cy = card_y + inner_padding
        
        # === 左列：基本信息 ===
        left_x = cx
        left_y = cy
        line_height = 22
        label_value_gap = 4  # 标签和值之间的间距
        
        # 地址（保持纵向）
        draw.text((left_x, left_y), "地址", font=self.fonts['small'], fill=COLORS['text_muted'])
        left_y += line_height
        address = store.get('address', '暂无信息')
        # 地址可能较长，需要换行处理
        max_addr_width = left_col_width - inner_padding
        addr_lines = self._wrap_text(draw, address, self.fonts['body'], max_addr_width)
        for line in addr_lines:
            draw.text((left_x, left_y), line, font=self.fonts['body'], fill=COLORS['text'])
            left_y += line_height
        left_y += 12
        
        # 营业、价格、本地群（标签左对齐，值从同一列开始）
        business = store.get('business_hours', '暂无信息')
        price = store.get('price_range', '暂无信息')
        local_group = store.get('local_group', '暂无信息')
        
        # 计算标签宽度（取最长的标签"本地群"的宽度）
        label_font = self.fonts['small']
        bbox = draw.textbbox((0, 0), "本地群", font=label_font)
        field_label_width = bbox[2] - bbox[0] + 12  # 标签宽度 + 间距
        
        # 计算值的最大宽度
        value_width = left_col_width - inner_padding - field_label_width - 8
        
        # 第一行：营业
        row_y = left_y
        draw.text((left_x, row_y), "营业", font=label_font, fill=COLORS['text_muted'])
        business_lines = self._wrap_text(draw, business, self.fonts['body'], value_width)
        for i, line in enumerate(business_lines):
            draw.text((left_x + field_label_width, row_y + i * line_height), line, font=self.fonts['body'], fill=COLORS['text'])
        business_height = len(business_lines) * line_height
        
        # 第二行：价格
        row_y += business_height + 8
        draw.text((left_x, row_y), "价格", font=label_font, fill=COLORS['text_muted'])
        price_lines = self._wrap_text(draw, price, self.fonts['body'], value_width)
        for i, line in enumerate(price_lines):
            draw.text((left_x + field_label_width, row_y + i * line_height), line, font=self.fonts['body'], fill=COLORS['text'])
        price_height = len(price_lines) * line_height
        
        # 第三行：本地群
        row_y += price_height + 8
        draw.text((left_x, row_y), "本地群", font=label_font, fill=COLORS['text_muted'])
        group_lines = self._wrap_text(draw, local_group, self.fonts['body'], value_width)
        for i, line in enumerate(group_lines):
            draw.text((left_x + field_label_width, row_y + i * line_height), line, font=self.fonts['body'], fill=COLORS['text'])
        group_height = len(group_lines) * line_height
        
        left_y = row_y + group_height
        left_col_bottom = left_y
        
        # === 右列：评分 ===
        right_x = cx + left_col_width
        right_y = cy
        
        # 机况评分 - 从总分和数量计算平均值
        condition_count = store.get('condition_rating_count', 0) or 0
        total_condition_score = store.get('total_condition_score', 0) or 0
        if condition_count > 0:
            condition_avg = total_condition_score / condition_count
            condition_score = f"{condition_avg:.1f}"
        else:
            condition_score = "N/A"
        
        draw.text((right_x, right_y), "机况评分", font=self.fonts['small'], fill=COLORS['text_muted'])
        right_y += line_height
        # 评分数值（大字体，彩色，加粗）
        if self.bold_font:
            score_font = ImageFont.truetype(self.bold_font, self.FONT_SIZE_SCORE)
        else:
            score_font = self.fonts['score']
        score_color = COLORS['primary'] if condition_score != "N/A" else COLORS['text_muted']
        # 计算分数宽度以便居中人数
        bbox = draw.textbbox((0, 0), condition_score, font=score_font)
        score_width = bbox[2] - bbox[0]
        draw.text((right_x, right_y), condition_score, font=score_font, fill=score_color)
        right_y += 36
        # 人数居中显示
        count_text = f"{condition_count} 人"
        count_font = self.fonts['tiny']
        bbox = draw.textbbox((0, 0), count_text, font=count_font)
        count_width = bbox[2] - bbox[0]
        count_x = right_x + (score_width - count_width) // 2
        draw.text((count_x, right_y), count_text, font=count_font, fill=COLORS['text_muted'])
        right_y += line_height + 16
        
        # 推荐指数 - 从总分和数量计算平均值
        recommend_count = store.get('recommendation_rating_count', 0) or 0
        total_recommendation_score = store.get('total_recommendation_score', 0) or 0
        if recommend_count > 0:
            recommend_avg = total_recommendation_score / recommend_count
            recommend_score = f"{recommend_avg:.1f}"
        else:
            recommend_score = "N/A"
        
        draw.text((right_x, right_y), "推荐指数", font=self.fonts['small'], fill=COLORS['text_muted'])
        right_y += line_height
        recommend_color = '#ff9800' if recommend_score != "N/A" else COLORS['text_muted']
        bbox = draw.textbbox((0, 0), recommend_score, font=score_font)
        score_width = bbox[2] - bbox[0]
        draw.text((right_x, right_y), recommend_score, font=score_font, fill=recommend_color)
        right_y += 36
        # 人数居中显示
        count_text = f"{recommend_count} 人"
        bbox = draw.textbbox((0, 0), count_text, font=count_font)
        count_width = bbox[2] - bbox[0]
        count_x = right_x + (score_width - count_width) // 2
        draw.text((count_x, right_y), count_text, font=count_font, fill=COLORS['text_muted'])
        
        right_col_bottom = right_y + line_height
        
        # 计算卡片高度
        card_height = max(left_col_bottom, right_col_bottom) - card_y + inner_padding
        
        # 绘制白色卡片背景（圆角）
        card_bg = Image.new('RGB', (card_width, card_height), COLORS['card_bg'])
        card_bg_draw = ImageDraw.Draw(card_bg)
        # 创建圆角蒙版
        mask = Image.new('L', (card_width, card_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, card_width, card_height], radius=16, fill=255)
        # 应用圆角
        header.paste(card_bg, (card_x, card_y), mask)
        
        # 绘制主题色渐变描边效果 + 阴影
        # 参考CSS: box-shadow: 0 2px 8px rgba(239, 94, 109, 0.08)
        primary_color = (239, 94, 109)  # 主题粉色
        shadow_color = (239, 94, 109)   # 阴影颜色（主题色）
        
        # 创建阴影图层（比卡片大一些）
        shadow_padding = 8
        shadow_img = Image.new('RGBA', (card_width + shadow_padding * 2, card_height + shadow_padding * 2), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)
        
        # 绘制柔和阴影 - 多层渐变
        for i in range(7, 0, -1):
            alpha = int(35 * (1 - i / 7))  # 从外到内递减的透明度
            offset = i
            shadow_draw.rounded_rectangle(
                [shadow_padding - offset, shadow_padding - offset + 2, 
                 shadow_padding + card_width + offset, shadow_padding + card_height + offset],
                radius=16 + offset,
                fill=(shadow_color[0], shadow_color[1], shadow_color[2], alpha)
            )
        
        # 应用阴影到header
        header.paste(shadow_img, (card_x - shadow_padding, card_y - shadow_padding), shadow_img)
        
        # 重新绘制白色卡片背景（因为被阴影覆盖了）
        card_bg = Image.new('RGB', (card_width, card_height), COLORS['card_bg'])
        mask = Image.new('L', (card_width, card_height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, card_width, card_height], radius=16, fill=255)
        header.paste(card_bg, (card_x, card_y), mask)
        
        # 绘制细边框
        border_img = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border_img)
        # 绘制淡淡的主题色边框
        border_draw.rounded_rectangle(
            [0, 0, card_width - 1, card_height - 1],
            radius=16,
            outline=(primary_color[0], primary_color[1], primary_color[2], 60),
            width=1
        )
        header.paste(border_img, (card_x, card_y), border_img)
        
        # 重新绘制所有内容（因为paste覆盖了）
        draw = ImageDraw.Draw(header)
        
        # 重新绘制左列
        left_x = cx
        left_y = cy
        
        # 地址
        draw.text((left_x, left_y), "地址", font=self.fonts['small'], fill=COLORS['text_muted'])
        left_y += line_height
        for line in addr_lines:
            draw.text((left_x, left_y), line, font=self.fonts['body'], fill=COLORS['text'])
            left_y += line_height
        left_y += 12
        
        # 营业
        row_y = left_y
        draw.text((left_x, row_y), "营业", font=self.fonts['small'], fill=COLORS['text_muted'])
        for i, line in enumerate(business_lines):
            draw.text((left_x + field_label_width, row_y + i * line_height), line, font=self.fonts['body'], fill=COLORS['text'])
        row_y += len(business_lines) * line_height + 8
        
        # 价格
        draw.text((left_x, row_y), "价格", font=self.fonts['small'], fill=COLORS['text_muted'])
        for i, line in enumerate(price_lines):
            draw.text((left_x + field_label_width, row_y + i * line_height), line, font=self.fonts['body'], fill=COLORS['text'])
        row_y += len(price_lines) * line_height + 8
        
        # 本地群
        draw.text((left_x, row_y), "本地群", font=self.fonts['small'], fill=COLORS['text_muted'])
        for i, line in enumerate(group_lines):
            draw.text((left_x + field_label_width, row_y + i * line_height), line, font=self.fonts['body'], fill=COLORS['text'])
        
        # 重新绘制右列
        right_x = cx + left_col_width
        right_y = cy
        
        # 机况评分
        draw.text((right_x-4, right_y), "机况评分", font=self.fonts['small'], fill=COLORS['text_muted'])
        right_y += line_height
        draw.text((right_x, right_y), condition_score, font=score_font, fill=score_color)
        right_y += 36
        draw.text((count_x, right_y), f"{condition_count} 人", font=count_font, fill=COLORS['text_muted'])
        right_y += line_height + 16
        
        # 推荐指数
        draw.text((right_x-4, right_y), "推荐指数", font=self.fonts['small'], fill=COLORS['text_muted'])
        right_y += line_height
        draw.text((right_x, right_y), recommend_score, font=score_font, fill=recommend_color)
        right_y += 36
        draw.text((count_x, right_y), f"{recommend_count} 人", font=count_font, fill=COLORS['text_muted'])
        
        # 裁剪头部到实际高度
        header_height = card_y + card_height + padding-12
        header = header.crop((0, 0, width, header_height))
        
        return header
    
    def _wrap_text(self, draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
        """自动换行文本
        
        Args:
            draw: ImageDraw对象
            text: 原始文本
            font: 字体
            max_width: 最大宽度
        
        Returns:
            换行后的文本列表
        """
        if not text:
            return ['']
        
        lines = []
        current_line = ''
        
        for char in text:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        # 如果没有换行，返回原文本
        if not lines:
            lines = [text]
        
        return lines
    
    def _wrap_text_for_drum(self, draw: ImageDraw.Draw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
        """为框体卡片自动换行文本 - 按字符逐个检查
        
        Args:
            draw: ImageDraw对象
            text: 要换行的文本
            font: 字体
            max_width: 最大宽度
            
        Returns:
            换行后的文本列表
        """
        if not text:
            return ['']
        
        lines = []
        current_line = ''
        
        for char in text:
            test_line = current_line + char
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        # 如果没有换行，返回原文本
        if not lines:
            lines = [text]
        
        return lines
    
    def generate_card(self, store: Dict, drums: List[Dict]) -> Image.Image:
        """生成完整的机厅信息卡片
        
        Args:
            store: 机厅数据
            drums: 框体列表
        
        Returns:
            完整的卡片图片
        """
        width = self.CARD_WIDTH
        
        # 绘制头部
        header = self._draw_store_header(store, width)
        header_height = header.height
        
        # 计算框体卡片区域高度
        drum_card_height = 140
        drum_spacing = 8
        drums_height = len(drums) * (drum_card_height + drum_spacing) + drum_spacing
        
        # 总高度
        total_height = header_height + drums_height
        
        # 创建最终图片
        final_img = Image.new('RGB', (width, total_height), COLORS['background'])
        
        # 粘贴头部
        final_img.paste(header, (0, 0))
        
        # 绘制框体卡片
        y_offset = header_height + drum_spacing
        for drum in drums:
            card = self._draw_drum_card(drum, width - 16)  # 左右留边距
            final_img.paste(card, (8, y_offset))
            y_offset += drum_card_height + drum_spacing
        
        return final_img
    
    def save_card(self, store: Dict, drums: List[Dict], output_path: str):
        """生成并保存卡片
        
        Args:
            store: 机厅数据
            drums: 框体列表
            output_path: 输出路径
        """
        card = self.generate_card(store, drums)
        card.save(output_path, 'PNG', quality=95)
        print(f"卡片已保存到: {output_path}")
        return output_path


async def fetch_store_data(store_id: str) -> Tuple[Optional[Dict], List[Dict]]:
    """从数据库获取机厅和框体数据
    
    Args:
        store_id: 机厅ID
    
    Returns:
        (机厅数据, 框体列表)
    """
    # 从环境变量读取数据库配置
    mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    database_name = os.getenv('DATABASE_NAME', 'kinoko_map')
    
    # 连接数据库
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[database_name]
    
    try:
        # 查询机厅信息
        store = await db.arcade_store.find_one({'_id': store_id})
        
        if not store:
            print(f"未找到机厅: {store_id}")
            return None, []
        
        # 查询框体信息
        cursor = db.drum.find({'store_id': store_id}).sort('track_no', 1)
        drums = await cursor.to_list(length=None)
        
        return store, drums
    finally:
        client.close()


async def main():
    """测试主函数"""
    store_id = '350104001'
    
    print(f"正在获取机厅 {store_id} 的数据...")
    
    # 获取数据
    store, drums = await fetch_store_data(store_id)
    
    if not store:
        print("机厅不存在")
        return
    
    print(f"机厅名称: {store.get('store_name')}")
    print(f"框体数量: {len(drums)}")
    
    # 创建生成器
    generator = StoreCardGenerator()
    
    # 生成卡片
    output_path = f'store_card_{store_id}.png'
    generator.save_card(store, drums, output_path)
    
    print("生成完成!")


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

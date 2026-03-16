from PIL import Image, ImageDraw, ImageFont
import os

class PixelTextImageGenerator:
    """像素风格文字转图片生成器（支持：新建画布 / 绘制到已有图片）"""
    
    def __init__(self, canvas_size=(800, 300), bg_color=(0, 0, 0), 
                 font_path="pixel_font.ttf", font_size=60):
        """
        初始化生成器（新建画布场景的默认配置）
        :param canvas_size: 新建画布尺寸 (宽, 高)
        :param bg_color: 新建画布背景色 (R, G, B)
        :param font_path: 像素字体文件路径（全局默认）
        :param font_size: 字体大小（全局默认）
        """
        # 全局默认配置（可被实例方法覆盖）
        self.canvas_size = canvas_size
        self.bg_color = bg_color
        self.font_path = font_path
        self.font_size = font_size
        
        # 新建画布的核心对象（原有功能保留）
        self.img = Image.new("RGB", self.canvas_size, self.bg_color)
        self.draw = ImageDraw.Draw(self.img)
        
        # 加载全局默认字体
        self.font = self._load_font(self.font_path, self.font_size)

    def _load_font(self, font_path, font_size):
        """私有方法：加载字体（复用逻辑，失败降级为系统默认）"""
        try:
            return ImageFont.truetype(font_path, font_size)
        except IOError:
            print(f"警告：未找到字体文件 {font_path}，使用系统默认像素字体替代")
            return ImageFont.load_default(size=font_size)

    def get_text_bbox(self, text, pos=(0, 0), font=None):
        """
        辅助方法：获取文字边界框（布局调整用）
        :param text: 要计算的文字
        :param pos: 文字起始位置
        :param font: 可选，指定字体（默认用全局字体）
        :return: 边界框 (x0, y0, x1, y1)，宽高 (w, h)
        """
        use_font = font or self.font
        bbox = self.draw.textbbox(pos, text, font=use_font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return bbox, (w, h)

    def add_3d_text(self, text, pos, main_color=(255, 127, 0), 
                    shadow_color=(150, 70, 0), offset=(3, 3)):
        """原有功能：给新建的画布添加立体像素文字"""
        shadow_pos = (pos[0] + offset[0], pos[1] + offset[1])
        self.draw.text(shadow_pos, text, font=self.font, fill=shadow_color)
        self.draw.text(pos, text, font=self.font, fill=main_color)

    def add_gradient_text(self, text, pos, start_color=(255, 215, 0), 
                          end_color=(255, 127, 0)):
        """原有功能：给新建的画布添加渐变像素文字"""
        bbox, (text_w, text_h) = self.get_text_bbox(text, pos)
        text_x, text_y = bbox[0], bbox[1]
        
        # 创建渐变层
        gradient = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(gradient)
        for x in range(text_w):
            ratio = x / text_w
            r = int(start_color[0]*(1-ratio) + end_color[0]*ratio)
            g = int(start_color[1]*(1-ratio) + end_color[1]*ratio)
            b = int(start_color[2]*(1-ratio) + end_color[2]*ratio)
            grad_draw.line([(x, 0), (x, text_h)], fill=(r, g, b))
        
        # 创建文字遮罩
        mask = Image.new("L", (text_w, text_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.text((0, 0), text, font=self.font, fill=255)
        
        # 粘贴到新建画布
        self.img.paste(gradient, (text_x, text_y), mask=mask)

    def draw_text_on_image(self, image_source, text, text_type="3d", pos=(50, 50),
                           font_path=None, font_size=None, main_color=(255, 127, 0),
                           shadow_color=(150, 70, 0), start_color=(255, 215, 0),
                           end_color=(255, 127, 0), offset=(3, 3), save_path="text_on_img.png"):
        """
        新增核心方法：将像素文字绘制到指定的已有图片中
        :param image_source: 图片路径（str）或 PIL Image 对象（支持RGB/RGBA）
        :param text: 要绘制的文字内容
        :param text_type: 文字类型 "3d"（立体） / "gradient"（渐变）
        :param pos: 文字左上角坐标 (x, y)
        :param font_path: 可选，覆盖全局字体路径
        :param font_size: 可选，覆盖全局字体大小
        :param main_color: 3d文字主色（仅3d模式生效）
        :param shadow_color: 3d文字阴影色（仅3d模式生效）
        :param start_color: 渐变起始色（仅渐变模式生效）
        :param end_color: 渐变结束色（仅渐变模式生效）
        :param offset: 3d文字阴影偏移（仅3d模式生效）
        :param save_path: 绘制后的保存路径
        :return: 修改后的 PIL Image 对象（不影响实例原有画布）
        """
        # 1. 加载已有图片（处理路径/Image对象两种输入）
        if isinstance(image_source, str):
            if not os.path.exists(image_source):
                raise FileNotFoundError(f"指定图片不存在：{image_source}")
            # 打开图片并转为RGB（避免透明通道干扰）
            target_img = Image.open(image_source).convert("RGB")
        elif isinstance(image_source, Image.Image):
            target_img = image_source.convert("RGB")
        else:
            raise TypeError("image_source 必须是图片路径（str）或 PIL Image 对象")
        
        # 2. 创建绘制对象（仅作用于目标图片，不影响self.draw）
        target_draw = ImageDraw.Draw(target_img)
        
        # 3. 加载字体（优先用方法传入的，否则用全局默认）
        use_font_path = font_path or self.font_path
        use_font_size = font_size or self.font_size
        target_font = self._load_font(use_font_path, use_font_size)
        
        # 4. 绘制文字（复用核心逻辑，适配目标图片）
        if text_type.lower() == "3d":
            # 绘制3D文字到目标图片
            shadow_pos = (pos[0] + offset[0], pos[1] + offset[1])
            target_draw.text(shadow_pos, text, font=target_font, fill=shadow_color)
            target_draw.text(pos, text, font=target_font, fill=main_color)
        
        elif text_type.lower() == "gradient":
            # 绘制渐变文字到目标图片
            # 计算文字边界（基于目标图片的绘制对象）
            bbox = target_draw.textbbox(pos, text, font=target_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x, text_y = bbox[0], bbox[1]
            
            # 创建渐变层
            gradient = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
            grad_draw = ImageDraw.Draw(gradient)
            for x in range(text_w):
                ratio = x / text_w
                r = int(start_color[0]*(1-ratio) + end_color[0]*ratio)
                g = int(start_color[1]*(1-ratio) + end_color[1]*ratio)
                b = int(start_color[2]*(1-ratio) + end_color[2]*ratio)
                grad_draw.line([(x, 0), (x, text_h)], fill=(r, g, b))
            
            # 创建文字遮罩
            mask = Image.new("L", (text_w, text_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.text((0, 0), text, font=target_font, fill=255)
            
            # 粘贴渐变到目标图片
            target_img.paste(gradient, (text_x, text_y), mask=mask)
        
        else:
            raise ValueError("text_type 仅支持 '3d' 或 'gradient'")
        
        # 5. 保存并返回修改后的图片
        target_img.save(save_path)
        print(f"文字已绘制到图片，保存路径：{save_path}")
        return target_img

    def save(self, save_path="pixel_text.png"):
        """原有功能：保存新建画布的图片"""
        self.img.save(save_path)
        print(f"新建画布图片已保存至：{save_path}")

    def show(self):
        """原有功能：显示新建画布的图片（调试用）"""
        self.img.show()


# ===================== 完整使用示例 =====================
if __name__ == "__main__":
    # 1. 初始化生成器（设置全局默认配置）
    generator = PixelTextImageGenerator(
        canvas_size=(1000, 400),
        bg_color=(10, 10, 20),
        font_path="../cache/font/Cave-Story.ttf",
        font_size=70
    )

    # 2. 原有功能：给新建画布添加文字
    generator.add_3d_text("CLAUDE", pos=(50, 80), main_color=(255, 140, 0), shadow_color=(180, 80, 0))
    generator.add_gradient_text("HUGGING FACE", pos=(50, 200), start_color=(255, 255, 0), end_color=(255, 69, 0))
    generator.save("new_canvas_text.png")  # 保存新建画布的图片

    # 3. 新增功能：绘制文字到已有图片（两种输入方式）
    # 传入图片路径 /PIL Image对象（支持二次编辑）
    bg_img = Image.open(r"C:\Users\DM\Pictures\Liu-Yifei_1.jpg")
    # 先画渐变文字，返回修改后的图片
    modified_img = generator.draw_text_on_image(
        image_source=bg_img,
        text="GRADIENT TEXT",
        text_type="gradient",
        pos=(200, 200),
        start_color=(255, 255, 0),
        end_color=(255, 69, 0),
        save_path="gradient_text_on_bg.png"
    )
    # 基于返回的图片继续绘制（比如再加一行3D文字）
    generator.draw_text_on_image(
        image_source=modified_img,
        text="EXTRA 3D TEXT",
        text_type="3d",
        pos=(300, 300),
        main_color=(255, 140, 0),
        shadow_color=(180, 80, 0),
        save_path="mixed_text_on_bg.png"
    )
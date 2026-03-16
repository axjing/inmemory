import os
import fitz
from PIL import Image
import shutil
from datetime import datetime


def resize_img(image, max_solution):
    isresize = False
    w = image.width
    h = image.height
    newh = h
    neww = w
    maxv = w
    if maxv < h:
        maxv = h
        if maxv > max_solution:
            raitoh = max_solution / h
            newh = max_solution
            neww = w * raitoh
    else:
        if maxv > max_solution:
            raitow = max_solution / w
            neww = max_solution
            newh = h * raitow

    if newh != h or neww != w:
        image = image.resize((int(neww), int(newh)), Image.LANCZOS)
        isresize = True
    return image, isresize


def process_img(filename):
    new_filename = filename
    max_file_size = 10.0
    max_solution = 8192.0
    if os.path.exists(filename):
        imgsize = os.path.getsize(filename) * 1.0 / 1024 / 1024
        image = Image.open(filename)
        if imgsize > 10:
            os.remove(filename)
            image, isresize = resize_img(image, max_solution)
            filename = filename.replace('.png', '.jpg')
            new_filename = filename
            image.save(new_filename, optimize=True, quality=50)
        else:
            image, isresize = resize_img(image, max_solution)
            if isresize:
                image.save(filename)
    return new_filename


def pdf_to_imgs_pymupdf(pdf_path, img_output_folder):
    index = 1
    image_paths = []
    with fitz.open(pdf_path) as pdf:
        for i, page in enumerate(pdf):
            trans = fitz.Matrix(2.0, 2.0)
            image = page.get_pixmap(matrix=trans, alpha=False)  # 获得每一页的流对象
            papername = os.path.basename(pdf_path)[:-4]
            filename = os.path.join(img_output_folder, f"{papername}_{index:02d}.png")
            image.save(filename, "PNG")
            new_filename = process_img(filename)
            image_paths.append(new_filename)
            index = index + 1
    return image_paths


def convert_pdf_to_images(pdf_path, output_dir):
    """
    将PDF文件转换为图片
    :param pdf_path: PDF文件的路径
    :param output_dir: 输出图片的文件夹路径
    :return: 生成的图片路径列表    """
    
    pdf_name=os.path.basename(pdf_path)[:-4]
    output_path=os.path.join(output_dir,pdf_name)
    os.makedirs(output_path,exist_ok=True)
    
    # 转换PDF为图片
    image_paths = pdf_to_imgs_pymupdf(pdf_path, output_path)
    return image_paths

if __name__ == "__main__":
    # 示例用法
    pdf_path = r"D:\An\CODE\datasets\质能等价-维基百科_自由的百科全书.pdf"  # 替换为你的PDF文件路径
    output_dir = r"D:\An\CODE\datasets"     # 替换为你想要保存图片的文件夹路径
    
    image_paths = convert_pdf_to_images(pdf_path, output_dir)
    print(f"已生成 {len(image_paths)} 个图片文件：")
    for path in image_paths:
        print(path)

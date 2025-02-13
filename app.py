from flask import Flask, render_template, request, send_file, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import zipfile
import io
import webbrowser
import sys
import threading
import piexif
from datetime import datetime
import numpy as np
import cv2
import uuid

app = Flask(__name__)
app.secret_key = 'gizli_anahtar_123'  # Session için gerekli

# Resource klasörü için yol belirleme
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

# Yükleme klasörü oluşturma
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 * 1024  # 16GB limit

# Desteklenen resim formatları
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff', 'ico'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def apply_effects(img, effects):
    if 'grayscale' in effects:
        img = img.convert('L')
    if 'sepia' in effects:
        img = img.convert('RGB')
        width, height = img.size
        pixels = img.load()
        for x in range(width):
            for y in range(height):
                r, g, b = img.getpixel((x, y))
                tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                pixels[x, y] = (min(tr, 255), min(tg, 255), min(tb, 255))
    if 'brightness' in effects:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(float(effects['brightness']))
    if 'contrast' in effects:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(float(effects['contrast']))
    if 'blur' in effects:
        img = img.filter(ImageFilter.GaussianBlur(radius=float(effects['blur'])))
    if 'sharpen' in effects:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=250, threshold=1))
    if 'edge_enhance' in effects:
        img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    if 'emboss' in effects:
        img = img.filter(ImageFilter.EMBOSS)
    if 'invert' in effects:
        img = ImageOps.invert(img)
    if 'posterize' in effects:
        img = ImageOps.posterize(img, int(effects['posterize']))
    if 'solarize' in effects:
        img = ImageOps.solarize(img, int(effects['solarize']))
    return img

def add_watermark(img, watermark_text, position, opacity, color, font_size_factor=20):
    if not watermark_text:
        return img
    
    txt = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt)
    
    # Font boyutunu ayarla
    font_size = int(min(img.size) / font_size_factor)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    text_size = draw.textsize(watermark_text, font=font)
    
    # Pozisyon hesaplama
    if position == 'bottom-right':
        position = (img.size[0] - text_size[0] - 10, img.size[1] - text_size[1] - 10)
    elif position == 'top-right':
        position = (img.size[0] - text_size[0] - 10, 10)
    elif position == 'bottom-left':
        position = (10, img.size[1] - text_size[1] - 10)
    elif position == 'top-left':
        position = (10, 10)
    else:  # center
        position = ((img.size[0] - text_size[0]) // 2, (img.size[1] - text_size[1]) // 2)
    
    # Renk dönüşümü
    try:
        rgb_color = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        fill_color = rgb_color + (int(255 * opacity),)
    except:
        fill_color = (255, 255, 255, int(255 * opacity))
    
    # Filigran çizimi
    draw.text(position, watermark_text, font=font, fill=fill_color)
    
    watermarked = Image.alpha_composite(img.convert('RGBA'), txt)
    return watermarked.convert('RGB')

def apply_filters(img, filters):
    if 'vintage' in filters:
        img = img.convert('RGB')
        r, g, b = img.split()
        r = r.point(lambda i: i * 1.2)
        b = b.point(lambda i: i * 0.8)
        img = Image.merge('RGB', (r, g, b))
    
    if 'cool' in filters:
        img = img.convert('RGB')
        r, g, b = img.split()
        b = b.point(lambda i: i * 1.2)
        img = Image.merge('RGB', (r, g, b))
    
    if 'warm' in filters:
        img = img.convert('RGB')
        r, g, b = img.split()
        r = r.point(lambda i: i * 1.2)
        img = Image.merge('RGB', (r, g, b))
    
    if 'dramatic' in filters:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.2)
    
    return img

def process_image(img, params):
    # Orijinal boyutları koru eğer hedef boyutlardan küçükse
    target_width = int(params.get('width', 1080))
    target_height = int(params.get('height', 1620))
    
    if img.size[0] <= target_width and img.size[1] <= target_height and not params.get('force_resize', False):
        processed_img = img
    else:
        processed_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # Rotasyon uygula
    if 'rotation' in params:
        processed_img = processed_img.rotate(float(params['rotation']), expand=True)
    
    # Efektleri uygula
    if 'effects' in params:
        processed_img = apply_effects(processed_img, params['effects'])
    
    # Filtreleri uygula
    if 'filters' in params:
        processed_img = apply_filters(processed_img, params['filters'])
    
    # Filigran ekle
    if 'watermark' in params:
        processed_img = add_watermark(
            processed_img,
            params['watermark'],
            params.get('watermark_position', 'bottom-right'),
            float(params.get('watermark_opacity', 0.5)),
            params.get('watermark_color', '#FFFFFF')
        )
    
    return processed_img

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/basic')
def basic():
    return render_template('basic.html')

@app.route('/advanced')
def advanced():
    return render_template('advanced.html')

@app.route('/filters')
def filters():
    return render_template('filters.html')

@app.route('/watermark')
def watermark():
    return render_template('watermark.html')

@app.route('/batch')
def batch():
    return render_template('batch.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'files' not in request.files:
        return 'Dosya seçilmedi', 400
    
    try:
        # Parametreleri al
        params = {
            'width': int(request.form.get('width', 1080)),
            'height': int(request.form.get('height', 1620)),
            'rotation': request.form.get('rotation', 0),
            'quality': int(request.form.get('quality', 100)),
            'format': request.form.get('format', None),
            'watermark': request.form.get('watermark', ''),
            'watermark_position': request.form.get('watermark_position', 'bottom-right'),
            'watermark_opacity': float(request.form.get('watermark_opacity', 0.5)),
            'watermark_color': request.form.get('watermark_color', '#FFFFFF'),
            'keep_exif': request.form.get('keep_exif', 'true') == 'true',
            'force_resize': request.form.get('force_resize', 'false') == 'true',
            'effects': {
                'grayscale': request.form.get('grayscale', 'false') == 'true',
                'sepia': request.form.get('sepia', 'false') == 'true',
                'brightness': request.form.get('brightness', 1.0),
                'contrast': request.form.get('contrast', 1.0),
                'blur': request.form.get('blur', 0),
                'sharpen': request.form.get('sharpen', 'false') == 'true',
                'edge_enhance': request.form.get('edge_enhance', 'false') == 'true',
                'emboss': request.form.get('emboss', 'false') == 'true',
                'invert': request.form.get('invert', 'false') == 'true',
                'posterize': request.form.get('posterize', 4),
                'solarize': request.form.get('solarize', 128)
            },
            'filters': {
                'vintage': request.form.get('vintage', 'false') == 'true',
                'cool': request.form.get('cool', 'false') == 'true',
                'warm': request.form.get('warm', 'false') == 'true',
                'dramatic': request.form.get('dramatic', 'false') == 'true'
            }
        }
        
        # Boyut kontrolü
        if params['width'] < 1 or params['height'] < 1:
            return 'Geçersiz boyut değerleri', 400
        if params['width'] > 10000 or params['height'] > 10000:
            return 'Maksimum boyut 10000x10000 olabilir', 400
            
    except ValueError:
        return 'Geçersiz parametre değerleri', 400
    
    files = request.files.getlist('files')
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            if file.filename and allowed_file(file.filename):
                try:
                    img = Image.open(file)
                    original_format = img.format
                    original_mode = img.mode
                    info = img.info
                    
                    # EXIF bilgilerini al
                    exif_data = None
                    if 'exif' in info and params['keep_exif']:
                        exif_data = info['exif']
                    
                    # Görüntü işleme
                    processed_img = process_image(img, params)
                    
                    # Çıktı formatını ayarla
                    output_format = params['format'] if params['format'] else original_format
                    
                    # Orijinal modu koru
                    if processed_img.mode != original_mode and output_format != 'PNG':
                        processed_img = processed_img.convert(original_mode)
                    
                    img_byte_arr = io.BytesIO()
                    
                    # Kaydetme parametreleri
                    save_kwargs = {
                        'format': output_format,
                        'quality': params['quality'] if output_format in ['JPEG', 'WEBP'] else None
                    }
                    
                    # EXIF bilgilerini ekle
                    if exif_data and output_format == 'JPEG':
                        save_kwargs['exif'] = exif_data
                    
                    # Dosyayı kaydet
                    processed_img.save(img_byte_arr, **save_kwargs)
                    img_byte_arr.seek(0)
                    
                    # Dosya adı oluştur
                    base_name = os.path.splitext(secure_filename(file.filename))[0]
                    extension = output_format.lower()
                    output_filename = f"{base_name}.{extension}"
                    
                    zf.writestr(output_filename, img_byte_arr.getvalue())
                    
                except Exception as e:
                    print(f"Hata oluştu: {str(e)} - Dosya: {file.filename}")
                    continue
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='converted_images.zip'
    )

def open_browser(): 
    webbrowser.open('http://127.0.0.1:5001/')

if __name__ == '__main__':
    # Tarayıcıyı otomatik aç
    threading.Timer(1.5, open_browser).start()
    # Uygulamayı başlat
    app.run(port=5001, debug=False) 
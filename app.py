from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import os
import zipfile
import io
import webbrowser
import sys
import threading

app = Flask(__name__)

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

def process_image(img, target_width, target_height):
    # Orijinal boyutları koru eğer hedef boyutlardan küçükse
    if img.size[0] <= target_width and img.size[1] <= target_height:
        return img
    
    # Direkt olarak istenen boyuta getir
    resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return resized

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    if 'files' not in request.files:
        return 'Dosya seçilmedi', 400
    
    # Kullanıcının girdiği boyutları al
    try:
        target_width = int(request.form.get('width', 1080))
        target_height = int(request.form.get('height', 1620))
        
        # Boyut kontrolü
        if target_width < 1 or target_height < 1:
            return 'Geçersiz boyut değerleri', 400
        if target_width > 10000 or target_height > 10000:
            return 'Maksimum boyut 10000x10000 olabilir', 400
            
    except ValueError:
        return 'Geçersiz boyut değerleri', 400
    
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
                    
                    # Kullanıcının girdiği boyutları kullan
                    resized_img = process_image(img, target_width, target_height)
                    
                    # Orijinal modu koru
                    if resized_img.mode != original_mode:
                        resized_img = resized_img.convert(original_mode)
                    
                    img_byte_arr = io.BytesIO()
                    
                    # Tüm orijinal bilgileri kullanarak kaydet
                    save_kwargs = {
                        'format': original_format,
                        **info  # Tüm orijinal meta verileri ekle
                    }
                    
                    # JPEG için özel ayarlar
                    if original_format == 'JPEG':
                        save_kwargs.update({
                            'quality': 100,
                            'subsampling': 0
                        })
                    
                    # PNG için özel ayarlar
                    elif original_format == 'PNG':
                        save_kwargs.update({
                            'optimize': False,  # Optimizasyonu kapat
                            'compress_level': 0  # Sıkıştırma yapma
                        })
                    
                    resized_img.save(img_byte_arr, **save_kwargs)
                    img_byte_arr.seek(0)
                    
                    output_filename = secure_filename(file.filename)
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
    webbrowser.open('http://127.0.0.1:5000/')

if __name__ == '__main__':
    # Tarayıcıyı otomatik aç
    threading.Timer(1.5, open_browser).start()
    # Uygulamayı başlat
    app.run(port=5000, debug=False) 
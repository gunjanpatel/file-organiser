from datetime import datetime
from typing import Optional

IMAGE_EXTS = {'.jpg', '.jpeg', '.tiff', '.tif', '.png', '.heic', '.webp'}

def get_exif_datetime_original(path: str) -> Optional[datetime]:
    try:
        from PIL import Image, ExifTags
    except Exception:
        return None
    try:
        img = Image.open(path)
        exif = img.getexif()
        if not exif:
            return None
        dt_key = None
        for k, v in ExifTags.TAGS.items():
            if v == 'DateTimeOriginal':
                dt_key = k
                break
        if dt_key is None:
            return None
        dt_val = exif.get(dt_key)
        if not dt_val:
            return None
        try:
            return datetime.strptime(dt_val, '%Y:%m:%d %H:%M:%S')
        except Exception:
            return None
    except Exception:
        return None

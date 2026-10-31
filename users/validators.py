from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions

MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB
ALLOWED_AVATAR_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_avatar_file(file):
    """头像文件校验：体积、后缀、真实图片尺寸，API 与表单共用。"""
    if file is None or not hasattr(file, "size"):
        return

    if file.size > MAX_AVATAR_SIZE:
        raise ValidationError("头像不能超过 2MB")

    name = getattr(file, "name", "") or ""
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in ALLOWED_AVATAR_SUFFIXES:
        raise ValidationError("头像仅支持 jpg / png / webp 格式")

    content_type = getattr(file, "content_type", None)
    if content_type and content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise ValidationError("头像文件类型不合法")

    try:
        width, height = get_image_dimensions(file)
    except Exception:
        raise ValidationError("无法识别的图片文件")

    if not width or not height:
        raise ValidationError("无法识别的图片文件")
    if width > 4000 or height > 4000:
        raise ValidationError("头像分辨率过大，请压缩后再上传")

    file.seek(0)

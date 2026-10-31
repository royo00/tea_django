"""用户业务的公共校验逻辑，被 REST 序列化器与门户表单共用。

这里只抛 django.core.exceptions.ValidationError：
DRF 的 Serializer 会自动把它转换成 400 的字段错误，表单也能直接显示。
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


def ensure_phone_available(phone, instance=None):
    """返回清洗后的手机号；空值返回 None，不占用唯一索引。"""
    if not phone:
        return None
    phone = str(phone).strip()
    if not phone:
        return None
    qs = User.objects.filter(phone=phone)
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise ValidationError("该手机号已被注册")
    return phone


def ensure_email_available(email, instance=None):
    if not email:
        return ""
    email = str(email).strip()
    if not email:
        return ""
    qs = User.objects.filter(email__iexact=email)
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise ValidationError("该邮箱已被注册")
    return email

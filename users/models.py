import uuid
from pathlib import Path

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# 中国大陆手机号：1 开头，第二位 3-9，共 11 位
phone_validator = RegexValidator(
    regex=r"^1[3-9]\d{9}$",
    message="请输入有效的 11 位手机号",
)


def avatar_upload_to(instance, filename: str) -> str:
    """头像存放路径：media/avatars/YYYY/MM/<uuid>.jpg，避免同名覆盖与中文名问题。"""
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"avatars/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{suffix}"


class User(AbstractUser):
    """项目统一用户模型。

    门户网页走 Session 登录（username 或 phone 均可），移动 APP 走 JWT，
    两端共用这一张表，因此扩展字段集中在这里维护。
    """

    phone = models.CharField(
        "手机号",
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        validators=[phone_validator],
        help_text="移动端登录账号，全局唯一；不填则存 NULL，MySQL 下允许多个 NULL",
    )
    avatar = models.ImageField(
        "头像",
        upload_to=avatar_upload_to,
        null=True,
        blank=True,
        help_text="建议正方形，2MB 以内的 jpg / png / webp",
    )

    class Meta:
        db_table = "users_user"
        verbose_name = "用户"
        verbose_name_plural = "用户"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.phone and f"{self.username}({self.phone})" or self.username

    def save(self, *args, **kwargs):
        # 空字符串统一转 None，否则 phone 的 unique 约束会把第二个空值用户挡掉
        if not self.phone:
            self.phone = None
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    @property
    def avatar_url(self) -> str:
        return self.avatar.url if self.avatar else ""

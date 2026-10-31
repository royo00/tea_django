from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "phone", "email", "avatar_preview", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "phone", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("avatar_preview", "last_login", "date_joined")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("扩展资料", {"fields": ("phone", "avatar", "avatar_preview")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("扩展资料", {"fields": ("phone", "avatar")}),
    )

    @admin.display(description="头像")
    def avatar_preview(self, obj):
        if not obj.avatar:
            return "—"
        return format_html(
            '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;">',
            obj.avatar.url,
        )

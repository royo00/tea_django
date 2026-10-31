from django.contrib import admin

from .models import UserCollect


@admin.register(UserCollect)
class UserCollectAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "formula", "collect_time")
    list_filter = ("collect_time",)
    search_fields = ("user__username", "user__phone", "formula__name")
    autocomplete_fields = ("user", "formula")
    readonly_fields = ("collect_time",)
    date_hierarchy = "collect_time"

"""后台仪表盘用的模板标签。

只服务于 admin 首页（templates/admin/index.html）：把几项核心数据的
统计与跳转地址算好，模板里循环渲染成卡片，避免在模板中写业务查询。
"""
from datetime import timedelta

from django import template
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

register = template.Library()


def _safe_url(name: str, fallback: str = "#") -> str:
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback


@register.simple_tag
def admin_stats():
    """返回仪表盘统计卡片数据；任何异常都降级为空列表，不影响后台可用性。"""
    try:
        from collects.models import UserCollect
        from recipes.models import Material, Tag, TeaFormula
        from users.models import User

        formula_total = TeaFormula.objects.count()
        formula_on_shelf = TeaFormula.objects.filter(is_on_shelf=True).count()
        material_total = Material.objects.count()
        tag_total = Tag.objects.count()
        user_total = User.objects.count()
        user_active = User.objects.filter(is_active=True).count()
        collect_total = UserCollect.objects.count()
        collect_week = UserCollect.objects.filter(
            collect_time__gte=timezone.now() - timedelta(days=7)
        ).count()
    except Exception:  # 数据库未迁移 / 表缺失时不影响首页渲染
        return []

    return [
        {
            "label": "配方总数",
            "value": formula_total,
            "hint": f"上架 {formula_on_shelf} 款",
            "url": _safe_url("admin:recipes_teaformula_changelist"),
        },
        {
            "label": "原料",
            "value": material_total,
            "hint": f"标签 {tag_total} 个",
            "url": _safe_url("admin:recipes_material_changelist"),
        },
        {
            "label": "用户",
            "value": user_total,
            "hint": f"启用 {user_active} 人",
            "url": _safe_url("admin:users_user_changelist"),
        },
        {
            "label": "收藏",
            "value": collect_total,
            "hint": f"近 7 天 {collect_week} 条",
            "url": _safe_url("admin:collects_usercollect_changelist"),
        },
    ]

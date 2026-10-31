"""移动 APP / 前端调用：/api/collects/"""

from django.urls import path

from . import views

app_name = "collects_api"

urlpatterns = [
    # 我的收藏列表（GET）/ 添加收藏（POST）
    path("", views.UserCollectListCreateView.as_view(), name="collect_list"),
    # 查询某配方是否已收藏，放在 <formula_id>/ 之前，避免被上面的规则误匹配
    path("<int:formula_id>/status/", views.UserCollectStatusView.as_view(), name="collect_status"),
    # 取消收藏
    path("<int:formula_id>/", views.UserCollectDeleteView.as_view(), name="collect_delete"),
]

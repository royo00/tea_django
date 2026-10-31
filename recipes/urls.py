"""移动 APP / 前端调用：/api/recipes/"""

from django.urls import path

from . import views

app_name = "recipes_api"

urlpatterns = [
    # 配方浏览 + 标签/难度筛选 + 关键词搜索（同一视图，参数区分）
    path("formulas/", views.FormulaListView.as_view(), name="formula_list"),
    # 搜索模块的独立入口，语义更清晰，行为与 formulas/?search= 完全一致
    path("search/", views.FormulaListView.as_view(), name="formula_search"),
    # 配方详情（自动累加浏览量）
    path("formulas/<int:pk>/", views.FormulaDetailView.as_view(), name="formula_detail"),
    # 首页筛选栏的标签列表
    path("tags/", views.TagListView.as_view(), name="tag_list"),
]

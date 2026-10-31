"""配方浏览 / 搜索 / 详情 API。

移动 APP 的游客也能浏览，因此这三个接口统一放开为 AllowAny；
后续「收藏」等写操作接口再单独要求 JWT 登录。

统一约束：只返回 is_on_shelf=True 的配方，未上架的配方对 APP 完全不可见。
"""

from django.db.models import F, Prefetch, Q
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import FormulaMaterial, FormulaTag, Tag, TeaFormula
from .pagination import FormulaPagination
from .serializers import FormulaDetailSerializer, FormulaListSerializer, TagSerializer

# 允许的排序字段白名单：?ordering=view_count / -create_time
ORDERING_FIELDS = {"create_time", "view_count", "difficulty", "duration", "id"}
DEFAULT_ORDERING = ("-create_time", "-id")


def on_shelf_queryset():
    """已上架配方 + 列表/详情共用的预取，避免 N+1 查询。"""
    return (
        TeaFormula.objects.filter(is_on_shelf=True)
        .prefetch_related(
            Prefetch("formula_tags", queryset=FormulaTag.objects.select_related("tag")),
            Prefetch("formula_materials", queryset=FormulaMaterial.objects.select_related("material")),
        )
    )


class FormulaListView(generics.ListAPIView):
    """GET /api/recipes/formulas/

    查询参数：
        tag        标签 id 或标签名，如 ?tag=3 或 ?tag=奶茶
        search     关键词，匹配配方名称或原料名称，如 ?search=红茶
        difficulty 难度 1-5
        ordering   排序字段，前缀 - 表示倒序，默认 -create_time
        page / page_size 分页，默认 10 条，最大 50 条
    """

    permission_classes = [AllowAny]
    pagination_class = FormulaPagination
    serializer_class = FormulaListSerializer

    def get_queryset(self):
        qs = on_shelf_queryset()
        params = self.request.query_params

        # ---- 标签筛选 ----
        tag = (params.get("tag") or "").strip()
        if tag:
            if tag.isdigit():
                qs = qs.filter(formula_tags__tag_id=int(tag))
            else:
                qs = qs.filter(formula_tags__tag__name__iexact=tag)

        # ---- 关键词搜索：配方名 或 原料名 ----
        keyword = (params.get("search") or params.get("q") or "").strip()
        if keyword:
            qs = qs.filter(
                Q(name__icontains=keyword) | Q(formula_materials__material__name__icontains=keyword)
            ).distinct()

        # ---- 难度筛选 ----
        difficulty = (params.get("difficulty") or "").strip()
        if difficulty.isdigit():
            qs = qs.filter(difficulty=int(difficulty))

        # ---- 排序 ----
        ordering = (params.get("ordering") or "").strip()
        if ordering and ordering.lstrip("-") in ORDERING_FIELDS:
            qs = qs.order_by(ordering, "-id")
        else:
            qs = qs.order_by(*DEFAULT_ORDERING)

        return qs


class FormulaDetailView(generics.RetrieveAPIView):
    """GET /api/recipes/formulas/<id>/

    打开详情即累加浏览量，用 F() 在数据库侧自增，避免并发下丢计数，
    同时不会触发 update_time 变化（内容本身没变）。
    """

    permission_classes = [AllowAny]
    serializer_class = FormulaDetailSerializer
    queryset = on_shelf_queryset()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        TeaFormula.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        instance.view_count += 1  # 内存同步，保证本次响应返回最新浏览量
        return super().retrieve(request, *args, **kwargs)


class TagListView(generics.ListAPIView):
    """GET /api/recipes/tags/  标签列表，供首页筛选栏使用。

    只返回至少挂了一个上架配方的标签，避免筛选出空结果。
    """

    permission_classes = [AllowAny]
    pagination_class = None
    serializer_class = TagSerializer
    queryset = (
        Tag.objects.filter(formula_tags__formula__is_on_shelf=True)
        .distinct()
        .order_by("name")
    )

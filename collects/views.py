"""用户收藏 API：/api/collects/

全部接口都要求登录（JWT 或 Session），且只能操作自己的收藏，
不同用户之间的收藏互不可见。

路由：
    GET    /api/collects/                      我的收藏列表（可按收藏时间正/倒序）
    POST   /api/collects/                      添加收藏  {"formula_id": 1}
    DELETE /api/collects/<formula_id>/         取消收藏
    GET    /api/collects/<formula_id>/status/  查询某配方是否已收藏（详情页按钮用）
"""

from django.db.models import Prefetch
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from recipes.models import FormulaTag

from .models import UserCollect
from .serializers import CollectCreateSerializer, UserCollectSerializer

# 允许的排序字段：?ordering=collect_time（最早在前）/ -collect_time（最新在前，默认）
ORDERING_FIELDS = {"collect_time", "id"}
DEFAULT_ORDERING = ("-collect_time", "-id")


class CollectPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class UserCollectListCreateView(generics.GenericAPIView):
    """GET 我的收藏列表 / POST 添加收藏。"""

    permission_classes = [IsAuthenticated]
    pagination_class = CollectPagination
    serializer_class = UserCollectSerializer

    def get_queryset(self):
        return (
            UserCollect.objects.filter(user=self.request.user, formula__is_on_shelf=True)
            .select_related("formula")
            # 卡片要展示标签，提前取出来，避免每条收藏多查一次
            .prefetch_related(
                Prefetch("formula__formula_tags", queryset=FormulaTag.objects.select_related("tag"))
            )
        )

    def get(self, request):
        queryset = self.get_queryset()
        ordering = (request.query_params.get("ordering") or "").strip()
        if ordering and ordering.lstrip("-") in ORDERING_FIELDS:
            queryset = queryset.order_by(ordering, "-id")
        else:
            queryset = queryset.order_by(*DEFAULT_ORDERING)

        page = self.paginate_queryset(queryset)
        serializer = UserCollectSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CollectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        formula = serializer.formula

        # get_or_create + 唯一约束：重复点击收藏按钮不会产生脏数据
        collect, created = UserCollect.objects.get_or_create(
            user=request.user, formula=formula,
        )
        data = UserCollectSerializer(collect, context={"request": request}).data
        if not created:
            return Response(
                {"detail": "该配方已在收藏中", "created": False, "collect": data},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"detail": "收藏成功", "created": True, "collect": data},
            status=status.HTTP_201_CREATED,
        )


class UserCollectDeleteView(generics.GenericAPIView):
    """DELETE /api/collects/<formula_id>/  按配方取消收藏。

    用 formula_id 而不是收藏记录 id：APP 在配方详情页只知道当前配方，
    直接带 formula_id 就能取消，省一次查询。
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, formula_id):
        deleted, _ = UserCollect.objects.filter(
            user=request.user, formula_id=formula_id,
        ).delete()
        if not deleted:
            return Response(
                {"detail": "尚未收藏该配方"}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserCollectStatusView(generics.GenericAPIView):
    """GET /api/collects/<formula_id>/status/  查询收藏状态。

    未收藏也返回 200（collected=false），避免前端把 404 当成请求失败。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, formula_id):
        collect = (
            UserCollect.objects.filter(user=request.user, formula_id=formula_id)
            .select_related("formula")
            .first()
        )
        if collect is None:
            return Response({"formula_id": formula_id, "collected": False, "collect": None})
        return Response(
            {
                "formula_id": formula_id,
                "collected": True,
                "collect": UserCollectSerializer(collect, context={"request": request}).data,
            }
        )

"""配方模块分页配置。

移动端列表用页码分页（page / page_size），同时允许客户端调整每页条数，
上限 50 条，避免一次拉取过多导致卡顿。
"""

from rest_framework.pagination import PageNumberPagination


class FormulaPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

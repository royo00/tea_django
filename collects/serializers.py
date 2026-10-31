"""收藏模块序列化器。

收藏列表直接复用配方模块的卡片序列化器，APP 端可以拿同一套渲染逻辑
展示「我的收藏」和首页列表，不用维护两套字段映射。
"""

from rest_framework import serializers

from recipes.models import TeaFormula
from recipes.serializers import FormulaListSerializer

from .models import UserCollect


class CollectCreateSerializer(serializers.Serializer):
    """添加收藏的入参：只收一个 formula_id，其余字段由后端决定。"""

    formula_id = serializers.IntegerField(min_value=1)

    def validate_formula_id(self, value):
        # 未上架 / 不存在的配方一律拒绝，和浏览接口的口径保持一致
        formula = TeaFormula.objects.filter(pk=value, is_on_shelf=True).first()
        if formula is None:
            raise serializers.ValidationError("配方不存在或已下架")
        self.formula = formula
        return value


class UserCollectSerializer(serializers.ModelSerializer):
    """收藏记录：外层是收藏元信息，内层 formula 是完整的配方卡片。"""

    formula = FormulaListSerializer(read_only=True)

    class Meta:
        model = UserCollect
        fields = ("id", "collect_time", "formula")
        read_only_fields = fields

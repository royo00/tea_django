"""配方模块序列化器：列表卡片用轻量版，详情用完整版。"""

from rest_framework import serializers

from .models import FormulaMaterial, Tag, TeaFormula


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name")
        read_only_fields = fields


class FormulaMaterialSerializer(serializers.ModelSerializer):
    """用料清单的一行：红茶 10 g"""

    material_name = serializers.CharField(source="material.name", read_only=True)
    quantity_display = serializers.CharField(read_only=True)

    class Meta:
        model = FormulaMaterial
        fields = ("id", "material_id", "material_name", "quantity", "unit", "quantity_display", "sort_order")
        read_only_fields = fields


class FormulaListSerializer(serializers.ModelSerializer):
    """首页 / 搜索列表卡片：封面、名称、标签、难度（附带耗时与温度，便于卡片副标题）。"""

    cover = serializers.ImageField(read_only=True)  # 有 request 上下文时自动输出绝对地址
    difficulty_display = serializers.CharField(source="get_difficulty_display", read_only=True)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = TeaFormula
        fields = (
            "id",
            "name",
            "cover",
            "difficulty",
            "difficulty_display",
            "duration",
            "temperature_desc",
            "tags",
        )
        read_only_fields = fields

    def get_tags(self, obj) -> list[dict]:
        # 依赖视图层的 prefetch_related("formula_tags__tag")，避免 N+1
        return [{"id": ft.tag_id, "name": ft.tag.name} for ft in obj.formula_tags.all()]


class FormulaDetailSerializer(FormulaListSerializer):
    """详情页：在卡片字段基础上补用料清单与分步步骤。"""

    materials = FormulaMaterialSerializer(source="formula_materials", many=True, read_only=True)
    steps = serializers.SerializerMethodField()

    class Meta(FormulaListSerializer.Meta):
        fields = FormulaListSerializer.Meta.fields + (
            "step_content",
            "steps",
            "materials",
            "view_count",
            "create_time",
            "update_time",
        )
        read_only_fields = fields

    def get_steps(self, obj) -> list[str]:
        """把 step_content 按行拆成数组，前端可直接逐条渲染；序号由前端按需拼。"""
        return obj.step_lines

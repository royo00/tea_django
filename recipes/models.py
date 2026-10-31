"""茶饮配方领域模型。

表结构（5 张）：
    Material        原料
    TeaFormula      配方
    FormulaMaterial 配方-原料（含用量、单位、排序）
    Tag             标签
    FormulaTag      配方-标签

设计取舍：
1. 制作步骤不单独建表，直接放在 TeaFormula.step_content 里，前端按换行符分段即可。
2. FormulaMaterial.material 使用 PROTECT，防止误删正在被配方引用的原料。
3. 列表页、搜索、详情统一以 is_on_shelf=True 为入口条件，索引也围绕它建立。
"""

import uuid
from pathlib import Path

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def cover_upload_to(instance, filename: str) -> str:
    """封面存放路径：media/covers/YYYY/MM/<uuid>.jpg，避免同名覆盖与中文名问题。"""
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"covers/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{suffix}"


class Material(models.Model):
    """原料，例如「红茶」「牛奶」「白砂糖」。"""

    name = models.CharField("原料名称", max_length=50, unique=True, db_index=True)
    category = models.CharField(
        "原料分类",
        max_length=20,
        blank=True,
        default="",
        help_text="自由填写，如：茶叶 / 乳制品 / 糖类 / 水果",
    )
    remark = models.CharField("备注", max_length=200, blank=True, default="")
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "recipes_material"
        verbose_name = "原料"
        verbose_name_plural = "原料"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    """配方分类标签，例如「奶茶」「果茶」「热饮」。"""

    name = models.CharField("标签名称", max_length=30, unique=True, db_index=True)

    class Meta:
        db_table = "recipes_tag"
        verbose_name = "标签"
        verbose_name_plural = "标签"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class TeaFormula(models.Model):
    """茶饮配方主体。"""

    class Difficulty(models.IntegerChoices):
        EASY = 1, "简单"
        MEDIUM_EASY = 2, "较简单"
        MEDIUM = 3, "中等"
        MEDIUM_HARD = 4, "较难"
        HARD = 5, "困难"

    name = models.CharField("配方名称", max_length=100, db_index=True)
    cover = models.ImageField("封面图片", upload_to=cover_upload_to, blank=True)
    difficulty = models.PositiveSmallIntegerField(
        "难度等级",
        choices=Difficulty.choices,
        default=Difficulty.EASY,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1-5，数字越大越难",
    )
    duration = models.PositiveIntegerField("制作耗时（分钟）", default=0)
    temperature_desc = models.CharField(
        "适用温度", max_length=50, blank=True, default="",
        help_text="如：85℃ / 冰饮 / 常温",
    )
    step_content = models.TextField(
        "制作步骤",
        blank=True,
        default="",
        help_text="纯文本，每行一步，前端按换行符分段展示",
    )
    is_on_shelf = models.BooleanField("是否上架", default=True, db_index=True)
    view_count = models.PositiveIntegerField("浏览量", default=0, db_index=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "recipes_tea_formula"
        verbose_name = "茶饮配方"
        verbose_name_plural = "茶饮配方"
        ordering = ["-create_time", "-id"]
        indexes = [
            # 首页卡片列表：is_on_shelf=True 按创建时间倒序
            models.Index(fields=["is_on_shelf", "-create_time"], name="idx_formula_shelf_ctime"),
            # 热度排序 / 后续「热门配方」入口
            models.Index(fields=["is_on_shelf", "-view_count"], name="idx_formula_shelf_views"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def step_lines(self) -> list[str]:
        """把 step_content 按行拆成列表，供序列化器复用。"""
        return [line.strip() for line in (self.step_content or "").splitlines() if line.strip()]


class FormulaMaterial(models.Model):
    """配方用料：某配方用了某原料多少量。"""

    formula = models.ForeignKey(
        TeaFormula,
        verbose_name="配方",
        on_delete=models.CASCADE,
        related_name="formula_materials",
    )
    material = models.ForeignKey(
        Material,
        verbose_name="原料",
        # PROTECT：原料被配方引用时不允许删除，避免用料清单出现空洞
        on_delete=models.PROTECT,
        related_name="formula_materials",
    )
    quantity = models.DecimalField("用量", max_digits=8, decimal_places=2, default=0)
    unit = models.CharField("单位", max_length=10, default="g", help_text="如：g / ml / 个 / 片")
    sort_order = models.PositiveIntegerField("展示顺序", default=0)

    class Meta:
        db_table = "recipes_formula_material"
        verbose_name = "配方用料"
        verbose_name_plural = "配方用料"
        # 移动端按 sort_order 升序渲染用料清单
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(fields=["formula", "sort_order"], name="idx_fm_formula_sort"),
        ]

    def __str__(self) -> str:
        return f"{self.formula.name} - {self.material.name} {self.quantity_display}"

    @property
    def quantity_display(self) -> str:
        """10.00 g -> 10 g，去掉无意义的尾随零。"""
        return f"{self.quantity.normalize():f} {self.unit}".strip()


class FormulaTag(models.Model):
    """配方与标签的多对多中间表（显式建表，便于后续扩展排序、权重等字段）。"""

    formula = models.ForeignKey(
        TeaFormula,
        verbose_name="配方",
        on_delete=models.CASCADE,
        related_name="formula_tags",
    )
    tag = models.ForeignKey(
        Tag,
        verbose_name="标签",
        on_delete=models.CASCADE,
        related_name="formula_tags",
    )

    class Meta:
        db_table = "recipes_formula_tag"
        verbose_name = "配方标签"
        verbose_name_plural = "配方标签"
        ordering = ["tag__name"]
        constraints = [
            models.UniqueConstraint(fields=["formula", "tag"], name="uniq_formula_tag"),
        ]

    def __str__(self) -> str:
        return f"{self.formula.name} - {self.tag.name}"

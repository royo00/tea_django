"""用户收藏：一个用户对一条配方的收藏记录。

表结构：
    id           主键
    user_id      收藏人（FK -> users.User）
    formula_id   被收藏的配方（FK -> recipes.TeaFormula）
    collect_time 收藏时间

约束与索引：
    - (user, formula) 唯一，同一配方不会重复收藏
    - (user, -collect_time) 复合索引，对应「我的收藏」按时间倒序翻页
"""

from django.conf import settings
from django.db import models


class UserCollect(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="collects",
    )
    formula = models.ForeignKey(
        "recipes.TeaFormula",
        verbose_name="配方",
        on_delete=models.CASCADE,
        related_name="collects",
    )
    collect_time = models.DateTimeField("收藏时间", auto_now_add=True)

    class Meta:
        db_table = "collects_user_collect"
        verbose_name = "用户收藏"
        verbose_name_plural = "用户收藏"
        ordering = ["-collect_time", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "formula"], name="uniq_user_formula_collect"),
        ]
        indexes = [
            models.Index(fields=["user", "-collect_time"], name="idx_collect_user_ctime"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.formula_id}"

from django.contrib import admin

from .models import FormulaMaterial, FormulaTag, Material, Tag, TeaFormula


class FormulaMaterialInline(admin.TabularInline):
    model = FormulaMaterial
    extra = 1
    autocomplete_fields = ["material"]
    fields = ("material", "quantity", "unit", "sort_order")
    ordering = ("sort_order",)


class FormulaTagInline(admin.TabularInline):
    model = FormulaTag
    extra = 1
    autocomplete_fields = ["tag"]
    fields = ("tag",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "remark", "create_time")
    list_filter = ("category",)
    search_fields = ("name", "remark")
    ordering = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(TeaFormula)
class TeaFormulaAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "difficulty", "duration", "is_on_shelf", "view_count", "create_time")
    list_filter = ("is_on_shelf", "difficulty")
    search_fields = ("name", "step_content", "formula_materials__material__name")
    list_editable = ("is_on_shelf",)
    readonly_fields = ("view_count", "create_time", "update_time")
    date_hierarchy = "create_time"
    inlines = [FormulaMaterialInline, FormulaTagInline]
    fieldsets = (
        ("基本信息", {"fields": ("name", "cover", "difficulty", "duration", "temperature_desc")}),
        ("内容", {"fields": ("step_content",)}),
        ("运营", {"fields": ("is_on_shelf", "view_count", "create_time", "update_time")}),
    )


@admin.register(FormulaMaterial)
class FormulaMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "formula", "material", "quantity", "unit", "sort_order")
    list_filter = ("unit",)
    search_fields = ("formula__name", "material__name")
    autocomplete_fields = ["formula", "material"]


@admin.register(FormulaTag)
class FormulaTagAdmin(admin.ModelAdmin):
    list_display = ("id", "formula", "tag")
    autocomplete_fields = ["formula", "tag"]

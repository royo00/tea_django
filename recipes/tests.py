"""配方 API 的行为测试：浏览、筛选、搜索、详情浏览量、下架隔离。"""

from django.db.models import ProtectedError
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import FormulaMaterial, FormulaTag, Material, Tag, TeaFormula


class FormulaAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tea = Material.objects.create(name="红茶", category="茶叶")
        cls.milk = Material.objects.create(name="牛奶", category="乳制品")
        cls.sugar = Material.objects.create(name="白砂糖", category="糖类")
        cls.lemon = Material.objects.create(name="柠檬", category="水果")

        cls.tag_milk_tea = Tag.objects.create(name="奶茶")
        cls.tag_fruit = Tag.objects.create(name="果茶")

        # 上架：经典红茶奶茶
        cls.milk_tea = TeaFormula.objects.create(
            name="经典红茶奶茶",
            difficulty=1,
            duration=8,
            temperature_desc="热饮 85℃",
            step_content="1. 将红茶放入茶壶中。\n\n2. 加入 300ml 热水，浸泡 5 分钟。\n3. 过滤茶汤，加入牛奶。",
            is_on_shelf=True,
        )
        FormulaMaterial.objects.create(formula=cls.milk_tea, material=cls.tea, quantity=10, unit="g", sort_order=1)
        FormulaMaterial.objects.create(formula=cls.milk_tea, material=cls.milk, quantity=200, unit="ml", sort_order=2)
        FormulaTag.objects.create(formula=cls.milk_tea, tag=cls.tag_milk_tea)

        # 上架：冰镇柠檬茶
        cls.lemon_tea = TeaFormula.objects.create(
            name="冰镇柠檬茶", difficulty=2, duration=10, is_on_shelf=True,
        )
        FormulaMaterial.objects.create(formula=cls.lemon_tea, material=cls.tea, quantity=8, unit="g", sort_order=1)
        FormulaMaterial.objects.create(formula=cls.lemon_tea, material=cls.lemon, quantity=2, unit="片", sort_order=2)
        FormulaTag.objects.create(formula=cls.lemon_tea, tag=cls.tag_fruit)

        # 未上架：不应出现在任何接口
        cls.off_shelf = TeaFormula.objects.create(name="隐藏红茶特调", difficulty=3, is_on_shelf=False)

    def test_list_only_on_shelf(self):
        resp = self.client.get(reverse("recipes_api:formula_list"))
        self.assertEqual(resp.status_code, 200)
        names = [item["name"] for item in resp.data["results"]]
        self.assertEqual(set(names), {"经典红茶奶茶", "冰镇柠檬茶"})
        self.assertNotIn("隐藏红茶特调", names)

    def test_list_card_fields_and_pagination(self):
        resp = self.client.get(reverse("recipes_api:formula_list"), {"page_size": 1})
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["count"], 2)
        card = resp.data["results"][0]
        for field in ("id", "name", "cover", "difficulty", "tags"):
            self.assertIn(field, card)

    def test_filter_by_tag_name_and_id(self):
        resp = self.client.get(reverse("recipes_api:formula_list"), {"tag": "果茶"})
        self.assertEqual([i["name"] for i in resp.data["results"]], ["冰镇柠檬茶"])

        resp = self.client.get(reverse("recipes_api:formula_list"), {"tag": self.tag_milk_tea.id})
        self.assertEqual([i["name"] for i in resp.data["results"]], ["经典红茶奶茶"])

    def test_search_matches_formula_name_and_material(self):
        # 匹配原料名：两款都用了红茶
        resp = self.client.get(reverse("recipes_api:formula_search"), {"search": "红茶"})
        names = {i["name"] for i in resp.data["results"]}
        self.assertEqual(names, {"经典红茶奶茶", "冰镇柠檬茶"})

        # 匹配配方名
        resp = self.client.get(reverse("recipes_api:formula_search"), {"search": "柠檬"})
        self.assertEqual([i["name"] for i in resp.data["results"]], ["冰镇柠檬茶"])

    def test_search_no_result_returns_empty_list(self):
        resp = self.client.get(reverse("recipes_api:formula_search"), {"search": "咖啡"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(resp.data["results"], [])

    def test_search_does_not_duplicate_rows(self):
        # 两款配方都引用红茶，命中多条关联行时必须 distinct 去重
        resp = self.client.get(reverse("recipes_api:formula_search"), {"search": "红茶"})
        self.assertEqual(resp.data["count"], len(resp.data["results"]))

    def test_detail_increments_view_count(self):
        url = reverse("recipes_api:formula_detail", args=[self.milk_tea.id])
        self.assertEqual(self.client.get(url).data["view_count"], 1)
        self.assertEqual(self.client.get(url).data["view_count"], 2)
        self.milk_tea.refresh_from_db()
        self.assertEqual(self.milk_tea.view_count, 2)

    def test_detail_materials_sorted_and_steps_split(self):
        resp = self.client.get(reverse("recipes_api:formula_detail", args=[self.milk_tea.id]))
        materials = resp.data["materials"]
        self.assertEqual([m["material_name"] for m in materials], ["红茶", "牛奶"])
        self.assertEqual(materials[0]["quantity_display"], "10 g")
        self.assertEqual(len(resp.data["steps"]), 3)  # 空行被丢弃

    def test_off_shelf_detail_404(self):
        resp = self.client.get(reverse("recipes_api:formula_detail", args=[self.off_shelf.id]))
        self.assertEqual(resp.status_code, 404)

    def test_material_protected_from_delete(self):
        with self.assertRaises(ProtectedError):
            self.tea.delete()

    def test_tag_list_excludes_tags_without_on_shelf_formula(self):
        lonely = Tag.objects.create(name="空标签")
        resp = self.client.get(reverse("recipes_api:tag_list"))
        names = {i["name"] for i in resp.data}
        self.assertIn("奶茶", names)
        self.assertNotIn(lonely.name, names)

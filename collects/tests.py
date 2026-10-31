"""收藏 API 行为测试：添加、幂等、列表排序、删除、用户隔离、下架过滤。"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from recipes.models import FormulaMaterial, Material, TeaFormula

from .models import UserCollect

User = get_user_model()


class UserCollectAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="alice", password="pwd-alice-123")
        cls.other = User.objects.create_user(username="bob", password="pwd-bob-123")

        cls.material = Material.objects.create(name="红茶")
        cls.f1 = TeaFormula.objects.create(name="经典红茶奶茶", difficulty=1, is_on_shelf=True)
        cls.f2 = TeaFormula.objects.create(name="冰镇柠檬茶", difficulty=2, is_on_shelf=True)
        cls.f3 = TeaFormula.objects.create(name="原味冷泡绿茶", difficulty=1, is_on_shelf=True)
        cls.off = TeaFormula.objects.create(name="下架配方", difficulty=3, is_on_shelf=False)
        FormulaMaterial.objects.create(formula=cls.f1, material=cls.material, quantity=10, unit="g")

    def setUp(self):
        self.client.force_authenticate(self.user)

    # ---------- 认证 ----------

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("collects_api:collect_list")).status_code, 401)
        self.assertEqual(
            self.client.post(reverse("collects_api:collect_list"), {"formula_id": self.f1.id}).status_code,
            401,
        )

    # ---------- 添加收藏 ----------

    def test_add_collect_returns_201_and_card(self):
        resp = self.client.post(reverse("collects_api:collect_list"), {"formula_id": self.f1.id})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data["created"])
        self.assertEqual(resp.data["collect"]["formula"]["name"], "经典红茶奶茶")
        self.assertEqual(UserCollect.objects.filter(user=self.user).count(), 1)

    def test_add_same_formula_twice_is_idempotent(self):
        url = reverse("collects_api:collect_list")
        self.assertEqual(self.client.post(url, {"formula_id": self.f1.id}).status_code, 201)
        resp = self.client.post(url, {"formula_id": self.f1.id})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["created"])
        self.assertEqual(UserCollect.objects.filter(user=self.user, formula=self.f1).count(), 1)

    def test_add_off_shelf_or_missing_formula_rejected(self):
        url = reverse("collects_api:collect_list")
        resp = self.client.post(url, {"formula_id": self.off.id})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(url, {"formula_id": 999999})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("formula_id", resp.data)

    # ---------- 查看收藏 ----------

    def test_list_only_returns_own_collects(self):
        UserCollect.objects.create(user=self.user, formula=self.f1)
        UserCollect.objects.create(user=self.other, formula=self.f2)
        resp = self.client.get(reverse("collects_api:collect_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["formula"]["name"], "经典红茶奶茶")

    def test_list_default_order_is_latest_first(self):
        base = timezone.now()
        for idx, formula in enumerate([self.f1, self.f2, self.f3]):
            collect = UserCollect.objects.create(user=self.user, formula=formula)
            # auto_now_add 会覆盖传参，这里直接改写时间模拟先后收藏
            UserCollect.objects.filter(pk=collect.pk).update(collect_time=base + timedelta(minutes=idx))

        resp = self.client.get(reverse("collects_api:collect_list"))
        names = [item["formula"]["name"] for item in resp.data["results"]]
        self.assertEqual(names, ["原味冷泡绿茶", "冰镇柠檬茶", "经典红茶奶茶"])

    def test_list_ascending_order(self):
        base = timezone.now()
        for idx, formula in enumerate([self.f1, self.f2, self.f3]):
            collect = UserCollect.objects.create(user=self.user, formula=formula)
            UserCollect.objects.filter(pk=collect.pk).update(collect_time=base + timedelta(minutes=idx))

        resp = self.client.get(reverse("collects_api:collect_list"), {"ordering": "collect_time"})
        names = [item["formula"]["name"] for item in resp.data["results"]]
        self.assertEqual(names, ["经典红茶奶茶", "冰镇柠檬茶", "原味冷泡绿茶"])

    def test_invalid_ordering_falls_back_to_default(self):
        UserCollect.objects.create(user=self.user, formula=self.f1)
        resp = self.client.get(reverse("collects_api:collect_list"), {"ordering": "name; DROP TABLE"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_list_hides_off_shelf_formula(self):
        UserCollect.objects.create(user=self.user, formula=self.f1)
        UserCollect.objects.create(user=self.user, formula=self.off)
        resp = self.client.get(reverse("collects_api:collect_list"))
        self.assertEqual(resp.data["count"], 1)

    def test_status_endpoint(self):
        url = reverse("collects_api:collect_status", args=[self.f2.id])
        self.assertFalse(self.client.get(url).data["collected"])

        UserCollect.objects.create(user=self.user, formula=self.f2)
        data = self.client.get(url).data
        self.assertTrue(data["collected"])
        self.assertEqual(data["collect"]["formula"]["id"], self.f2.id)

    # ---------- 删除收藏 ----------

    def test_delete_collect(self):
        UserCollect.objects.create(user=self.user, formula=self.f1)
        url = reverse("collects_api:collect_delete", args=[self.f1.id])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(UserCollect.objects.filter(user=self.user, formula=self.f1).exists())

    def test_delete_not_collected_returns_404(self):
        url = reverse("collects_api:collect_delete", args=[self.f1.id])
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_cannot_delete_other_users_collect(self):
        UserCollect.objects.create(user=self.other, formula=self.f1)
        url = reverse("collects_api:collect_delete", args=[self.f1.id])
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(UserCollect.objects.filter(user=self.other, formula=self.f1).exists())

    # ---------- 级联 ----------

    def test_formula_delete_cascades_collect(self):
        UserCollect.objects.create(user=self.user, formula=self.f3)
        self.f3.delete()
        self.assertFalse(UserCollect.objects.filter(formula_id=self.f3.id).exists())

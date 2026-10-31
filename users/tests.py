"""users 应用测试：覆盖 API（JWT）、门户（Session）与两者共用的用户模型。"""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

# 1x1 透明 PNG，用于头像上传测试
PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
    b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

MEDIA_ROOT = tempfile.mkdtemp(prefix="tea-test-media-")


def make_png(name="avatar.png"):
    return SimpleUploadedFile(name, PNG_1PX, content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class UserModelTests(TestCase):
    def test_blank_phone_becomes_null(self):
        a = User.objects.create_user("a", password="pw-tea-123456")
        b = User.objects.create_user("b", password="pw-tea-123456")
        self.assertIsNone(a.phone)
        self.assertIsNone(b.phone)  # 多个 NULL 不冲突

    def test_duplicate_phone_rejected(self):
        User.objects.create_user("a", password="pw-tea-123456", phone="13800000001")
        with self.assertRaises(Exception):
            User.objects.create_user("b", password="pw-tea-123456", phone="13800000001")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RegisterAPITests(TestCase):
    url = "/api/users/register/"

    def test_register_success(self):
        resp = self.client.post(self.url, {
            "username": "tea_lover",
            "password": "Tea-pass-2026",
            "password_confirm": "Tea-pass-2026",
            "phone": "13800000002",
            "email": "lover@tea.com",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["phone"], "13800000002")
        self.assertIsNone(resp.json()["avatar"])
        self.assertTrue(User.objects.filter(username="tea_lover").exists())

    def test_register_duplicate_phone(self):
        User.objects.create_user("old", password="Tea-pass-2026", phone="13800000003")
        resp = self.client.post(self.url, {
            "username": "new",
            "password": "Tea-pass-2026",
            "password_confirm": "Tea-pass-2026",
            "phone": "13800000003",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("phone", resp.json())

    def test_register_password_mismatch(self):
        resp = self.client.post(self.url, {
            "username": "mismatch",
            "password": "Tea-pass-2026",
            "password_confirm": "Tea-pass-2027",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_register_weak_password(self):
        resp = self.client.post(self.url, {
            "username": "weak",
            "password": "123456",
            "password_confirm": "123456",
        }, content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("password", resp.json())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class JWTFlowTests(TestCase):
    def setUp(self):
        self.password = "Tea-pass-2026"
        self.user = User.objects.create_user(
            "mobile_user", password=self.password, phone="13800000004", email="m@tea.com"
        )

    def _token(self, account):
        return self.client.post(
            "/api/users/token/",
            {"username": account, "password": self.password},
            content_type="application/json",
        )

    def test_token_by_username(self):
        resp = self._token("mobile_user")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("access", resp.json())
        self.assertIn("refresh", resp.json())

    def test_token_by_phone(self):
        resp = self._token("13800000004")
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_token_wrong_password(self):
        resp = self.client.post(
            "/api/users/token/",
            {"username": "mobile_user", "password": "wrong-pass"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_me_with_bearer(self):
        access = self._token("mobile_user").json()["access"]
        resp = self.client.get("/api/users/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["username"], "mobile_user")

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/users/me/").status_code, 401)

    def test_patch_profile_and_duplicate_phone(self):
        access = self._token("mobile_user").json()["access"]
        auth = {"HTTP_AUTHORIZATION": f"Bearer {access}"}

        other = User.objects.create_user("other", password=self.password, phone="13800000005")
        resp = self.client.patch(
            "/api/users/me/", {"phone": other.phone},
            content_type="application/json", **auth,
        )
        self.assertEqual(resp.status_code, 400)

        resp = self.client.patch(
            "/api/users/me/", {"first_name": "阿茶", "email": "new@tea.com"},
            content_type="application/json", **auth,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "阿茶")
        self.assertEqual(self.user.email, "new@tea.com")

    def test_avatar_upload(self):
        access = self._token("mobile_user").json()["access"]
        resp = self.client.post(
            "/api/users/me/avatar/", {"avatar": make_png()},
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()["avatar"].endswith(".png"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)

    def test_avatar_upload_rejects_text_file(self):
        access = self._token("mobile_user").json()["access"]
        bad = SimpleUploadedFile("x.txt", b"not an image", content_type="text/plain")
        resp = self.client.post(
            "/api/users/me/avatar/", {"avatar": bad},
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(resp.status_code, 400)

    def test_change_password(self):
        access = self._token("mobile_user").json()["access"]
        resp = self.client.post(
            "/api/users/me/password/",
            {"old_password": self.password, "new_password": "New-Tea-2026",
             "new_password_confirm": "New-Tea-2026"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-Tea-2026"))

    def test_refresh_and_blacklist(self):
        tokens = self._token("mobile_user").json()
        resp = self.client.post(
            "/api/users/token/refresh/", {"refresh": tokens["refresh"]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        new_refresh = resp.json()["refresh"]

        resp = self.client.post(
            "/api/users/logout/", {"refresh": new_refresh},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(resp.status_code, 204, resp.content)

        resp = self.client.post(
            "/api/users/token/refresh/", {"refresh": new_refresh},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SessionAPITests(TestCase):
    def setUp(self):
        self.password = "Tea-pass-2026"
        self.user = User.objects.create_user(
            "web_user", password=self.password, phone="13800000006"
        )

    def test_session_login_and_status(self):
        resp = self.client.post(
            "/api/users/session/login/",
            {"username": "13800000006", "password": self.password},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.client.get("/api/users/session/")
        self.assertTrue(resp.json()["authenticated"])
        self.assertEqual(resp.json()["user"]["username"], "web_user")

    def test_session_login_wrong_password(self):
        resp = self.client.post(
            "/api/users/session/login/",
            {"username": "web_user", "password": "nope"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_session_logout(self):
        self.client.post(
            "/api/users/session/login/",
            {"username": "web_user", "password": self.password},
            content_type="application/json",
        )
        resp = self.client.post("/api/users/session/logout/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(self.client.get("/api/users/session/").json()["authenticated"])

    def test_me_via_session(self):
        self.client.force_login(self.user)
        resp = self.client.get("/api/users/me/")
        self.assertEqual(resp.status_code, 200, resp.content)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PortalViewTests(TestCase):
    def setUp(self):
        self.password = "Tea-pass-2026"
        self.user = User.objects.create_user(
            "portal_user", password=self.password, phone="13800000007"
        )

    def test_login_page_renders(self):
        resp = self.client.get(reverse("users:login"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "用户名 / 手机号")

    def test_login_with_phone(self):
        resp = self.client.post(
            reverse("users:login"),
            {"username": "13800000007", "password": self.password},
        )
        self.assertRedirects(resp, reverse("users:profile"))

    def test_login_wrong_password(self):
        resp = self.client.post(
            reverse("users:login"), {"username": "portal_user", "password": "bad"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "请输入一个正确的用户名和密码")

    def test_profile_requires_login(self):
        resp = self.client.get(reverse("users:profile"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("users:login"), resp["Location"])

    def test_profile_update(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("users:profile"), {
            "first_name": "小茶", "last_name": "陈",
            "email": "portal@tea.com", "phone": "13800000007",
        })
        self.assertRedirects(resp, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "小茶")
        self.assertEqual(self.user.email, "portal@tea.com")

    def test_register_page_and_flow(self):
        resp = self.client.get(reverse("users:register"))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(reverse("users:register"), {
            "username": "fresh_user",
            "phone": "13800000008",
            "email": "fresh@tea.com",
            "password1": "Tea-pass-2026",
            "password2": "Tea-pass-2026",
        })
        self.assertRedirects(resp, reverse("users:profile"))
        self.assertTrue(User.objects.filter(username="fresh_user").exists())

    def test_avatar_upload_and_remove(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("users:profile"), {
            "first_name": "", "last_name": "", "email": "", "phone": "13800000007",
            "avatar": make_png(),
        })
        self.assertRedirects(resp, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)

        resp = self.client.post(reverse("users:profile"), {"action": "remove_avatar"})
        self.assertRedirects(resp, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_logout_is_post_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("users:logout")).status_code, 405)
        resp = self.client.post(reverse("users:logout"))
        self.assertEqual(resp.status_code, 302)

    def test_navbar_shows_user_menu(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("index"))
        self.assertContains(resp, "个人中心")
        self.assertContains(resp, "退出登录")


def tearDownModule():
    shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

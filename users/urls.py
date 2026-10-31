"""移动 APP / 前端调用：/api/users/"""

from django.urls import path

from . import api_views

app_name = "users_api"

urlpatterns = [
    # ---- 通用 ----
    path("register/", api_views.RegisterAPIView.as_view(), name="register"),

    # ---- JWT 通道（移动 APP） ----
    path("token/", api_views.JWTCreateView.as_view(), name="token"),
    path("token/refresh/", api_views.JWTRefreshView.as_view(), name="token_refresh"),
    path("logout/", api_views.JWTLogoutView.as_view(), name="logout"),

    # ---- Session 通道（门户网页 AJAX） ----
    path("session/", api_views.SessionStatusAPIView.as_view(), name="session_status"),
    path("session/login/", api_views.SessionLoginAPIView.as_view(), name="session_login"),
    path("session/logout/", api_views.SessionLogoutAPIView.as_view(), name="session_logout"),

    # ---- 当前用户 ----
    path("me/", api_views.MeAPIView.as_view(), name="me"),
    path("me/avatar/", api_views.AvatarUploadAPIView.as_view(), name="me_avatar"),
    path("me/password/", api_views.ChangePasswordAPIView.as_view(), name="me_password"),
]

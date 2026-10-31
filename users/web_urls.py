"""门户网页路由：/users/"""

from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", views.PortalLogoutView.as_view(), name="logout"),
    path("register/", views.register_view, name="register"),
    path("profile/", views.profile_view, name="profile"),
    path("password/change/", views.PortalPasswordChangeView.as_view(), name="password_change"),
]

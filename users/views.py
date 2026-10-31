"""门户网页（Session 认证）的用户视图。移动端 API 见 api_views.py。"""

from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import LoginForm, ProfileForm, RegisterForm


class PortalLoginView(LoginView):
    """Session 登录页；支持 ?next= 回跳，已登录用户直接放行。"""

    template_name = "users/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class PortalLogoutView(LogoutView):
    """登出仅接受 POST（Django 5 默认），由导航栏表单提交。"""

    next_page = reverse_lazy("index")


class PortalPasswordChangeView(PasswordChangeView):
    template_name = "users/password_change.html"
    success_url = reverse_lazy("users:profile")

    def form_valid(self, form):
        messages.success(self.request, "密码已更新")
        return super().form_valid(form)


def register_view(request):
    if request.user.is_authenticated:
        return redirect("users:profile")

    if request.method == "POST":
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            django_login(request, user)
            messages.success(request, f"欢迎加入，{user.username}！")
            return redirect("users:profile")
    else:
        form = RegisterForm()

    return render(request, "users/register.html", {"form": form})


@login_required
def profile_view(request):
    user = request.user

    if request.method == "POST":
        if request.POST.get("action") == "remove_avatar":
            user.avatar.delete(save=True)
            messages.success(request, "头像已移除")
            return redirect("users:profile")

        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "资料已保存")
            return redirect("users:profile")
    else:
        form = ProfileForm(instance=user)

    return render(request, "users/profile.html", {"form": form})

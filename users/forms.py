from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .services import ensure_email_available, ensure_phone_available
from .validators import validate_avatar_file

User = get_user_model()


class LoginForm(AuthenticationForm):
    """门户登录表单：账号栏同时接受用户名与手机号。"""

    username = forms.CharField(
        label="用户名 / 手机号",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )


class RegisterForm(UserCreationForm):
    """门户注册表单，字段与 API 的 RegisterSerializer 保持一致。"""

    email = forms.EmailField(label="邮箱", required=False)
    phone = forms.CharField(label="手机号", max_length=11, required=False)
    avatar = forms.ImageField(label="头像", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "phone", "email", "avatar")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("该用户名已被占用")
        return username

    def clean_phone(self):
        return ensure_phone_available(self.cleaned_data.get("phone"))

    def clean_email(self):
        return ensure_email_available(self.cleaned_data.get("email"))

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            validate_avatar_file(avatar)
        return avatar


class ProfileForm(forms.ModelForm):
    """个人资料编辑表单。"""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "avatar")
        labels = {
            "first_name": "名",
            "last_name": "姓",
            "email": "邮箱",
            "phone": "手机号",
            "avatar": "头像",
        }

    def clean_phone(self):
        return ensure_phone_available(self.cleaned_data.get("phone"), self.instance)

    def clean_email(self):
        return ensure_email_available(self.cleaned_data.get("email"), self.instance)

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and avatar != self.instance.avatar:
            validate_avatar_file(avatar)
        return avatar

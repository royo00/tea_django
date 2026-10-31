from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class UsernameOrPhoneBackend(ModelBackend):
    """允许「用户名」或「手机号」作为登录账号。

    门户的 Session 登录与 APP 的 JWT 登录都经由 django.contrib.auth.authenticate，
    所以只需要一个后端，两条通道就同时支持手机号登录。
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        user = self._get_user(username)
        if user is None:
            # 仍然跑一次哈希运算，避免通过响应时间探测账号是否存在
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    @staticmethod
    def _get_user(username):
        try:
            return UserModel._default_manager.get(username=username)
        except UserModel.DoesNotExist:
            pass
        try:
            return UserModel._default_manager.get(phone=username)
        except (UserModel.DoesNotExist, ValueError):
            return None

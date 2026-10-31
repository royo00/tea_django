"""移动 APP / 前端调用的 REST API 视图（JWT + Session 双通道）。"""

from django.contrib.auth import login as django_login, logout as django_logout
from django.contrib.auth import update_session_auth_hash
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)


def _user_payload(user, request):
    return UserSerializer(user, context={"request": request}).data


class RegisterAPIView(APIView):
    """POST /api/users/register/  注册（APP 与门户通用）"""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_user_payload(user, request), status=status.HTTP_201_CREATED)


class JWTCreateView(TokenObtainPairView):
    """POST /api/users/token/  账号（用户名或手机号）+ 密码换 access/refresh"""

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class JWTRefreshView(TokenRefreshView):
    """POST /api/users/token/refresh/  刷新 access token"""

    permission_classes = [AllowAny]


class JWTLogoutView(APIView):
    """POST /api/users/logout/  把 refresh token 加入黑名单（需已登录）"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "缺少 refresh 字段"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response({"detail": "refresh token 无效或已失效"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionLoginAPIView(APIView):
    """POST /api/users/session/login/  门户 AJAX 登录，写入 Session Cookie"""

    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth import authenticate

        username = request.data.get("username") or request.data.get("phone")
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "请提供账号和密码"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "账号或密码错误"}, status=status.HTTP_400_BAD_REQUEST)

        django_login(request, user)
        return Response(_user_payload(user, request))


class SessionLogoutAPIView(APIView):
    """POST /api/users/session/logout/  清空 Session"""

    permission_classes = [AllowAny]

    def post(self, request):
        django_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionStatusAPIView(APIView):
    """GET /api/users/session/  查询当前 Session 状态，未登录返回 authenticated=False"""

    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"authenticated": False, "user": None})
        return Response({"authenticated": True, "user": _user_payload(request.user, request)})


class MeAPIView(APIView):
    """GET / PATCH /api/users/me/  读取与更新当前用户资料（Session 或 Bearer 均可）"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_payload(request.user, request))

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            instance=request.user, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_user_payload(user, request))

    def put(self, request):
        return self.patch(request)


class AvatarUploadAPIView(APIView):
    """POST /api/users/me/avatar/  multipart 上传头像，字段名 avatar"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .utils import replace_avatar

        file = request.FILES.get("avatar")
        if file is None:
            return Response({"detail": "请使用 avatar 字段上传图片"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ProfileUpdateSerializer(instance=request.user, data={"avatar": file}, partial=True)
        serializer.is_valid(raise_exception=True)
        replace_avatar(request.user, serializer.validated_data["avatar"])
        return Response(_user_payload(request.user, request))

    def delete(self, request):
        request.user.avatar.delete(save=True)
        return Response(_user_payload(request.user, request))


class ChangePasswordAPIView(APIView):
    """POST /api/users/me/password/  修改密码；门户用户改完保持登录态"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        # 仅 Session 通道需要续期，否则会为纯 JWT 用户凭空创建 session 记录
        if isinstance(request.successful_authenticator, SessionAuthentication):
            update_session_auth_hash(request, user)
        return Response({"detail": "密码修改成功"})

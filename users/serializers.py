from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import phone_validator
from .services import ensure_email_available, ensure_phone_available
from .validators import validate_avatar_file

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """用户只读信息，avatar 由 DRF 自动拼接成绝对地址（需传 request 上下文）。"""

    avatar = serializers.ImageField(read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "phone",
            "email",
            "avatar",
            "display_name",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        )
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    phone = serializers.CharField(
        max_length=11, required=False, allow_blank=True, allow_null=True,
        validators=[phone_validator],
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    avatar = serializers.ImageField(required=False, allow_null=True)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("该用户名已被占用")
        return value

    def validate_phone(self, value):
        return ensure_phone_available(value)

    def validate_email(self, value):
        return ensure_email_available(value)

    def validate_avatar(self, value):
        validate_avatar_file(value)
        return value

    def validate_password(self, value):
        # 字段级校验，错误会挂在 password 上，方便 APP 端直接定位
        probe = User(
            username=self.initial_data.get("username") or "",
            email=self.initial_data.get("email") or "",
        )
        try:
            validate_password(value, user=probe)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "两次输入的密码不一致"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class ProfileUpdateSerializer(serializers.Serializer):
    """个人资料更新，字段全部可选，只更新传了的字段。"""

    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(
        max_length=11, required=False, allow_blank=True, allow_null=True,
        validators=[phone_validator],
    )
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    avatar = serializers.ImageField(required=False, allow_null=True)

    def validate_phone(self, value):
        return ensure_phone_available(value, self.instance)

    def validate_email(self, value):
        return ensure_email_available(value, self.instance)

    def validate_avatar(self, value):
        validate_avatar_file(value)
        return value

    def update(self, instance, validated_data):
        from .utils import replace_avatar

        if "avatar" in validated_data:
            replace_avatar(instance, validated_data.pop("avatar"))
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if validated_data:
            instance.save(update_fields=list(validated_data.keys()))
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("原密码不正确")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "两次输入的新密码不一致"})
        if attrs["new_password"] == attrs["old_password"]:
            raise serializers.ValidationError({"new_password": "新密码不能与原密码相同"})
        validate_password(attrs["new_password"], user=self.context["request"].user)
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """在 token 里带上常用资料，APP 端解析后可直接渲染用户信息。"""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["phone"] = user.phone or ""
        token["avatar"] = user.avatar_url
        return token

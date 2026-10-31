"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('home/', include('home.urls')),
    # 门户网页：Session 认证的登录 / 注册 / 个人中心
    path('users/', include('users.web_urls')),
    # 移动 APP / 前端：JWT 认证的 REST API
    path('api/users/', include('users.urls')),
    path('api/recipes/', include('recipes.urls')),
    path('api/collects/', include('collects.urls')),
]

if settings.DEBUG:
    # 开发环境由 Django 直接提供用户上传文件（头像），生产环境交给 Nginx
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

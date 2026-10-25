from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('apps.accounts.api.urls')),
    path('api/schedule/', include('apps.schedule.api.urls')),
    path('api/classes/', include('apps.classes.api.urls')),
]

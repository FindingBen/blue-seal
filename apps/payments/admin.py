from django.contrib import admin
from .models import ClassPackage, PaymentOrder, WebhookEvent

admin.site.register(ClassPackage)
admin.site.register(PaymentOrder)
admin.site.register(WebhookEvent)

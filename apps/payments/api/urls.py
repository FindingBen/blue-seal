from django.urls import path

from .views import ClassPackageView, StripeCheckoutPurchaseView, stripe_webhook

urlpatterns = [
    path("packages/", ClassPackageView.as_view(), name="class-packages"),
    path("checkout/", StripeCheckoutPurchaseView.as_view(), name="stripe-checkout"),
    path("webhook/", stripe_webhook, name="stripe-webhook"),
]
import hashlib
import json
import logging

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.service import PaymentOrderService

logger = logging.getLogger(__name__)


class StripeCheckoutPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        package_id = request.data.get("package_id")
        if not package_id:
            return Response(
                {"error": "package_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            checkout = PaymentOrderService.create_checkout_session(
                user=request.user,
                package_id=package_id,
            )
        except ValidationError as exc:
            return Response(
                {"error": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.StripeError:
            logger.exception("Stripe could not create a Checkout Session.")
            return Response(
                {"error": "Unable to start checkout. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(checkout, status=status.HTTP_201_CREATED)

class ClassPackageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        packages = PaymentOrderService.list_active_packages()
        return Response(
            [
                {
                    "package_id": str(package.package_id),
                    "name": package.name,
                    "class_count": package.class_count,
                    "price": str(package.price),
                    "currency": package.currency,
                }
                for package in packages
            ],
            status=status.HTTP_200_OK,
        )

@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE")
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured.")
        return HttpResponse(status=500)
    try:
        stripe_event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
        event = json.loads(payload)
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)

    try:
        PaymentOrderService.handle_stripe_webhook(
            event=event,
            payload=event,
            payload_hash=hashlib.sha256(payload).hexdigest(),
        )
    except ValidationError:
        logger.exception("Stripe webhook could not be matched to a payment order.")
        return HttpResponse(status=500)
    except Exception:
        logger.exception("Stripe webhook processing failed for event %s.", stripe_event["id"])
        return HttpResponse(status=500)

    return HttpResponse(status=200)

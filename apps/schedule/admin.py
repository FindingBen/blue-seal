from django.contrib import admin
from .models import Schedule
from .service import ScheduleService


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        is_new = obj._state.adding
        super().save_model(request, obj, form, change)

        if is_new and obj.activity_type == "unavailable":
            ScheduleService.apply_unavailability(obj)
from django.contrib import admin
from .models import Classes, Contents, YjsContent, Notebook

# Register your models here.
admin.site.register(Classes)
admin.site.register(Contents)
admin.site.register(YjsContent)
admin.site.register(Notebook)
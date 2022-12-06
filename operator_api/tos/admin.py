from django.contrib import admin
from .models import TOSConfig, TOSSignature


admin.site.register(TOSConfig)
admin.site.register(TOSSignature)

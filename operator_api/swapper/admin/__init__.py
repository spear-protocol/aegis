from django.contrib import admin
from swapper.models import Swap
from swapper.admin.swap import SwapAdmin


admin.site.register(Swap, SwapAdmin)

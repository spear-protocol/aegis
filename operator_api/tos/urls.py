from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.TOSSignatureView.as_view(), name='sign-tos'),
    url(r'^latest$', views.TOSConfigView.as_view(), name='get-tos'),
]

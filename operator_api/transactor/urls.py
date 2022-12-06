from django.conf.urls import url
from django.urls import path

from . import views


urlpatterns = [
    url(r'^$', views.TransferView.as_view(), name='transfer-endpoint'),
    path("delegated_withdrawal", views.delegated_withdrawal, name="delegated-withdrawal-endpoint"),
]

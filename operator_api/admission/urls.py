from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.WalletView.as_view(), name='admission-endpoint'),
    url(r'^bulk/?$', views.BulkWalletView.as_view(),
        name='bulk-admission-endpoint'),
]

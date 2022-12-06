from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.SLATokenView.as_view(), name='sla-token'),
    url(r'^(?P<wallet>[a-zA-Z0-9]+)$', views.SLAView.as_view(), name='sla'),
]

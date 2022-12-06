from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^$', views.SwapView.as_view(), name='swap-endpoint'),
    url(r'^(?P<pk>[0-9]+)/finalize', views.FinalizeSwapView.as_view(),
        name='finalize-swap-endpoint'),
    url(r'^(?P<pk>[0-9]+)/freeze', views.FreezeSwapView.as_view(),
        name='freeze-swap-endpoint'),
    url(r'^(?P<pk>[0-9]+)/cancel$',
        views.CancelSwapView.as_view(), name='cancel-swap-endpoint'),
]

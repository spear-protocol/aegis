from django.conf.urls import url, include
from django.conf import settings
from django.contrib import admin
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from synchronizer.docs import websocket_docs

api_info = openapi.Info(
    title="NOCUST OPERATOR API",
    description=websocket_docs,
    default_version='v1',
)

schema_view = get_schema_view(
    api_info,
    public=True,
    permission_classes=(permissions.AllowAny,),
)


urlpatterns = [
    url(r'^admin-0xMVP-teaser/', admin.site.urls),
    url(r'^admission/', include('admission.urls')),
    url(r'^audit/', include('auditor.urls')),
    url(r'^transfer/', include('transactor.urls')),
    url(r'^swap/', include('swapper.urls')),
    url(r'^analytics/', include('analytics.urls')),
    url(r'^sla/', include('leveller.urls')),
    url(r'^tos/', include('tos.urls')),
    url(r'^swagger/$', schema_view.with_ui('swagger',
                                           cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc',
                                         cache_timeout=0), name='schema-redoc'),
]

if settings.ENABLE_PROFILING:
    urlpatterns += [url(r'^silk/', include('silk.urls', namespace='silk'))]

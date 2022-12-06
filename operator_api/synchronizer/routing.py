from django.conf.urls import url

from .consumers.async_websocket_consumer import AsyncWebsocketConsumer

websocket_urlpatterns = [
    url(r'^ws/?$', AsyncWebsocketConsumer),
]

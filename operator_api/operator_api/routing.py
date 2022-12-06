from channels.routing import ProtocolTypeRouter, URLRouter
import synchronizer.routing

application = ProtocolTypeRouter({
    'websocket':
        URLRouter(
            synchronizer.routing.websocket_urlpatterns
        ),
})

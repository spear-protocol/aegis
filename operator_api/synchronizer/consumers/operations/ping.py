from synchronizer.utils import send_response

# ping-pong operation


async def ping(channel_layer, channel_name, args, operation, consumer):
    await send_response(channel_name, resource="ping", data="pong")

import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer as AWConsumer
from .operations import OPERATIONS
from synchronizer.utils import send_error, check_structure
from operator_api.celery import operator_celery


class AsyncWebsocketConsumer(AWConsumer):
    # used to cache subscription groups
    group_names = set()
    subscription_limit = 100

    # on websocket client connect
    async def connect(self):
        # accept connection
        await self.accept()

    # on websocket client disconnect
    async def disconnect(self, close_code):
        # unsubscribe client from all groups of interest
        await OPERATIONS["unsubscribe"](
            channel_layer=self.channel_layer,
            channel_name=self.channel_name,
            args={
                "streams": ["*"]
            },
            operation={},
            consumer=self
        )
        # close connection
        await self.close()

    # receive json from websocket client
    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            await send_error(
                self.channel_name,
                'No text data provided.',
            )
            return

        try:
            content = json.loads(text_data)
        except ValueError:
            await send_error(
                self.channel_name,
                'Invalid JSON format.',
                cause=text_data
            )
            return

        # make sure "op" and "args" are present
        if check_structure({"op": str, "args": dict}, content):
            # check if operation exists in operations' list
            if content.get("op") in OPERATIONS:
                # call operation
                await OPERATIONS[content.get("op")](
                    channel_layer=self.channel_layer,
                    channel_name=self.channel_name,
                    args=content.get("args"),
                    operation=content,
                    consumer=self,
                )
        else:
            await send_error(
                self.channel_name,
                'Invalid or missing fields, expecting { "op": string, "args": dictionary }.',
                cause=content
            )

    # forward message back to websocket client

    async def ws_forward(self, event):
        # extract message data
        message = event['message']

        # forward message to client
        await self.send(text_data=json.dumps(message))

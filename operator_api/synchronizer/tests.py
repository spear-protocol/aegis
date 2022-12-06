import pytest
from channels.testing import WebsocketCommunicator
from operator_api.routing import application
from .utils import send_notification_async


@pytest.mark.asyncio
async def test_consumer_connect():
    communicator = WebsocketCommunicator(application, '/ws/')
    connected, subprotocol = await communicator.connect()
    assert connected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_consumer_subscribe_success():
    communicator = WebsocketCommunicator(application, '/ws/')
    connected, subprotocol = await communicator.connect()
    assert connected
    request = {
        'op': 'subscribe',
        'args': {
            'streams': ['wallet/9561C133DD8580860B6b7E504bC5Aa500f0f06a7/3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9', 'wallet/9561C133DD8580860B6b7E504bC5Aa500f0f06a7/1dF62f291b2E969fB0849d99D9Ce41e2F137006e']
        }
    }
    await communicator.send_json_to(request)
    response = await communicator.receive_json_from()

    expected = {
        'type': 'response',
        'data': {
            'type': 'subscribe',
            'data': {
                'streams': ['wallet/9561C133DD8580860B6b7E504bC5Aa500f0f06a7/3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9', 'wallet/9561C133DD8580860B6b7E504bC5Aa500f0f06a7/1dF62f291b2E969fB0849d99D9Ce41e2F137006e']
            }
        }
    }
    assert response == expected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_consumer_subscribe_fail_malformed_json():
    communicator = WebsocketCommunicator(application, '/ws/')
    connected, subprotocol = await communicator.connect()
    assert connected
    await communicator.send_to(text_data='random')
    response = await communicator.receive_json_from()

    expected = {
        "type": "error",
        "data": {
            "message": "Invalid JSON format.",
            "cause": "random"
        }
    }
    assert response == expected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_consumer_subscribe_fail_invalid_action_missing():
    communicator = WebsocketCommunicator(application, '/ws/')
    connected, subprotocol = await communicator.connect()
    assert connected
    await communicator.send_json_to({'random': 10})
    response = await communicator.receive_json_from()

    expected = {
        "type": "error",
        "data": {
            "message": 'Invalid or missing fields, expecting { "op": string, "args": dictionary }.',
            "cause": {'random': 10}
        }
    }
    assert response == expected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_consumer_subscribe_fail_invalid_wallets_missing():
    communicator = WebsocketCommunicator(application, '/ws/')
    connected, subprotocol = await communicator.connect()
    assert connected
    request = {
        'op': 'subscribe',
        'args': {}
    }
    await communicator.send_json_to(request)
    response = await communicator.receive_json_from()
    expected = {
        "type": "error",
        "data": {
            "message": 'Missing arg array "streams".',
            "cause": request
        }
    }
    assert response == expected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_consumer_subscribe_fail_invalid_wallets_wrong():
    communicator = WebsocketCommunicator(application, '/ws/')
    connected, subprotocol = await communicator.connect()
    assert connected
    request = {
        'op': 'subscribe',
        'args': {
            'streams': ['f291b2E969fB0849d99D9Ce41e2F137006e']
        }
    }
    await communicator.send_json_to(request)
    response = await communicator.receive_json_from()
    expected = {
        "type": "error",
        "data": {
            "message": 'Invalid value found in "streams", f291b2E969fB0849d99D9Ce41e2F137006e.',
            "cause": request
        }
    }
    assert response == expected
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_consumer_receive_success():
    communicator = WebsocketCommunicator(application, '/ws/')
    connected, subprotocol = await communicator.connect()
    assert connected
    request = {
        'op': 'subscribe',
        'args': {
            'streams': ['wallet/9561C133DD8580860B6b7E504bC5Aa500f0f06a7/3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9', 'wallet/9561C133DD8580860B6b7E504bC5Aa500f0f06a7/1dF62f291b2E969fB0849d99D9Ce41e2F137006e']
        }
    }
    await communicator.send_json_to(request)
    await communicator.receive_json_from()

    await send_notification_async(
        stream_prefix='wallet',
        stream_id='9561C133DD8580860B6b7E504bC5Aa500f0f06a7/3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9',
        event_name='event_1',
        data='canary'
    )

    response = await communicator.receive_json_from()

    assert response['type'] == 'notification'
    assert response['data']['type'] == 'wallet/9561C133DD8580860B6b7E504bC5Aa500f0f06a7/3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9'
    assert response['data']['data']['type'] == 'event_1'
    assert response['data']['data']['data'] == 'canary'
    await communicator.disconnect()

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import re
import json
import logging

logger = logging.getLogger(__name__)

# set of message types to be used when invoking send_notification
# important for client to demultiplex messages
TRANSFER_CONFIRMATION = 'TRANSFER_CONFIRMATION'
SWAP_CONFIRMATION = 'SWAP_CONFIRMATION'
SWAP_CANCELLATION = 'SWAP_CANCELLATION'
SWAP_FINALIZATION = 'SWAP_FINALIZATION'
INCOMING_SWAP = 'INCOMING_SWAP'
MATCHED_SWAP = 'MATCHED_SWAP'
CANCELLED_SWAP = 'CANCELLED_SWAP'
REGISTERED_WALLET = 'REGISTERED_WALLET'
CONFIRMED_DEPOSIT = 'CONFIRMED_DEPOSIT'
REQUESTED_WITHDRAWAL = 'REQUESTED_WITHDRAWAL'
CONFIRMED_WITHDRAWAL = 'CONFIRMED_WITHDRAWAL'
CHECKPOINT_CREATED = 'CHECKPOINT_CREATED'

# subscription stream types and formats
STREAM_TYPES = {
    'wallet': re.compile(r'^[a-f0-9]{40}\/[a-f0-9]{40}$'),
    'tokenpair': re.compile(r'^[a-f0-9]{40}\/[a-f0-9]{40}$'),
}

# allowed group names
group_regex = re.compile('^[a-zA-Z0-9-.]+$')

channel_layer = get_channel_layer()


def check_structure(struct, conf):
    if isinstance(struct, dict) and isinstance(conf, dict):
        # struct is a dict of types or other dicts
        return all(k in conf and check_structure(struct[k], conf[k]) for k in struct)
    if isinstance(struct, list) and isinstance(conf, list):
        # struct is list in the form [type or dict]
        return all(check_structure(struct[0], c) for c in conf)
    elif isinstance(struct, type):
        # struct is the type of conf
        return isinstance(conf, struct)
    elif isinstance(struct, tuple) and isinstance(struct[0], type):
        # struct is the type of conf
        return isinstance(conf, struct[0]) and re.compile(struct[1]).match(conf.lower())
    else:
        # struct is neither a dict, nor list, not type
        return False


# check if stream is valid
# returns group name of that stream
def is_valid_stream(name):
    parts = name.split('/', 1)

    if len(parts) < 2:
        return False

    stream_type, stream_id = parts[0].lower(), parts[1].lower()

    if stream_type not in STREAM_TYPES:
        return False

    if not STREAM_TYPES.get(stream_type).match(stream_id):
        return False

    stream_id = stream_id.replace("/", ".")

    if not group_regex.match(stream_type) or not group_regex.match(stream_id):
        return False

    return '{}.{}'.format(stream_type, stream_id)


# send websocket notification
async def send_notification_async(stream_prefix, stream_id, event_name, data):
    stream_name = '{}/{}'.format(stream_prefix, stream_id)
    group_name = is_valid_stream(stream_name)

    message = {
        'type': 'notification',
        'data': {
            'type': stream_name,
            'data': {
                'type': event_name,
                'data': data
            }
        }
    }

    # if failed for some reason, log error to aid debugging
    try:
        await channel_layer.group_send(
            group_name,
            {
                'type': 'ws.forward',
                'message': message
            }
        )
    except Exception as e:
        logger.warning('failed to send notification, {}'.format(e))


def send_notification(stream_prefix, stream_id, event_name, data):
    async_to_sync(send_notification_async)(
        stream_prefix, stream_id, event_name, data)


# send websocket response
async def send_response(channel_name, resource, data):
    message = {
        'type': 'response',
        'data': {
            'type': resource,
            'data': data
        }
    }

    # if failed for some reason, log error to aid debugging
    try:
        await channel_layer.send(
            channel_name,
            {
                'type': 'ws.forward',
                'message': message
            }
        )
    except Exception as e:
        logger.warning('failed to send response, {}'.format(e))


# send websocket error
async def send_error(channel_name, error, cause=None):
    message = {
        'type': 'error',
        'data': {
            'message': error,
            'cause': cause
        }
    }

    # if failed for some reason, log error to aid debugging
    try:
        await channel_layer.send(
            channel_name,
            {
                'type': 'ws.forward',
                'message': message
            }
        )
    except Exception as e:
        logger.warning('failed to send error, {}'.format(e))

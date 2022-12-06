from synchronizer.utils import send_response, send_error, is_valid_stream
import re

# subscribe to a stream


async def subscribe(channel_layer, channel_name, args, operation, consumer):
    # if input does not include a stream array return an error message
    if 'streams' not in args and not isinstance(args.get('streams'), list):
        await send_error(channel_name, 'Missing arg array "streams".', cause=operation)
        return

    # if subscription limit exceeded, return an error message
    if len(args.get('streams')) + len(consumer.group_names) > consumer.subscription_limit:
        await send_error(channel_name, 'Invalid susbcription list is too long, more than {}.'.format(consumer.subscription_limit), cause=operation)
        return

    subscribed_streams = []

    for stream in args.get('streams'):
        # if stream input is valid
        # return stream name converted into channel's group name
        group_name = is_valid_stream(stream)
        if group_name:
            # add stream to this channel's subscription list
            await channel_layer.group_add(
                group_name,
                channel_name
            )
            # build up list to return success response
            subscribed_streams.append(stream)
            # cache group name to remove on disconnect
            consumer.group_names.add(group_name)
        else:
            await send_error(channel_name, 'Invalid value found in "streams", {}.'.format(stream), cause=operation)

    await send_response(
        channel_name,
        resource="subscribe",
        data={
            'streams': subscribed_streams
        }
    )


async def unsubscribe(channel_layer, channel_name, args, operation, consumer):
    # if input does not include a stream array return an error message
    if 'streams' not in args and not isinstance(args.get('streams'), list):
        await send_error(channel_name, 'Missing arg "streams"', cause=operation)

    unsubscribed_streams = []
    for stream in args.get('streams'):
        # if stream is wildcard
        if stream == '*':
            # discard all groups in group cache
            group_names = [g for g in consumer.group_names]
            for group_name in group_names:
                await channel_layer.group_discard(
                    group_name,
                    channel_name
                )
            # build up list to return success response
            unsubscribed_streams = ["*"]
            # remove all cached group names
            consumer.group_names.clear()
            break
        else:
            # if stream input is valid
            # return stream name converted into channel's group name
            group_name = is_valid_stream(stream)
            if group_name:
                await channel_layer.group_discard(
                    group_name,
                    channel_name
                )
                # build up list to return success response
                unsubscribed_streams.append(stream)
                # remove cached group name
                consumer.group_names.remove(group_name)
            else:
                await send_error(channel_name, 'Invalid value found in "streams", {}.'.format(stream), cause=operation)

    await send_response(
        channel_name,
        resource="unsubscribe",
        data={
            'streams': unsubscribed_streams
        }
    )

from synchronizer.utils import check_structure, send_error
from operator_api.celery import operator_celery

# expected schema for args to op get
args_struct = {
    'resource': str,
    'params': dict
}

# expected schema for parameters of resource wallet_data
wallet_data_struct = {
    'params': {
        'wallet_address': (str, r'^[a-f0-9]{40}$'),
        'token_address': (str, r'^[a-f0-9]{40}$'),
        'eon_number': int
    }
}

# get operation


async def get(channel_layer, channel_name, args, operation, consumer):
    # make sure args follow args_struct schema
    valid_args = check_structure(args_struct, args)

    if valid_args:

        # if requested resource is wallet
        if args.get('resource') == 'wallet':
            # validate params with wallet_data_struct schema
            valid_wallet_data_params = check_structure(
                wallet_data_struct, args)
            if valid_wallet_data_params:
                # dispatch async celery task
                operator_celery.send_task('auditor.tasks.get_wallet_data', args=[
                    channel_name,
                    operation,
                    args.get('params').get('wallet_address'),
                    args.get('params').get('token_address'),
                    args.get('params').get('eon_number'),
                ])
            else:
                await send_error(channel_name, 'Invalid or missing params.', cause=operation)

        # if requested resource is operator
        elif args.get('resource') == 'operator':
            # dispatch async celery task
            operator_celery.send_task('auditor.tasks.get_operator_data', args=[
                channel_name,
                operation,
            ])

        else:
            await send_error(channel_name, 'Resource not found.', cause=operation)

    else:
        await send_error(channel_name, 'Invalid args provided.', cause=operation)

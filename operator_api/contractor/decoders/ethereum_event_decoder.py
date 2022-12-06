from celery.utils.log import get_task_logger
from eth_utils import keccak, encode_hex, decode_hex
from eth_abi import decode_abi


logger = get_task_logger(__name__)


class EthereumEventDecoder:
    events = {}

    def __init__(self, abi):
        events = [event for event in abi if event.get(
            'type').lower() == 'event']
        for event in events:
            types = [param.get(u'type') for param in event.get('inputs')]
            topic = EthereumEventDecoder.topic(event[u'name'], types)
            self.events[topic] = event

    @staticmethod
    def topic(name, types):
        signature = '{}({})'.format(name, ','.join(types))
        return encode_hex(keccak(text=signature))

    def decode(self, log):
        topic = log[u'topics'][0]
        if topic not in self.events:
            logger.error("UNKNOWN EVENT TOPIC: {}\n{}".format(
                topic, self.events))
            return None

        event = self.events.get(topic)

        data_types = [param.get(u'type') for param in event.get(
            'inputs') if not param.get(u'indexed')]
        data = decode_abi(data_types, decode_hex(
            log.get(u'data'))) if log.get(u'data') != '0x0' else []

        decoded_inputs = {}
        data_ctr, topics_ctr = 0, 1
        for param in event.get(u'inputs'):
            if param.get(u'indexed'):
                value = log[u'topics'][topics_ctr]
                topics_ctr += 1
            else:
                value = data[data_ctr]
                data_ctr += 1

            if u'[]' in param.get(u'type'):
                value = list(value)

            decoded_inputs[param.get(u'name')] = value

        return {
            u'name': event.get(u'name'),
            u'data': decoded_inputs,
            u'txid': log[u'transactionHash']
        }

    def decode_many(self, logs):
        result = []
        for log in logs:
            sub_result = self.decode(log)
            if sub_result is not None:
                result.append(sub_result)
        return result

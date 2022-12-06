from .subscribe import (
    subscribe,
    unsubscribe,
)

from .ping import (
    ping,
)

from .get import (
    get,
)


OPERATIONS = {
    'subscribe': subscribe,
    'unsubscribe': unsubscribe,
    'ping': ping,
    'get': get,
}

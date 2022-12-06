websocket_docs = """
# Websocket Notifications

| protocol | url                  |
| -------  | -------              |
| HTTP     | ws://{server}/ws/    |
| HTTPS    | wss://{server}/ws/   |

## Generic Request
```
{
    "op": " < subscribe | unsubscribe | ping > ",
    "args": { < dictionary of arguments > }
}
```

## Generic Response
```
{
    "type": " < notification | response | error > ",
    "data": { < dictionary of data > }
}
```

## Errors
```
{
    "type": "error",
    "data": { 
        "message": " < error message > ",
        "cause": { < request object > }
    }
}
```

## Granular description of other operations

### A. Subscribe/Unsubscribe
* Request
```
{
    "op": " < subscribe | unsubscribe > ",
    "args": {
        "streams": [ 
            "wallet/[a-fA-F0-9]{40}/[a-fA-F0-9]{40}",   <--- (wallet/{token address}/{wallet address})
            "tokenpair/[a-fA-F0-9]{40}/[a-fA-F0-9]{40}",
            ... 
        ]
    }
}
```

* Response (received immediately after request)
```
{
    "type": "response",
    "data": {
        "type": " < subscribe | unsubscribe > ",
        "data": {
            "streams": [ " < added or removed streams > " ],
        }
    }
}
```

* Notification
```
{
    "type": "notification",
    "data": {
        "type": " < stream > ",
        "data": {
            "type": " < event type > ",
            "data": { < model object > }
        }
    }
}
```

### B. Ping
* Request
```
{
    "op": "ping",
    "args": {}
}
```

* Response (received immediately after request)
```
{
    "type": "response",
    "data": {
        "type": "ping",
        "data": "pong"
    }
}
```

## Stream Events and Models

### A. wallet/* streams
| event                 | model                                   | status              | desctiption                                                                      |
| -------               | -------                                 | -------             | -------                                                                          |
| TRANSFER_CONFIRMATION | Transfer                                | active              | transfer was confirmed, this event is triggered for the sender and recipient     |
| SWAP_CONFIRMATION     | Swap                                    | active              | swap was confirmed, this event is triggered for the sender and recipient         |
| SWAP_CANCELLATION     | SwapCancellation                        | active              | swap was cancelled, this event is triggered for the sender and recipient         |
| SWAP_FINALIZATION     | SwapFinalization                        | active              | swap was finalized, this event is triggered for the sender and recipient         |
| MATCHED_SWAP          | Swap                                    | active              | swap was partially or fully matched with another swap                            |
| REGISTERED_WALLET     | Admission                               | active              | wallet's registration request was confirmed by the operator                      |
| CONFIRMED_DEPOSIT     | Deposit                                 | active              | deposit was acknowledged by the operator                                         |
| REQUESTED_WITHDRAWAL  | WithdrawalRequest                       | active              | withdrawal request was acknowledged by the operator                              |
| CONFIRMED_WITHDRAWAL  | Withdrawal                              | active              | withdrawal request was confirmed                                                 |
| CHECKPOINT_CREATED    | WalletState                             | active              | checkpoint was created                                                           |

### B. tokenpair/* streams
| event                 | model                                   | status      | desctiption                           |
| -------               | -------                                 | -------     | -------                               |
| INCOMING_SWAP         | Swap                                    | active      | a new swap order was placed           |
| MATCHED_SWAP          | Swap                                    | active      | a swap was partially or fully matched |
| CANCELLED_SWAP        | SwapCancellation                        | active      | a swap was cancelled                  |


"""

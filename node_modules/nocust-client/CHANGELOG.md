# Changelog

## 3.3.0

- Push based wallet state update
- BREAKING: current cache might have to be wiped first
- Pre-registration function for TEX
- Add get swap history function to tex service
- Bug: fix return values for withdrawals
- Bug: fix address registration check

## 2.1.2

- BUG: throw correct UNREGISTERED_WITH_COMMIT_CHAIN error we needed
- BUG: buy SLA now throws INSUFFICIENT_COMMIT_CHAIN_BALANCE if not enough tokens to pay for the SLA
- BUG: throw INSUFFICIENT_COMMIT_CHAIN_BALANCE if not enough funds to make a commit-chain transaction
- BUG: (critical) Check the the balance of the correct token for withdrawals

## 2.1.1

- BUG: Fix SLA timestamp bug

## 2.1.0

- BUG: Fixed state update challenges bug.It should now work again.
- Throw errors on registration throttling. Error code: `REGISTRATION_THROTTLING`
- BREAKING: Changed the swap functions. Replaced by the new TEX module.
- POTENTIALLY BREAKING:Error handling refactor, throw proper errors with error codes available in `NOCUSTError`.
- POTENTIALLY BREAKING: Commit-chain transfers now return after hub processing (heartbeat) instead just the post request. `sendTransfer` will take slightly longer but following up transfers can be made right after.

## 2.0.3

- Websocket healthcheck
- BUG: On-the-flight registration fix (Hazem)
- Lock on wallet subscription, allow for concurrency of operations

## 2.0.2

- BUG: Registration timeout

## 2.0.1

- BUG: Incoming subscription bug

## 2.0.0

- Version compatible with post renaming PR server. Not backward compatible.

## 1.1.2

- BUG: (Sentry bug: null is not an object (evaluating 't.indexOf')) Issue #121
- BUG: (Sentry bug: undefined is not an object (evaluating 's.recipient.address')) Issue #123

## 1.1.1

- BUG: removed xmlhttprequest

## 1.1.0

- UPDATE TO 1.1.0 IS REQUIRED to be compatible with the hub deployed on 19.03.2019
- More explicit error messages
- BUG: Concurrent registration bug
- BUG: CORS issue on safari and firefox

## 1.0.6

- RENAME: Nocust -> NOCUST
- RENAME: ProofOfStake -> ProofOfExclusiveAllotment
- RENAME: Aggregate -> ActiveState
- RENAME: BalanceMarker -> MinimumAvailableBalanceMarker
- RENAME: Round -> Eon
- RENAME: Hub -> Operator
- RENAME: Paint -> ActiveStateChecksum

## 1.0.5

- BUG: wrong parameter on getOrderBook
- BUG Unsubscribe bug
- Added time in TransaferDataInterface

## 1.0.4

- BUG: Send notification on incoming_confirmation event instead of incoming_transfer.
- BUG: Token filter on registration.

## 1.0.3

- Passive validation bug (Leading to faucet bug)

## 1.0.2

- Passively gained bug
- Adjusted getSupportedToken return values
- Changed incomingTransactionObservable to subscribeToincomingTransaction

## 1.0.1

- reflect-metadata bug

## 1.0.0

- Renamed LQDManager to NOCUSTManager
- Renamed LQDClient to NOCUSTClient
- Remove register function, Event emitter replaced by incoming transfer observable
- Renamed getBlockNumber function to getEonNumber and sub block to Era
- sendTransfer renamed to sendTransaction
- sendTransaction support exclusively passive transfers, doesn't rely on websocket to receive transactions
- Added inline documentation
- Breaking change on getSupportedTokens, it returns now more information
- Breaking, moved swaps and challenges functions to the root of the nocust manager object
- Added incoming transfer event
- Faster and more reliable registration and synchronization.
- No private key required for operation where it is not needed
- Added getTransactionsForAddress function.

## 0.1.7

- Add approveAndDeposit function
- Performance improvements
- SLA functions
- Add support for bn.js and string in addition to BigNumber.js
- More explicit errors

### Bugs

- WebSocket bug of Typescript config in strict mode
- GetEonNumber bug
- Swap test bug
- Get undefined wallet data bug
- Registration timeout extended (3sec => 9sec)
- Proper check for withdrawal request fees
- Eon in withdrawal amount field (Leading to "balance less than expected error")
- hasOUtStanding Challenge missing

## 0.1.6

## 0.1.5

- Initial release

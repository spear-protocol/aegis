#!/usr/bin/env bash

# wait for RPC host
./wait_for_it.sh ${RPC_HOST} --timeout=0 --                                     \
# deploy hub contracts
python /code/deploy_linked.py /code/hub.json ${PRIV_KEY} ${RPC} --publish &&    \
# add slack until previous transactions are mined
sleep ${BLOCK_TIME}s                                                      &&    \
# deploy ERC20 contract
python /code/deploy.py /code/token.bc ${PRIV_KEY} ${RPC} --publish        &&    \
# return 0 if all went well
exit 0                                                                    ||    \
# return 1 if something went wrong
exit 1

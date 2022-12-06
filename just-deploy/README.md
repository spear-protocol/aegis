# just-deploy
NOCUST contract binaries and scripts to deploy all the nocust contracts.

## Deploy a contract
First, we need to configure contract constructor parameters. Go at the bottom of contracts/ethereum-hub-contract-10.json and set the eon block interval in the first parameter and the operator address in second parameter:

```
    "parameters": [
      {
        "type": "uint",
        "value": 8640
      },
      {
        "type": "address",
        "value": "0x8e0381EE8312C692921daA789a9c9EE0C480a946"
      }
    ]
```

Installs the dependencies in `requirements.txt` and use the deploy_linked.py script as follow to deploy the contracts:

```
python deploy_linked.py contracts/ethereum-hub-contract-10.json <PRIVATE KEY WITHOUT 0x> <RPC URL> --publish
```

The first argument is the contract binary, `ethereum-hub-contract-10.json` is the latest version. Omit `--publish` to make a dryrun.

The last contract deployed with the name `__NOCUSTCommitChain_____________________` is the main contract address to specify to `HUB_LQD_CONTRACT_ADDRESS` on the NOCUST server

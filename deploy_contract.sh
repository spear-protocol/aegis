set -e

read -p "Ethereum RPC URL: " rpc_url
read -p "Owner's Address: " owner_addr
read -sp "Owner's Private Key (hidden): " private_key

if [ "$rpc_url" == "" ]; then
      echo 1>&2 "Ethereum RPC URL is missing"
        exit 3
fi
if [ "$owner_addr" == "" ]; then
      echo 1>&2 "Owner's wallet address is missing"
        exit 3
fi
if [ "$private_key" == "" ]; then
      echo 1>&2 "Owner's wallet private key is missing"
        exit 3
fi

cp just-deploy/requirements.txt ./requirements.txt
cp just-deploy/deploy.py ./deploy.py
cp just-deploy/deploy_linked.py ./deploy_linked.py
cp just-deploy/contracts/ethereum-hub-contract-10.json ./contract.json
sed -i "s/0x8e0381EE8312C692921daA789a9c9EE0C480a946/$owner_addr/g" ./contract.json
docker build -t just-deploy -f just-deploy/Dockerfile-deploy .
rm ./contract.json
rm ./deploy.py
rm ./requirements.txt
rm ./deploy_linked.py

docker run -it just-deploy python /code/deploy_linked.py /code/contract.json $private_key $rpc_url --publish


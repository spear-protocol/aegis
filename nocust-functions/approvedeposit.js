const Web3 = require('web3'); // Web3 1.0.0-beta.37 only for now
const BigNumber = require('bignumber.js');
const { nocust } = require('nocust-client');

// Setup web3 with Infura
const web3 = new Web3(
  //new Web3.providers.HttpProvider('https://eth-goerli.g.alchemy.com/v2/5iFUzx90jhomMCuozX_1yJoKBtwDug9k')
  new Web3.providers.HttpProvider('http://192.168.86.33:7545')
);

const BOB_PUB = "0x7f23a4868860C09d5363317db2A87038E069DB27";
const BOB_PRIV = "2dc9d4eaaeb0569da74b67c1185cbe3b023574b0e6c49fdd5877ddd953eb54a9";
//const BOB_PUB = "0x913C8Ac1E214E70ac4002B81d6df9D430B91C291";
//const BOB_PRIV = "2f35f9b7146f7d4ef10a315cd34ab40c15d8b2a9d8021478bcdacfe66f80e993";
//const ALICE_PUB = "0xE5f450EeC0B99C7f3fDBF6698cE7551286c23842";
//const ALICE_PRIV = "576946a34dd205eb9d961d05da2d5ea3d96bfe80888c42eb0ad0c3133bc1cdc5";
//const ALICE_PUB= "0x8CF951Fc5d28f040f16eFbDB0A22c707DA62F0A6";
//const ALICE_PRIV   = "e6f20cbf2691ae55ce741fa48bc1f120a2aa455fe7b0075953f383d5e0166d25";
//const ALICE_PUB = "0xB73959A8D3F49195E5bCca3586B4BFB92487D804";
//const ALICE_PRIV = "942202df9bcfa355cb68a947e625eaaf42bc51c07ba303099195a4b32146d8d4"
//const ALICE_PUB = "0x16619454045Aee797E1cB2ebF7D154f326Cb1067";
//const ALICE_PRIV = "5c104fa9ff5bed26582dfbad24993eb96bcaf78aff38f950e31bdf6945e997d6"
const ALICE_PUB = "0x5A62cA211e892C41a91a520821D5020347DCA1a3";
const ALICE_PRIV = "b4d0f75abd00dde4d05520a6c688c53fc02160fd7f8c95df72df08a180b23f63"


const approveDeposit = async () => {

  // init nocust client
  await nocust.init({
    contractAddress: '0xe263C67c412A374Ea24eC7075C3DdbdC89b1e381',
    rpcUrl: 'http://192.168.86.33:7545',
    operatorUrl: 'http://localhost/'
  });

  await nocust.addPrivateKey(BOB_PRIV);
  console.log("BOB's private key added");

  //const amountVal = 50.00;
  const gasPriceVal = 30;

  const approvalPromise = await nocust.approveDeposits({
    address: BOB_PUB,                      // Account from which to make a deposit (its private key needs to be in the Web3 instance)
    gasPrice: web3.utils.toWei(gasPriceVal.toString(),'gwei'),   // Gas price, 10 Gwei
    token: '0x549BD80b7666e689b8f28FD554a66dC382E2388F',
    gasLimit: 150000                         // Gas Limit
  });
  
  console.log('Approve deposit successful! Transaction ID: ', approvalPromise);
};

approveDeposit();
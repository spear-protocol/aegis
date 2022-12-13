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
const ALICE_PUB= "0x32FDD7Ef1733074F4a5e309c839768EB2FCDc257";
const ALICE_PRIV  = "86d5989331b853d1a017b661e27a8a151a258c908fa9bd685efb1fca3774e8a5";


const getwallet = async () => {

  // init nocust client
  await nocust.init({
    contractAddress: '0xBA89efB1ABAF9FEF31C34E83c3B4683AEED2831D',
    //rpcUrl: 'https://eth-goerli.g.alchemy.com/v2/5iFUzx90jhomMCuozX_1yJoKBtwDug9k',
    rpcUrl: 'http://192.168.86.33:7545',
    operatorUrl: 'http://localhost/'
  });

  // Add BOB & ALICE privatekeys to nocust
  await nocust.addPrivateKey(BOB_PRIV);
  console.log("BOB's private key added");

  const response = await nocust.getWallet(BOB_PUB);
  
  console.log('SyncWallet response: ', response);
};

getwallet();
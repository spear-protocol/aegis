module.exports = {
  networks: {
    development: {
      host: "http://tartarus.spear.technology",
      //host: "https://eth-goerli.g.alchemy.com/v2/5iFUzx90jhomMCuozX_1yJoKBtwDug9k",
      //host: "localhost",
      port: 7545,
      network_id: 1337 // Match any network id
    }/* 
    ropsten: {
      host: "localhost",
      port: 7545,
      network_id: 3
    },
    live: {
      host: "localhost",
      port: 7545,
      network_id: 1
    } */
  },
  compilers: {
   solc: {
     version: "0.4.24"
   }
  },
  solc: {
    optimizer: {
      enabled: true,
      runs: 200
    }
  }
};

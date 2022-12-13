var ERC20TokenImplementation = artifacts.require("ERC20TokenImplementation");

module.exports = async function(deployer, network, accounts) {
  deployer.deploy(ERC20TokenImplementation, {overwrite: false});
};

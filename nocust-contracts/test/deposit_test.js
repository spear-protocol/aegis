const ERC20TokenImplementation = artifacts.require("ERC20TokenImplementation")
const NOCUSTCommitChain = artifacts.require("NOCUSTCommitChain")

const LQD_TOKEN_ADDRESS = "0x549BD80b7666e689b8f28FD554a66dC382E2388F"
const NOCUST_ADDRESS = "0xe263C67c412A374Ea24eC7075C3DdbdC89b1e381"

contract("NOCUSTCommitChain", accounts => {
    let owner = accounts[0]
    let minBalance = web3.utils.toWei('100')
    
    it("Current account is Ganache Account[0]", async () => {
        assert.equal(owner.toString(), '0x5A62cA211e892C41a91a520821D5020347DCA1a3');
    });

    it("Account[0] balance is more than 100", async () => {
        let accountBalance = await web3.eth.getBalance(owner);
        console.log('Account ETHBalance: ', web3.utils.fromWei(accountBalance, 'ether'))
        console.log('Minimum Balance: ', web3.utils.fromWei(minBalance, 'ether'))
        assert(accountBalance >= minBalance);
    });
    

    it("Deposit ETH is working", async () => {
        NOCUSTinstance = await NOCUSTCommitChain.deployed(NOCUST_ADDRESS)
        //console.log(NOCUSTinstance)
        let result = await NOCUSTinstance.deposit.sendTransaction(NOCUSTinstance.address, owner, web3.utils.toWei('1', 'ether'))
        console.log(result.receipt)
    });
    
    
    it("Account[0] LQD balance is more than 100", async () => {
        ERC20instance = await ERC20TokenImplementation.deployed(LQD_TOKEN_ADDRESS)
        LQDBalance = await ERC20instance.balanceOf(owner)
        console.log('Account LQD Balance: ', web3.utils.fromWei(LQDBalance, 'ether'))
        console.log('Minimum Balance: ', web3.utils.fromWei(minBalance, 'ether'))
        assert(LQDBalance >= minBalance);
    });
    /*
    it("LQD is added via RegisterERC20", async () => {
        NOCUSTinstance = await NOCUSTCommitChain.deployed(NOCUST_ADDRESS);
        await NOCUSTinstance.registerERC20(LQD_TOKEN_ADDRESS)
    });
    */

    it("NOCUST contract approved for ERC20 transferFrom", async () => {
        ERC20instance = await ERC20TokenImplementation.deployed(LQD_TOKEN_ADDRESS)
        await ERC20instance.approve(NOCUST_ADDRESS, web3.utils.toWei('1000'))
        const allowance = await ERC20instance.allowance(owner, NOCUST_ADDRESS)
        console.log('Allowance', web3.utils.fromWei(allowance, 'ether'))
    });
    
    it("Deposit LQD is working", async () => {
        NOCUSTinstance = await NOCUSTCommitChain.deployed(NOCUST_ADDRESS);
        ERC20instance = await ERC20TokenImplementation.deployed(LQD_TOKEN_ADDRESS);
        //console.log(ERC20instance)
        let result = await NOCUSTinstance.deposit.sendTransaction(ERC20instance.address, owner, web3.utils.toWei('1', 'ether'));
        console.log(result.receipt)
    });
})
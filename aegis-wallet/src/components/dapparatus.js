import { Component } from 'react'
import cookie from 'react-cookies'
import deepmerge from 'deepmerge'
import Web3 from 'web3'

const queryString = require('query-string')

let interval
const defaultConfig = {}
defaultConfig.DEBUG = false
defaultConfig.POLLINTERVAL = 1777

defaultConfig.requiredNetwork = [
  'Mainnet',
  'Unknown' // allow local RPC for testing
]

const burnMetaAccount = (skipReload) => {
  if (window.localStorage && typeof window.localStorage.setItem === 'function') {
    // window.localStorage.setItem(this.state.account + 'metaPrivateKey', '')
    window.localStorage.setItem('metaPrivateKey', '')
  } else {
    const expires = new Date()
    expires.setDate(expires.getDate() - 1)
    cookie.save('metaPrivateKey', 0, {
      path: '/',
      expires: expires
    })
  }
  if (!skipReload) {
    setTimeout(() => {
      window.location.reload(true)
    }, 300)
  }
}
function translateNetwork (id) {
  const networks = {
    1: 'Mainnet',
    2: 'Morden',
    3: 'Ropsten',
    4: 'Rinkeby',
    5: 'Goerli',
    42: 'Kovan',
    99: 'POA',
    100: 'xDai',
    1337: 'Local',
    5777: 'Ganache'
  }
  return networks[id] || 'Unknown'
}

class Dapparatus extends Component {
  constructor (props) {
    super(props)
    let config = defaultConfig

    if (props.config) {
      config = deepmerge(config, props.config)
      if (props.config.requiredNetwork && props.config.requiredNetwork[0] !== '') {
        config.requiredNetwork = props.config.requiredNetwork
      }
    }

    console.log('!!!!DAPPARATUS~~~~~ ', config)

    this.state = {
      status: 'loading',
      networkId: 0,
      account: false,
      etherscan: '',
      config: config,
      metaAccount: false,
      burnMetaAccount: burnMetaAccount,
      web3Fellback: false
    }
  }

  componentDidUpdate () {
    if (this.props.config) {
      const requiredNetwork = this.props.config.requiredNetwork
      const config = this.state.config
      if (requiredNetwork && requiredNetwork[0] !== '' && config.requiredNetwork !== requiredNetwork) {
        config.requiredNetwork = requiredNetwork
        this.setState({ config: config })
      }
    }
  }

  componentDidMount () {
    interval = setInterval(
      this.checkMetamask.bind(this),
      this.state.config.POLLINTERVAL
    )
    this.checkMetamask()
  }

  componentWillUnmount () {
    clearInterval(interval)
  }

  checkMetamask () {
    if (this.state.config.DEBUG) console.log('DAPPARATUS - checking state...')

    /*
    console.log("CHECK")
    try{
      console.log("GETTING NETWORK ")
      window.web3.version.getNetwork((err,network)=>{
        console.log("GOT")
        console.log(err)
        console.log(network)
      })
    }catch(e){
      console.log("FAILED ")
      console.log(e.toString())
      this.fallBackToInfura()
      return;
    } */

    if (typeof window.web3 === 'undefined' || (typeof window.web3.version === 'undefined' && typeof window.web3.eth === 'undefined') || window.web3.currentProvider.isMetaMask === true) {
      console.log('NO WEB3 YET (or no web3.version / web3.eth)')
      if (this.state.config.DEBUG) console.log('DAPPARATUS - no web3')
      console.log('Connecting to ganache...', this.props.fallbackWeb3Provider)
      window.web3 = new Web3(this.props.fallbackWeb3Provider) // CORS ISSUES!//
      console.log("web3 loaded, reporting as 'fellback'")
      // window.web3 = new Web3(new Web3.providers.WebsocketProvider('wss://rinkeby.infura.io/ws'))
      if (this.state.status === 'loading') {
        this.setState({ web3Fellback: true, status: 'noweb3' }, () => {
          this.props.onUpdate(Object.assign({}, this.state))
        })
      } else if (this.state.status !== 'noweb3') {
        if (this.state.config.DEBUG) console.log('DAPPARATUS - lost web3')
        /// window.location.reload(true);
        this.setState({ web3Fellback: true, status: 'error' }, () => {
          this.props.onUpdate(Object.assign({}, this.state))
        })
      }
    } else {
      if (this.state.config.DEBUG) {
        console.log('DAPPARATUS - yes web 3', window.web3)
      }
      if (typeof window.web3.version === 'undefined' || typeof window.web3.version.getNetwork !== 'function') {
        // console.log("cant use version to get network, trying web3.eth.net ...")
        window.web3.eth.net.getId((err, networkId) => {
          if (this.state.config.DEBUG) console.log('NETWORK GETID', err, networkId)
          this.inspectNetwork(networkId)
        })
      } else {
        window.web3.version.getNetwork((err, networkId) => {
          if (this.state.config.DEBUG) console.log('NETWORK GETNET', err, networkId)
          this.inspectNetwork(networkId)
        })
      }
    }

    const queryParams = queryString.parse(window.location.search)
    let metaPrivateKey
    if (this.props.newPrivateKey) {
      console.log('DAPPARATUS - NEW PRIVATE KEY')
      metaPrivateKey = this.props.newPrivateKey
      if (metaPrivateKey.indexOf('0x') !== 0) {
        metaPrivateKey = '0x' + metaPrivateKey
      }
      // console.log("SAVING HARD CODED PRIVATE KEY",metaPrivateKey)
      if (window.localStorage && typeof window.localStorage.setItem === 'function') {
        window.localStorage.setItem('metaPrivateKey', metaPrivateKey)
      } else {
        const expires = new Date()
        expires.setDate(expires.getDate() + 365)
        cookie.save('metaPrivateKey', metaPrivateKey, {
          path: '/',
          expires
        })
      }
      console.log('Clearing new private key...')
      this.setState({ newPrivateKey: false }, () => {
        // this is clunky, but reload once they enter a pk for now
        window.location = '/'
      })
    } else if (window.localStorage && typeof window.localStorage.setItem === 'function') {
      metaPrivateKey = window.localStorage.getItem('metaPrivateKey')
      if (metaPrivateKey === '0') metaPrivateKey = false
      if (metaPrivateKey && metaPrivateKey.length !== 66) metaPrivateKey = false
    }
    if (!metaPrivateKey) {
      metaPrivateKey = cookie.load('metaPrivateKey')
      // what we need to do is convert someone over to window.localStorage from a cookie too...
      // (we used to use cookies and we upgraded to window.localStorage)
      if (metaPrivateKey && window.localStorage && typeof window.localStorage.setItem === 'function') {
        window.localStorage.setItem('metaPrivateKey', metaPrivateKey)
        // now expire the cookie
        const expires = new Date()
        expires.setDate(expires.getDate() - 1)
        cookie.save('metaPrivateKey', 0, {
          path: '/',
          expires: expires
        })
      }
    }

    let metaAccount
    let account = 0
    if (metaPrivateKey && metaPrivateKey !== '0') {
      const tempweb3 = new Web3()
      metaAccount = tempweb3.eth.accounts.privateKeyToAccount(metaPrivateKey)
      account = metaAccount.address.toLowerCase()
    } else if (queryParams.privateKey) {
      metaPrivateKey = queryParams.privateKey
      if (window.localStorage && typeof window.localStorage.setItem === 'function') {
        window.localStorage.setItem('metaPrivateKey', queryParams.privateKey)
      } else {
        const expires = new Date()
        expires.setDate(expires.getDate() + 365)
        cookie.save('metaPrivateKey', queryParams.privateKey, {
          path: '/',
          expires
        })
      }
      // window.location = window.location.href.split('?')[0];
    }
    if (!this.state.account && account) {
      this.setState({ account, metaAccount }, () => {
        console.log('DAPP ONUPDATE', this.state)
        this.props.onUpdate(Object.assign({}, this.state))
      })
    }
  }

  inspectNetwork (networkId) {
    if (this.state.config.DEBUG) console.log('DAPPARATUS - network', networkId)
    if (this.state.config.DEBUG) console.log('DAPPARATUS - translated network', translateNetwork(networkId))
    try {
      if (this.state.config.DEBUG) console.log('DAPPARATUS - getting accounts...')
      window.web3.eth.getAccounts((err, _accounts) => {
        if (this.state.config.DEBUG) console.log('ACCOUNTS', err, _accounts)
        if (!_accounts || _accounts.length <= 0 || this.state.web3Fellback) {
          if (this.state.config.DEBUG) console.log('DAPPARATUS - no inject accounts - generate? ')
          if (!this.state.metaAccount || !this.state.metaAccount.address) {
            this.setState({ status: 'noaccount' }, () => {
              try {
                let metaPrivateKey
                if (window.localStorage && typeof window.localStorage.setItem === 'function') {
                  metaPrivateKey = window.localStorage.getItem('metaPrivateKey')
                  if (metaPrivateKey === '0') metaPrivateKey = false
                  if (metaPrivateKey && metaPrivateKey.length !== 66) metaPrivateKey = false
                }
                if (!metaPrivateKey) {
                  console.log('Generating account...')
                  const result = window.web3.eth.accounts.create()
                  if (window.localStorage && typeof window.localStorage.setItem === 'function') {
                    window.localStorage.setItem('metaPrivateKey', result.privateKey)
                  } else {
                    const expires = new Date()
                    expires.setDate(expires.getDate() + 365)
                    cookie.save('metaPrivateKey', result.privateKey, {
                      path: '/',
                      expires
                    })
                  }
                  metaPrivateKey = result.privateKey
                } else {
                  console.log('Loaded existing metaPK...')
                }

                const tempweb3 = new Web3()
                const metaAccount = tempweb3.eth.accounts.privateKeyToAccount(metaPrivateKey)
                const account = metaAccount.address.toLowerCase()

                this.setState({ metaAccount: metaAccount, account: account, burnMetaAccount: burnMetaAccount }, () => {
                  this.props.onUpdate(Object.assign({}, this.state))
                })
              } catch (e) {
                console.log(e)
              }
            })
          } else {
            const currentAccounts = []
            // console.log("generated account",this.state.metaAccount)
            currentAccounts.push(this.state.metaAccount.address)
            // console.log("currentAccounts",currentAccounts)
            this.inspectAccounts(currentAccounts, networkId)
          }
          if (this.state.metaAccount) {
            // console.log("metaAccount",this.state.metaAccount)
            this.updateInfo(this.state.metaAccount.address, networkId)
          } else {
            // console.lob("no metaAccount")
          }
        } else {
          if (this.state.config.DEBUG) {
            console.log('DAPPARATUS - injected account: ', _accounts)
          }

          // there is a strange bug where we end up with a meta account and then web3 is injected
          // What I want to do here is clear any window.localStorage if web3 is injected
          // burnMetaAccount(true)

          this.inspectAccounts(_accounts, networkId)
          this.setState({ metaAccount: false })
        }
      })
    } catch (e) {
      console.log(e)
      if (this.state.metamask !== -1) { this.setState({ metamask: -1, networkId: networkId, network: translateNetwork(networkId), web3: window.web3 }) }
    }
  }

  inspectAccounts (currentAccounts, networkId) {
    if (this.state.config.DEBUG) {
      console.log(
        'DAPPARATUS - accounts:',
        currentAccounts,
        this.state.account
      )
    }
    if (currentAccounts && this.state.account) {
      if (currentAccounts.length <= 0) {
        // window.location.reload(true);
        console.log('RELOAD BECAUSE LOST ACCOUNTS?')
      } else if (!this.state.metaAccount && this.state.account !== currentAccounts[0].toLowerCase()) {
        window.location.reload(true)
        console.log('RELOAD BECAUSE DIFFERENT ACCOUNTS?')
      }
    } else {
      this.updateInfo(currentAccounts[0].toLowerCase(), networkId)
    }
  }

  updateInfo (account, networkId) {
    // if (this.state.config.DEBUG) console.log("Adjusted balance",balance)
    let etherscan = 'https://etherscan.io/'
    const network = translateNetwork(networkId)
    if (network !== 'Mainnet') {
      etherscan = 'https://' + network.toLowerCase() + '.etherscan.io/'
    }

    if (this.state.status !== 'ready') {
      const update = {
        status: 'ready',
        networkId: networkId,
        network: network,
        web3Provider: window.web3.currentProvider,
        etherscan: etherscan,
        account: account.toLowerCase(),
        metaAccount: this.state.metaAccount
      }

      this.setState(update, () => {
        this.props.onUpdate(Object.assign({}, this.state))
      })
    }
  }

  render () {
    return null
  }
}
export default Dapparatus

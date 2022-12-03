import React from 'react'
import ReactDOM from 'react-dom'
import 'bootstrap/dist/css/bootstrap.min.css'
import './index.scss'
import Web3 from 'web3'

import App from './App'
import Dapparatus from './components/dapparatus'

import ThemeContext from './contexts/Theme'

require('dotenv').config()

const WEB3_PROVIDER = process.env.REACT_APP_WEB3_PROVIDER

class KeyManager extends React.Component {
  constructor (props) {
    super(props)
    this.state = {}
  }

  setPossibleNewPrivateKey (value) {
    this.setState({ possibleNewPrivateKey: value }, () => {
      this.dealWithPossibleNewPrivateKey()
    })
  }

  async dealWithPossibleNewPrivateKey () {
    // this happens as page load and you need to wait until
    if (this.state) {
      if (this.state.metaAccount && this.state.metaAccount.privateKey.replace('0x', '') === this.state.possibleNewPrivateKey.replace('0x', '')) {
        this.setState({ possibleNewPrivateKey: false })
        // this.changeAlert({
        //   type: 'warning',
        //   message: 'Imported identical private key.'
        // })
      } else {
        console.log('Checking on pk import...')
        console.log('this.state.metaAccount', this.state.metaAccount)

        this.setState({
          possibleNewPrivateKey: false,
          newPrivateKey: this.state.possibleNewPrivateKey
        })
      }
    } else {
      setTimeout(this.dealWithPossibleNewPrivateKey.bind(this), 500)
    }
  }

  render () {
    return (
      <>
        <Dapparatus
          config={{
            DEBUG: false,
            hide: true,
            //requiredNetwork: ['Unknown', 'Rinkeby'],
            requiredNetwork: ['Local', 'Goerli'],
            POLLINTERVAL: 5000 // responsible for slow load times
          }}
          // used to pass a private key into Dapparatus
          newPrivateKey={this.state.newPrivateKey}
          fallbackWeb3Provider={WEB3_PROVIDER}
          onUpdate={async (state) => {
            console.log('Dapparatus update', state)

            if (state.web3Provider) {
              state.web3 = new Web3(state.web3Provider)
              if (state.metaAccount) {
                state.web3.eth.accounts.wallet.add(state.metaAccount.privateKey)
              }

              this.setState(state, () => {
                // console.log("state set:",this.state)
                if (this.state.possibleNewPrivateKey) {
                  this.dealWithPossibleNewPrivateKey()
                }
              })
            }
          }}
        />
        <App
          web3={this.state.web3}
          address={this.state.account}
          privateKey={this.state.metaAccount && this.state.metaAccount.privateKey}
          network={this.state.network}
          networkId={this.state.networkId}
          burnMetaAccount={this.state.burnMetaAccount}
          setPossibleNewPrivateKey={this.setPossibleNewPrivateKey.bind(this)}
        />
      </>

    )
  }
}

ReactDOM.render(
  <ThemeContext>
    <KeyManager />
  </ThemeContext>
  , document.getElementById('root'))

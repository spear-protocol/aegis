import React from 'react'
import cookie from 'react-cookies'
import { CopyToClipboard } from 'react-copy-to-clipboard'
import Blockies from 'react-blockies'
import { scroller } from 'react-scroll'
import i18n from '../i18n'
import AddressBar from './AddressBar'
import AmountBar from './AmountBar'
import { ensLookup, reverseEnsLookup } from '../utils/ens'
import { nocust } from 'nocust-client'
import web3 from 'web3'

const { toWei, fromWei, toBN, isAddress } = require('web3-utils')

function scrollToBottom () {
  console.log('scrolling to bottom')
  scroller.scrollTo('theVeryBottom', {
    duration: 500,
    delay: 30,
    smooth: 'easeInOutCubic'
  })
}

function clearCookies () {
  cookie.remove('sendStartAmount', { path: '/' })
  cookie.remove('sendToAddress', { path: '/' })
}

function canSend (toAddress, amount, balance) {
  console.log('canSend toAddress', toAddress)
  console.log('canSend toAddress', typeof(toAddress))
  console.log('canSend amount', amount)
  console.log('canSend amount', typeof(amount))
  console.log('canSend balance', balance)
  console.log('canSend balance', typeof(balance))
  if (typeof amount !== 'string' || amount === '') return false
  //const amountWei = toBN(toWei(amount, 'ether'))
  const amountWei = web3.utils.toBN(web3.utils.toWei(amount,'ether'))
  return (isAddress(toAddress) &&
          amountWei.gte(web3.utils.toBN('0')) &&
          web3.utils.toBN(web3.utils.toWei(balance.toString())).gte(amountWei))
}

async function attemptSend (address, privateKey, token, offchainBalance, sendTransaction, toAddress, amount) {
  console.log('attemptSend address', address)
  console.log('attemptSend offchainBalance', offchainBalance)
  console.log('attemptSend toAddress', toAddress)
  if (canSend(toAddress, amount, offchainBalance)) {
    const nocustTransfer = async () => {
      await nocust.init({
        contractAddress: process.env.REACT_APP_HUB_CONTRACT_ADDRESS,
        rpcUrl: process.env.REACT_APP_WEB3_PROVIDER,
        operatorUrl: process.env.REACT_APP_HUB_API_URL
      });
      console.log('privateKey', privateKey)
      await nocust.addPrivateKey(privateKey);
      //console.log("Private key added");

      try {
        const txId = await nocust.transfer({
          to: toAddress,
          amount: amount,
          from: address,
          token: token
        });
        return { type: 'success', message: txId }
      } catch (e) {
        return { type: 'danger', message: 'Transaction Failed - Is this account registered with the hub?' }
      }
    }

    nocustTransfer()

  } else if (toBN(offchainBalance.toString(10)).lt(toBN(toWei(amount, 'ether')))) {
    return { type: 'warning', message: 'Not enough funds' }
  } else {
    return { type: 'warning', message: i18n.t('send_to_address.error') }
  }
}

export default class SendToAddress extends React.Component {
  constructor (props) {
    super(props)

    this.state = {
      amount: props.amount || cookie.load('sendStartAmount'),
      toAddress: props.toAddress || cookie.load('sendToAddress'),
      ensName: ''
    }

    this.attemptSend = (toAddress, amount) => attemptSend(this.props.address, this.props.privateKey, this.props.token, this.props.offchainBalance, this.props.sendTransaction, toAddress, amount)
  }

  async updateENSOrAddress (value) {
    if (!(typeof value === 'string' || value instanceof String)) {
      // Something's way off. Start again.
      this.setState({ toAddress: '' })
    } else if (value.indexOf('.eth') >= 0) {
      // Input is an ens domain
      console.log('Attempting to look up ', value)
      const addr = await ensLookup(value)

      console.log('Resolved:', addr)
      if (addr !== '0x0000000000000000000000000000000000000000') {
        this.setState({ toAddress: addr, ensName: value }, () => {
          this.amountInput.focus()
          cookie.save('sendToAddress', value, { path: '/', maxAge: 60 })
        })
      }
    } else if (isAddress(value)) {
      cookie.save('sendToAddress', value, { path: '/', maxAge: 60 })

      const ensName = await reverseEnsLookup(value)
      this.setState({ toAddress: value, ensName }, () => {
        this.amountInput.focus()
        cookie.save('sendToAddress', value, { path: '/', maxAge: 60 })
      })
    } else {
      // Input is incomplete
      this.setState({ toAddress: value }, () => {
        cookie.save('sendToAddress', value, { path: '/', maxAge: 60 })
      })
    }
  }

  componentDidMount () {
    this.updateENSOrAddress(this.state.toAddress)
      .then(() => {
        setTimeout(() => {
          if (!isAddress(this.state.toAddress) && this.addressInput) {
            this.addressInput.focus()
          } else if (!this.state.amount && this.amountInput) {
            this.amountInput.focus()
            scrollToBottom()
          }
        }, 350)
      }
      )
  }

  render () {
    const { amount, toAddress, ensName } = this.state
    const { buttonStyle, offchainBalance, token } = this.props
    const canSendTransaction = canSend(toAddress, amount, offchainBalance)

    return (
      <div>
        <div className='content row'>
          <div className='form-group w-100'>
            <div className='form-group w-100'>
              <label htmlFor='amount_input'>{i18n.t('send_to_address.to_address')}</label>
              <AddressBar
                buttonStyle={buttonStyle}
                toAddress={toAddress}
                setToAddress={(toAddress) => { this.updateENSOrAddress(toAddress) }}
                openScanner
                addressInput={(input) => { this.addressInput = input }}
              />
            </div>
            <div>  {isAddress(toAddress) &&
              <CopyToClipboard text={toAddress.toLowerCase()}>
                <div style={{ cursor: 'pointer' }} onClick={() => this.props.changeAlert({ type: 'success', message: toAddress + ' copied to clipboard' })}>
                  <div style={{ opacity: 0.75 }}>{ensName}</div>
                  <Blockies seed={toAddress.toLowerCase()} scale={10} />
                </div>
              </CopyToClipboard>}
            </div>
            <label htmlFor='amount_input'>{i18n.t('send_to_address.send_amount')}</label>
            <AmountBar
              ref={(input) => { this.amountInput = input }}
              buttonStyle={buttonStyle}
              unit={token ? 'f' + token.shortName : i18n.t('loading')}
              value={amount}
              updateValue={amount => {
                cookie.save('sendStartAmount', amount, { path: '/', maxAge: 60 })
                this.setState({ amount })
              }}
              maxValue={typeof offchainBalance !== 'undefined' ? fromWei(offchainBalance.toString(10), 'ether') : undefined}
              minValue='0'
            />
          </div>
        </div>
        <button
          name='theVeryBottom'
          className={`btn btn-lg w-100 ${canSendTransaction ? '' : 'disabled'}`}
          style={buttonStyle.primary}
          onClick={async () => {
            const { type, message } = await this.attemptSend(toAddress, amount)
            console.log(type, message)
            if (type === 'success') {
              clearCookies()
              this.props.onSend(message)
            } else {
              this.props.changeAlert({ type, message })
            }
          }}
        >
            Send
        </button>
      </div>
    )
  }
}

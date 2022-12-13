import React, { useState } from 'react'
import { Scaler } from 'dapparatus'

import i18n from '../i18n'

import 'react-input-range/lib/css/index.css'

import AmountBar from './AmountBar'
import useWindowDimensions from '../hooks/useWindowDimensions'
const { toWei, fromWei, toBN } = require('web3-utils')

const colStyle = {
  textAlign: 'center',
  whiteSpace: 'nowrap'
}

const Swapper = (props) => {
  const [amount, setAmount] = useState('')
  const { width } = useWindowDimensions()

  let canSwap = false
  try {
    canSwap = toBN(toWei(amount, 'ether')).gt(toBN('0')) && toBN(toWei(amount, 'ether')).lte(toBN(props.maxValue))
  } catch (e) {
    // Do nothing
  }

  return (
    <div className='content ops row'>

      <div className='col-1 p-1' style={colStyle}>
        <i className={`fas ${props.icon}`} />
      </div>
      <div className='col-6 p-1' style={colStyle}>
        <AmountBar
          buttonStyle={props.buttonStyle}
          unit={props.text}
          value={amount}
          updateValue={amount => setAmount(amount)}
          maxValue={typeof props.maxValue !== 'undefined' ? fromWei(props.maxValue.toString(10), 'ether') : undefined}
          minValue='0'
        />
      </div>
      <div className='col-2 p-1' style={colStyle}>
        <button className='btn btn-large w-100' style={props.buttonStyle.secondary} onClick={() => props.cancelAction()}>
          <i className='fas fa-times' /> {(width > 700) && i18n.t('cancel')}
        </button>
      </div>
      <div className='col-3 p-1'>
        <button
          className={`btn btn-large w-100 ${canSwap ? '' : 'disabled'}`} style={props.buttonStyle.primary} onClick={() => {
            return canSwap ? props.successAction(amount) : props.failAction(amount)
          }}
        >
          <Scaler config={{ startZoomAt: 600, origin: '10% 50%' }}>
            <i className={`fas ${props.icon}`} /> Send
          </Scaler>
        </button>

      </div>
    </div>
  )
}

export default class SwapBar extends React.Component {
  constructor (props) {
    super(props)

    this.state = {
      swapMode: false
    }
  }

  render () {
    const { swapMode } = this.state

    let display = i18n.t('loading')

    if (swapMode === 'deposit') {
      display = (
        <Swapper
          icon='fa-arrow-up'
          text={this.props.text}
          buttonStyle={this.props.buttonStyle}
          maxValue={this.props.OnChainBalance}
          successAction={(amount) => {
            this.props.deposit(toWei(amount, 'ether'))
            this.setState({ swapMode: false })
          }}
          failAction={(amount) => {
            if (amount && toBN(toWei(amount, 'ether')).gt(toBN('0'))) {
              return this.props.changeAlert({ type: 'warning', message: i18n.t('bridge.insufficient_funds') })
            } else {
              return this.props.changeAlert({ type: 'warning', message: i18n.t('bridge.zero_withdrawal') })
            }
          }}
          cancelAction={() => {
            this.setState({ swapMode: false })
          }}
        />
      )
    } else if (swapMode === 'withdraw') {
      if (this.props.ethBalance <= 0) {
        display = (
          <div className='content ops row' style={{ textAlign: 'center' }}>
            <div className='col-12 p-1'>
              Error: You must have ETH to withdraw {this.props.text}.
              <button className='btn btn-large' style={{ ...this.props.buttonStyle.secondary, marginLeft: 40 }} onClick={() => { this.setState({ swapMode: false }) }}>
                <i className='fas fa-times' /> dismiss
              </button>
            </div>
          </div>
        )
      } else {
        display = (
          <Swapper
            icon='fa-arrow-down'
            text={this.props.text}
            buttonStyle={this.props.buttonStyle}
            maxValue={this.props.withdrawLimit}
            successAction={(amount) => {
              this.props.requestWithdraw(toWei(amount, 'ether'))
              this.setState({ swapMode: false })
            }}
            failAction={(amount) => {
              if (amount && toBN(toWei(amount, 'ether')).gt(toBN('0'))) {
                this.props.changeAlert({ type: 'warning', message: i18n.t('bridge.exceed_withdrawal_limit') })
              } else {
                this.props.changeAlert({ type: 'warning', message: i18n.t('bridge.zero_withdrawal') })
              }
            }}
            cancelAction={() => {
              this.setState({ swapMode: false })
            }}
          />
        )
      }
    } else {
      display = (
        <div className='content ops row'>

          <div className='col-6 p-1'>
            <button
              className='btn btn-large w-100' style={this.props.buttonStyle.primary} onClick={() => {
                this.setState({ swapMode: 'deposit' })
              }}
            >
              <Scaler config={{ startZoomAt: 400, origin: '50% 50%' }}>
                <i className='fas fa-arrow-up' /> {this.props.text} to f{this.props.text}
              </Scaler>
            </button>
          </div>

          <div className='col-6 p-1'>
            <button
              className='btn btn-large w-100' style={this.props.buttonStyle.primary} onClick={() => {
                this.setState({ swapMode: 'withdraw' })
              }}
            >
              <Scaler config={{ startZoomAt: 400, origin: '50% 50%' }}>
                <i className='fas fa-arrow-down' /> f{this.props.text} to {this.props.text}
              </Scaler>
            </button>
          </div>
        </div>
      )
    }

    return (
      <div className='main-card card w-100'>
        {display}
      </div>
    )
  }
}

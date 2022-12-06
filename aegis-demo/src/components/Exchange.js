import React, { useState, useEffect } from 'react'
import { Scaler } from 'dapparatus'
import Ruler from './Ruler'
import Balance from './Balance'
import AmountBar from './AmountBar'
import i18n from '../i18n'
import { useNocustClient } from '../contexts/Nocust'
import { createNocustManager } from '../services/nocustManager'
import { nocust } from 'nocust-client'

import { useOrderbook } from '../contexts/Orderbook'
import { useTokens } from '../contexts/Tokens'
import { useOffchainAddressBalance } from '../contexts/Balances'
import { useButtonStyle } from '../contexts/Theme'

import useWindowDimensions from '../hooks/useWindowDimensions'
import { getAmountIn, getAmountOut, getMaxOutputs } from '../utils/exchange'

const { toWei, fromWei } = require('web3-utils')

const colStyle = {
  textAlign: 'center',
  whiteSpace: 'nowrap'
}

const rowStyle = {
  display: 'flex',
  flexDirection: 'row',
  flexWrap: 'nowrap',
  alignItems: 'center',
  justifyContent: 'space-between'
}

const flexColStyle = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'stretch',
  justifyContent: 'space-evenly'
}

const TEXSwapper = (props) => {
  const [buyAmount, setBuyAmount] = useState('')
  const [sellAmount, setSellAmount] = useState('')
  const [maxInput, maxOutput] = getMaxOutputs(props.orders, props.assetBalance)

  const { width } = useWindowDimensions()

  const buyAmountBar = (
    <AmountBar
      buttonStyle={props.buttonStyle}
      unit={props.assetBuyText}
      value={buyAmount}
      updateValue={amount => {
        setBuyAmount(amount)
        if (amount && typeof props.orders !== 'undefined') {
          setSellAmount(fromWei(getAmountIn(props.orders, toWei(amount, 'ether')), 'ether'))
        }
      }}
      maxValue={fromWei(maxOutput.toString(10), 'ether')}
      minValue='0'
    />
  )

  const sellAmountBar = (
    <AmountBar
      buttonStyle={props.buttonStyle}
      unit={props.assetSellText}
      value={sellAmount}
      updateValue={amount => {
        setSellAmount(amount)
        if (amount && typeof props.orders !== 'undefined') {
          setBuyAmount(fromWei(getAmountOut(props.orders, toWei(amount, 'ether')), 'ether'))
        }
      }}
      maxValue={fromWei(maxInput.toString(10), 'ether')}
      minValue='0'
    />
  )

  return (
    <div className='content ops row' style={rowStyle}>

      <div className='col-1 p-1' style={colStyle}>
        <i className={`fas ${props.icon}`} />
      </div>
      <div className='col-6 p-1' style={flexColStyle}>
        <div style={{ flexGrow: 1 }}>
          {props.reversed ? buyAmountBar : sellAmountBar}
        </div>
        <div style={{ flexGrow: 1 }}>
          {props.reversed ? sellAmountBar : buyAmountBar}
        </div>
      </div>

      <div className='col-2 p-1' style={colStyle}>
        <button className='btn btn-large w-100' style={props.buttonStyle.secondary} onClick={() => props.cancelAction()}>
          <i className='fas fa-times' /> {(width > 700) && i18n.t('cancel')}
        </button>
      </div>
      <div className='col-3 p-1'>
        <button
          className='btn btn-large w-100' disabled={props.buttonsDisabled} style={props.buttonStyle.primary} onClick={async () => {
            props.successAction(buyAmount, sellAmount)
          }}
        >
          <i className={`fas ${props.icon}`} /> Send
        </button>
      </div>
    </div>
  )
}

const TEXSwapBar = (props) => {
  const [swapMode, setSwapMode] = useState(false)
  const buttonStyle = useButtonStyle()

  //const nocust = useNocustClient()
  useEffect(() => {
    (async () => {
      await createNocustManager(process.env.REACT_APP_WEB3_PROVIDER, process.env.REACT_APP_HUB_CONTRACT_ADDRESS, process.env.REACT_APP_HUB_API_URL)
    })();
    
    return () => {
      // this now gets called when the component unmounts
    };
  }, []);

  const assetABalance = useOffchainAddressBalance(props.address, props.assetA ? props.assetA.tokenAddress : undefined, props.privateKey)
  const assetBBalance = useOffchainAddressBalance(props.address, props.assetB ? props.assetB.tokenAddress : undefined, props.privateKey)
  const ordersAToB = useOrderbook(props.assetB ? props.assetB.tokenAddress : undefined, props.assetA ? props.assetA.tokenAddress : undefined)
  const ordersBToA = useOrderbook(props.assetA ? props.assetA.tokenAddress : undefined, props.assetB ? props.assetB.tokenAddress : undefined)

  const invalidOrderbook = (ordersAToB === [] && ordersBToA === [])

  useEffect(() => {
    return () => {
      if (nocust) {
        console.log('syncing orders', props.address, props.assetA.tokenAddress, props.assetB.tokenAddress)
        nocust.synchronizeSwapOrders(props.address, props.assetA.tokenAddress, props.assetB.tokenAddress)
      }
    }
  }, [])

  let display = i18n.t('loading')

  if (invalidOrderbook) {
    display = (
      <div style={{ textAlign: 'center', width: '100%', fontSize: 20, marginTop: 10 }}>
        <Scaler config={{ startZoomAt: 400, origin: '50% 50%', adjustedZoom: 1 }}>
          Error connecting to TEX
        </Scaler>
      </div>
    )
  } else if (swapMode === 'AtoB') {
    display = (
      <TEXSwapper
        icon='fa-arrow-down'
        buttonStyle={buttonStyle}
        orders={ordersAToB}
        assetSellText={'f' + props.assetA.shortName}
        assetBuyText={'f' + props.assetB.shortName}
        assetBalance={assetABalance}
        successAction={(buyAmount, sellAmount) => {
          if (buyAmount !== '' && sellAmount !== '') {
            console.log('Buying ', buyAmount, props.assetB.shortName, ' for ', sellAmount, props.assetA.shortName)
            nocust.sendSwap(props.address, props.assetB.tokenAddress, props.assetA.tokenAddress, toWei(buyAmount, 'ether'), toWei(sellAmount, 'ether'))
            setSwapMode(false)
          }
        }}
        cancelAction={() => {
          setSwapMode(false)
        }}
      />
    )
  } else if (swapMode === 'BtoA') {
    display = (
      <TEXSwapper
        reversed
        icon='fa-arrow-up'
        buttonStyle={buttonStyle}
        orders={ordersBToA}
        assetSellText={'f' + props.assetB.shortName}
        assetBuyText={'f' + props.assetA.shortName}
        assetBalance={assetBBalance}
        successAction={(buyAmount, sellAmount) => {
          if (buyAmount !== '' && sellAmount !== '') {
            console.log('Buying ', buyAmount, props.assetA.shortName, ' for ', sellAmount, props.assetB.shortName)
            nocust.sendSwap(props.address, props.assetA.tokenAddress, props.assetB.tokenAddress, toWei(buyAmount, 'ether'), toWei(sellAmount, 'ether'))
            setSwapMode(false)
          }
        }}
        cancelAction={() => {
          setSwapMode(false)
        }}
      />
    )
  } else {
    display = (
      <div className='content ops row'>
        <div className='col-6 p-1'>
          <button
            className='btn btn-large w-100'
            style={buttonStyle.primary}
            onClick={() => {
              setSwapMode('BtoA')
            }}
          >
            <Scaler config={{ startZoomAt: 400, origin: '50% 50%' }}>
              <i className='fas fa-arrow-up' /> {typeof props.assetB !== 'undefined' ? 'f' + props.assetB.shortName : i18n.t('loading')} to {typeof props.assetA !== 'undefined' ? 'f' + props.assetA.shortName : i18n.t('loading')}
            </Scaler>
          </button>
        </div>

        <div className='col-6 p-1'>
          <button
            className='btn btn-large w-100'
            style={buttonStyle.primary}
            onClick={() => {
              setSwapMode('AtoB')
            }}
          >
            <Scaler config={{ startZoomAt: 400, origin: '50% 50%' }}>
              <i className='fas fa-arrow-down' /> {typeof props.assetA !== 'undefined' ? 'f' + props.assetA.shortName : i18n.t('loading')} to {typeof props.assetB !== 'undefined' ? 'f' + props.assetB.shortName : i18n.t('loading')}
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

export default (props) => {
  const tokens = useTokens(props.privateKey)

  const assetA = tokens[props.assetA]
  const assetB = tokens[props.assetB]

  return (
    <div>
      <Balance
        token={assetA}
        address={props.address}
        offchain
        selected
        privateKey={props.privateKey}
      />
      <Ruler />
      <TEXSwapBar
        address={props.address}
        assetA={assetA}
        assetB={assetB}
        privateKey={props.privateKey}
      />
      <Balance
        token={assetB}
        address={props.address}
        offchain
        selected
        privateKey={props.privateKey}
      />
      <Ruler />
    </div>
  )
}

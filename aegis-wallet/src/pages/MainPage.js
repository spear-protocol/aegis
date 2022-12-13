import React from 'react'
import { Link } from 'react-router-dom'
// import cookie from 'react-cookies'

import i18n from '../i18n'

import Ruler from '../components/Ruler'
import NavCard from '../components/NavCard'
import Bottom from '../components/Bottom'
import Transactions from '../components/Transactions'
import Balance from '../components/Balance'

import { registerTokens } from '../contexts/Tokens'
import { safeAccess } from '../utils'
import { useAddressBalance } from '../contexts/Balances'
import MainButtons from '../components/MainButtons'
import { useIsRecovery } from '../contexts/Nocust'

const TOKEN = process.env.REACT_APP_TOKEN

export default (props) => {

  const eth = safeAccess(props.tokens, ['ETH']) || {}
  const token = safeAccess(props.tokens, [TOKEN]) || {}
  const ethBalance = useAddressBalance(props.address, safeAccess(eth, ['tokenAddress']), props.privateKey)
  const tokenBalance = useAddressBalance(props.address, safeAccess(token, ['tokenAddress']), props.privateKey)

  const isRecovery = useIsRecovery(props.privateKey)
  if (isRecovery) console.log('HUB IS IN RECOVERY!!!!!')
  registerTokens(props.address, props.privateKey)
  return (
    <div>
      <div className='send-to-address card w-100' style={{ zIndex: 1 }}>
        {isRecovery && <NavCard title='HUB IS IN RECOVERY!!!!!' />}
        <div className='form-group w-100'>

          <div style={{ width: '100%', textAlign: 'center' }}>
            <Link to={{ pathname: `${props.url}/send`, search: '?token=' + TOKEN }}>
              <Balance
                token={token}
                balance={tokenBalance}
                offchain
                selected
                address={props.address}
                privateKey={props.privateKey}
              />
            </Link>
            <Ruler />
            <Balance
              token={token}
              balance={tokenBalance}
              address={props.address}
              privateKey={props.privateKey}
            />
            <Ruler />
            <Link to={{ pathname: `${props.url}/send`, search: '?token=ETH' }}>
              <Balance
                token={eth}
                balance={ethBalance}
                offchain
                selected
                address={props.address}
                privateKey={props.privateKey}
              />
            </Link>
            <Ruler />
            <Balance
              token={eth}
              balance={ethBalance}
              address={props.address}
              privateKey={props.privateKey}
            />
            <Ruler />

            <MainButtons
              url={props.url}
              address={props.address}
              tokenAddress={token.tokenAddress}
              gwei={props.gwei}
              token={TOKEN}
              changeAlert={props.changeAlert}
              privateKey={props.privateKey}
            />

          </div>
          <Transactions
            changeAlert={props.changeAlert}
            address={props.address}
            token={token}
          />
        </div>
      </div>
      <Link to='/advanced'>
        <Bottom
          icon='wrench'
          text={i18n.t('advance_title')}
          action={() => {}}
        />
      </Link>
    </div>
  )
}

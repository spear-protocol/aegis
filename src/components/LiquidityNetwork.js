import React from 'react'
import {
  Switch,
  Route,
  Link,
  Redirect
} from 'react-router-dom'
// import cookie from 'react-cookies'

import { Scaler } from 'dapparatus'

import NavCard from './NavCard'
import Bottom from './Bottom'
import Loader from './Loader'

import lqdImg from '../images/liquidity.png'
import { useTokens } from '../contexts/Tokens'

import {
  SendPage,
  ExchangePage,
  BridgePage,
  MainPage,
  RequestPage,
  ReceivePage
} from '../pages'

const LOADERIMAGE = lqdImg

export default (props) => {
  const tokens = useTokens(props.privateKey)

  const backButton = (
    <Link to={props.match.url}>
      <Bottom
        action={() => {}}
      />
    </Link>
  )

  return (
    <Switch>
      <Route
        path={`${props.match.url}/receive`}
        render={() =>
          <ReceivePage
            address={props.address}
            network={props.network ? props.network.toLowerCase() : ''}
            changeAlert={props.changeAlert}
            backButton={backButton}
          />}
      />

      <Route
        path={`${props.match.url}/sending`}
        render={({ history, location }) => (
          <div>
            <div style={{ zIndex: 1, position: 'relative', color: '#dddddd' }}>
              <NavCard title={(location.state && location.state.title) || 'Sending...'} darkMode />
            </div>
            <Loader
              loaderImage={LOADERIMAGE}
              onFinish={() => { history.replace('/') }}
            />
            {location.state && location.state.subtitle &&
              <div className='row' style={{ zIndex: 1, position: 'relative', color: '#dddddd' }}>
                <div style={{ textAlign: 'center', width: '100%', fontSize: 16, marginTop: 10 }}>
                  <Scaler config={{ startZoomAt: 400, origin: '50% 50%', adjustedZoom: 1 }}>
                    {location.state.subtitle}
                  </Scaler>
                </div>
              </div>}
          </div>
        )}
      />

      <Route
        path={`${props.match.url}/send/:toAddress`}
        render={({ location, match }) => (
          <Redirect to={{ pathname: `${props.match.url}/send`, search: location.search, state: { toAddress: match.params.toAddress } }} />
        )}
      />

      <Route
        path={`${props.match.url}/send`}
        render={({ history, location }) => {
          return (
            <SendPage
              history={history}
              location={location}
              url={props.match.url}
              tokens={tokens}
              address={props.address}
              changeAlert={props.changeAlert}
              backButton={backButton}
              privateKey={props.privateKey}
            />
          )
        }}
      />

      <Route
        path={`${props.match.url}/bridge`}
        render={() => {
          return (
            <BridgePage
              address={props.address}
              gwei={props.gwei}
              changeAlert={props.changeAlert}
              backButton={backButton}
              privateKey={props.privateKey}
            />
          )
        }}
      />

      { <Route
        path={`${props.match.url}/exchange/:assetA/:assetB`}
        render={({ history, match }) =>
          <ExchangePage
            history={history}
            match={match}
            tokens={tokens}
            address={props.address}
            backButton={backButton}
            privateKey={props.privateKey}
          />}
      /> }

      <Route
        path={`${props.match.url}/request/:token`}
        render={({ history, match }) =>
          <RequestPage
            address={props.address}
            networkId={props.networkId}
            history={history}
            match={match}
            changeAlert={props.changeAlert}
            backButton={backButton}
            privateKey={props.privateKey}
          />}
      />

      <Route
        path={`${props.match.url}`}
        render={({ match }) =>
          <MainPage
            url={match.url}
            address={props.address}
            privateKey={props.privateKey}
            tokens={tokens}
            gwei={props.gwei}
            changeAlert={props.changeAlert}
          />}
      />
    </Switch>
  )
}

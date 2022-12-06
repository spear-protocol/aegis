import React, { createContext, useContext, useReducer, useMemo, useCallback } from 'react'

const mainStyle = {
  width: '100%',
  height: '100%',
  backgroundImage: 'linear-gradient(#292929, #191919)',
  backgroundColor: '#191919',
  hotColor: '#F69E4D',
  mainColorAlt: '#6a528e',
  mainColor: '#183b6c'
}

const buttonStyle = {
  primary: {
    backgroundImage: 'linear-gradient(' + mainStyle.mainColorAlt + ',' + mainStyle.mainColor + ')',
    backgroundColor: mainStyle.mainColor,
    color: '#FFFFFF',
    whiteSpace: 'nowrap',
    cursor: 'pointer'
  },
  secondary: {
    border: '2px solid ' + mainStyle.mainColor,
    color: mainStyle.mainColor,
    whiteSpace: 'nowrap',
    cursor: 'pointer'
  }
}

const backgroundStyle = {
  DEFAULT: {
    image: mainStyle.backgroundImage,
    color: mainStyle.backgroundColor
  },
  WEB3: {
    image: 'linear-gradient(#234063, #305582)',
    color: '#305582'
  },
  METAMASK: {
    image: 'linear-gradient(#553319, #ca6e28)',
    color: '#ca6e28'
  },
  INCOGNITO: {
    image: 'linear-gradient(#862727, #671c1c)',
    color: '#671c1c'
  }
}

const THEME = {
  mainStyle,
  buttonStyle,
  backgroundStyle,
  currentBackground: 'DEFAULT'
}
const UPDATE = 'UPDATE'

export const ThemeContext = createContext()

export function useThemeContext () {
  return useContext(ThemeContext)
}

function reducer (state, { type, payload }) {
  switch (type) {
    case UPDATE: {
      const { currentBackground } = payload
      return {
        ...state,
        currentBackground
      }
    }
    default: {
      throw Error(`Unexpected action type in ThemeContext reducer: '${type}'.`)
    }
  }
}

export default function Provider ({ web3, children }) {
  const [state, dispatch] = useReducer(reducer, THEME)

  const update = useCallback((currentBackground) => {
    dispatch({ type: UPDATE, payload: { currentBackground } })
  }, [])

  return (
    <ThemeContext.Provider value={useMemo(() => [state, { update }], [state, update])}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useMainStyle () {
  const [state] = useThemeContext()
  const { mainStyle } = state

  return mainStyle
}

export function useButtonStyle () {
  const [state] = useThemeContext()
  const { buttonStyle } = state

  return buttonStyle
}

export function useBackgroundStyle () {
  const [state] = useThemeContext()
  const { backgroundStyle, currentBackground } = state

  return backgroundStyle[currentBackground]
}

export function setBackgroundStyle (style) {
  const [{ update }] = useThemeContext()
  update(style)
}

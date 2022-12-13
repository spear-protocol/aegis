import React, { Component } from 'react'
import { safeAccess } from '../utils'
import { ThemeContext } from '../contexts/Theme'

let interval

class App extends Component {
  static contextType = ThemeContext

  constructor (props) {
    super(props)
    this.state = {
      percent: 5
    }
  }

  componentDidMount () {
    interval = setInterval(this.loadMore.bind(this), 100)
  }

  componentWillUnmount () {
    clearInterval(interval)
  }

  loadMore () {
    let newPercent = this.state.percent + 3
    if (newPercent > 100) {
      newPercent = 100
      if (typeof this.props.onFinish === 'function') {
        this.props.onFinish()
      }
    }
    this.setState({ percent: newPercent })
  }

  render () {
    const shadowAmount = 100
    const { mainColor, mainColorAlt } = safeAccess(this.context[0], ['mainStyle']) || {}

    const shadowColor = mainColor
    const boxShadow = '0 0 ' + shadowAmount / 40 + 'px ' + shadowColor + ', 0 0 ' + shadowAmount / 30 + 'px ' + shadowColor + ', 0 0 ' + shadowAmount / 20 + 'px ' + shadowColor + ', 0 0 ' + shadowAmount / 10 + 'px #ffffff, 0 0 ' + shadowAmount / 5 + 'px ' + shadowColor + ', 0 0 ' + shadowAmount / 3 + 'px ' + shadowColor + ', 0 0 ' + shadowAmount / 1 + 'px ' + shadowColor + ''

    return (
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: '100%', paddingTop: '5%', paddingBottom: '10%' }}>
          <img src={this.props.loaderImage} alt='No loader available' style={{ maxWidth: '25%', paddingBottom: '5%' }} />
        </div>
        <div style={{ width: '80%', height: 1, backgroundColor: '#444444', marginLeft: '10%' }}>
          <div style={{ width: this.state.percent + '%', height: 1, backgroundColor: mainColorAlt, boxShadow }} />
        </div>
      </div>
    )
  }
}
export default App

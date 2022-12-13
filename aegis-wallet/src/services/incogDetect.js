
// snagged from https://stackoverflow.com/questions/52759238/private-incognito-mode-detection-for-ios-12-safari

function retry (isDone, next) {
  var currentTrial = 0; var maxRetry = 50; var isTimeout = false
  var id = window.setInterval(
    function () {
      if (isDone()) {
        window.clearInterval(id)
        next(isTimeout)
      }
      if (currentTrial++ > maxRetry) {
        window.clearInterval(id)
        isTimeout = true
        next(isTimeout)
      }
    },
    10
  )
}

function isIE10OrLater (userAgent) {
  var ua = userAgent.toLowerCase()
  if (ua.indexOf('msie') === 0 && ua.indexOf('trident') === 0) {
    return false
  }
  var match = /(?:msie|rv:)\s?([\d.]+)/.exec(ua)
  if (match && parseInt(match[1], 10) >= 10) {
    return true
  }
  // MS Edge Detection from this gist: https://gist.github.com/cou929/7973956
  var edge = /edge/.exec(ua)
  if (edge && edge[0] === 'edge') {
    return true
  }
  return false
}

module.exports = function (callback) {
  var isPrivate

  if (window.webkitRequestFileSystem) {
    window.webkitRequestFileSystem(
      window.TEMPORARY, 1,
      function () {
        isPrivate = false
      },
      function (e) {
        console.log(e)
        isPrivate = true
      }
    )
  } else if (window.indexedDB && /Firefox/.test(window.navigator.userAgent)) {
    var db
    try {
      db = window.indexedDB.open('test')
    } catch (e) {
      isPrivate = true
    }

    if (typeof isPrivate === 'undefined') {
      retry(
        function isDone () {
          return db.readyState === 'done'
        },
        function next (isTimeout) {
          if (!isTimeout) {
            isPrivate = !db.result
          }
        }
      )
    }
  } else if (isIE10OrLater(window.navigator.userAgent)) {
    isPrivate = false
    try {
      if (!window.indexedDB) {
        isPrivate = true
      }
    } catch (e) {
      isPrivate = true
    }
  } else if (window.localStorage && /Safari/.test(window.navigator.userAgent)) {
    // One-off check for weird sports 2.0 polyfill
    // This also impacts iOS Firefox and Chrome (newer versions), apparently
    // @see bglobe-js/containers/App.js:116
    if (window.safariIncognito) {
      isPrivate = true
    } else {
      try {
        window.openDatabase(null, null, null, null)
      } catch (e) {
        isPrivate = true
      }
      try {
        window.localStorage.setItem('test', 1)
      } catch (e) {
        isPrivate = true
      }
    }

    if (typeof isPrivate === 'undefined') {
      isPrivate = false
      window.localStorage.removeItem('test')
    }
  }

  retry(
    function isDone () {
      return typeof isPrivate !== 'undefined'
    },
    function next (isTimeout) {
      callback(isTimeout)
    }
  )
}

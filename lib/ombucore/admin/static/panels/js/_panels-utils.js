/**
 * Fires callback functions when an element is scrolled to or away from the top
 * or bottom. The boolean passed to the callback function denotes whether it is
 * at the top/bottom or not.
 *
 * onScrollTopAndBottom(domNode,
 *   function (isAtTop) {
 *     $(domNode).toggleClass('at-top', isAtTop);
 *   },
 *   function (isAtBottom) {
 *     $(domNode).toggleClass('at-bottom', isAtBottom);
 *   }
 * );
 */
function onScrollTopAndBottom(el, fnTop, fnBottom) {

  var MutationObserver = (function () {
    var prefixes = ['WebKit', 'Moz', 'O', 'Ms', '']
    for(var i=0; i < prefixes.length; i++) {
      if(prefixes[i] + 'MutationObserver' in window) {
        return window[prefixes[i] + 'MutationObserver'];
      }
    }
    return false;
  }());

  var AT_TOP = true;
  var AT_BOTTOM = false;
  var $el = $(el);
  var elHeight = $el.outerHeight();
  var scrollHeight = $el[0].scrollHeight;

  $(window).on('resize', onSizeChange);

  // Watch for DOM changes to recalculate element height.
  if (MutationObserver) {
    new MutationObserver(onSizeChange).observe(el, {
      childList: true,
      subtree: true
    });
  }

  // Watch for images loaded to recalculate element height.
  // @see https://stackoverflow.com/a/24611104
  document.body.addEventListener('load', onSizeChange, true);

  $el.on('scroll', onScroll)

  function onSizeChange() {
    elHeight = $el.outerHeight();
    scrollHeight = $el[0].scrollHeight;
    onScroll();
  }

  function onScroll() {
    var scrollTop = $el[0].scrollTop;

    if (AT_TOP && scrollTop > 0) {
      AT_TOP = false;
      fnTop(AT_TOP);
    }
    else if (!AT_TOP && scrollTop == 0) {
      AT_TOP = true;
      fnTop(AT_TOP);
    }

    if (!AT_BOTTOM && (scrollTop + elHeight >= scrollHeight)) {
      AT_BOTTOM = true;
      fnBottom(AT_BOTTOM);
    }
    if (AT_BOTTOM && (scrollTop + elHeight < scrollHeight)) {
      AT_BOTTOM = false;
      fnBottom(AT_BOTTOM);
    }

  }

  // Initialize.
  if ($el.scrollTop() !== 0) {
    AT_TOP = true;
  }
  fnTop(AT_TOP);

  if ($el.scrollTop() + elHeight >= scrollHeight) {
    AT_BOTTOM = true;
  }
  else {
    AT_BOTTOM = false;
  }
  fnBottom(AT_BOTTOM);
}


/**
 * Add event emitter functionality to an existing object.
 *
 * Based on https://gist.github.com/mudge/5830382#gistcomment-2281581.
 */
function eventify(self) {
    self.events = {}

    self.on = function (event, listener) {
        if (typeof self.events[event] !== 'object') {
            self.events[event] = []
        }

        self.events[event].push(listener)
    }

    self.removeListener = function (event, listener) {
        var idx;

        if (typeof self.events[event] === 'object') {
            idx = self.events[event].indexOf(listener)

            if (idx > -1) {
                self.events[event].splice(idx, 1)
            }
        }
    }

    self.removeListeners = function (event) {
       if (typeof self.events[event] === 'object') {
         self.events[event] = [];
       }
    }

    self.emit = function (event) {
        var i, listeners, length, args = [].slice.call(arguments, 1);

        if (typeof self.events[event] === 'object') {
            listeners = self.events[event].slice()
            length = listeners.length

            for (i = 0; i < length; i++) {
                listeners[i].apply(self, args)
            }
        }
    }

    self.once = function (event, listener) {
        self.on(event, function g () {
            self.removeListener(event, g)
            listener.apply(self, arguments)
        })
    }

    return self;
}

function preventDefault(fn) {
  return function() {
    arguments[0].preventDefault();
    return fn.apply(this, arguments);
  }
}

function stopPropagation(fn) {
  return function() {
    arguments[0].stopPropagation();
    return fn.apply(this, arguments);
  }
}

var KEYCODES = {
  ESC: 27
}

function onlyKeyCode(keyCode, fn) {
  return function() {
    var event = arguments[0];
    if (event.keyCode == keyCode) {
      event.preventDefault();
      return fn.apply(this, arguments);
    }
  }
}

/**
 * Combines a list of functions into a single one, executed from L to R.
 *
 * Similar to compose but L->R instead of compose's L<-R function order.
 */
function pipe(/* fns */) {
  var fns = Array.prototype.slice.call(arguments)
  return function(arg) {
    return fns.reduce(function(v, f) {
      return f(v);
    }, arg)
  }
}


function noop() {}


/*\
|*|
|*|  :: cookies.js ::
|*|
|*|  A complete cookies reader/writer framework with full unicode support.
|*|
|*|  Revision #3 - July 13th, 2017
|*|
|*|  https://developer.mozilla.org/en-US/docs/Web/API/document.cookie
|*|  https://developer.mozilla.org/User:fusionchess
|*|  https://github.com/madmurphy/cookies.js
|*|
|*|  This framework is released under the GNU Public License, version 3 or later.
|*|  http://www.gnu.org/licenses/gpl-3.0-standalone.html
|*|
|*|  Syntaxes:
|*|
|*|  * docCookies.setItem(name, value[, end[, path[, domain[, secure]]]])
|*|  * docCookies.getItem(name)
|*|  * docCookies.removeItem(name[, path[, domain]])
|*|  * docCookies.hasItem(name)
|*|  * docCookies.keys()
|*|
\*/

var docCookies = {
  getItem: function (sKey) {
    if (!sKey) { return null; }
    return decodeURIComponent(document.cookie.replace(new RegExp("(?:(?:^|.*;)\\s*" + encodeURIComponent(sKey).replace(/[\-\.\+\*]/g, "\\$&") + "\\s*\\=\\s*([^;]*).*$)|^.*$"), "$1")) || null;
  },
  setItem: function (sKey, sValue, vEnd, sPath, sDomain, bSecure) {
    if (!sKey || /^(?:expires|max\-age|path|domain|secure)$/i.test(sKey)) { return false; }
    var sExpires = "";
    if (vEnd) {
      switch (vEnd.constructor) {
        case Number:
          sExpires = vEnd === Infinity ? "; expires=Fri, 31 Dec 9999 23:59:59 GMT" : "; max-age=" + vEnd;
          /*
          Note: Despite officially defined in RFC 6265, the use of `max-age` is not compatible with any
          version of Internet Explorer, Edge and some mobile browsers. Therefore passing a number to
          the end parameter might not work as expected. A possible solution might be to convert the the
          relative time to an absolute time. For instance, replacing the previous line with:
          */
          /*
          sExpires = vEnd === Infinity ? "; expires=Fri, 31 Dec 9999 23:59:59 GMT" : "; expires=" + (new Date(vEnd * 1e3 + Date.now())).toUTCString();
          */
          break;
        case String:
          sExpires = "; expires=" + vEnd;
          break;
        case Date:
          sExpires = "; expires=" + vEnd.toUTCString();
          break;
      }
    }
    document.cookie = encodeURIComponent(sKey) + "=" + encodeURIComponent(sValue) + sExpires + (sDomain ? "; domain=" + sDomain : "") + (sPath ? "; path=" + sPath : "") + (bSecure ? "; secure" : "");
    return true;
  },
  removeItem: function (sKey, sPath, sDomain) {
    if (!this.hasItem(sKey)) { return false; }
    document.cookie = encodeURIComponent(sKey) + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT" + (sDomain ? "; domain=" + sDomain : "") + (sPath ? "; path=" + sPath : "");
    return true;
  },
  hasItem: function (sKey) {
    if (!sKey || /^(?:expires|max\-age|path|domain|secure)$/i.test(sKey)) { return false; }
    return (new RegExp("(?:^|;\\s*)" + encodeURIComponent(sKey).replace(/[\-\.\+\*]/g, "\\$&") + "\\s*\\=")).test(document.cookie);
  },
  keys: function () {
    var aKeys = document.cookie.replace(/((?:^|\s*;)[^\=]+)(?=;|$)|^\s*|\s*(?:\=[^;]*)?(?:\1|$)/g, "").split(/\s*(?:\=[^;]*)?;\s*/);
    for (var nLen = aKeys.length, nIdx = 0; nIdx < nLen; nIdx++) { aKeys[nIdx] = decodeURIComponent(aKeys[nIdx]); }
    return aKeys;
  }
};

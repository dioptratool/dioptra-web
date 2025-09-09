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

var PanelsAlerts = (function() {

    var isRoot = (window.parent === window);
    if (!isRoot && window.parent.PanelsAlerts) {
        return window.parent.PanelsAlerts;
    }

    var MESSAGE_TIMEOUT = 8 * 1000;
    var messages = [];
    var $panelsContainer;
    var $rootContainer;

    $(function() {
        $panelsContainer = $('<div id="panels-alerts-container"></div>');
        $panelsContainer.appendTo('body');
        $rootContainer = $('#root-alerts-container').length ? $('#root-alerts-container') : $panelsContainer;

        $panelsContainer.on('click', '.alert .close', alertCloseClick);
        if ($rootContainer.get(0) !== $panelsContainer.get(0)) {
          $rootContainer.on('click', '.alert .close', alertCloseClick);
        }
    });


    return {
        alert: openAlert
    }

    function openAlert(message, container, timeout) {
        var $container = (container == 'root') ? $rootContainer : $panelsContainer
        timeout = timeout || MESSAGE_TIMEOUT;
        var $alert = $(makeAlert(message));
        $container.prepend($alert);
        $container.addClass('open');
        $alert.addClass('in');
        setTimeout($.proxy(closeAlert, null, $alert), timeout);
    }

    function closeAlert($alert) {
        $alert.removeClass('in');
        var $container = $alert.parents('#panels-alerts-container, #root-alerts-container');
        setTimeout(function() {
            $alert.remove();
            if ($container.find('.alert').length == 0) {
                $container.removeClass('open');
            }
        }, 150);
    }

    function alertCloseClick(e) {
      e.preventDefault();
      var $alert = $(e.target).parents('.alert');
      closeAlert($alert);
    }

    function makeAlert(message) {
        var classes = ['alert', 'fade'];
        switch(message.level) {
            case 'error':
                classes.push('alert-danger');
                break;
            default:
                classes.push('alert-' + message.level);
                break;
        }

        if (message.extra_tags) {
            classes.push(message.extra_tags);
        }

        return [
            '<div class="' + classes.join(' ') + '">',
              '<div class="alert-inner">',
                '<button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="true">&times;</span></button>',
                '<div class="alert-level">' + message.level.toUpperCase() + '</div>',
                message.message,
              '</div>',
            '</div>',
        ''].join('');
    }

})();

/**
 * UI Interface to show contextual information in iframes above page content.
 *
 * The `Panels` object is a gobal singleton that is available on the parent
 * window and on each panel's iframe.  The `Panels` object in the iframe has
 * selectively exposes methods from the root `Panels` object.
 *
 *
 * In parent window:
 *
 * Panels.open(url)
 *   Opens a panel to the given url. Returns a promise that will be resolved one
 *   success and rejected if the panel is closed.
 *
 * Panels.isRoot
 *   Boolean, Whether the `Panels` object is the root one.
 *
 *
 * In a panel iframe it contains the same methods as above along with:
 *
 * Panels.current.resolve(args...)
 *   Resolves a panel and passes any arguments back to the promise returned
 *   from `Panels.open()`.
 *
 * Panels.current.reject(args...)
 *   Rejects a panel and passes any arguments back to the promise returned
 *   from `Panels.open()`.
 *
 *
 *
 * Example:
 *
 * In Parent window:
 *
 *     Panels.open('/media-select?type=video').then(
 *         function(videoData) {
 *             console.log(videoData);
 *         },
 *         function() {
 *             console.log("No video selected");
 *         }
 *     );
 *
 * In Media-Select Panel iframe:
 *
 *     $('.video .select-btn').on('click', function(e) {
 *         var videoId = $(e.target).attr('data-video-id');
 *         var videoTitle = $(e.target).attr('data-video-title');
 *         Panels.current.resolve({id: videoId, title: videoTitle);
 *     });
 *     $('.panel-close').on('click', function(e) {
 *         e.preventDefault();
 *         Panels.current.reject();
 *     });
 *
 */
;(function() {

    function makePanelsRoot() {

        var panelWidth = 60; // Percentage.
        var panelStack = [];
        var $container = $('<div id="panels-container"><div id="panels-container-veil"></div></div>');
        var scrollPosition = 0;

        $container.appendTo('body');

        $container.find('#panels-container-veil').on('click', rejectTopPanel);

        $(document).on('keyup.panels', function(e) {
            if (e.keyCode === 27) {
                rejectTopPanel();
            }
        });

        function open(url) {
            var panel = makePanel(url);

            // Set scroll position on first panel
            if (panelStack.length === 0) {
                scrollPosition = $('body').scrollTop();

                // Set a class on the root html element to prevent nested scrolling
                // using CSS.
                $('html').addClass('panel-open');
                $('body').css('top', -scrollPosition);
            }

            panel.$el.appendTo($container);
            panelStack.push(panel);

            openUpdateUI();

            return panel.deferred.promise()
        }

        function openUpdateUI() {
            if (panelStack.length === 1) {
                $container.addClass('active');
            }

            // Give time to have the 'active' class take effect.
            setTimeout(function() {
                $container.attr('data-panel-count', panelStack.length);
                panelStack.slice().reverse().map(function(panel, index) {
                    if (index !== 0) {
                        panel.$el.addClass('veil-open');
                        setTimeout(function() {
                            panel.$el.addClass('veiled');
                        }, 10);
                    }
                });
            }, 10);
        }

        function closeTopPanel() {
            var panel = panelStack.pop();

            $container.attr('data-panel-count', panelStack.length);

            panelStack.slice().reverse().map(function(panel, index) {
                if (index === 0) {
                    panel.$el.removeClass('veiled').one('transitionend', function() {
                        panel.$el.removeClass('veil-open');
                    });
                }
            });

            // If the panel closing is the last one, restore scrolling for the
            // root html element.
            if (panelStack.length === 0) {
                $('html').removeClass('panel-open');
                $('body').css('top', '');
                $('body').scroll(0, scrollPosition);
            }

            setTimeout(function() {
                panel.$el.remove();
                if (panelStack.length === 0) {
                    $container.removeClass('active');
                }
            }, 500);
        }

        function makePanel(url) {
            var deferred = $.Deferred();
            var panelIndex = panelStack.length;
            var html = ['',
                    '<div class="is-panel">',
                      '<div class="panel-inner">',
                        '<div class="loading"></div>',
                        '<iframe data-panel-index="' + panelIndex + '" src="' + url + '"></iframe>',
                        '<a href="#" class="panel-close">&times;</a>',
                      '</div>',
                      '<div class="panel-veil"></div>',
                    '</div>',
               ''].join('');
            var $el = $(html);

            $el.find('.panel-close').on('click', function(e) {
              e.preventDefault();
              rejectTopPanel();
            });
            $el.find('.panel-veil').on('click', rejectTopPanel);
            $el.find('iframe').on('load', function() {
                $el.find('.loading').remove();
            });

            return eventify({
                deferred: deferred,
                $el: $el
            });
        }

        function resolvePanel(index /* arguments */) {
            var panel = panelStack[index];
            var resolveArgs = sliceArgs(arguments, 1);
            closeTopPanel();
            panel.deferred.resolve.apply(null, resolveArgs);
        }

        function rejectPanel(index /* arguments */) {
            var panel = panelStack[index];
            var rejectArgs = sliceArgs(arguments, 1);
            if (panel) {
                var canceled = false;
                var e = {
                    preventDefault: function() { canceled = true; },
                    arguments: rejectArgs
                };
                panel.emit('beforeReject', e);
                if (!canceled) {
                    closeTopPanel();
                    panel.deferred.reject.apply(null, rejectArgs);
                }
            }
        }

        function notifyPanel(index /* arguments */) {
            var panel = panelStack[index];
            var args = sliceArgs(arguments, 1);
            if (panel) {
                panel.deferred.notify.apply(null, args);
            }
        }

        // Proxy `on`, `removeListener`, and `once` methods to the panel.
        function panelEventsOn(index /* arguments */) {
            var panel = panelStack[index];
            if (panel) {
                var args = sliceArgs(arguments, 1);
                return panel.on.apply(null, args);
            }
        }
        function panelEventsRemoveListener(index /* arguments */) {
            var panel = panelStack[index];
            if (panel) {
                var args = sliceArgs(arguments, 1);
                return panel.removeListener.apply(null, args);
            }
        }
        function panelEventsRemoveListeners(index /* arguments */) {
            var panel = panelStack[index];
            if (panel) {
                var args = sliceArgs(arguments, 1);
                return panel.removeListeners.apply(null, args);
            }
        }
        function panelEventsOnce(index /* arguments */) {
            var panel = panelStack[index];
            if (panel) {
                var args = sliceArgs(arguments, 1);
                return panel.once.apply(null, args);
            }
        }

        function rejectTopPanel() {
            rejectPanel(panelStack.length - 1);
        }

        function rootAlert(message, timeout) {
            var alertContainer = (panelStack.length > 0) ? 'panels' : 'root';
            PanelsAlerts.alert(message, alertContainer, timeout);
        }

        // Show initial messages.
        setTimeout(function() {
          var scriptTag = document.getElementById('_initialPanelsMessages');
          var messages = [];

          if (scriptTag) {
            try {
              messages = JSON.parse(scriptTag.textContent);
            } catch (e) {
              console.error('Failed to parse initial panels messages JSON', e);
            }
          }

          messages.forEach(function(message, i) {
            setTimeout(function() {
              rootAlert(message);
            }, i * 200);
          });
        }, 0);

        return {
            open: open,
            isRoot: true,
            resolvePanel: resolvePanel,
            rejectPanel: rejectPanel,
            notifyPanel: notifyPanel,
            rejectTopPanel: rejectTopPanel,
            panelEventsOn: panelEventsOn,
            panelEventsRemoveListener: panelEventsRemoveListener,
            panelEventsRemoveListeners: panelEventsRemoveListeners,
            panelEventsOnce: panelEventsOnce,
            alert: rootAlert
        };


    };

    function makePanelsChild() {
        var PanelsRoot = window.parent.Panels;
        var panelIndex = $(window.frameElement).attr('data-panel-index');

        $(document).on('keyup.panels', function(e) {
            if (e.keyCode === 27) {
                PanelsRoot.rejectPanel(panelIndex)
                e.stopPropagation();
            }
        });

        // Show initial messages.
        setTimeout(function() {
          var scriptTag = document.getElementById('_initialPanelsMessages');
          var messages = [];

          if (scriptTag) {
            try {
              messages = JSON.parse(scriptTag.textContent);
            } catch (e) {
              console.error('Failed to parse initial panels messages JSON', e);
            }
          }

          messages.forEach(function(message, i) {
            setTimeout(function() {
              PanelsRoot.alert(message);
            }, i * 200);
          });
        }, 0);

        // Initialize things in the panel.
        $(function() {
            focusFirstInput($('body'));
        });

        function rootRedirect(url) {
            window.parent.location = url;
        }

        function rootReload() {
            window.parent.location.reload();
        }

        return {
            isRoot: false,
            open: PanelsRoot.open,
            current: {
                resolve: PanelsRoot.resolvePanel.bind(null, panelIndex),
                reject: PanelsRoot.rejectPanel.bind(null, panelIndex),
                notify: PanelsRoot.notifyPanel.bind(null, panelIndex),
                on: PanelsRoot.panelEventsOn.bind(null, panelIndex),
                removeListener: PanelsRoot.panelEventsRemoveListener.bind(null, panelIndex),
                removeListeners: PanelsRoot.panelEventsRemoveListeners.bind(null, panelIndex),
                once: PanelsRoot.panelEventsOnce.bind(null, panelIndex)
            },
            root: {
              redirect: rootRedirect,
              reload: rootReload
            },
            alert: PanelsRoot.alert
        };

    }

    function focusFirstInput(el) {
        var $firstInput = $(el).find(':input:visible:first');

        if (!$firstInput.length) {
            return;
        }

        var inputType = $firstInput.attr('type');
        $firstInput.focus();
        if (inputType == 'text') {
            // @see https://stackoverflow.com/a/1675345
            var input = $firstInput.get(0);
            if (input.setSelectionRange) {
                var len = $($firstInput).val().length * 2;
                input.setSelectionRange(len, len);
            }
            else {
                // ... otherwise replace the contents with itself
                $firstInput.val($firstINput.val());
            }
        }
    }

    $(function() {
        window.Panels = (function() {

            var isRoot = (window.parent === window);

            if (isRoot) {
                return makePanelsRoot();
            }
            else {
                return makePanelsChild();
            }

        })();
    });

})();


// Common actions.
$(function() {

    $('body').on('click', '[data-panels-action="reject-close"]', function(e) {
        e.preventDefault();
        Panels.current.reject();
    });

    $('body').on('click', '[data-panels-trigger]', panelTriggerHandler);

    // Auto-open a panel.
    var currentHash = encodeURI(window.location.hash)
    if (currentHash && currentHash.slice(0, 7) == '#panel=') {
        var url = currentHash.slice(7);
        Panels.open(url);
    }

});

function panelTriggerHandler(e) {
    if (!e.metaKey) {
        e.preventDefault();
        var $link = $(e.currentTarget);
        var reloadOn = [];
        if ($link.attr('data-panels-reload-on') !== undefined) {
          reloadOn = $link.attr('data-panels-reload-on').split(',').map(function(s) { return s.trim(); });
        }

        var rejectEvents = [];

        function panelEventHandler(event) {
          if (event && event.operation && reloadOn.indexOf(event.operation) >= 0) {
            setTimeout(function() {
              window.location.reload();
            }, 200);
          }
          else if (event && event.redirect_to) {
            setTimeout(function() {
              window.location = event.redirect_to;
            }, 200);
          }
        }

        Panels
          .open($link.attr('href'))
          .then(

            // Resolved / closed.
            // Handle the returned event.
            panelEventHandler, 

            // Rejected / closed.
            // Handle events that were stashed during notify/progress.
            function rejectedHandler(event) {
              $.each(rejectEvents, function(i, event) {
                panelEventHandler(event);
              });
            },

            // Notify / progress.
            // Stash events so they can be triggered when the panel closes.
            function progressHandler(event) {
              rejectEvents.push(event);
            }
          )

    }
}


// Track if panel body has scrolled.
$(function() {
  var $panelBody = $('.panel-body.panel-body-scrollable');
  if ($panelBody.length) {
    onScrollTopAndBottom(
      $('.panel-body-scroller')[0],
      function atTopCallback(isAtTop) {
        $panelBody.toggleClass('at-top', isAtTop);
      },
      function atBottomCallback(isAtBottom) {
        $panelBody.toggleClass('at-bottom', isAtBottom);
      }
    );
  }
});



function sliceArgs(args, index) {
    return Array.prototype.slice.call(args, index);
}

$(function() {

  var $trigger = $('#admin-overlay-trigger');
  var $overlay = $('#admin-overlay');

  function openOverlay() {
    $trigger.addClass('inactive');
    $trigger.attr('aria-expanded', 'true');
    $overlay.addClass('active');
    $(window).on('keyup.admin-overlay-open', onlyKeyCode(KEYCODES.ESC, closeOverlay));
    docCookies.setItem('admin-overlay-open', 1, null, "/");
  }

  function closeOverlay() {
    $trigger.removeClass('inactive');
    $trigger.attr('aria-expanded', 'false');
    $overlay.removeClass('active');
    $trigger.focus();
    $(window).off('.admin-overlay-open');
    docCookies.setItem('admin-overlay-open', 0, null, "/");
  }

  $trigger.on('click', preventDefault(stopPropagation(openOverlay)));
  $('#admin-overlay-close').on('click', preventDefault(closeOverlay));

  if (docCookies.getItem('admin-overlay-open') == 1) {
    openOverlay();
  }

});

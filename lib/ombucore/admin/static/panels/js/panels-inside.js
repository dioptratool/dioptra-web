/* ========================================================================
 * Bootstrap: dropdown.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#dropdowns
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // DROPDOWN CLASS DEFINITION
  // =========================

  var backdrop = '.dropdown-backdrop'
  var toggle   = '[data-toggle="dropdown"]'
  var Dropdown = function (element) {
    $(element).on('click.bs.dropdown', this.toggle)
  }

  Dropdown.VERSION = '3.4.1'

  function getParent($this) {
    var selector = $this.attr('data-target')

    if (!selector) {
      selector = $this.attr('href')
      selector = selector && /#[A-Za-z]/.test(selector) && selector.replace(/.*(?=#[^\s]*$)/, '') // strip for ie7
    }

    var $parent = selector !== '#' ? $(document).find(selector) : null

    return $parent && $parent.length ? $parent : $this.parent()
  }

  function clearMenus(e) {
    if (e && e.which === 3) return
    $(backdrop).remove()
    $(toggle).each(function () {
      var $this         = $(this)
      var $parent       = getParent($this)
      var relatedTarget = { relatedTarget: this }

      if (!$parent.hasClass('open')) return

      if (e && e.type == 'click' && /input|textarea/i.test(e.target.tagName) && $.contains($parent[0], e.target)) return

      $parent.trigger(e = $.Event('hide.bs.dropdown', relatedTarget))

      if (e.isDefaultPrevented()) return

      $this.attr('aria-expanded', 'false')
      $parent.removeClass('open').trigger($.Event('hidden.bs.dropdown', relatedTarget))
    })
  }

  Dropdown.prototype.toggle = function (e) {
    var $this = $(this)

    if ($this.is('.disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('open')

    clearMenus()

    if (!isActive) {
      if ('ontouchstart' in document.documentElement && !$parent.closest('.navbar-nav').length) {
        // if mobile we use a backdrop because click events don't delegate
        $(document.createElement('div'))
          .addClass('dropdown-backdrop')
          .insertAfter($(this))
          .on('click', clearMenus)
      }

      var relatedTarget = { relatedTarget: this }
      $parent.trigger(e = $.Event('show.bs.dropdown', relatedTarget))

      if (e.isDefaultPrevented()) return

      $this
        .trigger('focus')
        .attr('aria-expanded', 'true')

      $parent
        .toggleClass('open')
        .trigger($.Event('shown.bs.dropdown', relatedTarget))
    }

    return false
  }

  Dropdown.prototype.keydown = function (e) {
    if (!/(38|40|27|32)/.test(e.which) || /input|textarea/i.test(e.target.tagName)) return

    var $this = $(this)

    e.preventDefault()
    e.stopPropagation()

    if ($this.is('.disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('open')

    if (!isActive && e.which != 27 || isActive && e.which == 27) {
      if (e.which == 27) $parent.find(toggle).trigger('focus')
      return $this.trigger('click')
    }

    var desc = ' li:not(.disabled):visible a'
    var $items = $parent.find('.dropdown-menu' + desc)

    if (!$items.length) return

    var index = $items.index(e.target)

    if (e.which == 38 && index > 0)                 index--         // up
    if (e.which == 40 && index < $items.length - 1) index++         // down
    if (!~index)                                    index = 0

    $items.eq(index).trigger('focus')
  }


  // DROPDOWN PLUGIN DEFINITION
  // ==========================

  function Plugin(option) {
    return this.each(function () {
      var $this = $(this)
      var data  = $this.data('bs.dropdown')

      if (!data) $this.data('bs.dropdown', (data = new Dropdown(this)))
      if (typeof option == 'string') data[option].call($this)
    })
  }

  var old = $.fn.dropdown

  $.fn.dropdown             = Plugin
  $.fn.dropdown.Constructor = Dropdown


  // DROPDOWN NO CONFLICT
  // ====================

  $.fn.dropdown.noConflict = function () {
    $.fn.dropdown = old
    return this
  }


  // APPLY TO STANDARD DROPDOWN ELEMENTS
  // ===================================

  $(document)
    .on('click.bs.dropdown.data-api', clearMenus)
    .on('click.bs.dropdown.data-api', '.dropdown form', function (e) { e.stopPropagation() })
    .on('click.bs.dropdown.data-api', toggle, Dropdown.prototype.toggle)
    .on('keydown.bs.dropdown.data-api', toggle, Dropdown.prototype.keydown)
    .on('keydown.bs.dropdown.data-api', '.dropdown-menu', Dropdown.prototype.keydown)

}(jQuery);

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


function setupPanelForm($form) {
  handleTaggitAutosuggestChange($form);
  handleCKEditorChange($form);
  handleAnyUrlChange($form);
  setupInputChangeHandlers($form);
  var confirmAbandonmentMessage = $form.attr('data-confirm-abandonment-message');

  // Clearn any 'changed' classes
  $form.find('.form-group.changed').removeClass('changed');

  // Find and disable submit buttons on page load; Enable them if user
  // makes any changes.
  var $submitButton = $form.find('[disable-when-form-unchanged]');
  $submitButton.prop('disabled', true);

  $form.on('panel:inputchanged', function(e) {
    var formHasChanges = !!$form.find('.form-group.changed').length;
    $submitButton.prop('disabled', !formHasChanges);
  });

  function confirmAbandonment(e) {
    var hasChanges = !!$form.find('.form-group.changed').length;
    var hasErrors = !!$form.find('.help-block.errors').length;
    if ((hasChanges || hasErrors) && confirmAbandonmentMessage) {
      var abandonChanges = confirm(confirmAbandonmentMessage);
      if (!abandonChanges) {
        e.preventDefault();
      }
    }
  }

  // Warn user on navigation away from edit/create panel to a localization panel
  $('#localization_link').on('click', confirmAbandonment);

  if (Panels.hasOwnProperty('current')) { // It's in a panel.
    // Reset the event handlers when the page loads so the abandonment
    // confirmation doesn't run multiple times if the form fails to validate
    // multiple times in a row.
    Panels.current.removeListeners('beforeReject');
    Panels.current.on('beforeReject', confirmAbandonment);
  }

  var $deleteButton = $form.find('a.panels-delete-btn');
  $deleteButton.on('click', function(e) {
    e.preventDefault();
    Panels.open($deleteButton.attr('href')).then(Panels.current.resolve);
  });

}

/**
 * Autosuggest and the django package are frustrating and we can't hook into
 * them easily. Use polling to watch if the value changes.
 */
function handleTaggitAutosuggestChange($form) {
  var $autosuggestFormGroups = $form.find('input[id*="__tagautosuggest"]').parents('.form-group');

  $autosuggestFormGroups.each(function(i, formGroup) {
    var $formGroup = $(formGroup);
    var $valueInput = $formGroup.find('input[type="hidden"].as-values');
    $formGroup.find('input').addClass('notrackchange');
    var startingValue = $valueInput.val();
    var lastValue = startingValue;

    setInterval(updateChanged, 300);

    function updateChanged() {
      var value = $valueInput.val();
      if (value == lastValue) {
        // pass.
      }
      else if (value == startingValue) {
        $formGroup.removeClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      else {
        $formGroup.addClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      lastValue = value;
    }

  });
}

function handleCKEditorChange($form) {
  if (!window.hasOwnProperty('CKEDITOR')) {
    return;
  }
  $form.find('textarea[data-type="ckeditortype"]').addClass('notrackchange');
  for (var key in CKEDITOR.instances) {
    if (CKEDITOR.instances.hasOwnProperty(key)) {
      var instance = CKEDITOR.instances[key];
      instance.on('change', ckeditorChangeHandler);
    }
  }

  function ckeditorChangeHandler(e) {
    var editor = e.editor;
    var $formGroup = $(editor.element.$).parents('.form-group');
    $formGroup
      .toggleClass('changed', editor.checkDirty())
      .trigger('panel:inputchanged');
  }
}

function handleAnyUrlChange($form) {
  var $typeWrappers = $form.find('ul.any_urlfield-url_type');

  $typeWrappers.each(function(i, typeWrapperEl) {
    handleField($(typeWrapperEl).parents('.form-group'));
  });

  function handleField($formGroup) {
    var startingVal = getValue($formGroup);
    var lastVal  = startingVal;

    var requiredFields = !!$formGroup.find(':input[required]').length;

    $formGroup
      .find(':input')
      .addClass('notrackchange')
      .on('change keyup', update);

    update();

    function update() {
      var val = getValue($formGroup);
      if (val == lastVal) {
        // pass.
      }
      else if (val == startingVal) {
        $formGroup.removeClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      else {
        $formGroup.addClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      lastVal = val;

      // Change which element is required.
      if (requiredFields) {
        $formGroup
          .find(':input')
          .not('[type="radio"]')
          .removeAttr('required');
        getActivePane($formGroup).find(':input').attr('required', 'required');
      }
    }
  }

  function getValue($formGroup) {
    var $typeRadios = $formGroup.find('input[type="radio"]');
    var typeVal = $typeRadios.filter(':checked').val();
    var $pane = getActivePane($formGroup);
    return typeVal + ':' + $pane.find(':input').val();
  }

  function getActivePane($formGroup) {
    var $typeRadios = $formGroup.find('input[type="radio"]');
    var typeVal = $typeRadios.filter(':checked').val();
    var $pane = $formGroup.find('.any_urlfield-url-' + typeVal.replace(/[^a-z0-9-_]/, ''));
    return $pane;
  }

}

function setupInputChangeHandlers($form) {
  // Track changes on form elements.
  var $inputs = $form.find(':input:not(.notrackchange)')
  var startingValues = $inputs.toArray()
                      .reduce(function(values, input) {
                        var $input = $(input);
                        values[$input.attr('name')] = inputVal($input);
                        return values;
                      }, {});

  $inputs.on('change keyup', inputChanged);

  function inputChanged(e) {
    var $input = $(e.target);
    var name = $input.attr('name');
    if (startingValues[name] == inputVal($input)) {
      $input.parents('.form-group').removeClass('changed');
    }
    else {
      $input.parents('.form-group').addClass('changed');
    }

    $input.trigger('panel:inputchanged');
  }

  function inputVal($input) {
    if ($input.attr('type') === 'checkbox') {
      var name = $input.attr('name');
      var $checkboxes = $form.find(':input[name="' + name + '"]');
      return $checkboxes
                .toArray()
                .map(function(checkbox) {
                  var $checkbox = $(checkbox);
                  return $checkbox.is(':checked') ? $checkbox.val() : '';
                })
                .join(',');
    }
    return $input.val();
  }
}

function setupPanelTabs($formTabs) {
  var $tabs = $formTabs.find('.form-tabs-tabs [data-tab]');
  $tabs.on('click', function(e) {
    var $clickedTab = $(this);
    $tabs.removeClass('active');
    $clickedTab.addClass('active');
    $formTabs
      .find('.form-tabs-contents [data-tab]')
      .removeClass('active')
      .filter('[data-tab="' + $clickedTab.attr('data-tab') + '"]')
      .addClass('active');
    $(window).trigger('resize');
  });

  if ($tabs.filter('.error').length) {
    // Open to a tab with an error.
    $tabs.filter('.error').first().click();
  }
  else if (window.location.hash) {
    // Form was opened to a specific tab.
    var hash = window.location.hash.slice().replace('#', '');
    if (hash.length) {
      $tabs.filter('[data-tab="' + hash + '"]').first().click();
    }
  }

  // Make tabs show changed status.
  $formTabs
    .find('.form-tabs-contents [data-tab]')
    .each(function(i, tabContent) {
      var $tabContent = $(tabContent);
      $tabContent.on('panel:inputchanged', function(e) {
        var hasChanged = !!$tabContent.find('.changed').length;
        var tabSlug = $tabContent.attr('data-tab');
        $formTabs.find('.form-tabs-tabs [data-tab="' + tabSlug + '"]').toggleClass('changed', hasChanged)
      });
    });

  var $formTabContents = $formTabs.find('.form-tabs-contents');
  if ($formTabContents.length) {
    onScrollTopAndBottom(
      $('.form-tabs-contents-scroller')[0],
      function atTopCallback(isAtTop) {
        $formTabContents.toggleClass('contents-at-top', isAtTop);
      },
      function atBottomCallback(isAtBottom) {
        $formTabContents.toggleClass('contents-at-bottom', isAtBottom);
      }
    );
  }
}

$(function() {
  var $form = $('form.panel-form');
  if ($form.length) {
    setupPanelForm($form);
  }

  var $formTabs = $('.form-tabs');
  if ($formTabs.length) {
    setupPanelTabs($formTabs);
  }

  // In the nested reorder view of an object with localization,
  // allow user to toggle between different sets of objects in different
  // localizations
  $('.nested-reorder-locale-select').change(function() {
    window.location.replace(window.location.href.split('?')[0] + '?locale=' + $(this).val());
  });

  // In the Localization management view, ask users if they are sure they want to delete an item
  $('.localization-menu--operations-link--delete').on('click', function(e) {
    var choice = confirm('Are you sure you want to delete this item forever?');
    if(!choice) {
      e.preventDefault();
    }
  });
});

// Allow user to hit 'Enter' to add tags using Tags field
function tagsFieldEnter() {
    var $tagsField = $('#id_tags__tagautosuggest');

    $tagsField.on('keydown', function(e) {
        if (e.keyCode == 13) {
            // 'Enter' was pressed; Trigger 'Tab' keydown
            e.preventDefault();
            var new_e = jQuery.Event("keydown");
            new_e.keyCode = 9;
            $(this).trigger(new_e);
        }
    });
}

$(document).ready(function() {
    tagsFieldEnter();
});

function setupFilterListForm($filterList) {

  var $form = $filterList.find('.filter-list-form');
  var $addFilterDropdown = $form.find('.add-filter-dropdown');
  var $dropdownMenuItems = $addFilterDropdown.find('.dropdown-menu-items');
  var $filterResults = $form.find('.filter-results');
  var $clearAll = $form.find('a.clear-all');
  var $clearSearchPhrase = $form.find('.clear-search-phrase');
  var loadedFormData = $form.serialize();

  // Wire up dropdown items to show filter form elements.
  $form.find('[data-filter-target]').click(function(e) {
    e.preventDefault();
    e.stopPropagation();
    var filterName = $(e.target).attr('data-filter-target');
    showFilterInDropdown(filterName);
  });

  $form.find('[name="order_by"]').on('change', submitForm);

  // Prevent clicks in dropdown content from closing the dropdown.
  $form
    .find('.dropdown-menu')
    .on('click.bs.dropdown.data-api', function (e) { e.stopPropagation() });

  // Reset the dropdown to the filter list when the dropdown closes.
  $addFilterDropdown.on('hidden.bs.dropdown', resetFilterDropdown);

  // When the search input’s clear affordance is clicked, empty its value and
  // submit the filter form.
  $clearSearchPhrase.on('click', function(e) {
    e.preventDefault();
    $form.find('[name="search"]').val('');
    submitForm();
  });

  // Initialize filter results.
  $form
    .find('[data-filter]')
    .each(function(i, filterEl) { initFilter(filterEl); });

  // Hide the filter dropdown if there are no filters left to add.
  if (!$dropdownMenuItems.find('li:not(.hidden)').length) {
    $addFilterDropdown.hide();
  }

  if ($filterResults.find('.filter-result').length) {
    $clearAll.removeClass('hidden');
    $form.addClass('filter-list-form-active');
  }

  $form.on('submit', function() {
    // If the form hasen't changed it won't actually make a request if the
    // action is `#` so only show the filtering wheel if something actually
    // changed.
    var currentFormData = $form.serialize();
    if (currentFormData !== loadedFormData) {
      setFiltering();
    }
  });
  $filterList.find('.pagination a').on('click', setFiltering);

  $filterResults.find('a.clear-filter').on('click', function(e) {
    e.preventDefault();
    var filterName = $(e.target).attr('data-filter-name');
    var filterValue = $(e.target).attr('data-filter-value')
    clearFilter(filterName, filterValue);
    submitForm();
  });

  $clearAll.on('click', function(e) {
    e.preventDefault();
    clearAllFilters();
    submitForm();
  });


  function clearAllFilters() {
    $filterResults
      .find('.filter-result')
      .map(function(i, el) {
        var $result = $(el);
        var filterName = $result.find('[data-filter-name]').attr('data-filter-name');
        var filterValue = $result.find('[data-filter-value]').attr('data-filter-value');
        clearFilter(filterName, filterValue);
      });
    $form.find('[name="search"]').val('');
    submitForm();
  }

  function showFilterInDropdown(filterName) {
    $dropdownMenuItems.addClass('hidden');
    $form
      .find('[data-filter="' + filterName + '"]')
      .removeClass('hidden');
  }

  function resetFilterDropdown() {
    $dropdownMenuItems.removeClass('hidden');
    $form
      .find('.add-filter-dropdown')
      .find('[data-filter]')
      .addClass('hidden');
  }

  function clearFilter(filterName, filterValue) {
    var selector = '[data-filter-name="' + filterName + '"][data-filter-value="' + filterValue + '"]';
    $filterResults
      .find(selector)
      .parents('.filter-result')
      .remove();

    var $filter = $form.find('[data-filter="' + filterName + '"]');


    var isFlatpickr = $filter.find('select').closest('.form-group').find('.flatpickr-calendar').length
    // Select
    if ($filter.find('select').length > 0 && !isFlatpickr) {
      $filter.find('select').val('');
    }
    // Checkboxes, Radios.
    else if ($filter.find(':input[value="' + filterValue + '"]') && !isFlatpickr) {
      var $input = $filter.find(':input[value="' + filterValue + '"]');
      if ($input.is(':checked')) {
        $input.removeAttr('checked');
      }
      else {
        $input.val('');
      }
    }
    // Text Fields.
    else {
      $filter.find(':input').val('');
    }

    if (!$filterResults.find('.filter-result').length) {
      $clearAll.hide();
    }
  }

  /**
   * If the filter has a value, it is added to the filter results and the item
   * in the dropdown is hidden.
   */
  function initFilter(filterEl) {
    var $el = $(filterEl);
    var $input = $el.find(':input');
    var inputType = $input.prop('type');

    if (inputType === 'select-one') {
      var val = $input.val();

      if (val) {
        var displayVal = $input.find('[value="' + val + '"]').text();
        var label = $el.find('label').text();
        addResult(label, val, displayVal, $input.attr('name'));
        hideDropdownMenuItem($el.attr('data-filter'));
      }
      else {
        $input.on('change', submitForm);
      }
    }
    else if (inputType === 'checkbox') {

        $el.find(':checked').each(function(i, checkbox) {
          var $checkbox = $(checkbox);
          var label = $checkbox.parents('[data-filter]').find('.control-label').text()
          var val = $checkbox.val();
          var displayVal = $checkbox.parents('label').text();
          var name = $checkbox.attr('name');
          addResult(label, val, displayVal, name);
        });

    }
    else if (inputType == 'radio') {

      var $radioChecked = $el.find(':checked');
      var val = $radioChecked.val();

      if (val) {
        var displayVal = $radioChecked.next().text();
        var label = $radioChecked[0].name;
        addResult(label, val, displayVal, $input.attr('name'));
        hideDropdownMenuItem($el.attr('data-filter'));
      }

      $input.on('change', submitForm);

    }
    else if ($input.attr('data-flatpickr') != undefined) {
      var val = $input.first().val();
      if (val) {
        var date = new Date(val);
        var displayVal = flatpickr.formatDate(date, 'M J, Y h:i K');
        var label = $el.find('label').text();
        addResult(label, val, displayVal, $input.attr('name'));
        hideDropdownMenuItem($el.attr('data-filter'));
      }
    }

  }

  function hideDropdownMenuItem(name) {
      $dropdownMenuItems
        .find('[data-filter-target="' + name + '"]')
        .parents('li')
        .addClass('hidden');
  }

  function addResult(label, value, displayValue, name) {
    var html = filterResultHtml(label, value, displayValue, name);
    if ($filterResults.find('.filter-result').length > 0) {
      $filterResults.find('.filter-result').last().after(html);
    }
    else {
      $filterResults.prepend(html);
    }
  }

  function filterResultHtml(label, value, displayValue, name) {
    return [
      '<div class="filter-result">',
        '<div class="label">' + label + '</div>',
        '<div class="value">' + displayValue + '</div>',
        '<a href="#" class="clear-filter close" data-filter-value="' + value + '" data-filter-name="' + name + '" title="Remove">×</a>',
      '</div>',
    ''].join('');
  }

  function submitForm() {
    $form.trigger('submit');
  }

  function setFiltering() {
    $filterList.addClass('filtering');
  }

  function inputHasValue($input) {
    return ($input.val() && $input.val().length);
  }

}

$(function() {

  var $filterList = $('.filter-list');
  if ($filterList.length) {
    $filterList.each(function(i, filterListEl) {
      var $filterList = $(filterListEl);
      if ($filterList.find('.filter-list-form').length) {
        setupFilterListForm($filterList);
      }
    });
  }

  var $markTriggers = $('.mark-trigger');
  $markTriggers.on('click', function(e) {
      var $el = $(e.currentTarget);
      var wasMarked = $el.hasClass('marked');
      $markTriggers.removeClass('marked');
      $el.addClass('marked');

      if (wasMarked && $el.parents('.grid-media').length) {
          $el.find('.operations-links a:first-child').trigger('click');
      }
  });

  $markTriggers.find('.operations-links a[data-panels-trigger]').on('click', function(e) {
      e.stopPropagation();
      panelTriggerHandler(e);
  });

  $markTriggers.find('.operations-close').on('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      $markTriggers.removeClass('marked');
  });

  // Makes list items click on the name twice trigger the first operation. 
  $markTriggers.find('.operations-primary').on('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      $primaryLink = $(this).next('.operations-links').find('a:first-child');
      $primaryLink.trigger('click');
  });

  var $selectButton = $('.panels-select-btn');
  if ($selectButton.length) {
      $markTriggers.on('click', function(e) {
          var hasMarked = !!$markTriggers.filter('.marked').length;
          $selectButton.prop('disabled', !hasMarked);
      });

      $markTriggers.find('.operations-select').on('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          $selectButton.trigger('click');
      });

      $selectButton.on('click', function(e) {
          e.preventDefault();
          $marked = $markTriggers.filter('.marked');
          if (!$marked.length) {
              return;
          }
          var objInfo = $marked.data('obj-info');
          Panels.current.resolve({
              operation: 'selected',
              info: objInfo
          });

      });
  }

  // Custom localization dropdown filter
  $('.locale-dropdown--toggle').on('click', function(e){
    e.preventDefault();
    $(this).next('.locale-dropdown--options').toggleClass('open');
  });

  $('body').click(function(e) {
    if (!$(e.target).closest('.locale-dropdown').length){
      $('.locale-dropdown--options').removeClass('open');
    }
  });   

});

// Keep focus in panel
// Adapted from https://github.com/udacity/ud891/blob/gh-pages/lesson2-focus/07-modals-and-keyboard-traps/solution/modal.js

$(function() {
    // Find the modal and its overlay
    var modal = document.querySelector('.panel-wrapper-wrapper');

    if (modal) {

        // Listen for and trap the keyboard
        modal.addEventListener('keydown', trapTabKey);

        // Find all focusable children
        var focusableElementsString = 'a[href], area[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), iframe, object, embed, [tabindex="0"], [contenteditable]';
        var focusableElements = modal.querySelectorAll(focusableElementsString);
        // Convert NodeList to Array
        focusableElements = Array.prototype.slice.call(focusableElements);

        var firstTabStop = focusableElements[0];
        var lastTabStop = focusableElements[focusableElements.length - 1];

        // Focus first child
        firstTabStop.focus();

        function trapTabKey(e) {
            // Check for TAB key press
            if (e.keyCode === 9) {

              // SHIFT + TAB
              if (e.shiftKey) {
                if (document.activeElement === firstTabStop) {
                  e.preventDefault();
                  lastTabStop.focus();
                }

              // TAB
              } else {
                if (document.activeElement === lastTabStop) {
                  e.preventDefault();
                  firstTabStop.focus();
                }
              }
            }
        }
    }
});

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

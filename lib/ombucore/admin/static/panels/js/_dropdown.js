/**
 * Dropdown menus (replaces Bootstrap 3's dropdown plugin).
 *
 *   <div class="dropdown">
 *     <a href="#" data-toggle="dropdown" aria-expanded="false">Menu</a>
 *     <div class="dropdown-menu">…</div>
 *   </div>
 *
 * Clicking a [data-toggle="dropdown"] toggles `.open` on its parent and
 * closes any other open dropdown. Clicking elsewhere or pressing Escape
 * closes it; arrow keys move between menu links. The parent element receives
 * `shown.dropdown` and `hidden.dropdown` events.
 *
 * Used by both the site bundle and panels-inside.js, so it is written as a
 * self-contained classic script.
 */
(function ($) {
  'use strict';

  var TOGGLE = '[data-toggle="dropdown"]';
  var KEY_ESCAPE = 27;
  var KEY_SPACE = 32;
  var KEY_UP = 38;
  var KEY_DOWN = 40;

  function close($toggle) {
    var $parent = $toggle.parent();
    if (!$parent.hasClass('open')) return;
    $toggle.attr('aria-expanded', 'false');
    $parent.removeClass('open').trigger($.Event('hidden.dropdown', { relatedTarget: $toggle[0] }));
  }

  function closeAll(e) {
    if (e && e.which === 3) return;
    $(TOGGLE).each(function () {
      var $toggle = $(this);
      var parent = $toggle.parent()[0];
      // Typing into a field inside the menu should not close it.
      if (e && e.type === 'click' && /input|textarea/i.test(e.target.tagName) && $.contains(parent, e.target)) {
        return;
      }
      close($toggle);
    });
  }

  function toggle() {
    var $toggle = $(this);
    if ($toggle.is('.disabled, :disabled')) return;
    var $parent = $toggle.parent();
    var wasOpen = $parent.hasClass('open');
    closeAll();
    if (!wasOpen) {
      $toggle.attr('aria-expanded', 'true').trigger('focus');
      $parent.addClass('open').trigger($.Event('shown.dropdown', { relatedTarget: this }));
    }
    // Stops the click reaching closeAll() and following the toggle's href.
    return false;
  }

  function keydown(e) {
    if ([KEY_ESCAPE, KEY_SPACE, KEY_UP, KEY_DOWN].indexOf(e.which) === -1) return;
    if (/input|textarea/i.test(e.target.tagName)) return;

    var $parent = $(this).closest('.dropdown');
    var $toggle = $parent.find(TOGGLE).first();
    if (!$toggle.length || $toggle.is('.disabled, :disabled')) return;
    e.preventDefault();
    e.stopPropagation();

    var isOpen = $parent.hasClass('open');
    if (e.which === KEY_ESCAPE) {
      if (isOpen) {
        close($toggle);
        $toggle.trigger('focus');
      }
      return;
    }
    if (!isOpen) {
      $toggle.trigger('click');
      return;
    }

    var $items = $parent.find('.dropdown-menu li:not(.disabled):visible a');
    if (!$items.length) return;
    var index = $items.index(e.target);
    if (e.which === KEY_UP && index > 0) index--;
    if (e.which === KEY_DOWN && index < $items.length - 1) index++;
    $items.eq(Math.max(index, 0)).trigger('focus');
  }

  $(document)
    .on('click.dropdown', closeAll)
    .on('click.dropdown', '.dropdown form', function (e) { e.stopPropagation(); })
    .on('click.dropdown', TOGGLE, toggle)
    .on('keydown.dropdown', TOGGLE, keydown)
    .on('keydown.dropdown', '.dropdown-menu', keydown);
})(jQuery);

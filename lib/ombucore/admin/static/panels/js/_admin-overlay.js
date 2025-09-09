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

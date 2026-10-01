// Analysis actions menu: close the popover once an item is chosen.
$(function () {
  $('body').on('click', '.actions-menu__item', function () {
    var popover = this.closest('[popover]');
    if (popover && typeof popover.hidePopover === 'function') {
      popover.hidePopover();
    }
  });
});

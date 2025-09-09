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

// Modals
$(function() {
  var KEYCODE_ESC = 27;

  // Keep focus in navigation
  // Adapted from https://github.com/udacity/ud891/blob/gh-pages/lesson2-focus/07-modals-and-keyboard-traps/solution/el.js

  // Find the modal and its overlay
  var modals = document.getElementsByClassName('help__modal');
  Array.prototype.forEach.call(modals, function(el, index, array){

    // Listen for and trap the keyboard
    el.addEventListener('keydown', trapTabKey);

    // Find all focusable children
    var focusableElementsString = 'a[href], area[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), iframe, object, embed, [tabindex="0"], [contenteditable]';
    var focusableElements = el.querySelectorAll(focusableElementsString);
    // Convert NodeList to Array
    focusableElements = Array.prototype.slice.call(focusableElements);

    var firstTabStop = focusableElements[0];
    var lastTabStop = focusableElements[focusableElements.length - 1];

    var helpButton = $(el).closest('.help').find('.help__button')[0];
    var helpClose = $(el).closest('.help').find('.help__close')[0];
    helpButton.addEventListener('click', openNavigation);
    helpClose.addEventListener('click', closeNavigation);

    function openNavigation() {
      $('.help').removeClass('help__modal--open');
      $(el).closest('.help').addClass('help__modal--open');
      $(el).closest('.help').find('.help__close')[0].focus();
      $('html').on('keyup.navigation', onlyKeyCode(KEYCODE_ESC, closeNavigation));
    }

    function closeNavigation() {
      $('.help__modal').closest('.help').removeClass('help__modal--open');  
      $('html').off('.navigation');
      helpButton.focus();
    }

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
  });

  function calculatePosition() {
    var position;
    var windowWidth;
    var leftPosition;

    $('.help').each(function(){
      position = $(this).offset();
      windowWidth = $(window).outerWidth();

      if ((position.left > (windowWidth / 2))) {
        $(this).addClass('help--right');
      }
      else {
        $(this).removeClass('help--right');
      }
    });
  }

  $(document).ready(function(){
    calculatePosition();
  });

  $(window).resize(function() {
    setTimeout(function(){ calculatePosition(); }, 200);
  }); 

  $('.analysis-table__category-toggle').on('click', function(e){
    calculatePosition();
  });
});

$(function() {
  $('.step-help__button').on('click', function(e){
    $(this).closest('.analysis').removeClass('analysis--guidance-collapsed');      
    $(this).attr('aria-expanded', 'true');
    $(this).closest('.step-help').find('.step-help__close').focus();      
  });

  $('.step-help__close').on('click', function(e){
    $(this).closest('.analysis').addClass('analysis--guidance-collapsed');   
    $(this).closest('.step-help').find('step-help__button').attr('aria-expanded', 'false');
    $(this).closest('.step-help').find('.step-help__button').focus();          
  });
});


$(function () {

  function stepGuideHelpState() {
    var cookieName = 'step_guidance_open'
    $('.step-help__button').on('click', function (evt) {
      setCookie(cookieName, 1, 365)
    });
    $('.step-help__close').on('click', function (evt) {
        setCookie(cookieName, 0, 365)
    });
  }

  stepGuideHelpState()

  function getCookie(name) {
    var v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
    return v ? v[2] : null;
  }

  function setCookie(name, value, days) {
    var d = new Date;
    d.setTime(d.getTime() + 24 * 60 * 60 * 1000 * days);
    document.cookie = name + "=" + value + ";path=/;expires=" + d.toGMTString();
  }

  function deleteCookie(name) {
    setCookie(name, '', -1);
  }
})



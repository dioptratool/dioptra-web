/**
 * Behaviour for FilterableChoiceWidget (website/templates/widgets/filterable-choice.html).
 *
 * At rest the visible input shows the selected option's label. Focusing the field starts a
 * blank search with the whole list open and the current selection highlighted, so typing
 * narrows the options and simply leaving the field keeps whatever is highlighted. Escape
 * abandons the search and leaves the previous selection alone; it dismisses the list without
 * closing the panel, so a second Escape closes the panel. The clear button empties the field.
 * Only listed options can be chosen; the hidden input carries the posted value.
 */
(function () {
  function initField(root) {
    if (root.dataset.filterableChoiceReady) {
      return;
    }
    root.dataset.filterableChoiceReady = 'true';

    var valueInput = root.querySelector('[data-filterable-choice-value]');
    var textInput = root.querySelector('[data-filterable-choice-input]');
    var list = root.querySelector('[data-filterable-choice-list]');
    var toggle = root.querySelector('[data-filterable-choice-toggle]');
    var clearButton = root.querySelector('[data-filterable-choice-clear]');
    if (!valueInput || !textInput || !list) {
      return;
    }

    var options = Array.prototype.slice.call(list.querySelectorAll('.filterable-choice__option'));
    var restingPlaceholder = textInput.getAttribute('placeholder') || '';
    // The value the current search started from: what Escape and an empty query fall back to.
    var searchedFrom = valueInput.value;
    // Set between the keydown and keyup of an Escape that dismissed the list.
    var escaped = false;

    function optionFor(value) {
      if (!value) {
        return null;
      }
      for (var i = 0; i < options.length; i++) {
        if (options[i].dataset.value === value) {
          return options[i];
        }
      }
      return null;
    }

    function matching() {
      return options.filter(function (option) {
        return !option.hidden;
      });
    }

    function highlighted() {
      return list.querySelector('.filterable-choice__option--active:not([hidden])');
    }

    function highlight(option) {
      options.forEach(function (each) {
        each.classList.toggle('filterable-choice__option--active', each === option);
      });
      if (option) {
        textInput.setAttribute('aria-activedescendant', option.id);
        option.scrollIntoView({ block: 'nearest' });
      } else {
        textInput.removeAttribute('aria-activedescendant');
      }
    }

    function filter(query) {
      var wanted = query.trim().toLowerCase();
      options.forEach(function (option) {
        option.hidden =
          wanted !== '' &&
          (option.dataset.value || '').toLowerCase().indexOf(wanted) === -1 &&
          (option.dataset.label || '').toLowerCase().indexOf(wanted) === -1;
      });
    }

    // An empty query is not a choice of the first option: it falls back to the selection.
    function highlightBestMatch() {
      highlight(textInput.value.trim() === '' ? optionFor(searchedFrom) : matching()[0] || null);
    }

    function open() {
      list.hidden = false;
      root.classList.add('filterable-choice--open');
      textInput.setAttribute('aria-expanded', 'true');
    }

    function close() {
      list.hidden = true;
      root.classList.remove('filterable-choice--open');
      textInput.setAttribute('aria-expanded', 'false');
      highlight(null);
    }

    /** Resting state: the selected label in the field, the clear button only when it applies. */
    function rest() {
      var selected = optionFor(valueInput.value);
      textInput.value = selected ? selected.dataset.label : '';
      textInput.setAttribute('placeholder', restingPlaceholder);
      if (clearButton) {
        clearButton.hidden = !selected;
      }
    }

    function commit(option) {
      var value = option ? option.dataset.value : '';
      var changed = valueInput.value !== value;
      valueInput.value = value;
      searchedFrom = value;
      options.forEach(function (each) {
        each.setAttribute('aria-selected', each === option ? 'true' : 'false');
      });
      rest();
      if (changed) {
        valueInput.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }

    /** Start a fresh search: blank query, whole list, current selection highlighted. */
    function startSearch() {
      searchedFrom = valueInput.value;
      escaped = false;
      textInput.value = '';
      if (searchedFrom) {
        // The selection is no longer in the field, so keep it visible behind the search.
        var selected = optionFor(searchedFrom);
        textInput.setAttribute('placeholder', selected ? selected.dataset.label : restingPlaceholder);
      }
      filter('');
      highlightBestMatch();
      open();
    }

    function move(delta) {
      var matches = matching();
      if (!matches.length) {
        return;
      }
      var current = highlighted();
      var index;
      if (current) {
        index = (matches.indexOf(current) + delta + matches.length) % matches.length;
      } else {
        index = delta > 0 ? 0 : matches.length - 1;
      }
      highlight(matches[index]);
    }

    textInput.addEventListener('focus', startSearch);

    textInput.addEventListener('input', function () {
      filter(textInput.value);
      highlightBestMatch();
      open();
    });

    textInput.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (list.hidden) {
          filter(textInput.value);
          open();
        }
        move(event.key === 'ArrowDown' ? 1 : -1);
      } else if (event.key === 'Enter' && !list.hidden) {
        // Choose from the list rather than submitting the panel form.
        event.preventDefault();
        var option = highlighted();
        if (option) {
          commit(option);
        } else {
          rest();
        }
        close();
      } else if (event.key === 'Escape') {
        if (list.hidden) {
          return; // Nothing of ours to dismiss, so let Escape close the panel.
        }
        // Dismiss only the list, keeping the previous selection. Focus stays in the field
        // so the keyup below can be swallowed before it reaches the panels layer.
        event.preventDefault();
        event.stopPropagation();
        escaped = true;
        close();
        rest();
      }
    });

    // The panels layer closes the panel on an Escape keyup at document level, so the keyup
    // that goes with a dismissed list must not get there.
    textInput.addEventListener('keyup', function (event) {
      if (event.key === 'Escape' && escaped) {
        escaped = false;
        event.stopPropagation();
      }
    });

    textInput.addEventListener('blur', function () {
      // A closed list has nothing highlighted, so an Escaped search commits nothing.
      var option = highlighted();
      if (option) {
        commit(option);
      } else {
        rest();
      }
      close();
    });

    // Options are chosen on mousedown, with focus held in the field so no blur races the click.
    list.addEventListener('mousedown', function (event) {
      var option = event.target.closest('.filterable-choice__option');
      if (!option || option.hidden) {
        return;
      }
      event.preventDefault();
      commit(option);
      close();
    });

    if (toggle) {
      toggle.addEventListener('mousedown', function (event) {
        event.preventDefault();
        if (!list.hidden) {
          close();
        } else if (document.activeElement === textInput) {
          startSearch();
        } else {
          textInput.focus(); // Opens through the focus handler.
        }
      });
    }

    if (clearButton) {
      // Keeping focus where it is means clearing never triggers the blur commit.
      clearButton.addEventListener('mousedown', function (event) {
        event.preventDefault();
      });
      clearButton.addEventListener('click', function (event) {
        event.preventDefault();
        // Enter or Space leaves the button focused, and clearing hides it, so hand focus
        // back to the field rather than letting it fall to the top of the page.
        var byKeyboard = document.activeElement === clearButton;
        commit(null);
        if (byKeyboard) {
          textInput.focus(); // Opens a fresh search through the focus handler.
        } else if (document.activeElement === textInput) {
          filter('');
          highlight(null);
          open();
        }
      });
    }

    rest();
  }

  function init() {
    document.querySelectorAll('[data-filterable-choice]').forEach(initField);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  // Panels load their form media in the head, so re-scan for fields added after load.
  window.addEventListener('load', init);
})();

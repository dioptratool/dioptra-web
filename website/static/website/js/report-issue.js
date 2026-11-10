/**
 * The "Report Issue" button (features/_report-issue.html) opens the Jira Service Management
 * widget in place of the widget's own launcher.
 *
 * embed.js writes the widget into a same-origin iframe, #jsd-widget, on DOMContentLoaded. While the
 * widget is closed the iframe holds only its launcher, #help-button, which CSS keeps hidden. Our
 * button clicks that launcher and shows the iframe; when #help-button comes back the widget has
 * been closed, so the iframe is hidden again and our button returns.
 */
var OPEN_CLASS = 'report-issue-open';

function widgetDocument() {
  var iframe = document.getElementById('jsd-widget');
  return iframe && iframe.contentDocument;
}

// Calls back with the widget's launcher, waiting for the widget's app to render it if needed.
function whenLauncherReady(callback) {
  var doc = widgetDocument();
  if (!doc || !doc.body) {
    return false;
  }
  var launcher = doc.getElementById('help-button');
  if (launcher) {
    callback(launcher);
    return true;
  }
  var observer = new MutationObserver(function() {
    var found = doc.getElementById('help-button');
    if (found) {
      observer.disconnect();
      callback(found);
    }
  });
  observer.observe(doc.body, { childList: true, subtree: true });
  return true;
}

// Hides the iframe again once the widget is closed, which brings its launcher back.
function watchForClose(doc) {
  var observer = new MutationObserver(function() {
    if (doc.getElementById('help-button')) {
      observer.disconnect();
      document.documentElement.classList.remove(OPEN_CLASS);
    }
  });
  observer.observe(doc.body, { childList: true, subtree: true });
}

function openWidget() {
  var ready = whenLauncherReady(function(launcher) {
    document.documentElement.classList.add(OPEN_CLASS);
    launcher.click();
    watchForClose(launcher.ownerDocument);
  });
  if (!ready) {
    console.error('Report Issue: the support widget has not loaded.');
  }
}

document.addEventListener('click', function(e) {
  if (e.target.closest('[data-report-issue]')) {
    e.preventDefault();
    openWidget();
  }
});

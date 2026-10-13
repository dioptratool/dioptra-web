/**
 * The page-wide jQuery, built to panels/js/jquery.js and loaded by every base
 * template before any other script. Site, panels and form-widget scripts all
 * use this one global copy.
 *
 * `django.jQuery` is aliased here as well: Django form widgets (e.g.
 * taggit-autosuggest) expect it, and the site overrides
 * admin/js/jquery.init.js so that Django's noConflict() never removes the
 * global.
 */
import jQuery from 'jquery';

window.jQuery = jQuery;
window.$ = jQuery;
window.django = window.django || {};
window.django.jQuery = jQuery;

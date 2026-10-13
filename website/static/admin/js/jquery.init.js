// Overrides django.contrib.admin's admin/js/jquery.init.js, which form
// widgets such as taggit-autosuggest include via their Media. Django's
// version calls jQuery.noConflict(true), which would remove the page-wide
// jQuery (panels/js/jquery.js, which already sets django.jQuery). This
// version leaves the global alone.
var django = django || {};
django.jQuery = django.jQuery || jQuery;

/**
 * Entry point for website/static/website/scripts.js, loaded on every
 * front-end page after the page-wide jQuery (panels/js/jquery.js, built by
 * ombucore) and before panels.js, whose globals such as `Panels` are only
 * used from event handlers.
 *
 * Page-specific scripts that are loaded on their own (insights charts,
 * form widgets) are listed in eslint.config.js and are not imported here.
 */
import '@panels/js/_dropdown.js';

import './global.js';
import './form-helpers.js';
import './loading-triggers.js';
import './analysis-categories.js';
import './analysis-table-nested-checkboxes.js';
import './corrections.js';
import './fix-missing-data.js';
import './categorize-cost_type.js';
import './allocate-bulk.js';
import './ajax-transactions.js';
import './filters.js';
import './actions-menu.js';
import './help.js';
import './table-edit-row.js';
import './analysis-table.js';

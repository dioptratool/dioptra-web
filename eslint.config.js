import js from '@eslint/js';
import globals from 'globals';

// Scripts in website/static/website/js that are loaded on their own (template
// <script> tags or form Media) rather than bundled into scripts.js.
const standaloneSiteScripts = [
  'bulk-allocate-form',
  'content-tabs',
  'duplicate',
  'filterable-choice',
  'insights-charts',
  'intervention-metadata-editor',
  'subcomponent-labels',
].map((name) => `website/static/website/js/${name}.js`);

const browserGlobals = {
  ...globals.browser,
  ...globals.jquery,
};

export default [
  {
    ignores: [
      '**/node_modules/**',
      '**/*.min.js',
      'website/static/website/scripts.js',
      'website/static/lib/**',
      'lib/ombucore/admin/static/panels/lib/**',
      'lib/ombucore/admin/static/panels/js/panels.js',
      'lib/ombucore/admin/static/panels/js/panels-inside.js',
      'lib/ombucore/admin/static/panels/js/jquery.js',
      'lib/ombucore/admin/static/django_ckeditor_5/dist/**',
      'website/static/admin/**',
      'static/**',
      'media/**',
    ],
  },
  js.configs.recommended,
  {
    rules: {
      'no-unused-vars': ['warn', { args: 'none', caughtErrors: 'none' }],
      // Defensive `let x = default; try { x = … } catch { x = default }` is fine.
      'no-useless-assignment': 'off',
    },
  },
  {
    // Build tooling.
    files: ['tools/**/*.mjs', 'lib/ombucore/frontend/*.mjs', 'eslint.config.js'],
    languageOptions: { globals: globals.node },
  },
  {
    // Site bundle: ES modules compiled into website/static/website/scripts.js.
    files: ['website/static/website/js/**/*.js'],
    ignores: ['website/static/website/js/admin/**', ...standaloneSiteScripts],
    languageOptions: {
      sourceType: 'module',
      // Provided by panels.js and page vendor scripts; only used from handlers.
      globals: { ...browserGlobals, Panels: 'readonly', onlyKeyCode: 'readonly', flatpickr: 'readonly' },
    },
  },
  {
    // CKEditor build sources.
    files: ['lib/ombucore/frontend/src/**/*.js'],
    languageOptions: { sourceType: 'module', globals: { ...globals.browser, django: 'readonly', Panels: 'readonly' } },
  },
  {
    // Classic scripts loaded directly with <script> or form Media. They share
    // the page's global scope, so cross-file globals are declared here.
    files: [
      'website/static/website/js/admin/**/*.js',
      ...standaloneSiteScripts,
      'website/static/website/steps/**/*.js',
      'lib/ombucore/**/static/**/*.js',
    ],
    languageOptions: {
      sourceType: 'script',
      globals: {
        ...browserGlobals,
        django: 'readonly',
        Chart: 'readonly',
        Sortable: 'readonly',
        flatpickr: 'readonly',
        Panels: 'writable',
        PanelsAlerts: 'writable',
        getDioptraCurrencySymbol: 'readonly',
        // Helpers defined by _panels-utils.js / _panels-core.js /
        // _filter-lists-form.js and shared through panels.js/panels-inside.js.
        KEYCODES: 'readonly',
        docCookies: 'readonly',
        eventify: 'readonly',
        noop: 'readonly',
        onlyKeyCode: 'readonly',
        onScrollTopAndBottom: 'readonly',
        panelTriggerHandler: 'readonly',
        preventDefault: 'readonly',
        setupFilterListForm: 'readonly',
        stopPropagation: 'readonly',
        // Defined by insights-charts.js, used by content-tabs.js.
        initProgressBar: 'readonly',
      },
    },
    rules: {
      // Classic scripts intentionally define globals for each other.
      'no-unused-vars': 'off',
      'no-redeclare': 'off',
    },
  },
];

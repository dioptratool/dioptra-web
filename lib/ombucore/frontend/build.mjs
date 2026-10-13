#!/usr/bin/env node
/**
 * ombucore asset build: admin panels stylesheets and scripts, the page-wide
 * jQuery, and the CKEditor 5 bundle used by django-ckeditor-5.
 *
 *   node lib/ombucore/frontend/build.mjs [css|js|vendor|ckeditor ...] [--watch]
 *   npm run build -w lib/ombucore/frontend
 *
 * Outputs are generated (not committed) and collected by Django's
 * staticfiles from lib/ombucore/admin/static/.
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';
import * as sass from 'sass';
import { runBuild } from './build-runner.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const STATIC = path.resolve(here, '../admin/static');
const PANELS = `${STATIC}/panels`;
const CKEDITOR_SRC = `${here}/src`;
const CKEDITOR_OUT = `${STATIC}/django_ckeditor_5/dist`;
const JQUERY_ENTRY = `${here}/src/jquery-global.js`;
const JQUERY_OUT = `${PANELS}/js/jquery.js`;

const stylesheets = ['panels', 'panels-relation-widget'].map((name) => ({
  src: `${PANELS}/css/${name}.scss`,
  out: `${PANELS}/css/${name}.css`,
}));

// The panels scripts share a global namespace (Panels, PanelsAlerts and the
// helpers in _panels-utils.js are used by templates and other scripts), so
// they are concatenated in order as classic scripts rather than bundled.
const concatenatedScripts = [
  {
    out: 'panels.js',
    files: ['_panels-utils.js', '_panels-alerts.js', '_panels-core.js'],
  },
  {
    out: 'panels-inside.js',
    files: [
      '_dropdown.js',
      '_panels-utils.js',
      '_panels-alerts.js',
      '_panels-core.js',
      '_panel-form.js',
      '_filter-lists-form.js',
      '_filter-lists.js',
      '_panels-focus.js',
    ],
  },
];

async function buildCss() {
  await Promise.all(
    stylesheets.map(async ({ src, out }) => {
      const result = await sass.compileAsync(src, { style: 'expanded', loadPaths: [STATIC] });
      await writeFile(out, `${result.css}\n`);
    }),
  );
}

async function buildJs() {
  await Promise.all(
    concatenatedScripts.map(async ({ out, files }) => {
      const sources = await Promise.all(files.map((f) => readFile(`${PANELS}/js/${f}`, 'utf8')));
      await writeFile(`${PANELS}/js/${out}`, sources.join('\n'));
    }),
  );
}

async function buildJquery() {
  await esbuild.build({
    entryPoints: [JQUERY_ENTRY],
    outfile: JQUERY_OUT,
    bundle: true,
    format: 'iife',
    target: 'es2020',
    minify: true,
    legalComments: 'eof',
    logLevel: 'warning',
  });
}

async function buildCkeditor() {
  await mkdir(CKEDITOR_OUT, { recursive: true });
  const result = await esbuild.build({
    entryPoints: [`${CKEDITOR_SRC}/ckeditor.js`],
    outfile: `${CKEDITOR_OUT}/bundle.js`,
    bundle: true,
    format: 'iife',
    globalName: 'CKEditor5Bundle',
    target: 'es2020',
    minify: true,
    sourcemap: 'linked',
    sourcesContent: false,
    legalComments: 'eof',
    write: false,
    logLevel: 'warning',
  });
  // django-ckeditor-5 expects the stylesheet at dist/styles.css.
  for (const file of result.outputFiles) {
    const name = path.basename(file.path);
    if (name === 'bundle.css') {
      await writeFile(`${CKEDITOR_OUT}/styles.css`, file.text.replace(/\/\*# sourceMappingURL=.*\*\/\s*$/, ''));
    } else if (name === 'bundle.js' || name === 'bundle.js.map') {
      await writeFile(file.path, file.contents);
    }
  }
}

await runBuild({
  name: 'ombucore',
  groups: { css: buildCss, js: buildJs, vendor: buildJquery, ckeditor: buildCkeditor },
  watchTargets: [
    { dir: `${PANELS}/css`, ext: '.scss', group: 'css' },
    {
      dir: `${PANELS}/js`,
      ext: '.js',
      group: 'js',
      ignore: [...concatenatedScripts.map((s) => s.out), path.basename(JQUERY_OUT)],
    },
    { dir: CKEDITOR_SRC, ext: path.basename(JQUERY_ENTRY), group: 'vendor' },
    { dir: CKEDITOR_SRC, group: 'ckeditor', ignore: [path.basename(JQUERY_ENTRY)] },
  ],
});

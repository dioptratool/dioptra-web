#!/usr/bin/env node
/**
 * Website asset build: site stylesheets (including the in-panel styles,
 * which build on the ombucore panels SCSS), the site script bundle and
 * vendored libraries.
 *
 *   node tools/build-website.mjs [css|js|vendor ...] [--watch]
 *
 * The ombucore assets (panels, CKEditor) have their own build in
 * lib/ombucore/frontend; `npm run build` runs both. Outputs are generated
 * (not committed) and collected by Django's staticfiles.
 */
import { copyFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runBuild } from '@ombucore/frontend/build-runner';
import * as esbuild from 'esbuild';
import * as sass from 'sass';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const r = (...parts) => path.join(root, ...parts);

const WEBSITE = r('website/static/website');
const OMBUCORE_STATIC = r('lib/ombucore/admin/static');
const PANELS = `${OMBUCORE_STATIC}/panels`;

const stylesheets = [
  { src: `${WEBSITE}/css/style.scss`, out: `${WEBSITE}/css/style.css` },
  { src: `${WEBSITE}/css/panels-inside.scss`, out: `${WEBSITE}/css/panels-inside.css` },
  { src: `${WEBSITE}/css/styleguide/styleguide.scss`, out: `${WEBSITE}/css/styleguide.css` },
];

const vendorFiles = [
  { src: r('node_modules/chart.js/dist/chart.umd.min.js'), out: `${WEBSITE}/js/chart.umd.min.js` },
];

async function buildCss() {
  await Promise.all(
    stylesheets.map(async ({ src, out }) => {
      const result = await sass.compileAsync(src, {
        style: 'expanded',
        // `@use 'init'` (website settings) and `@use 'panels/css/…'` resolve
        // from any depth.
        loadPaths: [`${WEBSITE}/css`, OMBUCORE_STATIC],
      });
      await writeFile(out, `${result.css}\n`);
    }),
  );
}

async function buildJs() {
  await esbuild.build({
    entryPoints: [`${WEBSITE}/js/main.js`],
    outfile: `${WEBSITE}/scripts.js`,
    bundle: true,
    format: 'iife',
    target: 'es2020',
    legalComments: 'inline',
    alias: { '@panels': PANELS },
    logLevel: 'warning',
  });
}

async function copyVendor() {
  await Promise.all(vendorFiles.map(({ src, out }) => copyFile(src, out)));
}

await runBuild({
  name: 'website',
  groups: { css: buildCss, js: buildJs, vendor: copyVendor },
  watchTargets: [
    { dir: `${WEBSITE}/css`, ext: '.scss', group: 'css' },
    // panels-inside.css builds on the ombucore panels SCSS.
    { dir: `${PANELS}/css`, ext: '.scss', group: 'css' },
    { dir: `${WEBSITE}/js`, ext: '.js', group: 'js' },
    // scripts.js bundles the panels dropdown.
    { dir: `${PANELS}/js`, ext: '_dropdown.js', group: 'js' },
  ],
});

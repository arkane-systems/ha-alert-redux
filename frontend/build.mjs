// Bundles the card source into the integration package, where Home Assistant serves
// it from. The output is committed so HACS installs need no build step; CI checks
// that it is up to date with the source.
import * as esbuild from "esbuild";
import { readFileSync } from "node:fs";

const manifest = JSON.parse(
  readFileSync(new URL("../custom_components/alert_redux/manifest.json", import.meta.url)),
);

const options = {
  entryPoints: ["src/alert-redux-card.ts"],
  outfile: "../custom_components/alert_redux/frontend/alert-redux-card.js",
  bundle: true,
  format: "esm",
  target: "es2021",
  minify: true,
  legalComments: "none",
  define: { __CARD_VERSION__: JSON.stringify(manifest.version) },
  logLevel: "info",
};

if (process.argv.includes("--watch")) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
} else {
  await esbuild.build(options);
}

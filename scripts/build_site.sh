#!/usr/bin/env bash
# Assemble the published site into _site/ from an ALLOWLIST.
#
# Used by .github/workflows/deploy.yml and for local preview. The repo also
# holds docs, scripts, tests and the Civis manifest, none of which is the site.
# A file not copied here is not published, whatever git tracks.
#
#   bash scripts/build_site.sh            # then: python -m http.server -d _site
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf _site
mkdir -p _site/fonts
cp site/index.html site/embed.js site/embed.css site/chrome.css \
   site/us-states.json site/favicon.svg site/favicon.png site/apple-touch-icon.png \
   _site/
cp site/fonts/figtree-latin.woff2 site/fonts/figtree-latin-ext.woff2 site/fonts/OFL.txt \
   _site/fonts/
cp data/opportunities.json _site/opportunities.json
echo "Built _site/ ($(find _site -type f | wc -l) files)"

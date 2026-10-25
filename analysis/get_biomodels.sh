#!/bin/sh
# Download BioModels release 31 (26 June 2017, the benchmark of reference 24), verify it,
# and extract the 640 curated SBML files to data/r31_curated/.
set -eu
cd "$(dirname "$0")/.."
URL="https://ftp.ebi.ac.uk/pub/databases/biomodels/releases/2017-06-26/BioModels_Database-r31_pub-sbml_files.tar.bz2"
SHA="b6fba03e9441157196cf566b493b64f3e2d08a07294786c672c9518a4c110532"
mkdir -p data
[ -f data/r31.tar.bz2 ] || curl -L --fail -o data/r31.tar.bz2 "$URL"
echo "$SHA  data/r31.tar.bz2" | shasum -a 256 -c -
if [ ! -d data/r31_curated ]; then
  tar -xjf data/r31.tar.bz2 -C data --include='*/curated/*'
  mv data/BioModels_Database-r31_pub-sbml_files/curated data/r31_curated
  rmdir data/BioModels_Database-r31_pub-sbml_files
fi
echo "curated models: $(ls data/r31_curated | wc -l | tr -d ' ')"

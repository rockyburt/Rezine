#!/bin/bash
# This script uninstalls rezine from PREFIX which defaults
# to /usr.

if [ x$PREFIX == x ]; then
  PREFIX=/usr
fi

echo "Uninstalling Rezine from $PREFIX"
rm -rf $PREFIX/lib/rezine
rm -rf $PREFIX/share/rezine
echo "All done."

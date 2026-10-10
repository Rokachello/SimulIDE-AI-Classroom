#!/usr/bin/env bash
# Called automatically by windows-tools.ps1 inside the verified local MSYS2.
set -euo pipefail
export PATH="$(cygpath -u "$SIMULIDE_MINGW_BIN"):/usr/bin:$PATH"
cd "$(cygpath -u "$SIMULIDE_TLS_SOURCE")"
tls_prefix="$(cygpath -m "$SIMULIDE_TLS_PREFIX")"
perl Configure mingw64 shared no-asm no-tests "--prefix=$tls_prefix" "--openssldir=$tls_prefix/ssl"
make -j4
make install_sw

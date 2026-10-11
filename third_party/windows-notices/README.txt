SimulIDE AI uses the upstream SimulIDE GPL/AGPL notices included in the package.
The exact application source revision is recorded in PREBERI.txt and in the title.

Qt 5.15.2 (dynamic libraries): https://download.qt.io/archive/qt/5.15/5.15.2/
Source and license notices: https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v5.15.2
Qt LGPLv3 and GPLv3 texts are included here; retain library notices and source access.

MinGW-w64 / GCC 8.1: official Qt tools_mingw archive qt.tools.win64_mingw810.
GCC runtime uses GPL with the GCC Runtime Library Exception.
Sources: https://gcc.gnu.org/releases.html and https://www.mingw-w64.org/
Notices shipped with the installed compiler are copied into licenses/MinGW.

OpenSSL 1.1 x64: reused from the existing tool cache, or built from the verified
official OpenSSL 1.1.1w source release using MinGW. The current Qt catalog no
longer provides tools_openssl_x64; OpenSSL 3 DLLs are incompatible with Qt 5.15.2.
Source: https://github.com/openssl/openssl/tree/OpenSSL_1_1_1w
OpenSSL's dual OpenSSL/SSLeay license text is included here; notices from the
actual installed archive are also copied when available.

Bootstrap Python, aqtinstall and MSYS2 are development tools only and are not included
in the compiled student ZIP. Python is downloaded from python.org and verified
against its pinned SHA256; aqtinstall is installed from PyPI over verified TLS.
Qt/tool archives are checked against SHA256 served by the official Qt repository.
OpenSSL and MSYS2 archives use pinned SHA256 from their official releases.
MSYS2 installs Perl and make from https://repo.msys2.org with package signature
verification enabled. Its tools are only used to build TLS with the cached Qt MinGW.

The x64 Visual C++ runtime DLLs are reused from the tool cache or supplied by the
official Python 3.12.10 embedded x64 archive. They are deployed alongside OpenSSL,
so a separate system-wide runtime install is not required. Python's accompanying
license is copied when available.
Visual Studio redistributable terms: https://visualstudio.microsoft.com/license-terms/

#!/usr/bin/env bash
# build-xapian-android.sh — cross-compile a pinned xapian-core with the Android
# NDK toolchain and install it into a vcpkg Android triplet root.
#
# Why this exists (design.md D2, full-text-search change): the stock vcpkg
# `xapian` port (1.4.22) fails to configure on the pinned baseline for the
# android triplets whenever the NDK install path contains spaces (e.g.
# `C:\Program Files (x86)\Android\AndroidNDK\...`): its autoconf configure
# word-splits `CC="C:/Program Files/.../clang.exe"` at the space and dies with
# "C:/Program: No such file or directory". Bypassing vcpkg and driving
# xapian's own ./configure directly (with a spaces-free NDK path) avoids this;
# the port's `configure.diff` (a zlib pkg-config workaround) is not needed for
# Android because bionic ships zlib + uuid in the platform.
#
# Usage (from the repo root):
#   scripts/build-xapian-android.sh <ndk-root> <abi> <install-prefix> [workdir]
#
#   ndk-root       Android NDK root (a directory like .../android-ndk-r23c).
#   abi            arm64-v8a | x86_64            (matches app abiFilters)
#   install-prefix vcpkg triplet root to install into, e.g.
#                  <vcpkg-root>/installed/arm64-android. Headers land in
#                  <prefix>/include, the archive in <prefix>/lib/xapian/...
#   workdir        optional scratch/build dir; defaults to "<prefix>/build-xapian".
#
# Requirements: a POSIX shell + GNU make + tar + sed (msys2/cygwin bash on
# Windows, the normal toolchain on Linux CI), and network access on first run.

set -euo pipefail

XAPIAN_VERSION="${XAPIAN_VERSION:-1.4.22}"
XAPIAN_URL="${XAPIAN_URL:-https://oligarchy.co.uk/xapian/${XAPIAN_VERSION}/xapian-core-${XAPIAN_VERSION}.tar.xz}"
XAPIAN_SHA512="60d66adbacbd59622d25e392060984bd1dc6c870f9031765f54cb335fb29f72f6d006d27af82a50c8da2cfbebd08dac4503a8afa8ad51bc4e6fa9cb367a59d29"
XAPIAN_MIN_API="${XAPIAN_MIN_API:-28}" # matches app minSdk

NDK_ROOT="${1:?usage: build-xapian-android.sh <ndk-root> <abi> <install-prefix> [workdir]}"
ABI="${2:?abi (arm64-v8a|x86_64)}"
PREFIX="${3:?install-prefix}"
WORK="${4:-${PREFIX}/build-xapian}"

case "${ABI}" in
  arm64-v8a)
    CLANG_TARGET="aarch64"
    CONFIGURE_HOST="aarch64-linux-android"
    EXTRA_CONFIGURE_ARGS=(ac_cv_have_decl___popcnt=no ac_cv_have_decl___popcnt64=no)
    ;;
  x86_64)
    CLANG_TARGET="x86_64"
    CONFIGURE_HOST="x86_64-linux-android"
    EXTRA_CONFIGURE_ARGS=()
    ;;
  *)
    echo "unsupported ABI: ${ABI} (want arm64-v8a or x86_64)" >&2
    exit 2
    ;;
esac

HOST_TRIPLE=""
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*) HOST_TRIPLE="windows-x86_64" ;;
  Linux*) HOST_TRIPLE="linux-x86_64" ;;
  Darwin*) HOST_TRIPLE="darwin-x86_64" ;;
  *)
    echo "unsupported host OS: $(uname -s)" >&2
    exit 2
    ;;
esac

NDK_BIN="${NDK_ROOT}/toolchains/llvm/prebuilt/${HOST_TRIPLE}/bin"
if [ ! -d "${NDK_BIN}" ]; then
  echo "NDK toolchain not found at ${NDK_BIN}" >&2
  exit 2
fi

# autoconf's configure cannot run toolchain binaries whose paths contain
# spaces: it word-splits `CC="C:/Program Files/.../clang.exe"` at the space
# ("C:/Program: No such file or directory"). When the NDK lives at a
# spaces-free path (CI checks out to ${{ github.workspace }}/ndk) we use the
# NDK wrappers directly; otherwise we drop thin POSIX-sh wrappers into
# ${WORK}/bin (a spaces-free location) that `exec` the real tools with the
# system path quoted. That mirrors what the NDK's own `-clang.cmd` wrapper does
# (adds --target=<triple>) without relying on cmd/mklink quirks.
case "${NDK_BIN}" in
  *' '*) WITH_SPACES=1 ;;
  *)     WITH_SPACES=0 ;;
esac

if [ "${WITH_SPACES}" = "1" ]; then
  TOOL_DIR="${WORK}/bin"
  mkdir -p "${TOOL_DIR}"
  wrap_tool() {
    local name="$1" exe="$2" extra="$3"
    if [ ! -e "${TOOL_DIR}/${name}" ]; then
      cat > "${TOOL_DIR}/${name}" <<EOF
#!/bin/sh
exec "${NDK_BIN}/${exe}" ${extra} "\$@"
EOF
      chmod +x "${TOOL_DIR}/${name}"
    fi
  }
  wrap_tool "${CLANG_TARGET}-clang"          "clang.exe"   "--target=${CLANG_TARGET}-linux-android${XAPIAN_MIN_API}"
  wrap_tool "${CLANG_TARGET}-clang++"        "clang++.exe" "--target=${CLANG_TARGET}-linux-android${XAPIAN_MIN_API}"
  wrap_tool "llvm-ar"                        "llvm-ar.exe"     ""
  wrap_tool "llvm-ranlib"                    "llvm-ranlib.exe" ""
  wrap_tool "llvm-strip"                     "llvm-strip.exe"  ""
  CC="${TOOL_DIR}/${CLANG_TARGET}-clang"
  CXX="${TOOL_DIR}/${CLANG_TARGET}-clang++"
  AR="${TOOL_DIR}/llvm-ar"
  RANLIB="${TOOL_DIR}/llvm-ranlib"
  STRIP="${TOOL_DIR}/llvm-strip"
else
  CC="${NDK_BIN}/${CLANG_TARGET}-linux-android${XAPIAN_MIN_API}-clang"
  CXX="${NDK_BIN}/${CLANG_TARGET}-linux-android${XAPIAN_MIN_API}-clang++"
  AR="${NDK_BIN}/llvm-ar"
  RANLIB="${NDK_BIN}/llvm-ranlib"
  STRIP="${NDK_BIN}/llvm-strip"
  # The NDK clang wrappers are .cmd batch files on Windows, plain executables
  # elsewhere.
  case "${HOST_TRIPLE}" in
    windows*) CC="${CC}.cmd"; CXX="${CXX}.cmd" ;;
  esac
fi

for t in "${CC}" "${CXX}" "${AR}" "${RANLIB}" "${STRIP}"; do
  if [ ! -e "${t}" ] && [ ! -e "${t}.exe" ]; then
    echo "missing NDK tool: ${t}" >&2
    exit 2
  fi
done

SRC_DIR="${WORK}/xapian-core-${XAPIAN_VERSION}"
DL_DIR="${WORK}/downloads"
ARCHIVE="${DL_DIR}/xapian-core-${XAPIAN_VERSION}.tar.xz"

download() {
  mkdir -p "${DL_DIR}"
  if [ -f "${ARCHIVE}" ]; then
    echo "${XAPIAN_SHA512}  ${ARCHIVE}" | sha512sum -c - >/dev/null 2>&1 && return 0
  fi
  echo "downloading ${XAPIAN_URL}"
  (cd "${DL_DIR}" && curl -fsSL -o "xapian-core-${XAPIAN_VERSION}.tar.xz" "${XAPIAN_URL}")
  echo "${XAPIAN_SHA512}  ${ARCHIVE}" | sha512sum -c - || {
    echo "xapian checksum mismatch" >&2
    exit 1
  }
}

extract() {
  if [ -f "${SRC_DIR}/configure" ]; then
    return 0
  fi
  if tar -xf "${ARCHIVE}" -C "${WORK}" 2>/dev/null; then
    return 0
  fi
  # GNU tar needs a separate `xz` binary (absent in stripped msys2 tools
  # roots); prefer the Windows bsdtar when present, then python's tarfile.
  if [ -f /c/Windows/System32/tar.exe ]; then
    /c/Windows/System32/tar.exe -xf "${ARCHIVE}" -C "${WORK}"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys, tarfile; tarfile.open(sys.argv[1], "r:xz").extractall(sys.argv[2])' \
      "${ARCHIVE}" "${WORK}"
    return 0
  fi
  echo "cannot extract ${ARCHIVE}: no xz-capable tar" >&2
  exit 1
}

echo "== xapian ${XAPIAN_VERSION} for ${ABI} -> ${PREFIX} =="
mkdir -p "${PREFIX}"
download
extract

cd "${SRC_DIR}"

# GNU make on Windows uses `SHELL` from the environment. When the invoking
# sh lives at a spaced path (Git for Windows: C:/Program Files/Git/usr/bin/sh),
# autoconf's depcomp/libtool invocations like `$(SHELL) ./depcomp` break:
# "C:/Program: No such file or directory". Prefer a spaces-free sh so those
# $(SHELL) calls work. MSYS2 (C:/msys64) qualifies if present; otherwise fall
# back to whatever sh is on PATH.
FREE_SHELL=""
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    for cand in /c/msys64/usr/bin/sh.exe /c/tools/msys64/usr/bin/sh.exe "$(command -v sh)"; do
      if [ -n "$cand" ] && [ -x "$cand" ]; then
        case "$cand" in
          *' '*) continue ;;   # skip spaced shells
          *) FREE_SHELL="$cand"; echo "using spaces-free shell: $FREE_SHELL"; break ;;
        esac
      fi
    done
    ;;
esac

if [ ! -f "config.status" ]; then
  echo "== configuring (host=${CONFIGURE_HOST}${XAPIAN_MIN_API}) =="
  # -fPIC is required: the static archive is linked into the android shared
  # library (libaurelex.so).
  env \
    CC="${CC}" \
    CXX="${CXX}" \
    AR="${AR}" \
    RANLIB="${RANLIB}" \
    STRIP="${STRIP}" \
    CFLAGS="-fPIC" \
    CXXFLAGS="-fPIC" \
    ./configure \
      --host="${CONFIGURE_HOST}${XAPIAN_MIN_API}" \
      --enable-static \
      --disable-shared \
      --disable-documentation \
      --prefix="${PREFIX}" \
      "${EXTRA_CONFIGURE_ARGS[@]}"
fi

echo "== building =="
MAKE_SHELL=""
if [ -n "$FREE_SHELL" ]; then MAKE_SHELL="SHELL=$FREE_SHELL"; fi
make $MAKE_SHELL -j"${XAPIAN_JOBS:-$(nproc 2>/dev/null || echo 4)}"
echo "== installing =="
make $MAKE_SHELL install

echo "== done: ${PREFIX}/include/xapian.h, ${PREFIX}/lib/libxapian.a =="
ls -l "${PREFIX}/include/xapian.h" "${PREFIX}/lib/libxapian.a"
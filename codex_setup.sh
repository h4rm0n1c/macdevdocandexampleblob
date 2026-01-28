#!/usr/bin/env bash
set -euo pipefail
set +H

# Mac Development Codex reference corpus installer
#
# Goals:
# - Fetch/unpack reference corpora into /opt/*
# - For git resources: pull files ONLY (no history) by doing a shallow clone then deleting .git
# - Idempotent via .installed.ok stamps
# - For integrity-sensitive artifacts: verify .sha256 if provided

# ---------- packages ----------
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  ca-certificates curl git unzip tar zstd poppler-utils

# ---------- helpers ----------
install_zip_dir() {
  local dest_dir="$1"
  local url="$2"

  local zip_name zip_path stamp tmpdir top_count top_entry
  zip_name="$(basename "$url")"
  zip_path="/tmp/${zip_name}"
  stamp="$dest_dir/.installed.ok"
  tmpdir="/tmp/unzip.$$"

  mkdir -p "$dest_dir"

  if [ -e "$stamp" ]; then
    echo "[setup] Already installed: $dest_dir"
    return 0
  fi

  echo "[setup] Downloading $(basename "$dest_dir")"
  curl -fL --retry 3 --retry-delay 2 -o "$zip_path" "$url"

  rm -rf "$tmpdir"
  mkdir -p "$tmpdir"

  echo "[setup] Unzipping into staging: $tmpdir"
  unzip -q -o "$zip_path" -d "$tmpdir"

  top_count="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')"
  if [ "$top_count" = "1" ]; then
    top_entry="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print)"
    if [ -d "$top_entry" ]; then
      echo "[setup] Installing contents of $(basename "$top_entry") -> $dest_dir"
      cp -a "$top_entry"/. "$dest_dir"/
    else
      echo "[setup] Installing single file -> $dest_dir"
      cp -a "$top_entry" "$dest_dir"/
    fi
  else
    echo "[setup] Installing multiple top-level entries -> $dest_dir"
    cp -a "$tmpdir"/. "$dest_dir"/
  fi

  rm -rf "$tmpdir" || true
  rm -f "$zip_path" || true

  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$stamp"
  echo "[setup] Installed: $dest_dir"
}

install_tgz_dir() {
  local dest_dir="$1"
  local url="$2"

  local tgz_name tgz_path stamp tmpdir top_count top_entry
  tgz_name="$(basename "$url")"
  tgz_path="/tmp/${tgz_name}"
  stamp="$dest_dir/.installed.ok"
  tmpdir="/tmp/tar.$$"

  mkdir -p "$dest_dir"

  if [ -e "$stamp" ]; then
    echo "[setup] Already installed: $dest_dir"
    return 0
  fi

  echo "[setup] Downloading $(basename "$dest_dir")"
  curl -fL --retry 3 --retry-delay 2 -o "$tgz_path" "$url"

  rm -rf "$tmpdir"
  mkdir -p "$tmpdir"

  echo "[setup] Extracting into staging: $tmpdir"
  tar -xzf "$tgz_path" -C "$tmpdir"

  top_count="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')"
  if [ "$top_count" = "1" ]; then
    top_entry="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print)"
    if [ -d "$top_entry" ]; then
      echo "[setup] Installing contents of $(basename "$top_entry") -> $dest_dir"
      cp -a "$top_entry"/. "$dest_dir"/
    else
      echo "[setup] Installing single file -> $dest_dir"
      cp -a "$top_entry" "$dest_dir"/
    fi
  else
    echo "[setup] Installing multiple top-level entries -> $dest_dir"
    cp -a "$tmpdir"/. "$dest_dir"/
  fi

  rm -rf "$tmpdir" || true
  rm -f "$tgz_path" || true

  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$stamp"
  echo "[setup] Installed: $dest_dir"
}

install_tar_zst_dir() {
  local dest_dir="$1"
  local url="$2"

  local arc_name arc_path stamp tmpdir top_count top_entry
  arc_name="$(basename "$url")"
  arc_path="/tmp/${arc_name}"
  stamp="$dest_dir/.installed.ok"
  tmpdir="/tmp/tarzst.$$"

  mkdir -p "$dest_dir"

  if [ -e "$stamp" ]; then
    echo "[setup] Already installed: $dest_dir"
    return 0
  fi

  echo "[setup] Downloading $(basename "$dest_dir")"
  curl -fL --retry 3 --retry-delay 2 -o "$arc_path" "$url"

  rm -rf "$tmpdir"
  mkdir -p "$tmpdir"

  echo "[setup] Extracting .tar.zst into staging: $tmpdir"
  tar --use-compress-program=zstd -xf "$arc_path" -C "$tmpdir"

  top_count="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')"
  if [ "$top_count" = "1" ]; then
    top_entry="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print)"
    if [ -d "$top_entry" ]; then
      echo "[setup] Installing contents of $(basename "$top_entry") -> $dest_dir"
      cp -a "$top_entry"/. "$dest_dir"/
    else
      echo "[setup] Installing single file -> $dest_dir"
      cp -a "$top_entry" "$dest_dir"/
    fi
  else
    echo "[setup] Installing multiple top-level entries -> $dest_dir"
    cp -a "$tmpdir"/. "$dest_dir"/
  fi

  rm -rf "$tmpdir" || true
  rm -f "$arc_path" || true

  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$stamp"
  echo "[setup] Installed: $dest_dir"
}

install_tar_zst_dir_with_sha256() {
  # Download <url> and <url>.sha256, verify, then extract.
  # Expects sha file format: "<hash>  <filename>"
  local dest_dir="$1"
  local url="$2"
  local sha_url="${3:-$2.sha256}"

  local arc_name arc_path sha_name sha_path stamp tmpdir top_count top_entry
  arc_name="$(basename "$url")"
  arc_path="/tmp/${arc_name}"
  sha_name="$(basename "$sha_url")"
  sha_path="/tmp/${sha_name}"
  stamp="$dest_dir/.installed.ok"
  tmpdir="/tmp/tarzst.$$"

  mkdir -p "$dest_dir"

  if [ -e "$stamp" ]; then
    echo "[setup] Already installed: $dest_dir"
    return 0
  fi

  echo "[setup] Downloading $(basename "$dest_dir") + sha256"
  curl -fL --retry 3 --retry-delay 2 -o "$arc_path" "$url"
  curl -fL --retry 3 --retry-delay 2 -o "$sha_path" "$sha_url"

  echo "[setup] Verifying sha256"
  # Verify in /tmp so the filename in the .sha256 matches (it references the archive basename)
  (
    cd /tmp
    sha256sum -c "$sha_name"
  )

  rm -rf "$tmpdir"
  mkdir -p "$tmpdir"

  echo "[setup] Extracting .tar.zst into staging: $tmpdir"
  tar --use-compress-program=zstd -xf "$arc_path" -C "$tmpdir"

  top_count="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')"
  if [ "$top_count" = "1" ]; then
    top_entry="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -print)"
    if [ -d "$top_entry" ]; then
      echo "[setup] Installing contents of $(basename "$top_entry") -> $dest_dir"
      cp -a "$top_entry"/. "$dest_dir"/
    else
      echo "[setup] Installing single file -> $dest_dir"
      cp -a "$top_entry" "$dest_dir"/
    fi
  else
    echo "[setup] Installing multiple top-level entries -> $dest_dir"
    cp -a "$tmpdir"/. "$dest_dir"/
  fi

  rm -rf "$tmpdir" || true
  rm -f "$arc_path" "$sha_path" || true

  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$stamp"
  echo "[setup] Installed: $dest_dir"
}

install_git_snapshot_dir() {
  # Fetch a repo as FILES ONLY (no version history):
  # - shallow clone depth=1, single branch, no tags
  # - then REMOVE .git and install into dest_dir
  #
  # Args:
  #   dest_dir  repo_url  [ref]
  # Where ref may be a branch name, tag, or commit-ish (default: HEAD of default branch)
  local dest_dir="$1"
  local repo_url="$2"
  local ref="${3:-}"

  local stamp tmpdir
  stamp="$dest_dir/.installed.ok"
  tmpdir="/tmp/gitsnap.$$"

  mkdir -p "$dest_dir"

  if [ -e "$stamp" ]; then
    echo "[setup] Already installed: $dest_dir"
    return 0
  fi

  rm -rf "$tmpdir"
  mkdir -p "$tmpdir"

  echo "[setup] Snapshotting repo (no history): $(basename "$dest_dir")"
  # Clone into tmpdir/repo
  if [[ -n "$ref" ]]; then
    git clone --depth 1 --single-branch --no-tags --branch "$ref" "$repo_url" "$tmpdir/repo"
  else
    git clone --depth 1 --single-branch --no-tags "$repo_url" "$tmpdir/repo"
  fi

  # Strip git metadata (this is the key “no version data” requirement)
  rm -rf "$tmpdir/repo/.git"

  echo "[setup] Installing snapshot -> $dest_dir"
  cp -a "$tmpdir/repo"/. "$dest_dir"/

  rm -rf "$tmpdir" || true

  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$stamp"
  echo "[setup] Installed: $dest_dir"
}

# ---------- GitHub release blob ----------
REL_BASE="https://github.com/h4rm0n1c/macdevdocandexampleblob/releases/download/thedocblob"

# Interfaces & Libraries (headers / libs; reference only)
install_zip_dir "/opt/Interfaces&Libraries" "${REL_BASE}/Interfaces.Libraries_3.6.zip"

# Latest Notes From Apple (release notes / docs; reference only)
install_zip_dir "/opt/Latest Notes From Apple" "${REL_BASE}/Latest.Notes.from.Apple.zip"

# MPW 3.6 (examples/demos/docs; reference only)
install_zip_dir "/opt/MPW" "${REL_BASE}/MPW.zip"

# Classic Mac Dev Docs corpus (ReadableOverlay; reference only)
install_tar_zst_dir "/opt/MacDevDocs" "https://github.com/h4rm0n1c/macdevdocandexampleblob/releases/download/thedocblobupdate1/ReadableOverlay-20251229.tar.zst"

# Appearance SDK 1.0.4 (ReadableOverlay capsule + sha256; reference only)
install_tar_zst_dir_with_sha256 "/opt/AppearanceSDK" \
  "${REL_BASE}/AppearanceSDK-1.0.4-ReadableOverlay.tar.zst" \
  "${REL_BASE}/AppearanceSDK-1.0.4-ReadableOverlay.tar.zst.sha256"

# Curated Classic Mac examples shortlist (reference only)
install_tgz_dir "/opt/MacExamples" "${REL_BASE}/MacVox68_Codex_Shortlist_Extracted.tgz"

# ---------- git resources (files-only snapshots; no history) ----------
# Retro68 (reference only)
install_git_snapshot_dir "/opt/Retro68" "https://github.com/autc04/Retro68"

# System 7.1 source reference (files-only snapshot; no history)
install_git_snapshot_dir "/opt/sys71src" "https://github.com/laniku/sys71src"

#Basilisk 2 most updated and recent fork, also useful for system reference data/hardware info in code form, notes about hardware bugs, possible beneficiary of anything discovered by this agent while doing other tasks to be considered as an aside note if things are stumbled upon that could improve then project. Basilisk 2 gives out error codes when it crashes and logs/dumps as well, could be useful info to have.
if [ ! -d /opt/KanjiTalkBasilisk2Fork/.git ]; then
  git clone --depth=1 https://github.com/kanjitalk755/macemu.git /opt/KanjiTalkBasilisk2Fork
else
  git -C /opt/KanjiTalkBasilisk2Fork pull --ff-only
fi


echo "[setup] Done."

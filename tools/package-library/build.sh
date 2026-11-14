#!/bin/bash
set -euo pipefail

tool_root="$(cd "$(dirname "$0")" && pwd)"
assets_dir="${1:-$tool_root/../../.lab/release-assets}"
output_dir="$tool_root/../../.lab/package-library"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
stage_dir="$(mktemp -d "$output_dir/build.XXXXXXXX")"
trap 'rm -rf "$stage_dir"' EXIT

app_name='A7M3 Package Library.app'
app_dir="$stage_dir/$app_name"
archive_name='A7M3-Package-Library-macOS.zip'
resource_dir="$app_dir/Contents/Resources/Releases"
mkdir -p "$app_dir/Contents/MacOS" "$resource_dir"
cp "$tool_root/Info.plist" "$app_dir/Contents/Info.plist"
cp "$assets_dir/v0.01/Sony_A7M3-v0.01.zip" "$resource_dir/Sony_A7M3-v0.01-r5.zip"
cp "$assets_dir/v0.01-r6/Sony_A7M3-v0.01.zip" "$resource_dir/Sony_A7M3-v0.01-r6.zip"
cp "$assets_dir/v0.01-r7/Sony_A7M3-v0.01.zip" "$resource_dir/Sony_A7M3-v0.01-r7.zip"

sdk_path="$(xcrun --sdk macosx --show-sdk-path)"
for arch in arm64 x86_64; do
    xcrun --sdk macosx swiftc -O -swift-version 6 \
        -module-cache-path "$output_dir/module-cache-$arch" \
        -sdk "$sdk_path" -target "$arch-apple-macosx13.0" \
        "$tool_root/Verifier.swift" "$tool_root/Simulator.swift" "$tool_root/main.swift" \
        -o "$stage_dir/A7M3PackageLibrary-$arch"
done
xcrun lipo -create "$stage_dir/A7M3PackageLibrary-arm64" "$stage_dir/A7M3PackageLibrary-x86_64" \
    -output "$app_dir/Contents/MacOS/A7M3PackageLibrary"
/usr/bin/codesign --force --sign - "$app_dir"
"$app_dir/Contents/MacOS/A7M3PackageLibrary" --catalog
/usr/bin/ditto -c -k --keepParent "$app_dir" "$stage_dir/$archive_name"
/usr/bin/ditto "$app_dir" "$output_dir/$app_name"
mv -f "$stage_dir/$archive_name" "$output_dir/$archive_name"
printf '%s\n' "$output_dir/$app_name" "$output_dir/$archive_name"

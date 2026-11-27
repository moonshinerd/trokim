#!/usr/bin/env bash
# Compila o app como Flutter Web numa pasta temporária e o serve na porta 8091.
# Uso: mobile/homologacao/preparar_web.sh [pasta-temporária]
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
W="${1:-$(mktemp -d)}"
mkdir -p "$W"
cd "$W"
cp "$MOBILE/pubspec.yaml" "$MOBILE/pubspec.lock" .
ln -sfn "$MOBILE/lib" lib
ln -sfn "$MOBILE/assets" assets
mkdir -p web_entry
cp "$MOBILE/homologacao/main_web.dart" web_entry/main_web.dart
flutter create --platforms=web --project-name trokim . >/dev/null
flutter pub get >/dev/null
flutter build web -t web_entry/main_web.dart --dart-define=API_BASE_URL=http://localhost:8010/v1
echo "App em http://localhost:8091 (pasta $W)"
exec python3 -m http.server 8091 -d "$W/build/web"

# SecureClick Android ekran görüntüsü yardımcıları (source ile kullanılır)
export ANDROID_HOME=~/Library/Android/sdk
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
export JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home
PKG=tr.edu.erdogan.secureclick
OUT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)/mobil"
SPD="${TMPDIR:-/tmp}/secureclick-shots"; mkdir -p "$SPD"
PY=python3
mkdir -p "$OUT"

shot() { adb exec-out screencap -p > "$OUT/$1.png" && echo "✓ $1.png"; }

ui_dump() { adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb pull /sdcard/ui.xml "$SPD/ui.xml" >/dev/null 2>&1; }

# Metni (veya içerik açıklamasını) içeren öğenin merkezine dokun
tap_text() {
  ui_dump
  local xy
  xy=$($PY - "$SPD/ui.xml" "$1" <<'EOF'
import sys, re, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot(); want = sys.argv[2]
for n in root.iter("node"):
    if want in (n.get("text") or "") or want in (n.get("content-desc") or ""):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        print((x1 + x2) // 2, (y1 + y2) // 2); break
EOF
)
  [ -z "$xy" ] && { echo "bulunamadı: $1"; return 1; }
  adb shell input tap $xy
}

# Ekranda verilen metin görünene kadar bekle (en fazla $2 sn)
wait_text() {
  local t=0
  while [ $t -lt ${2:-30} ]; do
    ui_dump
    grep -q "$1" "$SPD/ui.xml" && return 0
    sleep 1; t=$((t + 1))
  done
  echo "zaman aşımı: $1"; return 1
}

share_text() {
  adb shell am start -a android.intent.action.SEND -t text/plain \
    --es android.intent.extra.TEXT "'$1'" -n $PKG/.MainActivity >/dev/null
}

scroll_down() { adb shell input swipe 540 1900 540 ${1:-700} 500; sleep 1; }
scroll_top() { for i in 1 2 3; do adb shell input swipe 540 700 540 2000 200; done; sleep 1; }

_demo() { adb shell am broadcast -a com.android.systemui.demo -e command "$@" >/dev/null; }
demo_on() {
  adb shell settings put global sysui_demo_allowed 1
  _demo enter
  _demo clock -e hhmm 1041
  _demo battery -e level 100 -e plugged false
  _demo network -e wifi show -e level 4 -e fully true
  _demo network -e mobile show -e datatype none -e level 4
  _demo notifications -e visible ${1:-false}
}
demo_off() { adb shell am broadcast -a com.android.systemui.demo -e command exit >/dev/null; }

# Uygulama ayarlarını doğrudan yaz (debug derlemede run-as ile)
write_prefs() {  # $1=sunucu $2=sms_guard(true/false)
  adb shell am force-stop $PKG
  printf "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n    <string name=\"server\">%s</string>\n    <boolean name=\"sms_guard\" value=\"%s\" />\n    <boolean name=\"live_checks\" value=\"false\" />\n</map>\n" "$1" "$2" > "$SPD/prefs.xml"
  adb push "$SPD/prefs.xml" /data/local/tmp/prefs.xml >/dev/null
  adb shell "run-as $PKG sh -c 'mkdir -p shared_prefs && cp /data/local/tmp/prefs.xml shared_prefs/secureclick.xml'"
}

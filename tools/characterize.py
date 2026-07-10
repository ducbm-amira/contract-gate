#!/usr/bin/env python3
"""Port characterization harness (v0 — phác).

Ý tưởng: NGUỒN SỰ THẬT = legacy. Trích cơ học đơn vị từ Vue → tự kiểm React đang chạy
→ lôi ra chỗ THIẾU mà không cần người map tay. 3 lớp:

  [A] Feature coverage (observable, runtime): mọi nhãn JP trong template legacy
      → có render trong React /deal/map không? (bắt "sót cả mảng hiển thị")
  [B] Wiring coverage (static): mọi prop/emit của component legacy
      → tên đó có xuất hiện trong source React map không? (bắt "sót prop/emit/wiring")
  [C] Side-effect (static list): store.dispatch / api call legacy → liệt kê để đối chiếu.

Exit ≠ 0 nếu còn đơn vị ❌ chưa giải thích → "BUILD chưa xong".
Chạy: <gate-venv>/python characterize.py
"""
from __future__ import annotations
import re, sys, os, json, argparse
from pathlib import Path

# ---- cấu hình qua CLI (default = map port) — subagent trỏ vào trang bất kỳ ----
def _args():
    p = argparse.ArgumentParser(prog="characterize", description="Port coverage harness (v0)")
    p.add_argument("--legacy-root", default="/home/grayf/Projects/estimate")
    p.add_argument("--react-dir",   default="/home/grayf/Projects/estimate-client-sdd/src/views/map")
    p.add_argument("--url",         default="http://localhost:3000/deal/map")
    p.add_argument("--legacy-files", default="src/views/PropertiesView.vue,src/components/gmap/GmapResult.vue,src/components/gmap/GmapLayerSelect.vue",
                   help="comma-separated, relative to --legacy-root")
    p.add_argument("--no-runtime", action="store_true", help="bỏ qua lớp [A] runtime (khi app không chạy)")
    return p.parse_args()

_A = _args()
LEGACY = Path(_A.legacy_root)
REACT  = Path(_A.react_dir)
URL    = _A.url
LEGACY_FILES = [f.strip() for f in _A.legacy_files.split(",") if f.strip()]
# nhãn quá chung → bỏ khỏi feature-check (nhiễu)
STOP = {"OK","NEW","ー","−","-","円","㎡"}

CJK = re.compile(r"[぀-ヿ一-鿿]")

def read(p):
    try: return (LEGACY/p).read_text(encoding="utf-8")
    except Exception: return ""

# ---------- EXTRACT (chiều legacy) ----------
def extract_features(src: str) -> set[str]:
    """Nhãn JP quan sát được: text node template + chuỗi có CJK."""
    feats = set()
    # text giữa các tag > ... <
    for m in re.findall(r">([^<>{}]+)<", src):
        t = m.strip()
        if t and CJK.search(t) and len(t) <= 12 and not t.startswith("{{"):
            feats.add(t)
    # chuỗi 'literal' / "literal" chứa CJK (label trong script/const)
    for m in re.findall(r"""['"]([^'"]{1,12})['"]""", src):
        t = m.strip()
        if t and CJK.search(t):
            feats.add(t)
    return {f for f in feats if f not in STOP}

def extract_props_emits(src: str) -> tuple[set[str], set[str]]:
    props, emits = set(), set()
    # defineProps<{ a?: X; b: Y }>
    for block in re.findall(r"defineProps<\{(.+?)\}>", src, re.S):
        props |= set(re.findall(r"([A-Za-z_$][\w$]*)\s*\??\s*:", block))
    # props: { a, b } (options api)
    for block in re.findall(r"props:\s*\{(.+?)\}", src, re.S):
        props |= set(re.findall(r"([A-Za-z_$][\w$]*)\s*:", block))
    # $emit('name') + defineEmits
    emits |= set(re.findall(r"""\$emit\(\s*['"]([\w:-]+)['"]""", src))
    for block in re.findall(r"defineEmits<\{(.+?)\}>", src, re.S):
        emits |= set(re.findall(r"([A-Za-z_$][\w$:-]*)\s*:", block))
    for block in re.findall(r"defineEmits\(\s*\[(.+?)\]", src, re.S):
        emits |= set(re.findall(r"""['"]([\w:-]+)['"]""", block))
    return props, emits

def extract_sideeffects(src: str) -> set[str]:
    se = set()
    se |= set(re.findall(r"""store\.dispatch\(\s*['"]([\w/]+)['"]""", src))
    se |= set(re.findall(r"""(by_lat_lng|client_action_logs|[\w/]*_seen)""", src))
    return se

# ---------- CHECK React static ----------
def react_source_blob() -> str:
    buf = []
    for root,_,files in os.walk(REACT):
        for f in files:
            if f.endswith((".tsx",".ts")):
                try: buf.append((Path(root)/f).read_text(encoding="utf-8"))
                except Exception: pass
    return "\n".join(buf)

def check_wiring(names: set[str], blob: str) -> dict:
    return {n: (n in blob) for n in sorted(names)}

# ---------- CHECK React runtime (Playwright) ----------
def check_features_runtime(features: set[str]) -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width":1440,"height":900}).new_page()
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        try: pg.wait_for_selector("div.gm-style", timeout=15000)
        except Exception: pass
        pg.wait_for_timeout(3500)
        text = pg.inner_text("body")
        b.close()
    return {f: (f in text) for f in sorted(features)}

# ---------- RUN ----------
def main():
    blob_src = "\n".join(read(f) for f in LEGACY_FILES)
    features = extract_features(blob_src)
    props, emits = set(), set()
    for f in LEGACY_FILES:
        pr, em = extract_props_emits(read(f)); props|=pr; emits|=em
    sideeffects = extract_sideeffects(blob_src)

    react_blob = react_source_blob()
    wiring = check_wiring(props|emits, react_blob)
    feat_rt = {f: True for f in features} if _A.no_runtime else check_features_runtime(features)

    def line(sym, name, extra=""): print(f"  {sym} {name}{extra}")
    miss_feat = [k for k,v in feat_rt.items() if not v]
    miss_wire = [k for k,v in wiring.items() if not v]

    print("\n===== [A] FEATURE COVERAGE (nhãn legacy → React DOM runtime) =====")
    print(f"  legacy features: {len(feat_rt)} | ✅ thấy: {len(feat_rt)-len(miss_feat)} | ❌ THIẾU: {len(miss_feat)}")
    for k in miss_feat: line("❌", k)
    print("\n===== [B] WIRING COVERAGE (prop/emit legacy → source React) =====")
    print(f"  props+emits: {len(wiring)} | ✅: {len(wiring)-len(miss_wire)} | ❌ vắng tên: {len(miss_wire)}")
    for k in miss_wire: line("❌", k, "  (prop/emit legacy không thấy tên trong src/views/map)")
    print("\n===== [C] SIDE-EFFECT legacy (đối chiếu tay/char-test) =====")
    for s in sorted(sideeffects): line("•", s)

    total_gap = len(miss_feat) + len(miss_wire)
    print(f"\n===== VERDICT: {total_gap} đơn vị ❌ cần adjudicate =====")
    print("  ❌ = candidate gap (có thể THẬT / reword / dynamic) → người chỉ DUYỆT, không phải tự phát hiện.")
    sys.exit(1 if total_gap else 0)

if __name__ == "__main__":
    main()

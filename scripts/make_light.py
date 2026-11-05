"""Derive light-mode copies of the hand-written cards: assets/X.svg -> assets/X-light.svg.
Re-run after editing any dark card."""
import re

SWAP = {
    "#0a0e16": "#ffffff", "#121a2a": "#f3f6fb", "#1b2433": "#eef2f7",
    "#e6edf3": "#111827", "#c9d4e5": "#374151", "#7d8ba3": "#6b7280", "#5b6b85": "#9ca3af",
    "#ffffff": "#000000", '"#fff"': '"#111827"',
    "#3fd560": "#1a7f37", "#9be9a8": "#1a7f37", "#28c840": "#1a7f37",
    "#ffb38f": "#c2410c", "#9fdcf4": "#0369a1", "#FF9F45": "#ea580c", "#febc2e": "#b45309",
}
PATTERN = re.compile("|".join(re.escape(k) for k in SWAP))

for name in ["header", "stack", "marathon"]:
    s = open(f"assets/{name}.svg", encoding="utf-8").read()
    s = PATTERN.sub(lambda m: SWAP[m.group(0)], s)  # single pass so swaps never chain
    open(f"assets/{name}-light.svg", "w", encoding="utf-8").write(s)

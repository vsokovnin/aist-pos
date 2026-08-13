#!/usr/bin/env python3
"""Эхо вопрос-варианты: общих 2-грамм быть не должно."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inputs import ROOT  # noqa: E402


def norm(s):
    s = s.lower().replace("ё", "е")
    return [w for w in re.sub(r"[^а-я0-9 ]", " ", s).split() if len(w) > 2]


def bigrams(ws):
    return set(zip(ws, ws[1:]))


def run():
    text = (ROOT / "rubric" / "aist-pos-rubric.yaml").read_text(encoding="utf-8")
    bad = []
    for b in re.split(r"\n  - id: ", "\n" + text.partition("capabilities:")[2])[1:]:
        cid = b.split("\n", 1)[0].strip()
        ask = re.search(r'\n    ask: "(.*?)"\n', b, re.S)
        if not ask:
            continue
        a = bigrams(norm(ask.group(1)))
        for lvl, t in re.findall(r'^      (L[1-5]): "(.*)"$', b, re.M):
            hit = a & bigrams(norm(t))
            if hit:
                bad.append("%s/%s: %s" % (cid, lvl, sorted(hit)))
    if bad:
        print("эхо вопрос-вариант:")
        [print("  ·", x) for x in bad]
        sys.exit(1)
    print("эха нет: вопрос и варианты не делят 2-грамм")


if __name__ == "__main__":
    run()

# Включается в pack.sh после прохода по 18 (Task 13): python3 "$repo/scripts/audit/echo-check.py" || exit 1

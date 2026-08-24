import json
import sys
from collections import Counter

sys.path.insert(0, ".")

from fuckmark.transforms import content_region_coverage_transform_registry
from fuckmark.transforms.effectiveness_profile import zrd_destruction_transform_registry


def main() -> int:
    corpus = json.load(open("artifacts/cycle5-dev-corpus-710k.json", encoding="utf-8"))
    targets = {5: "sample_5", 12: "sample_12"}
    for entry in corpus["samples"]:
        if entry["index"] not in targets:
            continue
        text = entry["text"]
        print(f"===== {targets[entry['index']]} =====")
        print(repr(text[:340]))
        quotes = text.count('"') + text.count("\u201c") + text.count("\u201d")
        print("quote_marks:", quotes)
        for label, registry in (("coverage", content_region_coverage_transform_registry()), ("zrd", zrd_destruction_transform_registry())):
            enum = registry.enumerate(text)
            rejections = Counter(r.reason.value for r in enum.rejections)
            print(f"[{label}] candidates={len(enum.candidates)} rejections={dict(rejections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

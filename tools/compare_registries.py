import json

a = json.load(open("artifacts/cycle5-scored-coverage.json", encoding="utf-8"))
b = json.load(open("artifacts/cycle5-scored-zrd.json", encoding="utf-8"))
print("registry comparison on identical frozen texts (v4 arm):")
header = ("idx", "cov_v4", "zrd_v4", "cov_sel", "zrd_sel", "cov_leak", "zrd_leak")
print("{:>4} {:>8} {:>8} {:>7} {:>7} {:>8} {:>8}".format(*header))
for ra, rb in zip(a["rows"], b["rows"]):
    assert ra["text_sha256"] == rb["text_sha256"]
    print(
        "{:>4} {:>8.4f} {:>8.4f} {:>7} {:>7} {:>8} {:>8}".format(
            ra["index"],
            ra["v4"]["score"],
            rb["v4"]["score"],
            ra["v4"]["selected"],
            rb["v4"]["selected"],
            ra["v4"]["closure_leaks"],
            rb["v4"]["closure_leaks"],
        )
    )
print()
print("coverage detected:", a["summary"]["v4"]["detected"], "| zrd detected:", b["summary"]["v4"]["detected"])
det_zrd = [(r["index"], r["domain"]) for r in b["rows"] if r["v4"]["detected"]]
print("zrd-detected rows:", det_zrd)
for r in b["rows"]:
    if r["v4"]["detected"]:
        print("  row", r["index"], "v4:", json.dumps(r["v4"]))

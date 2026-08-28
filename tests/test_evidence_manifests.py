from pathlib import Path

from fuckmark.hashing import sha256_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[1]
CRLF_README = ROOT / "evidence/cycle7-stage-a-2026-08-25/README.md"
CRLF_DIGEST = "833d1d94fcea01bc09855f0af3a4bcc18df1010065fb3e2825f8e2e31733c2eb"
LF_DIGEST = "d7b7de433f5ca231ef2d9de586774ffdfe255b1625f902fa0bf9780019d62709"


def test_every_sha256sums_entry_matches_or_has_provenance() -> None:
    manifests = tuple(sorted(ROOT.glob("evidence/**/SHA256SUMS.txt")))
    assert manifests
    for manifest in manifests:
        folder = manifest.parent
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, name = line.split()
            path = folder / name
            assert path.is_file(), path
            actual = sha256_file(path)
            if path.resolve() == CRLF_README.resolve() and digest == CRLF_DIGEST:
                assert actual == LF_DIGEST
                assert sha256_bytes(path.read_bytes().replace(b"\n", b"\r\n")) == CRLF_DIGEST
                continue
            assert actual == digest, path


def test_cycle8_archive_pointers_exist() -> None:
    assert (ROOT / "docs/cycle8/gate-v2.md").is_file()
    assert (ROOT / "docs/cycle8/mix-second-model-transfer.md").is_file()
    distil = (ROOT / "evidence/cycle8-mix-distilgpt2-1090000-n16-2026-08-27/README.md").read_text(encoding="utf-8")
    h16 = (ROOT / "evidence/h16-local/README.md").read_text(encoding="utf-8")
    assert "docs/cycle8/mix-second-model-transfer.md" in distil
    assert "docs/cycle8/gate-v2.md" in h16
    assert (ROOT / "docs/limits.md").is_file()
    assert (ROOT / "docs/website.md").is_file()
    assert (ROOT / "docs/demo.html").is_file()
    website = (ROOT / "docs/website.md").read_text(encoding="utf-8")
    assert "| sh" not in website
    assert "| iex" not in website
    assert "curl -fsSL https://d.q1z.org/mark | sh" not in website
    assert "demo.html" in website

# v0.1.0 Release Process

FuckMark v0.1.0 is a research-harness and deterministic CLI release. Publishing the software does not authorize claims of watermark removal, universal undetectability, unknown-key transfer, proprietary-detector transfer, normalization durability, or completed human fidelity review.

## Required release sequence

1. Keep the release registry unchanged unless a separately reviewed promotion record authorizes a rule.
2. Run the complete test suite and dependency-lock check on the final source tree.
3. Build one wheel and one source distribution from that tree.
4. Run `twine check` on both distributions.
5. Clean-install and execute both distributions on Linux, macOS, and Windows.
6. Verify every installed console alias, `--version`, deterministic stream output, wheel metadata, and source-distribution metadata.
7. Generate `SHA256SUMS.txt` from the exact verified artifacts.
8. Confirm the project license and package metadata reflect the owner's explicit choice.
9. Push the final commit to `main` and require all repository workflows to succeed.
10. Create the immutable `v0.1.0` tag at that exact green commit.

The `Release Engineering` workflow implements steps 3 through 7 for all three operating systems. On a `v*` tag, its release job downloads the verified Linux-built artifacts only after every operating-system job succeeds, then creates the GitHub Release and uploads the wheel, source distribution, and checksum manifest.

## Current scientific boundary

The historical release-readiness artifact in `specs/fuckmark-v0.1.0-release-readiness-baseline.json` remains immutable. Later engineering fixes do not turn pending scientific gates into passes. In particular, the rejected calibration pair, absent confirmatory corpus, missing blind human fidelity judgments, and normalization-durability gaps continue to limit scientific wording.

The U+200C visible-projection experiment is quarantined. It is not release-safe, changes copied and DOM text, and loses the measured effect when Unicode format controls are stripped. Its contract explicitly forbids release-registry and CLI use.

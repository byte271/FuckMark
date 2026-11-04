"""Cold-process import boundaries and compatibility with the pre-refactor API.

The digests were derived from the import statements and ordered __all__ lists at
09c8cbf184e37e2e934e133b74a5db9af67b4f97. They pin export *targets*, not merely
names. No model, detector threshold, or frozen experiment is changed here.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = {
    "fuckmark": (
        "dd095eb14d8a0c73be8674f941739cc765271ae7ee0042fe4ce1faea5e0890ac",
        "fc656f5b8d63a9fd381369eb826510cdba3bb6b1a765f102f0b11c2fa2849287",
    ),
    "fuckmark.product": (
        "21433495e5266e2b6f72053c2eaf8f13d7eed3728e656be0d6272b1133e6302a",
        "83fe65314eeb827ee894350ea6cc2c0630a3631fca13b3643cd2a8a27509701b",
    ),
    "fuckmark.transforms": (
        "605ad75cee8e396a2665c0373c176246baabca27b44e5008a4a31aab6dcd896e",
        "17c92d95d25c384c39a33a655dfa520511a68f98605e43cd98efc1bcd7392174",
    ),
}


def run_cold(code: str) -> object:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("package", CONTRACTS)
def test_export_targets_and_wildcard_order_preserve_baseline(package: str) -> None:
    result = run_cold(f"""
        import hashlib, importlib, json
        p = importlib.import_module({package!r})
        def digest(value):
            data = json.dumps(value, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(data.encode()).hexdigest()
        print(json.dumps([digest(p._EXPORTS), digest(p.__all__)]))
    """)
    assert result == list(CONTRACTS[package])


@pytest.mark.parametrize("package", CONTRACTS)
def test_namespace_import_does_not_load_implementations(package: str) -> None:
    result = run_cold(f"""
        import importlib, json, sys
        importlib.import_module({package!r})
        print(json.dumps(sorted(n for n in sys.modules
                                if n == 'fuckmark' or n.startswith('fuckmark.'))))
    """)
    expected = ["fuckmark"] if package == "fuckmark" else ["fuckmark", package]
    assert result == expected


@pytest.mark.parametrize("package", CONTRACTS)
def test_dir_exposes_api_without_loading_it(package: str) -> None:
    assert run_cold(f"""
        import importlib, json, sys
        p = importlib.import_module({package!r})
        before = set(sys.modules)
        names = dir(p)
        assert set(p.__all__) <= set(names)
        assert set(p._EXPORTS) <= set(names)
        print(json.dumps(before == set(sys.modules)))
    """) is True


@pytest.mark.parametrize("package", CONTRACTS)
def test_unknown_attribute_has_no_import_side_effect(package: str) -> None:
    assert run_cold(f"""
        import importlib, json, sys
        p = importlib.import_module({package!r})
        before = set(sys.modules)
        try:
            getattr(p, 'this_symbol_does_not_exist')
        except AttributeError as error:
            assert p.__name__ in str(error)
        else:
            raise AssertionError('missing AttributeError')
        assert not hasattr(p, 'this_symbol_does_not_exist')
        print(json.dumps(before == set(sys.modules)))
    """) is True


@pytest.mark.parametrize("package", CONTRACTS)
def test_successful_resolution_is_cached(package: str) -> None:
    assert run_cold(f"""
        import importlib, json, types
        p = importlib.import_module({package!r})
        name = next(n for n, source in p._EXPORTS.items() if source is not None)
        sentinel = object()
        calls = []
        def load(source, parent):
            calls.append((source, parent))
            return types.SimpleNamespace(**{{name: sentinel}})
        p._import_module = load
        assert getattr(p, name) is sentinel
        assert getattr(p, name) is sentinel
        assert p.__dict__[name] is sentinel
        print(json.dumps(calls == [(p._EXPORTS[name], p.__name__)]))
    """) is True


@pytest.mark.parametrize("package", CONTRACTS)
def test_failed_import_is_not_hidden_or_cached(package: str) -> None:
    assert run_cold(f"""
        import importlib, json
        p = importlib.import_module({package!r})
        name = next(n for n, source in p._EXPORTS.items() if source is not None)
        def fail(source, parent):
            raise ImportError('deliberate test failure')
        p._import_module = fail
        for _ in range(2):
            try:
                getattr(p, name)
            except ImportError as error:
                assert str(error) == 'deliberate test failure'
            else:
                raise AssertionError('import failure was swallowed')
        print(json.dumps(name not in p.__dict__))
    """) is True


@pytest.mark.parametrize("package", CONTRACTS)
def test_reload_clears_previously_cached_exports(package: str) -> None:
    assert run_cold(f"""
        import importlib, json
        p = importlib.import_module({package!r})
        name = next(n for n, source in p._EXPORTS.items() if source is not None)
        p.__dict__[name] = object()
        public = list(p.__all__)
        importlib.reload(p)
        assert p.__all__ == public
        assert name not in p.__dict__
        if p.__name__ == 'fuckmark':
            assert p.__version__ == '0.4.1'
            assert p.__project_name__ == 'FuckMark'
        print('true')
    """) is True


@pytest.mark.parametrize("leaf", ["fuckmark.product.domain", "fuckmark.transforms.schema"])
def test_leaf_import_does_not_pull_research_packages(leaf: str) -> None:
    result = run_cold(f"""
        import importlib, json, sys
        importlib.import_module({leaf!r})
        forbidden = ('fuckmark.adapters', 'fuckmark.corpus', 'fuckmark.detectors',
                     'fuckmark.experiments', 'fuckmark.transforms.scheduler',
                     'fuckmark.transforms.effectiveness_profile',
                     'fuckmark.transforms.fidelity_readiness')
        loaded = sorted(n for n in sys.modules
                        if any(n == prefix or n.startswith(prefix + '.')
                               for prefix in forbidden))
        print(json.dumps(loaded))
    """)
    assert result == []


@pytest.mark.parametrize("package", CONTRACTS)
def test_real_exports_resolve_to_original_objects(package: str) -> None:
    assert run_cold(f"""
        import importlib, json
        p = importlib.import_module({package!r})
        for name, source in p._EXPORTS.items():
            if source is None:
                assert name in p.__dict__
                continue
            actual = getattr(p, name)
            original = getattr(importlib.import_module(source, p.__name__), name)
            assert actual is original, name
            assert getattr(p, name) is actual, name
        print('true')
    """) is True


@pytest.mark.parametrize("package", CONTRACTS)
def test_star_import_preserves_public_objects(package: str) -> None:
    assert run_cold(f"""
        import importlib, json
        p = importlib.import_module({package!r})
        namespace = {{}}
        exec('from ' + p.__name__ + ' import *', namespace)
        assert set(namespace) - {{'__builtins__'}} == set(p.__all__)
        for name in p.__all__:
            assert namespace[name] is getattr(p, name), name
        print('true')
    """) is True

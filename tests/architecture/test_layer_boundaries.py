"""
계층 경계 아키텍처 테스트.

WHY: import-linter 외부 의존 없이 AST 분석으로 계층 위반을 검증.
     CI 에서도 추가 도구 없이 동작 보장.
"""
import ast
import pathlib
from typing import Iterator

# 프로젝트 루트는 이 파일의 3단계 상위 (tests/architecture/ → tests/ → 루트)
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
_SRC_ROOT = _PROJECT_ROOT / "src"

# L3 패키지 목록 — 이 목록을 수정하면 ADR-001 도 함께 수정해야 한다
_L3_PACKAGES = frozenset({"portfolio", "signal", "backtest", "trading", "risk"})


def _iter_python_files(package_dir: pathlib.Path) -> Iterator[pathlib.Path]:
    """패키지 디렉터리 내 모든 .py 파일을 순회한다."""
    return package_dir.rglob("*.py")


def _extract_top_level_imports(source_file: pathlib.Path) -> list[str]:
    """파일에서 최상위 import 모듈명 목록을 추출한다."""
    try:
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


def _collect_imports_in_package(pkg_name: str) -> list[tuple[pathlib.Path, str]]:
    """패키지 내 모든 파일의 (파일경로, import된_모듈) 쌍을 수집한다."""
    pkg_dir = _SRC_ROOT / pkg_name
    if not pkg_dir.exists():
        return []

    results: list[tuple[pathlib.Path, str]] = []
    for py_file in _iter_python_files(pkg_dir):
        for imp in _extract_top_level_imports(py_file):
            results.append((py_file, imp))
    return results


def _assert_no_l3_imports(pkg_name: str) -> None:
    """해당 패키지가 L3 패키지를 import하지 않음을 검증한다."""
    violations: list[str] = []
    for file_path, imported in _collect_imports_in_package(pkg_name):
        if imported in _L3_PACKAGES:
            rel_path = file_path.relative_to(_PROJECT_ROOT)
            violations.append(f"  {rel_path} → {imported}")

    assert not violations, (
        f"\n[계층 위반] {pkg_name} 에서 L3 패키지 import 감지:\n"
        + "\n".join(violations)
    )


def test_market_data_가_L3_패키지를_import_하지_않는다():
    """L2 market_data 는 L3 패키지(portfolio/signal/backtest/trading/risk)를 import 금지."""
    _assert_no_l3_imports("market_data")


def test_universe_가_L3_패키지를_import_하지_않는다():
    """L2 universe 는 L3 패키지를 import 금지."""
    _assert_no_l3_imports("universe")


def test_similarity_가_L3_패키지를_import_하지_않는다():
    """L2 similarity 는 L3 패키지를 import 금지."""
    _assert_no_l3_imports("similarity")


def _collect_imports_in_subpackage(pkg_name: str, subpkg: str) -> list[tuple[pathlib.Path, str]]:
    """패키지의 특정 서브패키지 내 모든 파일의 import 쌍을 수집한다."""
    pkg_dir = _SRC_ROOT / pkg_name / subpkg
    if not pkg_dir.exists():
        return []

    results: list[tuple[pathlib.Path, str]] = []
    for py_file in _iter_python_files(pkg_dir):
        for imp in _extract_top_level_imports(py_file):
            results.append((py_file, imp))
    return results


def test_market_data_domain_은_adapters_를_import_하지_않는다():
    """도메인 순수성: market_data.domain 은 adapters 를 직접 import 금지."""
    # adapters 서브패키지 내부 모듈명을 감지
    _ADAPTER_MODULES = frozenset({"adapters"})
    violations: list[str] = []

    domain_dir = _SRC_ROOT / "market_data" / "domain"
    if not domain_dir.exists():
        return  # 아직 생성 전이면 통과

    for py_file in _iter_python_files(domain_dir):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                # market_data.adapters.* 형태 감지
                if (
                    len(parts) >= 2
                    and parts[0] == "market_data"
                    and parts[1] in _ADAPTER_MODULES
                ):
                    rel_path = py_file.relative_to(_PROJECT_ROOT)
                    violations.append(f"  {rel_path} → {node.module}")

    assert not violations, (
        "\n[도메인 순수성 위반] market_data.domain 에서 adapters import 감지:\n"
        + "\n".join(violations)
    )

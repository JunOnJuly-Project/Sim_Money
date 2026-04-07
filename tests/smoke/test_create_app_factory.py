"""
main.py 앱 팩토리 스모크 테스트.

WHY: CI 에서 ASGI app 객체가 정상 생성되고 /health 라우트를 포함하는지
     빠르게 검증한다. 무거운 통합 테스트 없이 부트스트랩 오류를 조기에 발견한다.
"""
from __future__ import annotations

import os
import importlib
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _set_duckdb_env(tmp_path, monkeypatch):
    """WHY: main.py 는 모듈 로딩 시 DuckDB 연결을 생성하므로
    임시 경로로 환경변수를 설정해 디스크 잔여물 없이 테스트한다."""
    db_file = str(tmp_path / "test.duckdb")
    monkeypatch.setenv("DUCKDB_PATH", db_file)
    monkeypatch.setenv("SEED_TICKERS", "KRX:005930,KRX:000660")

    # WHY: main 모듈은 모듈 로딩 시점에 app 을 생성하므로
    #      환경변수 설정 후 매 테스트마다 재import 해야 올바른 경로를 사용한다.
    module_name = "similarity.adapters.inbound.main"
    if module_name in sys.modules:
        del sys.modules[module_name]

    yield


def _import_app() -> FastAPI:
    """main 모듈을 import 하고 app 객체를 반환한다."""
    module = importlib.import_module("similarity.adapters.inbound.main")
    return module.app


def test_app_객체가_FastAPI_인스턴스이다():
    """app 이 FastAPI 인스턴스여야 한다."""
    app = _import_app()
    assert isinstance(app, FastAPI)


def test_health_라우트가_존재한다():
    """app 라우트 목록에 /health 가 포함되어야 한다."""
    app = _import_app()
    routes = [r.path for r in app.routes]
    assert "/health" in routes


def test_health_엔드포인트가_200을_반환한다():
    """/health 엔드포인트가 status ok 를 반환해야 한다."""
    app = _import_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

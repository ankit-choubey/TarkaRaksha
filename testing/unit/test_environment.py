"""
T02 Environment baseline smoke test.
Verifies backend dependencies, imports, and client instantiation capability.
"""
import pytest
import importlib.metadata

def test_python_version():
    import sys
    assert sys.version_info >= (3, 11), "Python must be 3.11+"

def test_fastapi_and_pydantic_imports():
    import fastapi
    import pydantic
    assert hasattr(fastapi, "FastAPI")
    assert hasattr(pydantic, "BaseModel")

def test_httpx_import():
    import httpx
    assert hasattr(httpx, "AsyncClient")

def test_groq_sdk_import_and_init():
    import groq
    client = groq.Client(api_key="mock_env_smoke_test_key")
    assert client is not None

def test_razorpay_sdk_import_and_init():
    import razorpay
    client = razorpay.Client(auth=("mock_env_key_id", "mock_env_key_secret"))
    assert client is not None

#!/usr/bin/env python3
"""
TarkaRaksha Environment Verification Script (T02).
Checks Python, Node.js, npm, Git, backend packages, AI client, and payment integration readiness.
"""
import sys
import os
import subprocess
import importlib.metadata

def check_command(cmd, name):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        version = res.stdout.strip().split('\n')[0]
        print(f"[✓] {name}: {version}")
        return True
    except Exception as e:
        print(f"[✗] {name} failed: {e}")
        return False

def check_python_package(pkg_name, import_name=None):
    if import_name is None:
        import_name = pkg_name
    try:
        mod = __import__(import_name)
        ver = getattr(mod, '__version__', None)
        if not ver:
            try:
                ver = importlib.metadata.version(pkg_name)
            except Exception:
                ver = "installed"
        print(f"[✓] Python package '{pkg_name}': v{ver}")
        return True
    except ImportError as e:
        print(f"[✗] Failed to import '{import_name}': {e}")
        return False

def main():
    print("=== TarkaRaksha Environment Verification ===")
    all_ok = True

    # 1. System toolchains
    print("\n--- System Toolchains ---")
    all_ok &= check_command([sys.executable, "--version"], f"Python (active venv: {sys.executable})")
    all_ok &= check_command(["node", "--version"], "Node.js")
    all_ok &= check_command(["npm", "--version"], "npm")
    all_ok &= check_command(["git", "--version"], "Git")

    # 2. Backend core packages
    print("\n--- Backend Core Packages ---")
    backend_pkgs = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("httpx", "httpx"),
        ("pytest", "pytest"),
        ("pytest-asyncio", "pytest_asyncio"),
    ]
    for pkg, imp in backend_pkgs:
        all_ok &= check_python_package(pkg, imp)

    # 3. AI & Payment Client Packages
    print("\n--- AI & Payment SDK Packages ---")
    all_ok &= check_python_package("groq", "groq")
    all_ok &= check_python_package("razorpay", "razorpay")

    # 4. Client initialization tests
    print("\n--- Client Initialization Viability ---")
    try:
        import groq
        _ = groq.Client(api_key="mock_env_verification_key")
        print("[✓] Groq client instantiation: OK")
    except Exception as e:
        print(f"[✗] Groq client instantiation failed: {e}")
        all_ok = False

    try:
        import razorpay
        _ = razorpay.Client(auth=("mock_env_key_id", "mock_env_key_secret"))
        print("[✓] Razorpay client instantiation: OK")
    except Exception as e:
        print(f"[✗] Razorpay client instantiation failed: {e}")
        all_ok = False

    # 5. Frontend toolchain verification
    print("\n--- Frontend Build Verification ---")
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if os.path.exists(frontend_dir):
        print(f"[✓] Frontend directory exists at {frontend_dir}")
        try:
            res = subprocess.run(["npm", "run", "build"], cwd=frontend_dir, capture_output=True, text=True, check=True)
            print("[✓] Next.js frontend production build: OK")
        except subprocess.CalledProcessError as e:
            print(f"[✗] Frontend build failed:\n{e.stderr or e.stdout}")
            all_ok = False
    else:
        print("[✗] Frontend directory not found")
        all_ok = False

    print("\n============================================")
    if all_ok:
        print("[✓] ALL T02 ENVIRONMENT CHECKS PASSED")
        sys.exit(0)
    else:
        print("[✗] SOME ENVIRONMENT CHECKS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()

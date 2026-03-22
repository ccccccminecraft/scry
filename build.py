"""
build.py - Scry ビルドスクリプト

使用方法:
    python build.py           # 全ステップ実行
    python build.py --backend # バックエンドのみ
    python build.py --frontend # フロントエンドのみ
    python build.py --electron # Electron のみ（backend.exe と dist/ が必要）

前提条件:
    pip install pyinstaller
    npm install --legacy-peer-deps（frontend/ で実施済みであること）

出力:
    backend/dist/backend.exe
    frontend/dist/          （Vue ビルド）
    frontend/dist_electron/ （インストーラー）
        └── ScrySetup.exe
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
BACKEND_EXE = BACKEND_DIR / "dist" / "backend.exe"
FRONTEND_DIST = FRONTEND_DIR / "dist"


def step(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def run(cmd: list[str], cwd: Path) -> None:
    """コマンドを実行し、失敗時は終了する。

    Windows では npm 等が .cmd 経由で呼ばれるため shell=True を使用する。
    """
    print(f"$ {' '.join(cmd)}  (cwd: {cwd})")
    result = subprocess.run(cmd, cwd=cwd, shell=(sys.platform == "win32"))
    if result.returncode != 0:
        print(f"\n[ERROR] コマンドが失敗しました (exit code {result.returncode})")
        sys.exit(result.returncode)


def build_backend() -> None:
    step("Step 1/3: バックエンド (PyInstaller)")
    # FastAPI / uvicorn / pydantic 等は動的インポートを含むため --collect-all で明示収集する
    collect_all_packages = [
        "fastapi", "uvicorn", "starlette",
        "pydantic", "pydantic_core",
        "anyio", "multipart",
        "sqlalchemy", "aiofiles",
        "keyring", "anthropic", "openai", "httpx",
    ]
    collect_args: list[str] = []
    for pkg in collect_all_packages:
        collect_args += ["--collect-all", pkg]
    run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", "backend",
            *collect_args,
            "app/main.py",
            "--clean",
        ],
        cwd=BACKEND_DIR,
    )
    if not BACKEND_EXE.exists():
        print(f"\n[ERROR] backend.exe が見つかりません: {BACKEND_EXE}")
        sys.exit(1)
    print(f"\n[OK] {BACKEND_EXE}")


def build_frontend() -> None:
    step("Step 2/3: フロントエンド (Vite)")
    run(["npm", "run", "build"], cwd=FRONTEND_DIR)
    if not FRONTEND_DIST.exists():
        print(f"\n[ERROR] dist/ が見つかりません: {FRONTEND_DIST}")
        sys.exit(1)
    print(f"\n[OK] {FRONTEND_DIST}")


def build_electron() -> None:
    step("Step 3/3: Electron パッケージング (electron-builder)")

    if not BACKEND_EXE.exists():
        print(f"\n[ERROR] backend.exe が存在しません。先に --backend を実行してください。")
        print(f"        期待パス: {BACKEND_EXE}")
        sys.exit(1)

    if not FRONTEND_DIST.exists():
        print(f"\n[ERROR] dist/ が存在しません。先に --frontend を実行してください。")
        print(f"        期待パス: {FRONTEND_DIST}")
        sys.exit(1)

    run(["npm", "run", "build:electron"], cwd=FRONTEND_DIR)

    installer = FRONTEND_DIR / "dist_electron" / "ScrySetup.exe"
    if installer.exists():
        print(f"\n[OK] インストーラー生成完了: {installer}")
    else:
        # NSIS 以外のターゲットでは別ファイル名になることがある
        outputs = list((FRONTEND_DIR / "dist_electron").glob("*.exe"))
        if outputs:
            print(f"\n[OK] インストーラー生成完了: {outputs[0]}")
        else:
            print("\n[WARN] .exe が見つかりません。dist_electron/ を確認してください。")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scry ビルドスクリプト")
    parser.add_argument("--backend",  action="store_true", help="バックエンドのみビルド")
    parser.add_argument("--frontend", action="store_true", help="フロントエンドのみビルド")
    parser.add_argument("--electron", action="store_true", help="Electron のみビルド")
    args = parser.parse_args()

    # 引数なし → 全ステップ
    run_all = not (args.backend or args.frontend or args.electron)

    if run_all or args.backend:
        build_backend()
    if run_all or args.frontend:
        build_frontend()
    if run_all or args.electron:
        build_electron()

    if run_all:
        step("ビルド完了")
        installer = FRONTEND_DIR / "dist_electron" / "ScrySetup.exe"
        if installer.exists():
            print(f"  インストーラー: {installer}")


if __name__ == "__main__":
    main()

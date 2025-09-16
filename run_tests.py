#!/usr/bin/env python3
"""テスト実行スクリプト"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_unit_tests(verbose=False):
    """単体テストを実行"""
    print("🧪 単体テストを実行中...")
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/unit/",
        "-m", "unit or not integration",
        "--tb=short"
    ]
    
    if verbose:
        cmd.append("-v")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def run_integration_tests(verbose=False):
    """統合テストを実行"""
    print("🔗 統合テストを実行中...")
    
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/integration/",
        "-m", "integration or not unit",
        "--tb=short"
    ]
    
    if verbose:
        cmd.append("-v")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def run_all_tests(verbose=False, coverage=True):
    """全テストを実行"""
    print("🚀 全テストスイートを実行中...")
    
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend([
            "--cov=src/nocturnal_agent",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing"
        ])
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def run_specific_test(test_path, verbose=False):
    """特定のテストを実行"""
    print(f"🎯 特定テストを実行中: {test_path}")
    
    cmd = [sys.executable, "-m", "pytest", test_path]
    
    if verbose:
        cmd.append("-v")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def check_test_requirements():
    """テスト要件をチェック"""
    required_packages = [
        "pytest",
        "pytest-asyncio",
        "pytest-cov"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 必要なパッケージが不足しています:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n以下のコマンドでインストールしてください:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True


def generate_test_report():
    """テストレポートを生成"""
    print("📊 テストレポートを生成中...")
    
    # HTMLカバレッジレポートの場所を表示
    html_report_path = Path("htmlcov/index.html")
    if html_report_path.exists():
        print(f"✅ HTMLカバレッジレポート: {html_report_path.absolute()}")
    
    # XML カバレッジレポートの場所を表示
    xml_report_path = Path("coverage.xml")
    if xml_report_path.exists():
        print(f"✅ XMLカバレッジレポート: {xml_report_path.absolute()}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Nocturnal Agent テストスイート")
    parser.add_argument(
        "--type", 
        choices=["unit", "integration", "all", "specific"],
        default="all",
        help="実行するテストの種類"
    )
    parser.add_argument(
        "--test-path",
        help="特定のテストパス（--type specific時に使用）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細出力"
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true", 
        help="カバレッジレポートを無効化"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="テスト要件のみチェック"
    )
    
    args = parser.parse_args()
    
    # 要件チェック
    if not check_test_requirements():
        sys.exit(1)
    
    if args.check_only:
        print("✅ テスト要件は満たされています")
        return
    
    success = False
    
    try:
        if args.type == "unit":
            success = run_unit_tests(args.verbose)
        elif args.type == "integration":
            success = run_integration_tests(args.verbose)
        elif args.type == "all":
            success = run_all_tests(args.verbose, not args.no_coverage)
        elif args.type == "specific":
            if not args.test_path:
                print("❌ --test-path が必要です")
                sys.exit(1)
            success = run_specific_test(args.test_path, args.verbose)
        
        if success:
            print("✅ テスト実行完了")
            if args.type == "all" and not args.no_coverage:
                generate_test_report()
        else:
            print("❌ テスト実行失敗")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⚠️ テスト実行が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"❌ テスト実行中にエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
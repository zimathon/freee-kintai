#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""
freee 勤怠管理 CLI ツール

使い方:
    uv run freee_kintai.py auth      # 初回認証
    uv run freee_kintai.py info      # 事業所ID・従業員ID取得
    uv run freee_kintai.py in        # 出勤打刻
    uv run freee_kintai.py out       # 退勤打刻
    uv run freee_kintai.py status    # 今日の打刻状況
    uv run freee_kintai.py available # 打刻可能な種別を確認
"""

import argparse
import json
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

# 設定ファイルのパス (スクリプトと同じディレクトリ)
CONFIG_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = CONFIG_DIR / "config.json"
TOKEN_FILE = CONFIG_DIR / "token.json"

# freee API エンドポイント
AUTH_URL = "https://accounts.secure.freee.co.jp/public_api/authorize"
TOKEN_URL = "https://accounts.secure.freee.co.jp/public_api/token"
API_BASE = "https://api.freee.co.jp/hr/api/v1"

# リダイレクトURI (OOB)
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

# 必要なスコープ
SCOPES = "hr.time_clocks hr.employees offline_access"


def load_config() -> dict:
    """設定ファイルを読み込む"""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict):
    """設定ファイルを保存する"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    os.chmod(CONFIG_FILE, 0o600)


def load_token() -> dict:
    """トークンファイルを読み込む"""
    if not TOKEN_FILE.exists():
        return {}
    with open(TOKEN_FILE) as f:
        return json.load(f)


def save_token(token: dict):
    """トークンファイルを保存する"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f, indent=2)
    os.chmod(TOKEN_FILE, 0o600)


def get_access_token() -> str:
    """有効なアクセストークンを取得（必要に応じてリフレッシュ）"""
    token = load_token()
    config = load_config()

    if not token.get("access_token"):
        print("エラー: 認証されていません。先に 'auth' コマンドを実行してください。")
        sys.exit(1)

    # リフレッシュトークンでアクセストークンを更新
    if token.get("refresh_token"):
        response = requests.post(
            TOKEN_URL,
            auth=(config["client_id"], config["client_secret"]),
            data={
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
            },
        )

        if response.status_code == 200:
            new_token = response.json()
            save_token(new_token)
            return new_token["access_token"]
        else:
            print(f"トークン更新エラー: {response.text}")
            print("再度 'auth' コマンドを実行してください。")
            sys.exit(1)

    return token["access_token"]


def cmd_setup(args):
    """初期設定: CLIENT_ID と CLIENT_SECRET を保存"""
    print("=== freee API 初期設定 ===\n")

    config = load_config()

    client_id = input(f"CLIENT_ID [{config.get('client_id', '')}]: ").strip()
    if client_id:
        config["client_id"] = client_id

    client_secret = input("CLIENT_SECRET: ").strip()
    if client_secret:
        config["client_secret"] = client_secret

    if not config.get("client_id") or not config.get("client_secret"):
        print("エラー: CLIENT_ID と CLIENT_SECRET は必須です。")
        sys.exit(1)

    save_config(config)
    print(f"\n設定を保存しました: {CONFIG_FILE}")
    print("次に 'auth' コマンドで認証を行ってください。")


def cmd_auth(args):
    """OAuth認証を行う"""
    config = load_config()

    if not config.get("client_id") or not config.get("client_secret"):
        print("エラー: 先に 'setup' コマンドで CLIENT_ID/SECRET を設定してください。")
        sys.exit(1)

    # 認可URLを生成
    params = {
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "prompt": "select_company",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print("=== freee OAuth 認証 ===\n")
    print("ブラウザで認証ページを開きます...")
    print(f"\nURL: {auth_url}\n")

    webbrowser.open(auth_url)

    print("ブラウザで許可した後、表示される認可コードを入力してください。")
    auth_code = input("\n認可コード: ").strip()

    if not auth_code:
        print("エラー: 認可コードが入力されていません。")
        sys.exit(1)

    # トークンを取得
    response = requests.post(
        TOKEN_URL,
        auth=(config["client_id"], config["client_secret"]),
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if response.status_code != 200:
        print(f"エラー: トークン取得に失敗しました。\n{response.text}")
        sys.exit(1)

    token = response.json()
    save_token(token)
    print(f"\n認証成功！トークンを保存しました: {TOKEN_FILE}")
    print("次に 'info' コマンドで事業所ID・従業員IDを取得してください。")


def cmd_info(args):
    """事業所IDと従業員IDを取得・設定"""
    access_token = get_access_token()
    config = load_config()
    headers = {"Authorization": f"Bearer {access_token}"}

    print("=== 事業所・従業員情報の取得 ===\n")

    # ユーザー情報を取得
    response = requests.get(f"{API_BASE}/users/me", headers=headers)
    if response.status_code != 200:
        print(f"エラー: {response.text}")
        sys.exit(1)

    user_info = response.json()
    companies = user_info.get("companies", [])

    if not companies:
        print("エラー: 所属する事業所がありません。")
        sys.exit(1)

    print("所属事業所一覧:")
    for i, company in enumerate(companies):
        print(f"  [{i + 1}] {company['name']} (ID: {company['id']})")

    if len(companies) == 1:
        selected_company = companies[0]
    else:
        choice = input(f"\n事業所を選択 [1-{len(companies)}]: ").strip()
        selected_company = companies[int(choice) - 1]

    company_id = selected_company["id"]
    config["company_id"] = company_id
    print(f"\n事業所ID: {company_id}")

    # 従業員一覧を取得
    response = requests.get(
        f"{API_BASE}/employees",
        headers=headers,
        params={"company_id": company_id, "limit": 100},
    )

    if response.status_code != 200:
        print(f"エラー: {response.text}")
        sys.exit(1)

    employees = response.json().get("employees", [])

    print("\n従業員一覧:")
    for i, emp in enumerate(employees):
        email = emp.get("email", "")
        print(f"  [{i + 1}] {emp['display_name']} (ID: {emp['id']}) {email}")

    if len(employees) == 1:
        selected_employee = employees[0]
    else:
        choice = input(f"\n自分を選択 [1-{len(employees)}]: ").strip()
        selected_employee = employees[int(choice) - 1]

    employee_id = selected_employee["id"]
    config["employee_id"] = employee_id

    save_config(config)
    print(f"\n従業員ID: {employee_id}")
    print(f"\n設定を保存しました: {CONFIG_FILE}")
    print("\nこれで準備完了です！")
    print("  'in'     - 出勤打刻")
    print("  'out'    - 退勤打刻")
    print("  'status' - 打刻状況確認")


def cmd_clock_in(args):
    """出勤打刻"""
    _clock("clock_in", "出勤")


def cmd_clock_out(args):
    """退勤打刻"""
    _clock("clock_out", "退勤")


def cmd_break_begin(args):
    """休憩開始"""
    _clock("break_begin", "休憩開始")


def cmd_break_end(args):
    """休憩終了"""
    _clock("break_end", "休憩終了")


def _clock(clock_type: str, label: str):
    """打刻を実行"""
    access_token = get_access_token()
    config = load_config()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    if not config.get("company_id") or not config.get("employee_id"):
        print("エラー: 先に 'info' コマンドで事業所ID・従業員IDを設定してください。")
        sys.exit(1)

    base_date = datetime.now().strftime("%Y-%m-%d")

    data = {
        "company_id": config["company_id"],
        "type": clock_type,
        "base_date": base_date,
    }

    response = requests.post(
        f"{API_BASE}/employees/{config['employee_id']}/time_clocks",
        headers=headers,
        json=data,
    )

    if response.status_code in (200, 201):
        result = response.json()
        clock_time = result.get("datetime", "")
        if clock_time:
            # ISO形式から時刻部分を抽出
            try:
                dt = datetime.fromisoformat(clock_time.replace("Z", "+00:00"))
                clock_time = dt.strftime("%H:%M:%S")
            except ValueError:
                pass
        print(f"✓ {label}打刻完了: {clock_time}")
    else:
        error = response.json()
        error_msg = error.get("message", error.get("errors", response.text))
        print(f"✗ {label}打刻失敗: {error_msg}")
        sys.exit(1)


def cmd_status(args):
    """打刻状況を確認"""
    from datetime import timedelta

    access_token = get_access_token()
    config = load_config()
    headers = {"Authorization": f"Bearer {access_token}"}

    if not config.get("company_id") or not config.get("employee_id"):
        print("エラー: 先に 'info' コマンドで事業所ID・従業員IDを設定してください。")
        sys.exit(1)

    # 日付指定の処理
    if args.date:
        target_date = args.date
    elif args.yesterday:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    response = requests.get(
        f"{API_BASE}/employees/{config['employee_id']}/time_clocks",
        headers=headers,
        params={
            "company_id": config["company_id"],
            "from_date": target_date,
            "to_date": target_date,
        },
    )

    if response.status_code != 200:
        print(f"エラー: {response.text}")
        sys.exit(1)

    clocks = response.json()

    print(f"=== {target_date} の打刻状況 ===\n")

    items = clocks if isinstance(clocks, list) else clocks.get("items", [])

    if not items:
        print("打刻記録がありません。")
        return

    type_labels = {
        "clock_in": "出勤",
        "clock_out": "退勤",
        "break_begin": "休憩開始",
        "break_end": "休憩終了",
    }

    for clock in items:
        clock_type = clock.get("type", "unknown")
        label = type_labels.get(clock_type, clock_type)
        clock_time = clock.get("datetime", "")
        if clock_time:
            try:
                dt = datetime.fromisoformat(clock_time.replace("Z", "+00:00"))
                clock_time = dt.strftime("%H:%M:%S")
            except ValueError:
                pass
        print(f"  {label}: {clock_time}")


def cmd_available(args):
    """打刻可能な種別を確認"""
    access_token = get_access_token()
    config = load_config()
    headers = {"Authorization": f"Bearer {access_token}"}

    if not config.get("company_id") or not config.get("employee_id"):
        print("エラー: 先に 'info' コマンドで事業所ID・従業員IDを設定してください。")
        sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")

    response = requests.get(
        f"{API_BASE}/employees/{config['employee_id']}/time_clocks/available_types",
        headers=headers,
        params={
            "company_id": config["company_id"],
            "date": today,
        },
    )

    if response.status_code != 200:
        print(f"エラー: {response.text}")
        sys.exit(1)

    result = response.json()
    types = result.get("available_types", result.get("types", []))

    type_labels = {
        "clock_in": "出勤 (in)",
        "clock_out": "退勤 (out)",
        "break_begin": "休憩開始 (break-begin)",
        "break_end": "休憩終了 (break-end)",
    }

    print("=== 現在打刻可能な種別 ===\n")
    if not types:
        print("打刻可能な種別がありません。")
    else:
        for t in types:
            label = type_labels.get(t, t)
            print(f"  - {label}")


def main():
    parser = argparse.ArgumentParser(
        description="freee 勤怠管理 CLI ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s setup       # 初期設定 (CLIENT_ID/SECRET)
  %(prog)s auth        # OAuth認証
  %(prog)s info        # 事業所ID・従業員ID取得
  %(prog)s in          # 出勤打刻
  %(prog)s out         # 退勤打刻
  %(prog)s break-begin # 休憩開始
  %(prog)s break-end   # 休憩終了
  %(prog)s status      # 今日の打刻状況
  %(prog)s available   # 打刻可能な種別
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    subparsers.add_parser("setup", help="初期設定 (CLIENT_ID/SECRET)")
    subparsers.add_parser("auth", help="OAuth認証")
    subparsers.add_parser("info", help="事業所ID・従業員ID取得")
    subparsers.add_parser("in", help="出勤打刻")
    subparsers.add_parser("out", help="退勤打刻")
    subparsers.add_parser("break-begin", help="休憩開始")
    subparsers.add_parser("break-end", help="休憩終了")
    status_parser = subparsers.add_parser("status", help="打刻状況")
    status_parser.add_argument("-y", "--yesterday", action="store_true", help="昨日の状況")
    status_parser.add_argument("-d", "--date", type=str, help="日付指定 (YYYY-MM-DD)")
    subparsers.add_parser("available", help="打刻可能な種別")

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "auth": cmd_auth,
        "info": cmd_info,
        "in": cmd_clock_in,
        "out": cmd_clock_out,
        "break-begin": cmd_break_begin,
        "break-end": cmd_break_end,
        "status": cmd_status,
        "available": cmd_available,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

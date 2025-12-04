# freee-kintai

freee人事労務の勤怠打刻をCLIから行うツール

## 必要条件

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (依存関係の自動管理)

## セットアップ

### 1. freee APIアプリの作成

1. [freee開発者ポータル](https://developer.freee.co.jp/)にアクセス
2. 「アプリ管理」→「新規作成」
3. 以下の設定でアプリを作成:
   - **アプリ種別**: Public API
   - **リダイレクトURI**: `urn:ietf:wg:oauth:2.0:oob`
   - **権限 (Scope)**:
     - `hr.employees:read` (従業員情報の取得)
     - `hr.time_clocks:read` (打刻情報の取得)
     - `hr.time_clocks:write` (打刻の登録)

4. 作成後、`CLIENT_ID`と`CLIENT_SECRET`をメモ

### 2. スクリプトのダウンロード

```bash
git clone git@github.com:zimathon/freee-kintai.git ~/scripts/freee-kintai
cd ~/scripts/freee-kintai
chmod +x freee_kintai.py
```

### 3. 初期設定

```bash
./freee_kintai.py setup
```

`CLIENT_ID`と`CLIENT_SECRET`を入力

### 4. OAuth認証

```bash
./freee_kintai.py auth
```

ブラウザが開くので、freeeアカウントでログインして許可。
表示される認可コードをターミナルに貼り付け。

### 5. 事業所・従業員IDの取得

```bash
./freee_kintai.py info
```

一覧から事業所と自分を選択。

#### 従業員一覧の取得に権限エラーが出る場合

会社の設定によっては従業員一覧APIへのアクセス権限がない場合があります。
その場合、`/users/me` APIから自分の従業員IDを取得できます：

```bash
# token.jsonからアクセストークンを取得
ACCESS_TOKEN=$(jq -r '.access_token' ~/scripts/freee-kintai/token.json)

# ユーザー情報を取得 (employee_idが含まれる)
curl -s "https://api.freee.co.jp/hr/api/v1/users/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
```

レスポンス例:
```json
{
  "id": 12345678,
  "companies": [
    {
      "id": 1234567,
      "name": "株式会社○○",
      "role": "self_only",
      "employee_id": 9876543,
      "display_name": "山田 太郎"
    }
  ]
}
```

`companies[].id` が事業所ID、`companies[].employee_id` が従業員IDです。

取得したIDを `config.json` に手動で設定：

```json
{
  "client_id": "あなたのCLIENT_ID",
  "client_secret": "あなたのCLIENT_SECRET",
  "company_id": 1234567,
  "employee_id": 9876543
}
```

## 使い方

### 基本コマンド

```bash
# 出勤
./freee_kintai.py in

# 退勤
./freee_kintai.py out

# 休憩開始
./freee_kintai.py break-begin

# 休憩終了
./freee_kintai.py break-end
```

### 状況確認

```bash
# 今日の打刻状況
./freee_kintai.py status

# 昨日の打刻状況
./freee_kintai.py status -y

# 特定日の打刻状況
./freee_kintai.py status -d 2025-12-01

# 打刻可能な種別を確認
./freee_kintai.py available
```

### ヘルプ

```bash
./freee_kintai.py --help
```

## エイリアス設定 (オプション)

`~/.zshrc`または`~/.bashrc`に追加:

```bash
alias kintai="~/scripts/freee-kintai/freee_kintai.py"
alias syukkin="~/scripts/freee-kintai/freee_kintai.py in"
alias taikin="~/scripts/freee-kintai/freee_kintai.py out"
```

## ファイル構成

```
freee-kintai/
├── freee_kintai.py   # メインスクリプト
├── config.json       # 設定ファイル (gitignore)
├── token.json        # トークン (gitignore)
├── .gitignore
└── README.md
```

## トラブルシューティング

### トークン期限切れエラー

`invalid_access_token`エラーが出た場合、スクリプトは自動でトークンを更新します。
それでもエラーが続く場合は再認証:

```bash
./freee_kintai.py auth
```

### 権限エラー

`access_denied`エラーが出た場合、freee開発者ポータルでアプリの権限(Scope)を確認してください。

## ライセンス

MIT

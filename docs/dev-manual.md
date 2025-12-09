# 開発者マニュアル

このドキュメントは開発中のツールの使用方法とテスト方法を記載します。

## 環境セットアップ

```bash
# 仮想環境の有効化（すでに作成済み）
source ./venv/bin/activate

# 開発用依存パッケージのインストール
pip install pytest
```

## 開発中ツール

### scripts/stats.py

SVGファイル内の要素統計を取得するツールです。グループごとに含まれる描画要素の数を階層構造で表示します。

#### 機能

- グループ名の識別（`inkscape:label` 優先、なければ `id` 属性を使用）
- 描画要素のカウント（rect, circle, ellipse, line, polyline, polygon, path, text, tspan, image, use）
- 階層構造の表示
- テキスト表形式 / JSON形式の出力

#### 使用方法

```bash
# 基本的な使い方（テキスト表形式）
./venv/bin/python scripts/stats.py <SVGファイル>

# JSON形式で出力
./venv/bin/python scripts/stats.py <SVGファイル> -f json

# ファイルに出力
./venv/bin/python scripts/stats.py <SVGファイル> -o output.txt
./venv/bin/python scripts/stats.py <SVGファイル> -f json -o output.json
```

#### 出力例

テキスト形式：
```
File: assets/source/example.svg
Total elements: 821

Group                           Elements                 Count
------------------------------  --------------------  --------
Layer 1                         (empty)                      0
  outer-case                    rect                         1
  shapes                        rect                        10
                                circle                       5
                                (subtotal)                  15
```

JSON形式：
```json
{
  "file": "assets/source/example.svg",
  "total_elements": 821,
  "groups": [
    {
      "name": "Layer 1",
      "depth": 0,
      "element_counts": {},
      "total_elements": 0,
      "children": [
        {
          "name": "shapes",
          "depth": 1,
          "element_counts": {"rect": 10, "circle": 5},
          "total_elements": 15
        }
      ]
    }
  ],
  "ungrouped": {}
}
```

#### オプション

| オプション | 説明 |
|-----------|------|
| `-f, --format` | 出力形式（`text` または `json`、デフォルト: `text`） |
| `-o, --output` | 出力ファイルパス（省略時は標準出力） |

## テスト

### テストの実行

```bash
# 全テストを実行
./venv/bin/python -m pytest tests/ -v

# 特定のテストファイルを実行
./venv/bin/python -m pytest tests/test_utils.py -v

# 特定のテストクラスを実行
./venv/bin/python -m pytest tests/test_utils.py::TestGetLocalName -v

# 特定のテストメソッドを実行
./venv/bin/python -m pytest tests/test_utils.py::TestGetLocalName::test_with_namespace -v
```

### テストカバレッジ

```bash
# カバレッジ付きでテスト実行（要 pytest-cov）
pip install pytest-cov
./venv/bin/python -m pytest tests/ --cov=src/svg_tools --cov-report=term-missing
```

## モジュール構成

```
src/svg_tools/
├── __init__.py      # パッケージ初期化
└── utils.py         # ユーティリティ関数・クラス

scripts/
└── stats.py         # SVG統計ツール（CLI）

tests/
├── __init__.py
└── test_utils.py    # utils.py のテスト
```

### utils.py の主要関数

| 関数/クラス | 説明 |
|------------|------|
| `parse_svg(file_path)` | SVGファイルをパースしてルート要素を返す |
| `get_local_name(tag)` | 名前空間を除いたタグ名を取得 |
| `get_group_name(element)` | グループ要素の表示名を取得 |
| `is_drawing_element(element)` | 描画要素かどうかを判定 |
| `analyze_svg(file_path)` | SVGを解析して統計を収集 |
| `iter_all_groups(stats)` | 全グループを深さ優先で走査 |
| `GroupStats` | グループの統計データクラス |
| `SVGStats` | SVG全体の統計データクラス |

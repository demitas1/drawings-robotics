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

### scripts/svg_align.py

SVGファイル内の形状要素（rect, arc）を検査し、指定されたルールに基づいてバリデーションおよび修正を行うツールです。

#### 機能

- グループ内の形状要素を検査
- グリッド位置（中心座標が指定単位の倍数か）の検証
- サイズ（width, height）の検証
- arc要素の start/end 角度の検証
- 許容範囲内の誤差は自動修正

#### 使用方法

```bash
# 検査のみ（レポート出力）
./venv/bin/python scripts/svg_align.py <SVGファイル> --rule <ルールYAML>

# 検査＋修正出力
./venv/bin/python scripts/svg_align.py <SVGファイル> --rule <ルールYAML> --output <出力SVG>
```

#### 使用例

```bash
# breadboard SVGを検査
./venv/bin/python scripts/svg_align.py assets/source/svg-test1-breadboard1.svg \
  --rule assets/source/rules/breadboard.yaml

# 修正して出力
./venv/bin/python scripts/svg_align.py assets/source/svg-test1-breadboard1.svg \
  --rule assets/source/rules/breadboard.yaml \
  --output assets/normalized/svg-test1-breadboard1.svg
```

#### オプション

| オプション | 説明 |
|-----------|------|
| `--rule, -r` | ルールYAMLファイルのパス（必須） |
| `--output, -o` | 出力SVGファイルのパス（指定時に修正を実行） |

#### ルールYAMLの形式

```yaml
groups:
  - name: "s-rect"        # inkscape:label で指定されたグループ名
    shape: rect           # 形状タイプ（rect または arc）
    grid:
      x: 1.27             # X方向グリッド単位
      y: 1.27             # Y方向グリッド単位
    size:
      width: 1.27         # 期待する幅
      height: 1.27        # 期待する高さ

  - name: "s-circle"
    shape: arc
    grid:
      x: 1.27
      y: 1.27
    size:
      width: 0.635        # 直径（rx * 2）
      height: 0.635       # 直径（ry * 2）
    arc:
      start: 0            # 開始角度（rad）
      end: 6.2831853      # 終了角度（rad）= 2π

tolerance:
  acceptable: 0.001       # 許容誤差（mm または rad）
  error_threshold: 0.1    # エラー閾値（10% = 0.1）
```

#### 検査ロジック

1. **許容範囲（acceptable）以内**: 修正不要（OK）
2. **許容範囲超え〜エラー閾値（error_threshold）以内**: 修正可能（FIXABLE）
3. **エラー閾値超え**: エラー（ERROR）- 修正不可

#### 修正順序

1. サイズ（width, height または rx, ry）を修正
2. arc の場合は start/end を修正
3. 修正後のサイズに基づいて中心座標をグリッドにスナップ

#### 出力例

```
File: assets/source/svg-test1-breadboard1.svg
Total elements checked: 816
Errors: 0
Fixable: 408

Group: s-rect (rect)
  OK: 408, Fixable: 0, Errors: 0

Group: s-circle (arc)
  OK: 0, Fixable: 408, Errors: 0
  [FIXABLE] path27-9
    - end=6.217097 (expected: 6.2831853)
  [FIXABLE] path27-9-8
    - end=6.217097 (expected: 6.2831853)
    - center_y=5.100967 (remainder: 0.020967)
  ...

All fixable issues can be corrected.

Output written to: assets/normalized/svg-test1-breadboard1.svg
```

#### 終了コード

| コード | 意味 |
|--------|------|
| 0 | 成功（エラーなし） |
| 1 | ファイル読み込みエラーなど |
| 2 | バリデーションエラー（10%超の誤差あり） |

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
├── utils.py         # ユーティリティ関数・クラス
├── geometry.py      # 形状解析・修正ユーティリティ
└── align.py         # バリデーション・アライメントロジック

scripts/
├── stats.py         # SVG統計ツール（CLI）
└── svg_align.py     # SVG形状検査・修正ツール（CLI）

tests/
├── __init__.py
├── test_utils.py    # utils.py のテスト
└── fixtures/        # テスト用データ
    └── breadboard-rule.yaml
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

### geometry.py の主要関数

| 関数/クラス | 説明 |
|------------|------|
| `BoundingBox` | バウンディングボックスのデータクラス |
| `RectInfo` | rect要素の情報データクラス |
| `ArcInfo` | arc要素の情報データクラス |
| `parse_rect(element)` | rect要素をパースしてRectInfoを返す |
| `parse_arc(element)` | arc要素をパースしてArcInfoを返す |
| `snap_to_grid(value, grid_unit)` | 値を最も近いグリッド位置にスナップ |
| `check_grid_alignment(value, grid_unit, tolerance)` | グリッド位置へのアライメントをチェック |
| `check_value_match(actual, expected, tolerance, error_threshold)` | 値が期待値と一致するかチェック |
| `update_rect(element, ...)` | rect要素の属性を更新 |
| `update_arc(element, ...)` | arc要素の属性を更新 |

### align.py の主要関数

| 関数/クラス | 説明 |
|------------|------|
| `parse_rule_file(rule_path)` | YAMLルールファイルをパース |
| `validate_svg(svg_path, rule, fix)` | SVGファイルを検査（オプションで修正） |
| `format_report(report)` | 検査結果をテキストにフォーマット |
| `AlignmentRule` | アライメントルールのデータクラス |
| `AlignmentReport` | 検査結果レポートのデータクラス |
| `GroupRule` | グループごとのルールデータクラス |
| `ValidationResult` | 要素ごとの検査結果データクラス |

# SVG Text要素自動追加機能 仕様書

## 1. 概要

### 1.1 目的

SVGファイルに指定されたグリッド位置にtext要素を自動追加し、ブレッドボード等の図面に座標ラベルを作成する。

### 1.2 背景

ブレッドボード図面には列ラベル（1, 2, 3...）や行ラベル（a, b, c...）が必要である。これらのtext要素を手動で作成するのは手間がかかりミスも発生しやすいため、グリッド位置に正確に配置する自動化ツールを提供する。

## 2. 機能要件

### 2.1 コマンドラインインターフェース

```bash
./scripts/svg_add_text.py <SVG_FILE> --rule <RULE_YAML> [--output <OUTPUT_SVG>]
```

| 引数 | 必須 | 説明 |
|------|------|------|
| `SVG_FILE` | Yes | 入力SVGファイルパス |
| `--rule, -r` | Yes | YAMLルールファイルパス |
| `--output, -o` | No | 出力SVGファイルパス |
| `--dry-run` | No | 変更を適用せずプレビューのみ |

### 2.2 動作モード

| モード | 条件 | 動作 |
|--------|------|------|
| プレビュー | `--output`なし | 作成されるtext要素を報告。ファイル修正なし |
| 適用 | `--output`あり | text要素を作成し出力ファイルに書き込み |
| ドライラン | `--dry-run`と`--output` | 作成内容を表示するが書き込みなし |

## 3. ルールファイル仕様

### 3.1 ファイル形式

YAML形式で記述する。

### 3.2 構造

```yaml
groups:
  - name: "<グループ名>"          # 作成するグループ名（inkscape:label）
    y: <y座標>                    # Y座標（mm）
    x_start: <開始x座標>          # 開始X座標（mm）
    x_end: <終了x座標>            # 終了X座標（mm）
    x_interval: <x間隔>           # X間隔（mm）

    font:                         # フォント設定（省略可）
      family: "<フォント名>"       # フォントファミリー、デフォルト: "Noto Sans CJK JP"
      size: <サイズ>              # フォントサイズ（px）、デフォルト: 1.41111
      color: "<色>"               # 文字色、デフォルト: "#000000"

    format:                       # ラベル形式設定（省略可）
      type: <形式タイプ>          # number | letter | letter_upper | custom
      padding: <パディング>       # ゼロパディング幅、デフォルト: 0
      start: <開始インデックス>   # 開始インデックス、デフォルト: 1
      custom: []                  # カスタムラベルリスト（type: custom時）
```

### 3.3 ルールファイル例

```yaml
groups:
  - name: "col-labels"
    y: 2.54
    x_start: 5.08
    x_end: 78.74
    x_interval: 2.54
    font:
      family: "Noto Sans CJK JP"
      size: 1.41111
      color: "#0000ff"
    format:
      type: number
      padding: 0
      start: 1

  - name: "row-labels-left"
    y: 5.08
    x_start: 2.54
    x_end: 2.54
    x_interval: 2.54
    format:
      type: letter
      start: 1

  - name: "custom-labels"
    y: 10.16
    x_start: 0.0
    x_end: 10.16
    x_interval: 2.54
    format:
      type: custom
      custom: ["+", "a", "b", "c", "-"]
```

## 4. テキスト配置

### 4.1 座標系

- すべての座標はミリメートル（mm）単位
- グリッド位置は`x_start`から`x_end`まで`x_interval`刻みで計算
- テキストのバウンディングボックス中心がグリッド位置に配置される

### 4.2 バウンディングボックス中央配置

text要素の位置はバウンディングボックスの中心がグリッド点に一致するよう計算する：

```
グリッド位置: (grid_x, grid_y)  # mm単位
テキスト位置: (text_x, text_y)  # SVG text要素のx,y（ベースライン左端）

オフセット計算（px単位）:
  text_width = len(text) * font_size * char_width_ratio
  cap_height = font_size * cap_height_ratio

  offset_x = -text_width / 2   # 水平中央に配置するため左へシフト
  offset_y = cap_height / 2    # ベースラインは中心より下なので下へシフト

最終位置:
  text_x = mm_to_px(grid_x) + offset_x
  text_y = mm_to_px(grid_y) + offset_y
```

### 4.3 フォントメトリクス推定値

デフォルトのフォントメトリクス比率（概算値）：

| メトリクス | 比率 | 説明 |
|-----------|------|------|
| `cap_height_ratio` | 0.72 | 大文字の高さ / フォントサイズ |
| `char_width_ratio` | 0.55 | 平均文字幅 / フォントサイズ |

## 5. ラベル形式タイプ

### 5.1 number形式

`start`インデックスからの連番。

| インデックス | 出力（padding=0） | 出力（padding=2） |
|-------------|-------------------|-------------------|
| 1 | "1" | "01" |
| 10 | "10" | "10" |
| 100 | "100" | "100" |

### 5.2 letter形式

小文字アルファベット（a-z, aa-az, ba-bz, ...）。

| インデックス | 出力 |
|-------------|------|
| 1 | "a" |
| 26 | "z" |
| 27 | "aa" |
| 52 | "az" |

### 5.3 letter_upper形式

大文字アルファベット（A-Z, AA-AZ, BA-BZ, ...）。

| インデックス | 出力 |
|-------------|------|
| 1 | "A" |
| 26 | "Z" |
| 27 | "AA" |

### 5.4 custom形式

`custom`リストで定義されたユーザー指定ラベル。

```yaml
format:
  type: custom
  custom: ["+", "a", "b", "c", "d", "e", "-"]
```

## 6. 出力仕様

### 6.1 レポート出力（標準出力）

```
File: <入力ファイルパス>

Group: <グループ名>
  Y: <y座標> mm
  X range: <開始x> - <終了x> mm
  X interval: <x間隔> mm
  Elements: <要素数>

  Created elements:
    <要素ID>: "<テキスト>" at (<grid_x>, <grid_y>) mm
    ...

Summary:
  Total groups: <グループ数>
  Total elements: <総要素数>

<結果メッセージ>
```

### 6.2 結果メッセージ

| 状態 | メッセージ |
|------|-----------|
| エラーあり | `*** ERRORS DETECTED - Output file will not be generated ***` |
| 成功 | （メッセージなし） |

### 6.3 終了コード

| コード | 意味 |
|--------|------|
| 0 | 成功 |
| 1 | 入出力エラー（ファイル読み込み失敗等） |
| 2 | ルールファイル解析エラー |
| 3 | 処理エラー（ラベル生成失敗等） |

### 6.4 出力ファイル生成条件

| 条件 | 出力ファイル |
|------|-------------|
| エラー検出 | 生成しない |
| エラーなし | 新規textグループを追加して生成 |

## 7. SVG出力構造

### 7.1 生成されるグループ構造

```xml
<g id="col-labels" inkscape:label="col-labels">
  <text id="col-labels-text-1" x="..." y="..."
        style="font-family:...;font-size:...px;fill:...">1</text>
  <text id="col-labels-text-2" x="..." y="..."
        style="font-family:...;font-size:...px;fill:...">2</text>
  ...
</g>
```

### 7.2 使用する名前空間

| プレフィックス | URI |
|---------------|-----|
| svg | `http://www.w3.org/2000/svg` |
| inkscape | `http://www.inkscape.org/namespaces/inkscape` |

## 8. デフォルト値

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `font.family` | "Noto Sans CJK JP" | フォントファミリー |
| `font.size` | 1.41111 | フォントサイズ（px） |
| `font.color` | "#000000" | 文字色 |
| `format.type` | "number" | 形式タイプ |
| `format.padding` | 0 | ゼロパディング幅 |
| `format.start` | 1 | 開始インデックス |

## 9. 単位変換

SVGは標準で96 DPIを使用してpxと物理単位を変換する：

```
1 inch = 96 px = 25.4 mm
1 mm = 96 / 25.4 px ≈ 3.7795 px
1 px = 25.4 / 96 mm ≈ 0.2646 mm
```

## 10. 制約事項

### 10.1 対応機能

- グループごとに1行のテキスト（全要素が同じY座標）
- 複数行は複数グループで定義可能
- 開始インデックスからの連番ラベル

### 10.2 未対応機能

- 回転テキスト
- 複数行テキスト要素
- グループ内での可変間隔
- パスに沿ったテキスト

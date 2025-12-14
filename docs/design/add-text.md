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

2つのレイアウトモードをサポート：
- **横配置（Horizontal）**: Y座標固定、X軸方向に配置
- **縦配置（Vertical）**: X座標固定、Y軸方向に配置

レイアウトモードはフィールドの存在で自動判定される。

```yaml
groups:
  # 横配置（Horizontal）: Y固定、X可変
  - name: "<グループ名>"          # 作成するグループ名（inkscape:label）
    y: <y座標>                    # 固定Y座標（mm）
    x_start: <開始x座標>          # 開始X座標（mm）
    x_end: <終了x座標>            # 終了X座標（mm）
    x_interval: <x間隔>           # X間隔（mm）

    font:                         # フォント設定（省略可）
      family: "<フォント名>"       # フォントファミリー、デフォルト: "Noto Sans CJK JP"
      size: <サイズ>              # フォントサイズ（mm）、デフォルト: 1.0
      color: "<色>"               # 文字色、デフォルト: "#000000"

    format:                       # ラベル形式設定（省略可）
      type: <形式タイプ>          # number | letter | letter_upper | custom
      padding: <パディング>       # ゼロパディング幅、デフォルト: 0
      start: <開始インデックス>   # 開始インデックス、デフォルト: 1
      custom: []                  # カスタムラベルリスト（type: custom時）

  # 縦配置（Vertical）: X固定、Y可変
  - name: "<グループ名>"          # 作成するグループ名（inkscape:label）
    x: <x座標>                    # 固定X座標（mm）
    y_start: <開始y座標>          # 開始Y座標（mm）
    y_end: <終了y座標>            # 終了Y座標（mm）
    y_interval: <y間隔>           # Y間隔（mm）
    font: ...                     # 上記と同じ
    format: ...                   # 上記と同じ
```

### 3.2.1 レイアウトモード

| モード | 固定軸 | 可変軸 | 必須フィールド |
|--------|-------|--------|----------------|
| 横配置（Horizontal） | Y | X | `y`, `x_start`, `x_end`, `x_interval` |
| 縦配置（Vertical） | X | Y | `x`, `y_start`, `y_end`, `y_interval` |

**注意**: 同一グループに横配置と縦配置の両方のフィールドを指定するとエラーになる。

### 3.3 ルールファイル例

```yaml
groups:
  # 横配置の例（列ラベル）
  - name: "col-labels"
    y: 2.54
    x_start: 5.08
    x_end: 78.74
    x_interval: 2.54
    font:
      family: "Noto Sans CJK JP"
      size: 1.4   # mm
      color: "#0000ff"
    format:
      type: number
      padding: 0
      start: 1

  # 横配置の例（単一位置）
  - name: "row-labels-left"
    y: 5.08
    x_start: 2.54
    x_end: 2.54
    x_interval: 2.54
    format:
      type: letter
      start: 1

  # 縦配置の例（行ラベル）
  - name: "row-labels"
    x: 2.54
    y_start: 5.08
    y_end: 38.1
    y_interval: 2.54
    font:
      family: "Noto Sans CJK JP"
      size: 1.4
      color: "#0000ff"
    format:
      type: custom
      custom: [a, b, c, d, e, f, _, _, g, h, i, j, k, l]

  # カスタムラベルの例
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
- テキストのバウンディングボックス中心がグリッド位置に配置される

**横配置（Horizontal）の場合：**
- グリッド位置は`x_start`から`x_end`まで`x_interval`刻みで計算
- Y座標は`y`で固定

**縦配置（Vertical）の場合：**
- グリッド位置は`y_start`から`y_end`まで`y_interval`刻みで計算
- X座標は`x`で固定

### 4.2 バウンディングボックス中央配置

text要素の位置はバウンディングボックスの中心がグリッド点に一致するよう計算する。
FreeTypeライブラリを使用して正確なフォントメトリクスを取得する：

```
グリッド位置: (grid_x, grid_y)  # mm単位
テキスト位置: (text_x, text_y)  # SVG text要素のx,y（ベースライン左端）

FreeTypeによるオフセット計算:
  1. fc-matchでフォントファイルを検索
  2. FreeTypeで100ptサイズで測定（精度向上のため）
  3. バウンディングボックス情報（x_bearing, width, y_bearing, height）を取得
  4. ターゲットサイズにスケール

  offset_x = -(x_bearing + width / 2)   # 水平中央に配置
  offset_y = -(y_bearing + height / 2)  # 垂直中央に配置

最終位置:
  text_x = grid_x + offset_x  # mm単位
  text_y = grid_y + offset_y  # mm単位
```

### 4.3 フォントメトリクス（フォールバック）

FreeTypeが利用できない場合の推定値：

| メトリクス | 比率 | 説明 |
|-----------|------|------|
| `cap_height_ratio` | 0.75 | 大文字の高さ / フォントサイズ |
| `char_width_ratio` | 0.50 | 平均文字幅 / フォントサイズ |

### 4.4 SVG font-size互換性

SVGのviewBoxがmm相当の座標系（例: `viewBox="0 0 210 297"` with `width="210mm"`）を使用する場合、
`font-size`は単位なしで出力される（viewBox単位として解釈される）：

```xml
<text style="font-size:1.4">  <!-- 1.4 viewBox単位 = 1.4mm -->
```

これにより、FreeTypeで計算したメトリクスとInkscapeのレンダリング結果が一致する。

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

#### スキップマーカー

`_`（アンダースコア）はスキップマーカーとして予約されている。
このインデックスに対応する位置ではテキスト要素は生成されず、エラーとして報告される。

```yaml
format:
  type: custom
  custom: [a, b, c, _, _, d, e, f]  # インデックス4,5はスキップ
```

これはブレッドボードの電源レール（穴がない行）などに有用。

## 6. 出力仕様

### 6.1 レポート出力（標準出力）

**横配置（Horizontal）の場合：**
```
File: <入力ファイルパス>

Group: <グループ名>
  Layout: horizontal (Y fixed)
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
```

**縦配置（Vertical）の場合：**
```
File: <入力ファイルパス>

Group: <グループ名>
  Layout: vertical (X fixed)
  X: <x座標> mm
  Y range: <開始y> - <終了y> mm
  Y interval: <y間隔> mm
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
| `font.size` | 1.0 | フォントサイズ（mm） |
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

- 2つのレイアウトモード: 横配置（Y固定）と縦配置（X固定）
- グループごとに1ライン（行または列）のテキスト
- 複数ラインは複数グループで定義可能
- 開始インデックスからの連番ラベル
- カスタムラベルのスキップマーカー（`_`）

### 10.2 未対応機能

- 回転テキスト
- 複数行テキスト要素
- グループ内での可変間隔
- パスに沿ったテキスト
- 斜め配置

## 11. 依存関係

| パッケージ | 用途 |
|-----------|------|
| `freetype-py` | フォントメトリクス計算 |
| `PyYAML` | ルールファイル解析 |
| `fontconfig` (システム) | `fc-match`によるフォント検索 |

# SVG形状ラベル付け替え要求仕様書

## 1. 概要

### 1.1 目的

Inkscapeで作成されたSVGファイル内の形状要素（rect, arc等）のラベル（`inkscape:label`属性）を、座標に基づいた規則的な命名に付け替えるツールを提供する。

### 1.2 背景

ブレッドボードや基板図面などでは、グリッド配置された多数の穴（矩形または円）に対して、座標に基づいた体系的なラベル付けが必要となる。手動でのラベル付けは非効率であり、エラーも発生しやすいため、自動化が必要となる。

### 1.3 ユースケース

- ブレッドボード穴の座標ラベル付け（例: `hole-1-a`, `hole-2-b`）
- 基板パッド/ビアの座標ラベル付け
- グリッド配置された部品の識別子付与

## 2. 機能要件

### 2.1 コマンドラインインターフェース

```bash
./scripts/svg_relabel.py <SVG_FILE> --rule <RULE_YAML> [--output <OUTPUT_SVG>] [--dry-run]
```

| 引数 | 必須 | 説明 |
|------|------|------|
| `SVG_FILE` | Yes | 入力SVGファイルパス |
| `--rule, -r` | Yes | YAMLルールファイルパス |
| `--output, -o` | No | 出力SVGファイルパス |
| `--dry-run` | No | 変更を適用せず、プレビューのみ表示 |

### 2.2 動作モード

| モード | 条件 | 動作 |
|--------|------|------|
| プレビューモード | `--output`なし または `--dry-run` | ラベル変更内容を標準出力に報告。ファイル修正なし |
| 修正モード | `--output`あり かつ `--dry-run`なし | ラベルを付け替えて出力 |

## 3. ルールファイル仕様

### 3.1 ファイル形式

YAML形式で記述する。

### 3.2 構造

```yaml
groups:
  - name: "<グループ名>"           # inkscape:label属性で指定されたグループ名
    shape: <形状タイプ>            # rect | arc
    label_template: "<テンプレート>"  # ラベルテンプレート文字列

    # 座標系設定
    origin:                        # 原点位置（省略可、デフォルト: グループ内最小座標）
      x: <X座標>                   # 原点X座標（mm）
      y: <Y座標>                   # 原点Y座標（mm）

    grid:                          # グリッド単位（必須）
      x: <グリッド単位>            # X方向グリッド単位（mm）
      y: <グリッド単位>            # Y方向グリッド単位（mm）

    # 軸方向設定（省略可）
    axis:
      x_direction: <方向>          # positive（右が+）| negative（左が+）、デフォルト: positive
      y_direction: <方向>          # positive（下が+）| negative（上が+）、デフォルト: positive

    # インデックス開始値（省略可）
    index:
      x_start: <開始値>            # X方向開始インデックス、デフォルト: 1
      y_start: <開始値>            # Y方向開始インデックス、デフォルト: 1

    # ラベルフォーマット（省略可）
    format:
      x_type: <型>                 # number | letter | letter_upper、デフォルト: number
      y_type: <型>                 # number | letter | letter_upper、デフォルト: letter
      x_padding: <桁数>            # 数値ゼロ埋め桁数、デフォルト: 0（埋めなし）
      y_padding: <桁数>            # 数値ゼロ埋め桁数、デフォルト: 0（埋めなし）
```

### 3.3 ラベルテンプレート

テンプレート内で以下のプレースホルダーが使用可能。

| プレースホルダー | 説明 | 例 |
|-----------------|------|-----|
| `{x}` | X方向インデックス（フォーマット適用済み） | `1`, `01`, `a`, `A` |
| `{y}` | Y方向インデックス（フォーマット適用済み） | `1`, `01`, `a`, `A` |
| `{x_raw}` | X方向インデックス（数値） | `1`, `2`, `3` |
| `{y_raw}` | Y方向インデックス（数値） | `1`, `2`, `3` |
| `{cx}` | 要素中心X座標（mm） | `12.70` |
| `{cy}` | 要素中心Y座標（mm） | `25.40` |

### 3.4 フォーマット型

| 型 | 説明 | 出力例 |
|----|------|--------|
| `number` | 数値 | `1`, `2`, `3`, ... `26`, `27`, ... |
| `letter` | 小文字アルファベット | `a`, `b`, `c`, ... `z`, `aa`, `ab`, ... |
| `letter_upper` | 大文字アルファベット | `A`, `B`, `C`, ... `Z`, `AA`, `AB`, ... |

### 3.5 ルールファイル例

```yaml
groups:
  - name: "s-circle"
    shape: arc
    label_template: "hole-{x}-{y}"
    grid:
      x: 2.54
      y: 2.54
    origin:
      x: 10.16
      y: 10.16
    axis:
      x_direction: positive
      y_direction: positive
    index:
      x_start: 1
      y_start: 1
    format:
      x_type: number
      y_type: letter
      x_padding: 0

  - name: "s-rect"
    shape: rect
    label_template: "pad-{x}{y}"
    grid:
      x: 1.27
      y: 1.27
    format:
      x_type: letter_upper
      y_type: number
      y_padding: 2
```

上記例の出力ラベル:
- `s-circle`グループ: `hole-1-a`, `hole-1-b`, `hole-2-a`, ...
- `s-rect`グループ: `pad-A01`, `pad-A02`, `pad-B01`, ...

## 4. 処理仕様

### 4.1 対象形状

| 形状タイプ | SVG要素 | 説明 |
|-----------|---------|------|
| `rect` | `<rect>` | 矩形要素 |
| `arc` | `<path sodipodi:type="arc">` | Inkscape円弧要素 |

### 4.2 グループの識別

- `inkscape:label`属性でグループを識別する
- ネストされたグループも検索対象とする

### 4.3 中心座標の計算

| 形状 | 中心座標 | 計算方法 |
|------|----------|----------|
| rect | `(cx, cy)` | `(x + width/2, y + height/2)` |
| arc | `(cx, cy)` | `(sodipodi:cx, sodipodi:cy)` |

### 4.4 インデックス計算

1. **原点の決定**
   - `origin`が指定されている場合: 指定値を使用
   - `origin`が省略されている場合: グループ内全要素の最小中心座標を原点とする

2. **グリッドインデックスの計算**
   ```
   grid_x = round((center_x - origin_x) / grid.x)
   grid_y = round((center_y - origin_y) / grid.y)
   ```

3. **軸方向の適用**
   - `x_direction: negative` の場合: `grid_x = -grid_x`
   - `y_direction: negative` の場合: `grid_y = -grid_y`

4. **開始インデックスの加算**
   ```
   index_x = grid_x + x_start
   index_y = grid_y + y_start
   ```

### 4.5 ラベルフォーマット

#### 4.5.1 数値フォーマット（number）

```
padding = 0の場合: str(index)        → "1", "2", "10"
padding = 2の場合: str(index).zfill(2) → "01", "02", "10"
padding = 3の場合: str(index).zfill(3) → "001", "002", "010"
```

#### 4.5.2 アルファベットフォーマット（letter / letter_upper）

```python
def to_letter(n: int, upper: bool = False) -> str:
    """1から始まるインデックスをアルファベットに変換

    1 -> 'a', 26 -> 'z', 27 -> 'aa', 28 -> 'ab', ...
    """
    result = []
    while n > 0:
        n -= 1
        result.append(chr(ord('a') + (n % 26)))
        n //= 26
    return ''.join(reversed(result)).upper() if upper else ''.join(reversed(result))
```

### 4.6 ラベル更新

`inkscape:label`属性を新しいラベル値で更新する。

```xml
<!-- Before -->
<rect id="rect123" inkscape:label="old-label" ... />

<!-- After -->
<rect id="rect123" inkscape:label="hole-1-a" ... />
```

## 5. 出力仕様

### 5.1 レポート出力（標準出力）

```
File: <入力ファイルパス>

Group: <グループ名> (<形状タイプ>)
  Total elements: <要素数>
  Origin: (<origin_x>, <origin_y>)
  Grid: (<grid_x>, <grid_y>)

  Label changes:
    <要素ID>: "<旧ラベル>" -> "<新ラベル>"
    <要素ID>: "<旧ラベル>" -> "<新ラベル>"
    ...

  Unchanged: <変更なし要素数>
  Changed: <変更要素数>

Summary:
  Total elements: <全要素数>
  Total changed: <全変更数>

[Output written to: <出力ファイルパス>]
```

### 5.2 終了コード

| コード | 意味 |
|--------|------|
| 0 | 成功 |
| 1 | 入出力エラー（ファイル読み込み/書き込み失敗等） |
| 2 | ルールファイルエラー（フォーマット不正等） |
| 3 | 対象グループが見つからない |

## 6. エラーハンドリング

### 6.1 グループ未検出

指定されたグループが見つからない場合、警告を出力して処理を継続する。

```
Warning: Group 's-circle' not found in SVG
```

### 6.2 グリッド外要素

グリッド位置から大きく外れた要素（グリッド単位の50%以上のズレ）がある場合、警告を出力する。

```
Warning: Element 'rect123' is off-grid by 0.5mm (threshold: 0.635mm)
```

### 6.3 重複ラベル

計算結果として同一ラベルが複数要素に割り当てられる場合、エラーとする。

```
Error: Duplicate label 'hole-1-a' would be assigned to rect123 and rect456
```

## 7. 制約事項

### 7.1 対応形状

現バージョンで対応する形状は以下の2種類のみ。

- rect
- arc（Inkscape sodipodi:type="arc"）

### 7.2 SVG名前空間

以下の名前空間を使用する。

| プレフィックス | URI |
|---------------|-----|
| svg | `http://www.w3.org/2000/svg` |
| inkscape | `http://www.inkscape.org/namespaces/inkscape` |
| sodipodi | `http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd` |

### 7.3 ラベル属性の扱い

- `inkscape:label`属性のみを更新対象とする
- `id`属性は変更しない
- 要素に`inkscape:label`属性が存在しない場合、新規に追加する

## 8. デフォルト値

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `origin` | (グループ内最小座標) | 自動計算 |
| `axis.x_direction` | `positive` | 右が正方向 |
| `axis.y_direction` | `positive` | 下が正方向 |
| `index.x_start` | `1` | X方向開始インデックス |
| `index.y_start` | `1` | Y方向開始インデックス |
| `format.x_type` | `number` | 数値フォーマット |
| `format.y_type` | `letter` | 小文字アルファベット |
| `format.x_padding` | `0` | ゼロ埋めなし |
| `format.y_padding` | `0` | ゼロ埋めなし |

## 9. 将来拡張

以下の機能は将来バージョンでの追加を検討する。

- **カスタムフォーマット関数**: 正規表現やPython式によるカスタムフォーマット
- **条件付きラベル付け**: 座標範囲によるフィルタリング
- **既存ラベルの保持オプション**: 特定パターンのラベルを保持
- **バッチ処理**: 複数SVGファイルの一括処理

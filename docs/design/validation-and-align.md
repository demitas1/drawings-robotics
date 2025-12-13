# SVG形状バリデーション・アラインメント要求仕様書

## 1. 概要

### 1.1 目的

Inkscapeで作成されたSVGファイル内の形状要素（rect, arc, path）を検査し、指定されたグリッドおよびサイズ仕様に適合するよう修正するツールを提供する。

### 1.2 背景

ブレッドボード等の電子部品図面では、穴位置が2.54mmピッチ（または1.27mmの倍数）で配置される必要がある。Inkscapeでの手動編集時に微小なズレが生じることがあるため、自動検査・修正機能が必要となる。

## 2. 機能要件

### 2.1 コマンドラインインターフェース

```bash
./scripts/svg_align.py <SVG_FILE> --rule <RULE_YAML> [--output <OUTPUT_SVG>]
```

| 引数 | 必須 | 説明 |
|------|------|------|
| `SVG_FILE` | Yes | 入力SVGファイルパス |
| `--rule, -r` | Yes | YAMLルールファイルパス |
| `--output, -o` | No | 出力SVGファイルパス |

### 2.2 動作モード

| モード | 条件 | 動作 |
|--------|------|------|
| 検査モード | `--output`なし | 検査結果を標準出力に報告。ファイル修正なし |
| 修正モード | `--output`あり | 検査後、修正可能な要素を修正して出力 |

## 3. ルールファイル仕様

### 3.1 ファイル形式

YAML形式で記述する。

### 3.2 構造

```yaml
groups:
  - name: "<グループ名>"      # inkscape:label属性で指定されたグループ名
    shape: <形状タイプ>       # rect | arc | path
    grid:                     # グリッド位置検査（省略可）
      x: <グリッド単位>       # X方向グリッド単位（mm）
      y: <グリッド単位>       # Y方向グリッド単位（mm）
    size:                     # サイズ検査（省略可、rect/arcのみ）
      width: <幅>             # 期待する幅（mm）
      height: <高さ>          # 期待する高さ（mm）
    arc:                      # arc形状固有パラメータ（省略可）
      start: <開始角度>       # 開始角度（rad）、デフォルト: 0
      end: <終了角度>         # 終了角度（rad）、デフォルト: 6.2831853 (2π)

tolerance:                    # 許容誤差設定（省略可）
  acceptable: <許容値>        # 許容誤差（mm/rad）、デフォルト: 0.001
  error_threshold: <閾値>     # エラー閾値（比率）、デフォルト: 0.1 (10%)
```

### 3.3 ルールファイル例

```yaml
groups:
  - name: "s-rect"
    shape: rect
    grid:
      x: 1.27
      y: 1.27
    size:
      width: 1.27
      height: 1.27

  - name: "s-circle"
    shape: arc
    grid:
      x: 1.27
      y: 1.27
    size:
      width: 0.635
      height: 0.635
    arc:
      start: 0
      end: 6.2831853

  - name: "connection"
    shape: path
    grid:
      x: 1.27
      y: 1.27

tolerance:
  acceptable: 0.001
  error_threshold: 0.1
```

## 4. 検査仕様

### 4.1 対象形状

| 形状タイプ | SVG要素 | 説明 |
|-----------|---------|------|
| `rect` | `<rect>` | 矩形要素 |
| `arc` | `<path sodipodi:type="arc">` | Inkscape円弧要素 |
| `path` | `<path>` (arc以外) | 線分パス要素 |

### 4.2 グループの識別

- `inkscape:label`属性でグループを識別する
- ネストされたグループも検索対象とする

### 4.3 位置の基準点

| 形状 | 基準点 | 計算方法 |
|------|--------|----------|
| rect | 中心座標 | `(x + width/2, y + height/2)` |
| arc | 中心座標 | `(sodipodi:cx, sodipodi:cy)` |
| path | 始点・終点 | d属性から抽出した `(start_x, start_y)`, `(end_x, end_y)` |

### 4.4 検査項目

#### 4.4.1 グリッド位置検査

中心座標（rect, arc）または始点・終点座標（path）が指定グリッド単位の倍数であることを検査する。

- **検査対象**:
  - rect/arc: 中心のX座標、Y座標
  - path: 始点のX座標、Y座標、終点のX座標、Y座標
- **判定基準**: `座標 % グリッド単位` の余り（または`グリッド単位 - 余り`の小さい方）

#### 4.4.2 サイズ検査

要素のサイズが指定値と一致することを検査する。

| 形状 | 検査対象 |
|------|----------|
| rect | `width`, `height`属性 |
| arc | `sodipodi:rx * 2`, `sodipodi:ry * 2`（直径） |

#### 4.4.3 arc固有パラメータ検査

- **開始角度**: `sodipodi:start`
- **終了角度**: `sodipodi:end`

#### 4.4.4 path固有パラメータ

pathはd属性から始点・終点を抽出する。対応するSVGパスコマンド:

| コマンド | 説明 |
|---------|------|
| `M`/`m` | Moveto（絶対/相対） |
| `L`/`l` | Lineto（絶対/相対） |
| `H`/`h` | 水平Lineto（絶対/相対） |
| `V`/`v` | 垂直Lineto（絶対/相対） |
| `Z`/`z` | クローズパス |

### 4.5 判定ロジック

各検査項目について以下の3段階で判定する。

| 判定 | 条件 | 動作 |
|------|------|------|
| OK | `偏差 ≤ acceptable` | 修正不要 |
| FIXABLE | `acceptable < 偏差 ≤ expected × error_threshold` | 修正可能 |
| ERROR | `偏差 > expected × error_threshold` | 修正不可（エラー） |

## 5. 修正仕様

### 5.1 修正順序

修正は以下の順序で実行する。

1. **サイズ修正**: width/height または rx/ry を指定値に設定
2. **arc固有パラメータ修正**: start/end を指定値に設定
3. **位置修正**: 修正後のサイズに基づいて中心座標を最近傍グリッド位置にスナップ

### 5.2 位置スナップ

```
スナップ後の値 = round(現在値 / グリッド単位) × グリッド単位
```

### 5.3 rect要素の修正

```
新しいx = スナップ後の中心x - width / 2
新しいy = スナップ後の中心y - height / 2
```

### 5.4 arc要素の修正

```
sodipodi:cx = スナップ後の中心x
sodipodi:cy = スナップ後の中心y
```

### 5.5 path要素の修正

始点・終点をスナップし、d属性を再生成する。

```
スナップ後の始点 = (round(start_x / grid) * grid, round(start_y / grid) * grid)
スナップ後の終点 = (round(end_x / grid) * grid, round(end_y / grid) * grid)
```

パスの種類に応じたd属性の再生成:
- **垂直線**: `start_x == end_x` の場合 → `M start_x,start_y V end_y`
- **水平線**: `start_y == end_y` の場合 → `M start_x,start_y H end_x`
- **斜め線**: それ以外 → `M start_x,start_y L end_x,end_y`

## 6. 出力仕様

### 6.1 レポート出力（標準出力）

```
File: <入力ファイルパス>
Total elements checked: <検査要素数>
Errors: <エラー要素数>
Fixable: <修正可能要素数>

Group: <グループ名> (<形状タイプ>)
  OK: <OK数>, Fixable: <修正可能数>, Errors: <エラー数>
  [FIXABLE] <要素ID>
    - <検査項目>=<実測値> (expected: <期待値>)
  [ERROR] <要素ID>
    - <検査項目>=<実測値> (expected: <期待値>)

<結果メッセージ>
```

### 6.2 結果メッセージ

| 状態 | メッセージ |
|------|-----------|
| エラーあり | `*** ERRORS DETECTED - Output file will not be generated ***` |
| 修正可能のみ | `All fixable issues can be corrected.` |

### 6.3 終了コード

| コード | 意味 |
|--------|------|
| 0 | 成功（エラーなし） |
| 1 | 入出力エラー（ファイル読み込み失敗等） |
| 2 | バリデーションエラー（ERROR判定の要素あり） |

### 6.4 出力ファイル生成条件

| 条件 | 出力ファイル |
|------|-------------|
| ERROR判定の要素が1つ以上存在 | 生成しない |
| ERROR判定の要素が存在しない | 生成する（FIXABLE要素は修正済み） |

## 7. 制約事項

### 7.1 対応形状

現バージョンで対応する形状は以下の3種類。

- rect
- arc（Inkscape sodipodi:type="arc"）
- path（線分パス、M/L/H/V/Zコマンドのみ）

### 7.2 SVG名前空間

以下の名前空間を使用する。

| プレフィックス | URI |
|---------------|-----|
| svg | `http://www.w3.org/2000/svg` |
| inkscape | `http://www.inkscape.org/namespaces/inkscape` |
| sodipodi | `http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd` |

### 7.3 arc要素のpath d属性

arc要素の`d`属性（パスデータ）は更新しない。sodipodi属性のみを修正する。Inkscapeで再度開いた際に`d`属性は自動再生成される。

## 8. デフォルト値

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `tolerance.acceptable` | 0.001 | 許容誤差（mm/rad） |
| `tolerance.error_threshold` | 0.1 | エラー閾値（10%） |
| `arc.start` | 0 | 開始角度（rad） |
| `arc.end` | 6.2831853 | 終了角度（2π rad） |

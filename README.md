# SVG Cross-Platform Compatibility Tools

InkscapeでつくったSVGをクロスプラットフォーム（Ubuntu, macOS, Windows）で一貫したレンダリング結果を得るためのツール集です。

## 概要

- SVGの正規化（フォントスタック適用、不要属性削除、キャンバスサイズ検証）
- マルチOS環境でのレンダリングテスト
- 画像類似度による品質検証

## キャンバス仕様

| 項目 | 値 |
|------|-----|
| 基準サイズ | A4 300dpi |
| 縦向き | 2480px × 3508px |
| 横向き | 3508px × 2480px |

## ディレクトリ構成

```
assets/source/       # Inkscapeで作成したSVG
assets/normalized/   # 正規化済みSVG
assets/baseline/     # 基準PNG
src/svg_tools/       # Pythonパッケージ
templates/           # A4テンプレート
```

## 使い方

### SVG統合処理（推奨）

`svg_process.py` は align → relabel → add_text の3ステップを統合したパイプライン処理ツールです。

```bash
# 検証のみ（出力ファイルなし）
./venv/bin/python scripts/svg_process.py input.svg --rule rules.yaml

# 処理して出力
./venv/bin/python scripts/svg_process.py input.svg --rule rules.yaml --output output.svg

# 特定ステップのみ実行
./venv/bin/python scripts/svg_process.py input.svg --rule rules.yaml --steps align,relabel

# ドライラン（変更プレビューのみ）
./venv/bin/python scripts/svg_process.py input.svg --rule rules.yaml --output output.svg --dry-run
```

#### 統合ルールファイル形式

```yaml
# 各セクションは省略可能（省略されたステップはスキップ）

align:
  groups:
    - name: "s-rect"
      shape: rect
      grid: { x: 1.27, y: 1.27 }
      size: { width: 1.27, height: 1.27 }
  tolerance:
    acceptable: 0.001
    error_threshold: 0.1

relabel:
  groups:
    - name: "s-circle"
      shape: arc
      label_template: "hole-{x}-{y}"
      grid: { x: 2.54, y: 2.54 }

add_text:
  groups:
    - name: "col-labels"
      y: 2.54
      x_start: 5.08
      x_end: 78.74
      x_interval: 2.54
```

サンプル: `assets/source/rules/breadboard.yaml`

### 個別ツール

```bash
# SVG正規化（計画中）
svg-tools normalize assets/source/file.svg -o assets/normalized/

# キャンバスサイズ検証（計画中）
svg-tools validate-canvas assets/source/file.svg

# PNG出力（A4 300dpi）
svg-tools render assets/normalized/file.svg -o output.png --preset a4-portrait
```

## ライセンス

- コード: MIT License
- アセット（SVG, PNG）: CC-BY 4.0

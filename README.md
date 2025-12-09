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

```bash
# SVG正規化
svg-tools normalize assets/source/file.svg -o assets/normalized/

# キャンバスサイズ検証
svg-tools validate-canvas assets/source/file.svg

# PNG出力（A4 300dpi）
svg-tools render assets/normalized/file.svg -o output.png --preset a4-portrait
```

## ライセンス

- コード: MIT License
- アセット（SVG, PNG）: CC-BY 4.0

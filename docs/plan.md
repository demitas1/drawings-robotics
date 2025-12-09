## SVGクロスプラットフォーム互換性プロジェクト設計書（改訂版）

---

## 1. プロジェクト概要

| 項目 | 内容 |
|------|------|
| 目的 | Inkscapeで作成したSVGをクロスプラットフォームで一貫したレンダリング結果を得る |
| 公開範囲 | GitHub Public |
| コードライセンス | MIT |
| アセットライセンス | CC-BY 4.0 |

---

## 2. キャンバスサイズ仕様

### A4 300dpi 基準値

| 項目 | 値 |
|------|-----|
| A4物理サイズ | 210mm × 297mm |
| 解像度 | 300dpi |
| ピクセルサイズ | **2480px × 3508px** |
| アスペクト比 | 約 1:1.414 |

### 計算式

```
幅:  210mm ÷ 25.4mm/inch × 300dpi = 2480px
高さ: 297mm ÷ 25.4mm/inch × 300dpi = 3508px
```

### SVGでの指定

```xml
<svg
  xmlns="http://www.w3.org/2000/svg"
  width="210mm"
  height="297mm"
  viewBox="0 0 2480 3508">
  ...
</svg>
```

### 横向き（Landscape）の場合

| 項目 | 値 |
|------|-----|
| ピクセルサイズ | **3508px × 2480px** |

---

## 3. ディレクトリ構成

```
drawings-robotics/
├── README.md
├── LICENSE-CODE                 # MIT (Python等)
├── LICENSE-ASSETS               # CC-BY 4.0 (SVG, PNG)
├── pyproject.toml
│
├── src/
│   └── svg_tools/
│       ├── __init__.py
│       ├── normalizer.py
│       ├── font_stacks.py
│       ├── cleaner.py
│       ├── canvas.py            # キャンバスサイズ検証・変換
│       └── cli.py
│
├── tests/
│   ├── __init__.py
│   ├── test_normalizer.py
│   ├── test_font_stacks.py
│   ├── test_canvas.py
│   └── fixtures/
│       ├── sample.svg
│       └── a4-template.svg      # A4テンプレート
│
├── assets/
│   ├── source/
│   │   ├── diagram-001.svg
│   │   └── ...
│   │
│   ├── normalized/
│   │   ├── diagram-001.svg
│   │   └── ...
│   │
│   └── baseline/
│       ├── diagram-001.png
│       └── ...
│
├── templates/
│   ├── a4-portrait.svg          # A4縦 テンプレート
│   └── a4-landscape.svg         # A4横 テンプレート
│
├── scripts/
│   ├── normalize_all.py
│   ├── render.py
│   └── compare_images.py
│
├── .github/
│   ├── workflows/
│   │   ├── test.yml
│   │   ├── render-test.yml
│   │   └── release.yml
│   │
│   └── ISSUE_TEMPLATE/
│       └── new-svg.md
│
└── docs/
    ├── CONTRIBUTING.md
    ├── plan.md
    ├── svg-guidelines.md
    └── font-policy.md
```

---

## 4. 処理フロー

```
┌─────────────────┐
│  Inkscapeで作成  │
│  (A4テンプレート使用)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ assets/source/  │
│ diagram-xxx.svg │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Python正規化    │
│ - キャンバスサイズ検証
│ - フォントスタック適用
│ - id/label整理
│ - 不要属性削除
└────────┬────────┘
         │
         ▼
┌────────────────────┐
│ assets/normalized/ │
│ diagram-xxx.svg    │
└────────┬───────────┘
         │
         ▼ (GitHub Actions)
┌─────────────────────────────────────┐
│ マルチOSレンダリング (300dpi)        │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│ │ Ubuntu  │ │ macOS   │ │ Windows │ │
│ └────┬────┘ └────┬────┘ └────┬────┘ │
│      ▼           ▼           ▼      │
│  2480×3508   2480×3508   2480×3508  │
│    PNG         PNG         PNG      │
└─────────────────┬───────────────────┘
                  │
                  ▼
         ┌───────────────┐
         │ 類似度 > 90%? │
         └───────┬───────┘
           Yes   │   No
         ┌───────┴───────┐
         ▼               ▼
┌─────────────┐   ┌─────────────┐
│ Release作成  │   │ テスト失敗  │
└─────────────┘   └─────────────┘
```

---

## 5. レンダリング設定

### Inkscapeコマンド

```bash
# A4 300dpi でPNG出力
inkscape input.svg \
  --export-filename=output.png \
  --export-dpi=300 \
  --export-width=2480 \
  --export-height=3508
```

### GitHub Actions での設定

```yaml
- name: Render SVG to PNG (A4 300dpi)
  run: |
    inkscape ${{ matrix.svg }} \
      --export-filename=output-${{ matrix.os }}.png \
      --export-dpi=300
```

---

## 6. CLIツール設計

```bash
# 単一ファイル正規化（キャンバスサイズ検証含む）
svg-tools normalize assets/source/diagram-001.svg -o assets/normalized/

# キャンバスサイズ検証のみ
svg-tools validate-canvas assets/source/diagram-001.svg

# PNG生成（A4 300dpi）
svg-tools render assets/normalized/diagram-001.svg -o output.png \
  --preset a4-portrait

# プリセット一覧
svg-tools presets
#   a4-portrait:  2480 x 3508 px (300dpi)
#   a4-landscape: 3508 x 2480 px (300dpi)
```

---

## 7. SVG作成ガイドライン（docs/svg-guidelines.md）

| 項目 | ルール |
|------|--------|
| キャンバスサイズ | A4 300dpi（2480×3508px または 3508×2480px） |
| 単位 | SVG属性は`mm`、viewBoxは`px` |
| フォント | Noto Sans JP を優先使用 |
| id命名 | `{種別}-{連番}` 例: `rect-001`, `text-header` |
| レイヤー構成 | background, content, labels の3層推奨 |
| テキスト | アウトライン化しない |
| 余白 | 四辺10mm（約118px）推奨 |

---

## 8. テンプレートファイル

### templates/a4-portrait.svg

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg
  xmlns="http://www.w3.org/2000/svg"
  xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
  width="210mm"
  height="297mm"
  viewBox="0 0 2480 3508">
  
  <defs>
    <style type="text/css">
      .default-text {
        font-family: 'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', sans-serif;
        font-size: 42px;
      }
    </style>
  </defs>
  
  <!-- 背景レイヤー -->
  <g inkscape:groupmode="layer" inkscape:label="background" id="layer-background">
  </g>
  
  <!-- コンテンツレイヤー -->
  <g inkscape:groupmode="layer" inkscape:label="content" id="layer-content">
  </g>
  
  <!-- ラベルレイヤー -->
  <g inkscape:groupmode="layer" inkscape:label="labels" id="layer-labels">
  </g>
  
</svg>
```

---

## 9. 出力ファイルサイズ目安

| 形式 | サイズ目安 |
|------|-----------|
| SVG（ソース） | 50KB - 500KB |
| SVG（正規化後） | 30KB - 400KB |
| PNG（A4 300dpi） | 2MB - 10MB |
| PNG（圧縮後） | 500KB - 3MB |

---

## 10. 類似度判定基準

| レベル | 閾値 | 判定 |
|--------|------|------|
| 合格 | ≥ 95% | 実質同一 |
| 許容 | 90-95% | フォント差異のみ |
| 要確認 | 80-90% | レイアウト崩れの可能性 |
| 不合格 | < 80% | 修正必須 |

デフォルト閾値: **90%**

---

## 11. 将来的な拡張案

- [ ] A3、Letter等の追加プリセット
- [ ] 解像度オプション（150dpi, 600dpi）
- [ ] PDF出力対応（印刷用途）
- [ ] Webフォント埋め込みオプション
- [ ] GitHub Pages プレビューサイト

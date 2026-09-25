# 机と猫耳のブロック・ジオラマ

**[GitHub Pagesで組み立てる](https://ktanino10.github.io/octodesk-brick-kit/) · [オフライン一括ZIP](https://github.com/ktanino10/octodesk-brick-kit/releases/download/v1.0.0/octodesk-r1-offline.zip) · [Releaseとハッシュ](https://github.com/ktanino10/octodesk-brick-kit/releases/tag/v1.0.0)**

![配布STLから生成した完成CG（実物写真ではありません）](dist/octodesk-r1/media/hero.png)

ユーザー提供の写真を参考にした、個人用・非公式の独立設計です。箱、印字、ロゴ、元写真は含みません。既存作品のコード・CAD・画像は複製せず、8 mm規格と制作手順のみを参考にしています。市販ブロックとの互換保証・玩具認証はありません。

| 完成寸法 | 組込部品 | 工程・色 | 印刷データ |
| --- | --- | --- | --- |
| **191.8 × 127.8 × 128.0 mm** | **137個・15型** | **37工程・5色** | 本番3MF 8枚。試験片は別枠 |

**対象：Bambu Lab P1S / 0.2 mmノズル / PLA。** プレート・PLA銘柄・実プロファイルは未確認です。全3MFは **NOT_SLICED**。実スライス、嵌合、反り、保持、強度、転倒、耐久性は未評価で、全数印刷の合格を意味しません。プリンター送信・印刷開始は行っていません。

**最初は[ゆるい試験片1組](https://ktanino10.github.io/octodesk-brick-kit/coupons/01-loose-pair-NOT_SLICED.3mf)だけ。** FIT-M-D470とFIT-F-CP12を試し、指で軽く着座・取り外しできることを確認してから、本番2×2・2×4の少量試験へ進みます。STLはmm・100%。同じ部品をSTLと3MFから重複読込みしないでください。

## 保存するもの

| 内容 | ダウンロード |
| --- | --- |
| 日本語の寸法・断面・全工程 | [44ページPDF](https://ktanino10.github.io/octodesk-brick-kit/docs/assembly-manual.pdf) |
| 字幕付き組立動画 | [MP4 / H.264](https://ktanino10.github.io/octodesk-brick-kit/media/assembly.mp4) · [WebM / VP9](https://ktanino10.github.io/octodesk-brick-kit/media/assembly.webm) |
| 印刷形状と数量 | [型別STL](dist/octodesk-r1/stl/) · [色別3MF](dist/octodesk-r1/plates/) · [試験片](dist/octodesk-r1/coupons/) · [BOM](dist/octodesk-r1/data/bom.csv) |
| 編集用CAD | [完成配置FCStd](https://ktanino10.github.io/octodesk-brick-kit/cad/Octodesk-r1.FCStd) · [型ライブラリFCStd](https://ktanino10.github.io/octodesk-brick-kit/cad/Type-library.FCStd) · [STEP](https://ktanino10.github.io/octodesk-brick-kit/cad/Octodesk-r1.step) |
| 編集可能なCG・動画シーン | [Blender](https://ktanino10.github.io/octodesk-brick-kit/cad/Octodesk-r1.blend) |
| 印刷と組立の対応 | [双方向3Dガイド](https://ktanino10.github.io/octodesk-brick-kit/#guide) · [全slotと候補CSV](dist/octodesk-r1/data/plate-to-assembly.csv) |
| 全ファイルを別PCへ | [オフラインZIP](https://github.com/ktanino10/octodesk-brick-kit/releases/download/v1.0.0/octodesk-r1-offline.zip) · [配布receipt](dist/release-receipt.json) |

ZIPを展開して `octodesk-r1/index.html` を開くと、ネットワークやサーバーなしでもガイドを操作できます。リポジトリをcloneした場合の入口は `dist/octodesk-r1/index.html` です。印刷順と組立順は別で、同形同色の部品は交換可能です。

## 公開範囲と検査

この作品の設計ソース・生成物を、承認済みのPublicリポジトリ、GitHub Pages、同リポジトリのReleaseで配布します。元写真・他作品の画像・個人情報・認証情報・ローカル設定・キャッシュは含めません。完成CGの非表示PNGメタデータのみ除去し、画素とr1の形状・配置・数量・公差は維持しています。公開版ZIPのハッシュは旧ローカル版とは異なります。

[デジタル検査レポート](dist/octodesk-r1/validation/report.json)には、native/STEP対応、メッシュ、干渉・挿入経路、数量・3MF対応、動画デコード、PC/375px/オフライン操作の範囲を記載しています。実物の合格判定ではありません。

包括的な再利用ライセンスは未設定です。公開されていることだけをもって自由な再利用が許可されたとは扱わないでください。[NOTICE](NOTICE)と[出典・第三者ライセンス](https://ktanino10.github.io/octodesk-brick-kit/docs/notices.html)を確認してください。

## 再生成

`design/kit.json` を中心データとし、型・個体・工程・接続・色・数量を共有します。配置を改める場合は `scripts/design.py`、形状は `scripts/freecad_build.py` を変更し、関係する出力をすべて再生成してください。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
python3 scripts/design.py
QT_QPA_PLATFORM=offscreen PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/freecad_build.py
QT_QPA_PLATFORM=offscreen PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/native_documents.py
QT_QPA_PLATFORM=offscreen PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/verify_cad.py
.venv/bin/python scripts/package_prints.py
.venv/bin/python scripts/verify_meshes.py
QT_QPA_PLATFORM=offscreen PYTHONPATH="$FREECAD_LIB:scripts" \
  "$FREECAD_PYTHON" scripts/cad_details.py
"$BLENDER" --background --factory-startup --threads 2 --python scripts/blender_scene.py
"$BLENDER" --background --factory-startup --threads 2 \
  dist/octodesk-r1/cad/Octodesk-r1.blend --python scripts/verify_blender.py
.venv/bin/python scripts/encode_movie.py
.venv/bin/python scripts/build_docs.py
node scripts/export_pdf.mjs
npm run build:web
npm run test:web
.venv/bin/python scripts/prepare_publication.py
.venv/bin/python scripts/package_release.py
KIT_DIR="$PWD/build/archive-test/octodesk-r1" \
  BROWSER_REPORT="$PWD/build/archive-browser.json" npm run test:web
.venv/bin/python scripts/package_release.py --finalize
python3 scripts/verify_publication.py --stage
```

FreeCADの組込みPythonと同じABIのライブラリを指定します。別のoffscreen/headlessプロセスで作り、表示中のCAD/Blender文書は操作しません。実スライス、保持力、反り、強度、転倒、耐久性の評価は別途必要です。印刷時間・重量の推定を実スライス値として示しません。

FreeCADのGUI表示色は未確認です。この環境ではoffscreen GUI起動が止まったため、`native_documents.py` が完成配置だけのFCStdと、別に並べた23型（本番15型・試験8型）のFCStdを生成します。形状・位置・工程・色名・PartColor属性はネイティブ再読込で照合します。画面が既定の灰色でも、色を変えて印刷する指示ではありません。色はガイド・BOM・Blenderを参照してください。

動画字幕はインストール済み日本語フォントでラスタライズします。macOS以外では `JAPANESE_FONT` に利用許可されたTTF/TTCを指定してください。フォントファイルは配布しません。MP4はH.264/yuv420p、H.264を持たないChromium等のためWebM/VP9も同梱します。実行環境にPlaywrightのブラウザーがない場合に限り `npx playwright install chromium` で用意します。

ローカルサーバーで見る場合は `python3 -m http.server 8765 --bind 127.0.0.1 --directory dist/octodesk-r1`。完成ZIPはサーバーなしの `file://` でも動作します。

`.github/workflows/pages.yml` は、公開候補の監査・ハッシュ確認・PC/モバイル/オフライン操作が成功してから、`build/pages` の静的ファイルだけを配信します。ソース、依存パッケージ、キャッシュ、ローカル設定をPagesの配布rootへ含めません。重いZIPはGit履歴ではなくRelease assetに置きます。プリンター接続は再生成・公開手順に含みません。

import html
from collections import Counter
from pathlib import Path

from common import OUT, kit, read_json


def esc(text):
    return html.escape(str(text))


STYLE = """
@page{size:A4;margin:13mm}
*{box-sizing:border-box}body{font:10px/1.55 -apple-system,"Hiragino Kaku Gothic ProN",sans-serif;color:#183e35;margin:0}
.page{break-after:page;min-height:263mm;position:relative;padding-bottom:7mm}.page:last-child{break-after:auto}
h1{font-size:27px;line-height:1.5;margin:0 0 10px}h2{font-size:21px;margin:0 0 10px}h3{font-size:13px}
.eyebrow{font-size:9px;letter-spacing:.12em;color:#557a6c}.note{background:#f1ecdc;padding:10px;border-left:3px solid #b9a258}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.grid img{width:100%;object-fit:contain;max-height:91mm}
.hero{width:100%;max-height:150mm;object-fit:contain}.footer{position:absolute;bottom:0;border-top:1px solid #ccd8ce;width:100%;font-size:8px;padding-top:4px;color:#557267}
table{border-collapse:collapse;width:100%;font-size:9px}td,th{border-bottom:1px solid #d1ddd4;padding:5px 4px;text-align:left;vertical-align:top}th{background:#edf3ed}
small{font-size:8px}.diagrams{display:grid;grid-template-columns:1fr 1fr;gap:12px}.diagrams svg{width:100%;height:88mm}
.code{font-family:ui-monospace,monospace;font-size:8px}.tiny{font-size:8px}.pill{display:inline-block;background:#e8efe8;padding:2px 6px}
a{color:#146b56}p{margin:8px 0}.wide img{width:100%;max-height:125mm;object-fit:contain}
"""


def page(title, body, number):
    return f'<section class="page"><p class="eyebrow">DESK / BRICK LAB · R1 · DIGITAL PROTOTYPE</p><h2>{title}</h2>{body}<div class="footer">{number} / 単位mm・縮尺は印刷時に変わります。現物未評価 / オリジナル写真・ロゴは非同梱</div></section>'


def diagram(data, catalog, number, front=False, language="ja"):
    instances = [i for i in data["instances"] if i["step"] <= number]
    if front:
        viewbox = "-15 -145 220 166"
        instances.sort(key=lambda i: -i["anchor_mm"][1])
    else:
        viewbox = "-15 -142 220 162"
        instances.sort(key=lambda i: i["anchor_mm"][2])
    paths, labels = [], []
    for inst in instances:
        p = catalog["parts"][inst["part"]]
        x, y, z = inst["anchor_mm"]
        w, d = [n * 8 - .2 for n in inst["footprint_studs"]]
        h = p["bounds_mm"][1][2]
        xx, yy, ww, hh = (x + .1, -z - h, w, h) if front else (x + .1, -y - d - .1, w, d)
        is_new = inst["step"] == number
        color = data["colors"][inst["color"]]["hex"] if is_new else "#e8ece8"
        paths.append(f'<rect x="{xx}" y="{yy}" width="{ww}" height="{hh}" fill="{color}" stroke="{"#b95429" if is_new else "#b9c8be"}" stroke-width="{.75 if is_new else .18}"/>')
        if is_new:
            label = inst["id"].split("-")[1]
            labels.append(f'<g><rect x="{xx + ww/2 - 5.5}" y="{yy + hh/2 - 2.5}" width="11" height="5" rx="1.4" fill="#b95429"/><text x="{xx + ww/2}" y="{yy + hh/2 + 1.3}" font-size="3.5" fill="white" text-anchor="middle">{label}</text></g>')
    title = "正面（−Yから）/ X→, Z↑" if front else "上面 / X→, Y↑"
    note = "配置図：外接枠 / 橙枠と番号=今回追加 / 薄灰=組立済み"
    if language == "en":
        title = "FRONT (from −Y) / X→, Z↑" if front else "TOP / X→, Y↑"
        note = "Bounding boxes: orange = added now / pale gray = already placed"
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"><rect x="-15" y="-145" width="220" height="180" fill="#f7f8f4"/><text x="0" y="-132" font-size="5">{title}</text>{"".join(paths + labels)}<text x="0" y="14" font-size="{3.2 if language == "en" else 4}">{note}</text></svg>'


def main():
    data, catalog = kit(), read_json(OUT / "data" / "catalog.json")
    manifest = read_json(OUT / "data" / "print-manifest.json")
    docs = OUT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    size = " × ".join(f"{n:.1f}" for n in catalog["assembly_size_mm"])
    count = data["counts"]
    pages = []
    pages.append(page("机と猫耳のブロック・ジオラマ", f"""
<img class="hero" src="../media/hero.png" alt="実際の配布メッシュの完成CG">
<h3>{size} mm / {count['assembly_instances']}個 / {count['assembly_types']}型 / {count['steps']}工程 / 5色</h3>
<p>写真の机・椅子・黒い猫耳キャラクター・淡いベージュの無地の顔・黄色いマグを、分割印刷して積む独立設計です。8 mmピッチ、本体9.6 mm、プレート3.2 mm。箱・印字・公式ロゴは作りません。</p>
<p class="note"><b>P1S · 0.2 mmノズル · PLA / NOT_SLICED</b><br>デジタル試作です。実機の嵌合・反り・保持・強度・転倒・耐久性は未評価。プレート・PLA銘柄・実プロファイルは未確認。全数印刷の前に試験片を確認してください。</p>
<p>このPDFの図はCGまたはCAD投影・断面、あるいは明記した外接枠配置図です。実物写真ではありません。番号は案内用で、部品に刻印されていません。同じ型・色は交換可能です。</p>
<p><a href="assembly-manual.en.pdf">English PDF</a> / 対話ガイドは「日本語 / English」で状態を保って切替できます。動画の日本語焼込みは残し、英語の同期字幕とSRT/VTTを同梱しています。</p>
""", 1))
    pages.append(page("まず試す / 印刷と組立は別の順序", """
<h3>1. ゆるい1組だけ</h3><p class="code">coupons/01-loose-pair-NOT_SLICED.3mf</p>
<p>FIT-M-D470（オス径4.70）と FIT-F-CP12（メスの半径方向クリアランス+0.12）。オス径補正とメスの半径設定は独立です。指で軽く着座・取り外しできるか確認します。試験片は完成137個のBOMに含みません。</p>
<h3>2. 本番の2×2と2×4を各2個</h3><p class="code">coupons/02-representative-NOT_SLICED.3mf</p>
<p>本番はオス4.80 / メス半径+0.04の未評価候補。試験片のゆるさだけで本番を合格にしません。設定変更が必要なら全生成物を同じ版に再生成し、STLだけを勝手に拡大しないでください。</p>
<h3>3. 台座の継ぎ目、次に本番台座</h3><p class="code">coupons/03-base-joint-NOT_SLICED.3mf</p>
<p>8×8を2枚、X方向に並べます。4×8の長辺をXへ向け、下角X=32、Y=0に置き、X=64の継ぎ目をまたぎます。上段はZ=3.2。反り・整列・保持を確認してから本番台座、机、残りを少量ずつ印刷します。</p>
<h3>スライサー</h3><p>ZIPを展開し、形状3MFを読み込み、P1S・0.2 mmノズル・実際のPLA/プレートのプロファイルを選択。STLはmm・100%。同じ部品のSTLと3MFを重複読込みしないでください。単色プレートなのでAMSは必須ではありません。</p>
<p>開いた下面をベッドへ。入口・内部空洞をサポートやbrimで埋めないこと。屋根ブリッジ、マグの取っ手の5.2 mmブリッジ、キー浮彫0.7 mm、スタッドの各層を確認。部品間10 mm、端10 mmは名目余白です。実プレートの除外領域・brim・支持材・ツールパスは未検証です。</p>
<p class="note"><b>中止条件：</b>孔の閉塞、着座しない、強い力・工具が必要、白化、割れ、保持不足、反り。負のクリアランスは初回に使いません。マグは飲食用ではありません。小部品を乳幼児へ渡さないでください。</p>
""", 2))
    pages.append(page("完成寸法 / 実CADからの正投影", """
<div class="wide"><img src="../media/cad-front.svg"></div>
<div class="grid"><img src="../media/cad-top.svg"><img src="../media/cad-right.svg"></div>
<p>FreeCAD BRepをTechDrawで投影した隠線除去図。外寸には耳と最上部スタッドを含みます。写真の計測値ではなく、この独立設計の寸法です。台座は191.8×127.8、本体厚6.4、露出スタッド込み8.2 mm。</p>
""", 3))
    pages.append(page("開いた下面 / 接続の断面", """
<div class="grid"><img src="../media/brick-top.svg"><img src="../media/brick-bottom.svg"></div>
<div class="grid"><img src="../media/brick-section-y4.svg"><img src="../media/brick-section-y8.svg"></div>
<p>B-2x4のCAD投影・実BRep平面断面。外寸15.8×31.8×9.6、スタッド径4.8、高さ1.8。ピッチ8、中心は4から8刻み。積層は9.6または3.2で、スタッド高を毎段加算しません。</p>
<p>下面は屋根を残した開放空洞、壁・筒・1.2 mmリブ。通常屋根1.6、プレート屋根1.0。標準外壁1.46、入口最小1.26、筒内径3.2 mm。スタッド頭上の名目余裕は薄プレートで0.4 mm。寸法が適正でも摩擦保持を保証しません。</p>
""", 4))
    bom_rows = "".join(f'<tr><td class="code">{r["part"]}</td><td>{data["colors"][r["color"]]["name"]}</td><td>{r["quantity"]}</td><td>{" × ".join(f"{b-a:.1f}" for a,b in zip(*catalog["parts"][r["part"]]["bounds_mm"]))}</td></tr>' for r in data["bom"])
    pages.append(page("部品表 / 完成品だけを数える", f"""
<table><thead><tr><th>型ID（STL名）</th><th>色</th><th>個数</th><th>実外接寸法 mm</th></tr></thead><tbody>{bom_rows}</tbody></table>
<p>合計{count['assembly_instances']}個、{count['assembly_types']}種類。試験片8型・代表部品試験・台座試験はこの表の外です。同じ型のSTLは1ファイルですが、必要数だけ印刷します。STLには単位情報がないためmmで扱います。</p>
<p class="tiny">全slotと全組立候補は data/plate-to-assembly.csv、逆引きは data/print-manifest.json、個体の位置・向きは data/instances.csv。オフライン3Dガイドで同じ対応を操作できます。</p>
""", 5))
    plate_rows = "".join(f'<tr><td class="code">{esc(p["file"].split("/")[-1])}</td><td>{len(p["slots"])}</td><td>{data["colors"][p["color"]]["name"]}</td></tr>' for p in manifest["plates"])
    pages.append(page("3MFの取り出し元 / 両方向で探す", f"""
<table><thead><tr><th>本番ファイル（印刷順の例）</th><th>独立部品数</th><th>色</th></tr></thead><tbody>{plate_rows}</tbody></table>
<p><b>印刷順と組立順は違います。</b> 下記の工程表では、各個体についてslot割当の一例を示します。同じ型・色の別slotも使えます。物理シリアル番号ではありません。</p>
<p>ファイル名 → slot → 型/色 → 全組立候補 → 工程/位置/向き、また個体 → 全ファイル/slotを、index.htmlから双方向にたどれます。すべての候補はCSVへも保存しています。</p>
<p>3MFをスライサーで自動整列・再配置した時は、元のslot位置図と場所が変わります。型・色・数量を照合してください。全8枚の3MF、BOM、組立個体、工程の合計は137個で一致します。</p>
<h3>座標と向き</h3><p>X：椅子から机へ。Y：手前から奥へ。Z：上へ。写真に近い視点は斜め+X/−Y。顔は+Xです。各表の位置は配置範囲の下角、回転はZ軸右手回り。詳細のtranslation_mmは部品ローカル原点の座標です。</p>
<h3>組立・取り外し</h3><p>全工程は上から差し込みます。頭を付ける前に黄色いマグ。大きな面は真上から押し、部品をこじらないこと。背もたれ・首などは頭がない間に作る順序です。完成後は逆順で外し、マグより先に頭を外します。</p>
""", 6))
    assigned = {s["example_instance"]: (p["file"].split("/")[-1], s["slot"])
                for p in manifest["plates"] for s in p["slots"]}
    instance_map = {i["id"]: i for i in data["instances"]}
    for step in data["steps"]:
        rows = []
        for iid in step["instances"]:
            inst = instance_map[iid]
            file, slot = assigned[iid]
            rows.append(f'<tr><td><b>{iid}</b><br>{esc(inst["role"])}</td><td class="code">{inst["part"]}<br>{data["colors"][inst["color"]]["name"]}</td><td>{", ".join(f"{v:.1f}" for v in inst["anchor_mm"])}<br>Z回転 {inst["rotation_deg"]}°</td><td class="code">{file}<br>slot {slot}（割当例）</td></tr>')
        body = f"""
<p class="note"><b>追加 {len(step['instances'])}個 / 上から↓</b>　{esc(step['note'])}</p>
<div class="diagrams">{diagram(data,catalog,step['number'])}{diagram(data,catalog,step['number'],True)}</div>
<table><thead><tr><th>個体ID / 役割</th><th>型 / 色</th><th>下角X,Y,Z mm / 向き</th><th>取り出し元の例</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<p class="tiny">同型・同色はすべて交換可能。全取り出し元と実形状はオフライン3Dガイドで確認できます。図の番号はO-を省略しています。前面図は奥行方向に重なる番号があります。上面図も合わせて確認してください。</p>"""
        pages.append(page(f"工程 {step['number']:02d} / {esc(step['title'])}", body, len(pages) + 1))
    pages.append(page("試作状況・出典・再確認の範囲", """
<h3>実施したデジタル検査</h3><p>検査の具体的な実行結果は validation/ 配下のJSONと統合report.jsonにあります。FCStd再オープン、STEPの全ソリッド対応、メッシュ閉鎖/法線/寸法、全ペアの意図しない干渉、組立時の上方挿入路、支持接続、数量・3MF対応、動画デコード、オフラインブラウザー操作が対象です。</p>
<h3>実施していないこと</h3><p>実スライス、実レイヤー確認、印刷、嵌合、保持力、反り、象足、ブリッジ品質、実機強度、転倒、耐久性。デジタル検査はこれらを保証しません。名目のCAD体積・重心を実際の印刷重量や転倒試験として扱いません。</p>
<p>FreeCAD画面上の色表示は未確認です。offscreen GUI起動が止まったため、完成配置FCStdと別の型ライブラリをheadlessで保存・再読込しています。形状・位置・工程・色名/PartColor属性は照合済みですが、表示は既定の灰色になる場合があります。色確認には3DガイドまたはBlenderを使います。</p>
<h3>基準と独立設計</h3><p>8 mmの寸法体系・制作手順はCopilot Brick Displayの固定コミット0967390547184b342adea0d7e8659dc8ac8f153bと個人用スキルを参考にしています。参照作品には包括ライセンスがないため、そのコード・CAD・画像・フォントはコピーしていません。</p>
<p>ユーザー提供写真は目視の参考としてのみ利用し、元写真・箱・公式ロゴ・印字・個人情報を成果物へ転載していません。見えない背面や内部は独自に設計しています。LEGO、GitHub、Bambu Labの公式製品ではなく、承認・互換性保証はありません。</p>
<h3>公開版とオフライン</h3><p>この作品のソースと生成物は、承認済みのPublicリポジトリ ktanino10/octodesk-brick-kit、対応するGitHub Pages、同リポジトリのReleaseで配布します。元写真・個人情報・ローカル設定は含みません。公開によって包括的な再利用ライセンスが与えられるわけではありません。</p><p>ZIPを展開してindex.htmlを開きます。Three.jsはMITライセンスでローカル同梱。外部CDN・ログイン・ローカルサーバーは不要です。FreeCAD、Blender、ffmpeg、Python/Node等は生成ツールであり、その実行バイナリは同梱していません。</p>
""", len(pages) + 1))
    html_doc = f'<!doctype html><html lang="ja"><meta charset="utf-8"><title>組立説明・図面 R1</title><style>{STYLE}</style><body>{"".join(pages)}</body></html>'
    (docs / "assembly-manual.html").write_text(html_doc, encoding="utf-8")
    notices = """<!doctype html><html lang="ja"><meta charset="utf-8"><title>出典と注意</title><style>body{font:16px/1.8 sans-serif;max-width:900px;margin:40px auto;padding:20px}</style><h1>出典・利用上の注意</h1>
<p>本作品は個人用・非公式の独立設計です。ユーザー提供写真の全体配置と色を目視参考にしましたが、元写真、箱、印字、公式ロゴ、既存の製品用CADは含みません。市販品互換保証、メーカー承認、玩具認証はありません。飲食用・乳幼児用ではありません。</p>
<p>Copilot Brick Displayの固定コミット0967390547184b342adea0d7e8659dc8ac8f153bを機械寸法・制作手順の参考としました。参照リポジトリには包括ライセンスがないため、既存のコード・CAD・画像・フォントは複製していません。写真に写らない構造は独自に設計しています。</p>
<p>配布している第三者ランタイムはThree.js 0.180.0のみ（MIT、<a href="../licenses/THREE-LICENSE.txt">全文</a>）。ビルドツール・アプリのバイナリ・フォントファイルは配布していません。PDFにはブラウザーが生成したシステムフォントの表示用サブセットが含まれる場合があります。</p>
<p>FreeCAD 1.1.3、Blender 5.1.1を独立プロセスで使用。形状・CG・動画・図面・ガイドは新規生成しました。新作のコードやCADに包括的な第三者利用ライセンスを自動設定したものではありません。再利用の条件はリポジトリ所有者へ確認してください。</p>
<p>承認済みの公開先は <a href="https://github.com/ktanino10/octodesk-brick-kit">ktanino10/octodesk-brick-kit</a>、<a href="https://ktanino10.github.io/octodesk-brick-kit/">GitHub Pages</a>、同リポジトリのReleaseです。元写真・参考画像・個人情報・ローカル設定は非公開のままです。完成CGは画素を変更せず、ローカルパスを含む非表示PNGメタデータだけを除去しています。形状・数量・公差はローカルr1から変更していません。</p>
<p>全3MFはNOT_SLICED。対象はP1S / 0.2 mmノズル / PLAですが、実プロファイル・プレート・色別材料条件、実スライス・嵌合・強度・安定性は未評価です。プリンターへの送信・印刷開始は実行していません。</p><p>FreeCADの形状・位置・工程・色属性はheadlessで保存・再読込済みですが、offscreen GUI起動の停止によりネイティブ画面の表示色は未確認です。既存アプリの文書は操作していません。</p><p><a href="../index.html">ガイドに戻る</a></p></html>"""
    (docs / "notices.html").write_text(notices, encoding="utf-8")
    print("JAPANESE_MANUAL_HTML", len(pages), "logical pages")
    from english_docs import build_english
    from build_captions import build_captions
    build_english(data, catalog, manifest, STYLE, diagram)
    build_captions()


if __name__ == "__main__":
    main()

# indoor-geolocator

[English](README.md) · [简体中文](README.zh-CN.md) · [Português](README.pt-BR.md) · [Français](README.fr.md) · [Español](README.es.md) · **日本語** · [Deutsch](README.de.md)

**屋内写真がどこで撮られたか**を突き止めるエージェント用スキルです。ホテルの客室、アパート、レストラン、店舗、駅、博物館、教室、車内などが対象です。施設名、住所、誤差半径つきの座標、そして証拠が実際に裏づける確信度を返します。あわせて、推論の全手順がわかる整理されたケースフォルダーを残します。

AI エージェント向けのオープンソース OSINT 画像ジオロケーションツールです。GeoGuessr のような推論を屋内に適用し、画像の逆検索、OCR、EXIF メタデータ、参照写真との照合で裏づけます。

**プロジェクトページとインタラクティブなデモ：** https://ezharjan.github.io/indoor-geolocator/

写真を添付してスキルを呼び出すだけで、プロンプトは不要です。回答はユーザーの言語で、次の形で返ります（値は例です）。

```
📍 <施設> — <住所、都市、国>
   51.044560, -114.064700 (WGS84) ± 60 m · レベル: site · 確信度: MEDIUM
理由: ... 決定的な証拠 2〜4 点。それぞれの出所と検証方法
照合先: ... 比較した参照写真、一致した特徴、検証した対抗候補
最有力の手がかり（未検証）: ... より細かい候補、その座標（最も可能性の高い一点）、それを確定させる検証
代替候補: ... 次点、その確率、両者を分ける検証
未検証・限界: ... 確認できなかったことと、その理由
ケースフォルダー: .../photo-geolocation（REPORT.md に推論の全経過があります）
```

## 何をするか

このスキルは、正確さを最優先する厳格なワークフローと、コマンドラインのツールボックス（`scripts/igl.py`、Python 3.9+、Pillow）をモデルに与えます。観察はすべて一つの台帳に記録され、順位と確信度は主張されるのではなく、その台帳から計算されます。

屋内写真の場所を誤る原因は数種類に限られ、ワークフローはそれらを軸に組み立てられています。よく似た部屋をその場所と取り違える、最初のもっともらしい候補に固執する、機械の出力（カーペットを読んだ OCR、検索エンジンのラベル、実行されなかった検索）を事実として読む、持ち運べる物を建物の特徴として読む、ブランドを特定の店舗と取り違える、そして精度をでっち上げる、の六つです。

1. **取り込み。** 写真をバイト単位でそのまま複製します。EXIF、GPS、XMP、IPTC、ICC、埋め込みサムネイル（切り抜きや編集が判明します）、ファイル名のパターン、AI マーカー、C2PA コンテンツクレデンシャルを読み、UTC オフセットをタイムゾーンに対応づけます。ツールボックスが到達できるオンラインサービスを 5 秒で確認します。
2. **まず仮説。** ツールの出力を見る前に、順位をつけた仮説を 2〜4 個記録します（アンカリング対策）。
3. **写真全体を読む。**
   - 精度重視でフィルターした OCR（模様を文字として報告しません）、QR コードとバーコードの内容解釈（EMV 決済コード、スイスの QR 請求書、SEPA、UPI、Wi-Fi、vCard、GS1 プレフィックス）、テキスト解析（市まで絞れる電話番号、ドメイン、価格、郵便番号、単位、税に関する語）。
   - 約 200 項目の手がかりカタログ。エージェントが重なり合うタイルで読みます。対象は、識別の決め手（名称、一点物のアート、窓外の眺め）、固定された規格（コンセント、スイッチ、配管、安全標識）、地域への言及（地元の名所の絵、地図、リーフレット）です。
4. **候補を見つける。**
   - **画像の逆検索**を Yandex、TinEye、Baidu でヘッドレス実行し、Google Lens と Bing はブラウザーツール経由で使います。ヒットはすべて写真と比較され、**COPY**（同一の写真：出所）、**SAME SCENE** / **PARTIAL**（構造が一致）、**unconfirmed** のいずれかに分類されます。
   - **テキストによる画像検索**（`refs`）：一つの施設、またはある地域内の同種の施設すべてについて画像を検索します。画像は写真と比較され、**似ている順**に表示されるので（DINOv2）、キャプションに何も書かれていなくても正しい施設が浮かび上がります。あるテストでは、米国の一つの州のホテルバーを探す一般的な検索 2 回で、別々のバーの画像 100 枚の中から実際のバーが 1 位になりました。
   - 名称、電話番号、URL、Wi-Fi 名はエージェント自身のウェブ検索で調べます。固定規格は 250 の国・地域にわたってオフラインで絞り込みます。同種の施設は OpenStreetMap と Wikidata からすべて列挙します。掲載サイトとソーシャルメディアも使います（場所に限定）。
5. **検証：手がかりと回答を分ける関門。** まず反証テストを書きます。候補自身の写真を対象の写真の横に並べ、具体的な固定の特徴を数えます（窓、天井、造り付けの設備、眺め、その施設のために作られたアート。家具が示すのは内装デザインだけです）。最も近い対抗候補にも同じ比較を行います。対抗候補も「一致」するなら、その特徴は共通のデザインです。一致はグループの地域に対して記録され、個々の施設は手がかりのままです。
6. **整合性。** タイムゾーン、太陽、天候、季節、規格を候補と突き合わせ、次点の側に立って論じ、決め手となった手順を別の方法でやり直します。
7. **判断。** 回答は、証拠が検証できる最も細かいレベルにとどめます。検証済みの地域の下にある未検証の施設は、最有力の手がかりとしてその座標（最も可能性の高い一点）とともに報告し、決して回答にはしません。ケースフォルダーを確定し、不要なものを取り除きます。

### コードに組み込まれた正確さのルール

- **ステータス別の上限。** 手がかりの重みは、その得られ方によって上限が決まります。推論は ≤3、観察は ≤6、第三者の報告は ≤10、ファイルのメタデータや写真の追跡済みコピーは ≤20、拡大した切り抜きで読んだ文字や計算結果は ≤50、独立した参照画像との一致は ≤100 です。検索エンジンのラベルは、何と言っていようと手がかり（≤3）です。
- **特定する手がかりと分類の手がかり。** 決定的な手がかり（写真の中で読んだ名称、デコードしたコード、GPS、追跡済みコピー、一致した参照）は一つの場所を特定し、すべての代替候補をまとめた全体と比べて重みづけされます。LR 50 は、対抗候補をいくつ挙げていても約 50 対 1 を意味します。分類の手がかり（コンセントの型、言語、様式）は代替候補の一つ一つと競うので、いくつか揃って初めて国が決まります。
- **監査できる一致。** `matched` の手がかりは、具体的な固定の特徴を 3 つ以上挙げ、比較ファイルを引用しなければなりません。写真のコピーは一致として認められません。それは出所であり、掲載ページとともに `traced` として記録されます。
- **対抗候補による対照。** 参照との一致が HIGH に達するのは、対抗する施設が同じ比較を受けた場合か、第二の決定的な系統（写真の中で読んだ名称、GPS、追跡済みコピー）が同じ施設を指す場合だけです。
- **施設には決定的な手がかりが必要。** 類似、検索エンジンのラベル、キャプションは、いくつ揃っても施設を LOW にとどめます。その組み合わせこそ、そっくりな別の場所が生み出すものだからです。
- **独立した系統。** 一致が数えられるのは、独立した情報源（image, text, metadata, web, engine, map, reference, geometry）の間だけです。内装の手がかり 5 つは一つの系統です。
- **開かれた、整合するボード。** 挙げられていない代替候補はどのレベルでも取り分を保ち、都市がその国より確かになることはなく、国に対する矛盾はその国のホテルの HIGH も阻みます。
- **正直な失敗。** ブロックされた検索や開始されなかった検索は、そのとおりに報告され、「結果なし」とは報告されません。未確認の画像を「別物」と呼ぶことはありません。
- **網羅の関門。** 13 の中核メソッドがそれぞれ results、no_results、not_applicable のいずれかで終わるまで `check` は通りません。`check` は、参照との比較や対抗候補のない施設、同じく一致してしまった対抗候補、実行されなかった逆検索も指摘します。

## インストール

### ひとことでインストール

Claude Code や、シェルコマンドを実行できるエージェントなら、**「https://github.com/Ezharjan/indoor-geolocator から indoor-geolocator スキルをインストールして」**と伝えるだけです。この節の残りはエージェント向けに書かれています。

**AI エージェント向けの手順。** ユーザーのためにこのスキルをインストールするには、次を実行します。

```bash
curl -L -o indoor-geolocator.zip https://github.com/Ezharjan/indoor-geolocator/releases/latest/download/indoor-geolocator.zip
mkdir -p ~/.claude/skills && unzip -o indoor-geolocator.zip -d ~/.claude/skills    # ~/.claude/skills/indoor-geolocator/ が作られます
python3 -m pip install -r ~/.claude/skills/indoor-geolocator/requirements.txt
python3 ~/.claude/skills/indoor-geolocator/scripts/igl.py doctor                   # 使えるものと足りないものを報告
```

- Windows では、スキルのフォルダーは `%USERPROFILE%\.claude\skills\` です。`Expand-Archive` で展開し、`python3` の代わりに `python` を使います。
- 任意の追加パッケージを黙ってインストールしないでください。`doctor` が不足と報告したものをユーザーに示し、`requirements-optional.txt` を提案します。これらのパッケージは大きいためです。
- `~/.claude/skills/indoor-geolocator/SKILL.md` があることを確認し、新しいセッションで `/indoor-geolocator` として使えることをユーザーに伝えます。

**プラグインとして。** スキルのフォルダーは Claude プラグインでもあります。Claude Code で `claude plugin marketplace add Ezharjan/indoor-geolocator` を実行し、続けて `claude plugin install indoor-geolocator@ezharjan-plugins` を実行します。スキルが接続しうるすべてのサービスを列挙したプライバシー通知は https://ezharjan.github.io/indoor-geolocator/privacy.html にあります。プラグインもスキルと同じく Pillow が必要です：`pip install pillow`（Windows では `tzdata` も）。スキルとプラグインはどちらか一方だけをインストールしてください。プラグインとして入れた場合の呼び出し名は `/indoor-geolocator` ではなく `/indoor-geolocator:indoor-geolocator` です。
- claude.ai や Claude Desktop のチャットでは、エージェントが自分でスキルを追加することはできません。上の zip のリンクと下の 3 つのアップロード手順をユーザーに渡してください。

**claude.ai、Claude Desktop、Cowork。**
1. コード実行が有効になっていることを確認します（*Settings → Capabilities*）。コード実行にネットワークアクセスがあると役立ちます（ツールボックスが地図サービスと逆検索サービスに自分で到達できます）。ない場合は、エージェントが自身のウェブ検索、フェッチ、ブラウザーの各ツールでその手順を行います。
2. *Customize → Skills* を開き、**+** をクリックし、**+ Create skill → Upload a skill** を選んで `indoor-geolocator.zip` を指定します。
3. 写真を添付してスキルを呼び出すか、単に「これはどこで撮られましたか？」と尋ねます。

zip は、アップロードの要件どおり、最上位に `indoor-geolocator/` フォルダーを持ちます。

**Claude Code。** `indoor-geolocator/` フォルダーを `~/.claude/skills/`（全プロジェクト）または `<project>/.claude/skills/`（一つのプロジェクト）にコピーします。`/indoor-geolocator` で呼び出すか、屋内写真を共有したときに Claude が自動で使うのに任せます。

**その他のエージェント**（Codex、Gemini CLI、Cursor など）：エージェントに `indoor-geolocator/SKILL.md` を参照させます。ツールボックスは素の Python CLI です。

**依存関係。** Pillow が必須で、Windows では `tzdata` も必須です。それ以外はすべて任意で、対応するメソッドを有効にするだけです。

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow（+ tzdata、Windows で必要）
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV + numpy、Playwright、onnxruntime、phonenumbers、HEIC、RapidOCR
playwright install chromium                                   # ヘッドレスの逆検索、画像検索、ページのスナップショット
# OCR エンジン（推奨）：言語パックつきの tesseract
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # この環境で使えるものと足りないもの
```

正確さに最も効く追加要素は三つです。OpenCV（COPY / SAME SCENE の判定）、Chromium つきの Playwright（画像の逆検索と画像検索）、onnxruntime（写真との類似順に画像を並べる）です。類似度モデル（DINOv2 ViT-S/14、24 MB、Apache-2.0）はスキルに含まれません。初回使用時に huggingface.co から一度だけダウンロードされ、SHA-256 で照合されます。`IGL_NO_EMBED=1` で無効にできます。

## ツールボックスを直接使う

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # ケースフォルダー + メタデータ + グリッド表示 + ネットワーク確認
$IGL note CASE "Hypotheses: 1) ... 2) ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR、QR/バーコード、テキストのシグナル、走査用タイル
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL revsearch CASE --cell B2:C3 --flip                # Yandex、TinEye、Baidu。ヒットはすべて写真と照らして分類
$IGL share CASE --cell B2:C3                           # Google Lens と Bing 用のリンク（一時コピー）
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL refs CASE "hotel lounge sea view Poole"           # 地域全体の画像を、似ている順に
$IGL geo poi --tag tourism=hotel --area "Poole" --case CASE --add site --parent C3
$IGL refs CASE "Hotel Name Poole lounge" --for C12     # 一つの候補の写真を自分の写真の横に
$IGL compare CASE --refs E14 --pick 3,7 --for C12      # 大きな左右比較 + 一致判定
$IGL note CASE "Matches a traveller photo (2023)" --kind match --status matched --source reference --file E16 \
     --features "arched window pair; coffered ceiling 3x4; green marble fireplace" --for C12:60 --why "..."
$IGL refs CASE "Rival Hotel Poole lounge" --for C13    # 対抗候補による対照
$IGL rank CASE
$IGL answer CASE C12 --summary "..."
$IGL check CASE
$IGL finalize CASE
```

`$IGL <command> -h` ですべてのオプションを確認できます。Windows では `python3` の代わりに `python` を使います。南緯と西経の座標は入力したとおりに使えます（`--at -33.86,151.21`）。

## 得られるもの

```
photo-geolocation/
├── REPORT.md       回答、最有力の手がかり、レベル別の確信度、証拠、候補、時系列、メソッド、データの扱い
├── result.json     同じ内容の機械可読 JSON（スキーマ igl.result/1）
├── case.json       完全な台帳：手がかり、候補、リンク、除外、試行、タイムスタンプ
├── input/          写真（バイト単位で同一）と metadata.json
└── evidence/       台帳が引用する切り抜き、シート、比較ビュー、スナップショットのみ
```

作業用のファイル（タイル、キャッシュ、ダウンロード）は `.work/` に置かれ、`finalize` が削除します。`finalize` は、どこからも引用されていない証拠ファイルもすべて取り除きます。既存のケースフォルダーが上書きされることはありません。

## プライバシーと責任ある利用

- **人は対象にしません。** 顔認識も個人の特定も行いません。
  - 衣服、制服、名札、所持品は、場所について何を示すかという点でのみ使います。
  - 見た目の民族性は、弱く偏りやすい文脈として扱い、除外の根拠にはしません。
  - ソーシャルメディアで検索するのは場所、テキスト、タグ、写真そのものであり、人物や投稿者は検索しません。
- **個人の住宅。** 特定できる個人の住居で目的が示されていない場合、スキルは結果の用途を一度だけ尋ねます。正当な目的がなければ、市または近隣のレベルで止めます。
- **伏せ字。** 個人の氏名と自宅住所はレポートに載せません。Wi-Fi のパスワード、IBAN、連絡先カードの氏名は、デコードされた箇所でも、検索エンジンやページが返してきた箇所でも伏せます。
- **アップロード。** 画像の逆検索は、写真（メタデータを除去したもの）を検索エンジンにアップロードします。`share` は、メタデータのないコピーを一時ホスト（1〜3 時間後に削除）に置いて Lens と Bing に渡し、`revsearch` も、検索エンジンのアップロードフォームが失敗したときは自動で同じことを行います（`--no-share` で防げます）。レポートには、すべての検索エンジンと一時コピーが列挙されます。`refs` が送るのは検索テキストだけで、類似度モデルはローカルで動きます。人が写っていない切り抜きを優先してください。ユーザーが写真を非公開と示した場合は、確認なしに何もアップロードしません。
- **サービス。** スキルは各サービスのポリシーを守ります（Nominatim は毎秒 1 リクエスト以下、範囲を限定した Overpass クエリ、識別可能な User-Agent）。誰かに代わってログインすることも、CAPTCHA を解くことも、大量収集を行うこともありません。任意のユーザーキー：`revsearch` 内の Google Lens 用の `SERPAPI_KEY`、Wi-Fi SSID 検索用の `WIGLE_API_NAME` / `WIGLE_API_TOKEN`。`IGL_USER_AGENT` で独自の User-Agent を設定できます。

位置特定の結果は、証拠に基づいて重みづけした推定であり、確実なものではありません。回答に基づいて行動する前に、確信度、最有力の手がかり、「未検証」の行を読んでください。

## リポジトリの構成

```
.
├── indoor-geolocator/          スキル本体（インストールされるのはこのフォルダー）
│   ├── SKILL.md                ワークフロー、証拠のルール、行動規範、回答の形式
│   ├── LICENSE.txt             LICENSE のコピー（zip にはリポジトリのルートが含まれないため）
│   ├── requirements*.txt
│   ├── references/             手がかりカタログ、場面別と検索の手引き、窓と光、検証、
│   │                           証拠と確信度、情報源とツール
│   ├── scripts/igl.py          CLI。モジュールは scripts/iglib/ にあります
│   └── data/                   countries.json、gs1_prefixes.json（+ 出典とライセンスを記した README）
├── indoor-geolocator.zip       同じスキルをアップロード用にまとめたもの
├── build_skill_zip.py          zip を再構築して検証します（スキルを変更するたびに実行）
├── tools/build_data.py         保守用ツール：Unicode CLDR と Wikipedia から data/ を再構築
├── tools/make_demo.py          保守用ツール：現在のバージョンで docs/demo/ を再構築
├── tests/                      オフラインのテストスイート（pytest。`pytest.ini` が指定）
├── docs/                       プロジェクトページ（GitHub Pages）と公開中のデモケース
├── LICENSE
├── README.md                   この README の英語版
└── README.*.md                 翻訳（zh-CN、pt-BR、fr、es、ja、de）
```

## 開発

```bash
python -m pytest                   # オフラインテスト：台帳のルール、上限、照合、順位づけ、パーサー、幾何計算。
                                   # さらに、ドキュメントと CLI、zip とスキルフォルダー、プロジェクトページとデモケースの一致
python tools/build_data.py         # data/ を更新（出典を .data-src/ にキャッシュ。--offline はキャッシュから再構築）
python tools/make_demo.py          # docs/demo/ のデモケースを現在のバージョンで再構築
python build_skill_zip.py          # フォルダーに変更があれば indoor-geolocator.zip を再構築。--check は検証のみ
```

## 変更履歴

### 2.0.1

パッケージングのみの変更です。スキルの動作は 2.0.0 と同じです。

- **プラグイン。** スキルのフォルダーが Claude プラグインにもなりました（`.claude-plugin/plugin.json`、アイコン、スキルが実行・送信・取得するものをすべて列挙した README）。リポジトリはプラグインのマーケットプレイスでもあります。
- **データ。** `countries.json` を 1 か国 1 行で書き出すようにしました。データは同じで、ファイルが小さくなります。
- **プライバシー通知。** スキルが接続しうるすべてのサービスと、そこに送られる内容を列挙したページを追加しました。

### 2.0.0

正確さのためのリリースです。最もよくある誤答、つまりそっくりな別の施設を自信をもって名指しすることへの対策として作られました。

- **探す。** 新しい `refs` コマンド：テキストによる画像検索（Brave、Startpage）とギャラリーページ。画像はすべて写真と比較されます。画像と逆検索のヒットは視覚的な類似度（DINOv2、任意）で並べ替えられるので、最も有力な参照が、エージェントが最初に目にするタイルになります。
- **逆検索。** ヒットはすべて写真と照らして COPY / SAME SCENE / PARTIAL / unconfirmed に分類されます。開始されなかった検索は `no_results` ではなく `unavailable` です。アップロードフォームが失敗したときは URL による代替手段を使います。ユーザーの SerpApi キーによる Google Lens も任意で使えます。
- **検証。** `matched` の手がかりは特徴を 3 つ挙げ、比較を引用しなければなりません。コピーは一致として認められず、出所 `traced` として記録されます。`compare --refs E## --pick` を追加しました。HIGH には対抗候補による対照が必須です。デザインの一致は地域に対して記録され、施設は手がかりとして扱われます。
- **確信度。** 決定的な手がかりは候補全体と比べて重みづけされます（検証済みの施設が、挙げられていない国や、エージェントが列挙した対抗候補によって薄められることはなくなりました）。施設が MEDIUM になるには決定的な手がかりが必要です。検索エンジンのラベルの上限は 3 です。矛盾は連鎖の下位まで HIGH を阻みます。ある場所の確かさは、その中にある検証済みの場所を下回りません。
- **読み取り。** OCR の出力は精度重視でフィルターされます（カーペットや天井から「文字」や珍しい文字体系を読み取ることはなくなりました）。`scan` はテキストの切り抜きをまとめたシートを書き出します。`crop --of` はどの証拠画像も拡大できます。
- **堅牢性。** Overpass に到達できないときの Photon への切り替え、ダウンロードの再試行、実行ごとのレート制限の報告、記録済みの手がかりから導かれるメソッド、カンマ区切りのリストを受け付ける `log`。
- **出力。** 最良推定のピン（回答のほうが粗い場合は手がかりの座標）、対抗候補による対照を載せたレポートの検証セクション、各行が何であるか（回答、回答を含む場所、未検証の手がかり、ボードにない代替候補）を示す候補表、デモケースを再構築する `tools/make_demo.py`、そしてプロジェクトページをそのケースに、zip をスキルフォルダーに一致させ続けるテスト。

### 1.1.0

単独ではタグづけもリリースもされていません。これらの変更は 2.0.0 で初めて公開されます。

- 完全一致の経路と検証の関門を軸にワークフローを再構成。ツールの出力より先に仮説を記録。ツールボックスと、エージェント自身のウェブ検索、フェッチ、ブラウザーの各ツールとの役割分担を明確化。
- スコアリング：どのレベルでも開かれたボード、連鎖に沿って整合する取り分、分類の手がかりを上位レベルに波及させない、最有力の手がかりを別に示す回答の関門、レポート前のチェック。
- 逆検索：Baidu を追加、類似画像のコンタクトシート、URL で Lens と Bing に渡す `share`。
- `compare`：ほぼ重複、同一写真、SIFT/RANSAC による幾何の各判定。左右反転した部屋にも対応。
- `init` のネットワーク確認、`geo ... --print-url`、一度の呼び出しで行える `note --for/--against`、C2PA リーダー。

### 1.0.0

最初の公開リリース。

## ライセンス

コードとドキュメントは [MIT License](LICENSE) のもとで公開されています。`indoor-geolocator/data/` のデータファイルは、それぞれの出典のライセンスに従います。
- Unicode CLDR 由来の項目：[Unicode License v3](https://www.unicode.org/license.txt)。
- Wikipedia 由来の項目（プラグの型、電源、通行区分、緊急通報番号、GS1 プレフィックス）：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)、© Wikipedia の執筆者。

詳細は [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md) にあります。

設計上の着想は、オープンソースのプロジェクト geo-sleuth、Geo-Guesser、Searching-skill から取り入れました。コードで強制するルール、尤度比による候補ボード、系統で格付けする証拠、メソッド網羅の関門、DINOv2 の類似順による「まず機械が並べる」、SIFT/RANSAC による検証です。類似度モデルは DINOv2（Meta AI、Apache-2.0）で、`Xenova/dinov2-small` として公開されている ONNX エクスポートを使います。実行時にダウンロードされ、ここでは再配布していません。

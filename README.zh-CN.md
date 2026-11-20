# indoor-geolocator

[English](README.md) · **简体中文** · [Português](README.pt-BR.md) · [Français](README.fr.md) · [Español](README.es.md) · [日本語](README.ja.md) · [Deutsch](README.de.md)

一个智能体技能（Agent Skill），根据**一张室内照片判断拍摄地点**：酒店客房、公寓、餐厅、商店、车站、博物馆、教室、车内等。它给出场所名称、街道地址、带误差半径的坐标，以及证据真正支持的置信度；同时留下一个整洁的案例文件夹，记录推理的每一步。

**项目主页与交互式演示：** https://ezharjan.github.io/indoor-geolocator/

附上照片并调用技能即可，无需任何提示词。回答使用用户的语言，格式如下（数值仅为示意）：

```
📍 <场所> — <街道地址，城市，国家>
   51.044560, -114.064700 (WGS84) ± 60 m · 层级：场所 · 置信度：中（MEDIUM）
依据：2–4 条决定性证据，各自注明来源与核实方式
核验对照：对比过的参考照片、吻合的特征、检验过的对照候选
最佳线索（未核实）：更精细的候选、其坐标（最可能的单点）及可证实它的检验
备选：次优候选、其概率，以及区分二者的检验方法
未核实 / 局限：未能核实的内容及原因
案例文件夹：…/photo-geolocation（REPORT.md 含完整推理记录）
```

## 功能概览

技能为模型提供一套以准确性为先的严格工作流程和一个命令行工具箱（`scripts/igl.py`，需 Python 3.9+ 与 Pillow）。所有观察都记入同一份台账，排名与置信度由台账计算得出，而不是凭空断言。

室内照片定位出错，原因不外乎几种，工作流程正是围绕它们设计的：把相似的房间当成了那个地方；抓住第一个说得通的候选不放；把机器输出（地毯上“读”出的文字、引擎给的标签、根本没跑起来的搜索）当成事实；把可携带的物品当成建筑本身；把品牌当成具体门店；凭空编造精度。

1. **接收**：逐字节复制照片；读取 EXIF、GPS、XMP、IPTC、ICC、内嵌缩略图（可发现裁剪或编辑痕迹）、文件名模式、AI 标记与 C2PA 内容凭证，并把 UTC 偏移映射到时区。同时用 5 秒检查工具箱能连通哪些在线服务。
2. **先立假设**：在查看任何工具输出之前，先记下 2–4 个按可能性排序的假设（锚定防御）。
3. **通读整张照片**：
   - 经过精度过滤的 OCR（不再把纹理报成文字）；二维码与条形码解析（EMV 支付码、瑞士 QR 账单、SEPA、UPI、Wi-Fi、vCard、GS1 前缀）；文本挖掘（电话号码到城市、域名、价格、邮编、单位、税务用语）。
   - 约 200 条线索目录，由智能体在重叠切片上逐一查看：身份载体（名称、独有的艺术品、窗外景观）、固定标准（插座、开关、给排水、安全标识）和本地参照物（画着当地地标的画、地图、宣传页）。
4. **寻找候选**：
   - **以图搜图**：无头方式同时使用 Yandex、TinEye 与百度，Google Lens 与 Bing 通过浏览器工具完成。每条结果都与照片比对并归类：**COPY**（同一张照片，属于出处）、**SAME SCENE** / **PARTIAL**（结构吻合）或 **unconfirmed**（未确认）。
   - **按文字搜图**（`refs`）：搜索某个场所的图片，或某一地区所有同类场所的图片；每张图片都与照片比对，并按**相似度从高到低**排列（DINOv2），即使没有任何文字描述过，正确的场所也会浮到最前面。实测中，仅用两条泛泛的“某州酒店酒吧”搜索，真正的那间酒吧就排在 100 张不同酒吧图片的第一位。
   - 名称、电话、网址与 Wi-Fi 名称交给智能体自身的网页搜索；固定标准在 250 个国家和地区的离线数据表上取交集；从 OpenStreetMap 与 Wikidata 枚举该地所有同类场所；房源、点评与社交媒体（只针对地点）。
5. **核验：线索与答案之间的关卡**：先写下证伪检验；把候选场所自己的照片与本照片并排，清点具体的固定特征（窗、天花、固定装修、窗外景观、为该场所定制的艺术品；家具只能证明设计风格）。最接近的对照候选要走同样的比对。如果对照候选也“吻合”，那些特征就是共用的设计：匹配记在该集团所在的区域上，各场所仍只是线索。
6. **一致性检查**：用时区、太阳、天气、季节和各类标准检验候选；为次优候选做最有力的辩护；把决定性的一步换一种方式重做。
7. **结论**：答案定在证据能核实的最精细层级。已核实区域之下尚未核实的场所，只作为“最佳线索”连同其坐标（最可能的单点）单独报告，绝不当作答案。最后整理并精简案例文件夹。

### 写进代码的准确性规则

- **状态上限**：线索权重受其获取方式限制：推断 ≤3，直接观察 ≤6，第三方说法 ≤10，文件元数据或照片的可追溯副本 ≤20，放大核对过的文字或计算结果 ≤50，与独立参考影像的匹配 ≤100。引擎给出的标签无论怎么说都只是线索（≤3）。
- **识别性线索与类别线索**：决定性线索（照片中读到的名称、解码结果、GPS、可追溯副本、参考影像匹配）指向唯一的地点，与所有备选作为一个整体来权衡：LR 50 就是约 50:1，不论榜上列了多少对手。类别线索（插座类型、语言、风格）要与每个备选逐一竞争，所以要好几条合起来才能确定一个国家。
- **可审计的匹配**：`matched` 线索必须写明至少三个具体的固定特征，并引用比对文件。照片自身的副本不能算匹配：它是出处，应连同所在网页记为 `traced`。
- **对照候选检验**：参考影像匹配只有在某个对照场所也走过同样的比对之后，或另有一条决定性证据链（照片中读到的名称、GPS、可追溯副本）指向同一场所时，才能达到 HIGH。
- **场所需要决定性线索**：相似、引擎标签和图片说明，无论有多少条彼此一致，场所都只能是 LOW：这恰恰是“撞脸”场所会产生的组合。
- **独立证据链**：只有相互独立的来源（图像、文字、元数据、网页、引擎、地图、参考影像、几何）之间的一致才算数。五条装饰线索只算一条链。
- **开放且前后一致的候选榜**：每一层级的未列出备选都保留份额；城市的确定程度不会高于其所在国家；针对国家的矛盾同样会阻止其中的酒店达到 HIGH。
- **如实报告失败**：被拦截或根本没启动的搜索会如实报告，绝不写成“无结果”；未确认的图片绝不说成“不是同一处”。
- **覆盖关卡**：13 项核心方法都必须以 results、no_results 或 not_applicable 结束，`check` 才会通过；`check` 还会提示：场所答案缺少参考比对或对照候选、对照候选同样吻合、以图搜图从未真正运行等情况。

## 安装

**claude.ai、Claude 桌面版与 Cowork**
1. 确认已开启代码执行（*Settings → Capabilities*）。为代码执行开放网络访问会更好（工具箱可自行访问地图与以图搜图服务）；若未开放，智能体会改用自身的网页搜索、网页抓取和浏览器工具完成这些步骤。
2. 打开 *Customize → Skills*，点击 **+**，选择 **+ Create skill → Upload a skill**，然后选择 `indoor-geolocator.zip`。
3. 附上照片并调用技能，或直接问“这是在哪里拍的？”。

压缩包顶层就是 `indoor-geolocator/` 文件夹，符合上传要求。

**Claude Code**：把 `indoor-geolocator/` 文件夹复制到 `~/.claude/skills/`（所有项目）或 `<project>/.claude/skills/`（单个项目）。用 `/indoor-geolocator` 调用，或在分享室内照片时由 Claude 自动启用。

**其他智能体**（Codex、Gemini CLI、Cursor 等）：让智能体读取 `indoor-geolocator/SKILL.md` 即可。工具箱是普通的 Python 命令行程序。

**依赖**：必需 Pillow，Windows 上还需要 `tzdata`。其余依赖均为可选，只决定对应方法能否启用。

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow（Windows 另需 tzdata）
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV + numpy、Playwright、onnxruntime、phonenumbers、HEIC、RapidOCR
playwright install chromium                                   # 无头以图搜图、按文字搜图与网页快照
# OCR 引擎（推荐）：tesseract 及语言包
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # 检查本机可用与缺失的组件
```

对准确性影响最大的三项可选依赖：OpenCV（COPY / SAME SCENE 检验）、Playwright 与 Chromium（以图搜图和按文字搜图）、onnxruntime（按与照片的相似度排列图片）。相似度模型（DINOv2 ViT-S/14，24 MB，Apache-2.0）不随技能分发：首次使用时从 huggingface.co 下载一次，并用 SHA-256 校验。设置 `IGL_NO_EMBED=1` 可关闭。

## 直接使用工具箱

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # 新建案例文件夹 + 元数据 + 网格视图 + 网络检查
$IGL note CASE "Hypotheses: 1) ... 2) ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR、二维码/条形码、文本信号、排查切片
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL revsearch CASE --cell B2:C3 --flip                # Yandex、TinEye、百度；每条结果都与照片比对归类
$IGL share CASE --cell B2:C3                           # 生成 Google Lens 与 Bing 检索链接（临时副本）
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL refs CASE "hotel lounge sea view Poole"           # 整个地区的同类图片，按相似度排列
$IGL geo poi --tag tourism=hotel --area "Poole" --case CASE --add site --parent C3
$IGL refs CASE "Hotel Name Poole lounge" --for C12     # 把某个候选的照片与本照片并排
$IGL compare CASE --refs E14 --pick 3,7 --for C12      # 大幅并排对照图 + 匹配检验
$IGL note CASE "Matches a traveller photo (2023)" --kind match --status matched --source reference --file E16 \
     --features "arched window pair; coffered ceiling 3x4; green marble fireplace" --for C12:60 --why "..."
$IGL refs CASE "Rival Hotel Poole lounge" --for C13    # 对照候选检验
$IGL rank CASE
$IGL answer CASE C12 --summary "..."
$IGL check CASE
$IGL finalize CASE
```

`$IGL <command> -h` 可查看全部选项。Windows 上请用 `python` 代替 `python3`。南纬、西经坐标可直接输入（`--at -33.86,151.21`）。

## 输出内容

```
photo-geolocation/
├── REPORT.md       答案、最佳线索、各层级置信度、证据、候选、时间线、方法、数据处理说明
├── result.json     同上内容的机器可读 JSON（schema igl.result/1）
├── case.json       完整台账：线索、候选、关联、排除、尝试记录、时间戳
├── input/          照片（逐字节原样）与 metadata.json
└── evidence/       仅保留台账引用的裁剪图、对照图、匹配连线图与网页快照
```

临时文件（切片、缓存、下载）存放在 `.work/`，由 `finalize` 删除；未被引用的证据文件也会一并清除。已有的案例文件夹永远不会被覆盖。

## 隐私与负责任使用

- **不以人为目标**：不做人脸识别，不识别任何个人。
  - 服装、制服、胸牌与个人物品只用于推断地点。
  - 表观族裔只作为易带偏见的弱背景信息，绝不用作排除依据。
  - 社交媒体只搜索地点、文字、标签与照片本身，从不搜索人物或发帖者。
- **私人住宅**：如可识别为私人住宅且未说明用途，技能会询问一次用途；若无正当用途，只给到城市或街区层级。
- **脱敏**：报告不包含私人姓名与住宅地址；Wi-Fi 密码、IBAN 与名片中的姓名，无论是解码得到的，还是引擎或网页回显的，都会被隐去。
- **上传**：以图搜图会把照片（已去除元数据）上传给各引擎；`share` 会把去除元数据的副本放到临时图床（1–3 小时后删除），供 Lens 与 Bing 使用；当某个引擎的上传表单失败时，`revsearch` 也会自行这样做（`--no-share` 可禁止）。报告会列出每个接收照片的引擎和每份临时副本。`refs` 只发送搜索文字，相似度模型在本机运行。优先使用不含人物的裁剪图；用户标明照片私密时，未经同意不会上传。
- **服务规范**：遵守各服务的使用政策（Nominatim 每秒不超过 1 次请求、限定范围的 Overpass 查询、可识别的 User-Agent）。从不代任何人登录，不破解验证码，不批量抓取。可选用户密钥：`SERPAPI_KEY` 用于在 `revsearch` 中调用 Google Lens，`WIGLE_API_NAME` / `WIGLE_API_TOKEN` 用于 Wi-Fi SSID 查询；`IGL_USER_AGENT` 可设置自定义 User-Agent。

地理定位结果是基于证据权衡的估计，而非确定结论。据此行动前，请先查看置信度、最佳线索与“未核实”说明。

## 仓库结构

```
.
├── indoor-geolocator/          技能本体（安装的就是这个文件夹）
│   ├── SKILL.md                工作流程、证据规则、行为准则、回答格式
│   ├── LICENSE.txt             LICENSE 的副本（压缩包不含仓库根目录）
│   ├── requirements*.txt
│   ├── references/             线索目录、场景与检索手册、窗外与光线、核验、证据与置信度、来源与工具
│   ├── scripts/igl.py          命令行工具；模块位于 scripts/iglib/
│   └── data/                   countries.json、gs1_prefixes.json（含来源与许可证说明）
├── indoor-geolocator.zip       同一技能的上传用压缩包
├── build_skill_zip.py          重建并校验压缩包（每次修改技能后运行）
├── tools/build_data.py         维护工具：从 Unicode CLDR 与维基百科重建 data/
├── tools/make_demo.py          维护工具：用当前版本重建 docs/demo/
├── tests/                      离线测试（pytest；由 pytest.ini 指定）
├── docs/                       项目主页（GitHub Pages）及公开的演示案例
├── LICENSE
├── README.md                   英文版说明
└── README.*.md                 其他语言版本（zh-CN、pt-BR、fr、es、ja、de）
```

## 开发

```bash
python -m pytest                   # 离线测试：台账规则、置信度上限、图像匹配与排序、解析器、几何计算；
                                   # 以及文档与命令行、压缩包与技能文件夹、项目主页与演示案例的一致性
python tools/build_data.py         # 更新 data/（源数据缓存在 .data-src/；--offline 仅用缓存重建）
python tools/make_demo.py          # 用当前版本重建 docs/demo/ 中的演示案例
python build_skill_zip.py          # 技能文件夹有变动时重建压缩包；--check 只做校验
```

## 更新日志

### 2.0.0

准确性版本：针对最常见的错误答案——把“撞脸”的场所言之凿凿地报出来。

- **寻找**：新增 `refs` 命令：按文字搜图（Brave、Startpage）并抓取图库页面，每张图片都与照片比对。图片与以图搜图结果按视觉相似度排序（DINOv2，可选），最可能的参考图排在智能体最先看到的位置。
- **以图搜图**：每条结果都与照片比对，归为 COPY / SAME SCENE / PARTIAL / unconfirmed。没有启动的搜索记为 `unavailable`，而不是 `no_results`；上传表单失败时自动改用按网址检索；可选通过用户自己的 SerpApi 密钥使用 Google Lens。
- **核验**：`matched` 线索必须写明三个特征并引用比对文件；副本不能算匹配，应记为 `traced` 出处；新增 `compare --refs E## --pick`；达到 HIGH 必须做对照候选检验；“设计吻合”记在区域上，各场所作为线索。
- **置信度**：决定性线索与全部备选整体权衡（已核实的场所不再被未列出的国家或智能体枚举出的对手稀释）；场所达到 MEDIUM 需要决定性线索；引擎标签上限为 3；矛盾沿链条向下阻止 HIGH；一个地点的确定程度不低于其内部已核实的地点。
- **阅读**：OCR 输出经精度过滤（不再从地毯和天花板上“读”出文字和生僻文字系统）；`scan` 输出文字裁剪对照图；`crop --of` 可放大任意证据图片。
- **稳健性**：Overpass 不可达时回退到 Photon；下载自动重试；逐次报告限流情况；已记录的线索可代表相应方法已执行；`log` 支持逗号列表。
- **输出**：最佳估计点（答案较粗时取线索的坐标）；报告新增核验一节并列出对照候选；候选表标明每一行的身份（答案、包含答案的上级地点、未核实的最佳线索、未列出的备选）；`tools/make_demo.py` 可重建演示案例，并有测试确保项目主页与该案例一致、压缩包与技能文件夹一致。

### 1.1.0

未单独打标签或发布：这些改动随 2.0.0 首次公开。

- 工作流程围绕精确匹配路线与核验关卡重新编排；先立假设再看工具输出；明确工具箱与智能体自身网页搜索、抓取、浏览器工具之间的分工。
- 评分：每一层级都是开放的、链式份额前后一致、类别线索不再向上传递、答案分级并单列最佳线索、新增报告前检查。
- 以图搜图：新增百度、相似图片对照图、用于 Lens 与 Bing 按网址检索的 `share`。
- `compare`：近似重复、同一张照片与 SIFT/RANSAC 几何检验，支持镜像户型。
- `init` 网络检查；`geo ... --print-url`；`note --for/--against` 一次调用完成关联；C2PA 读取。

### 1.0.0

首个公开版本。

## 许可证

代码与文档以 [MIT 许可证](LICENSE) 发布。`indoor-geolocator/data/` 中的数据文件沿用其来源的许可证：
- Unicode CLDR 字段：[Unicode License v3](https://www.unicode.org/license.txt)。
- 维基百科衍生字段（插头类型、市电参数、行车方向、紧急电话、GS1 前缀）：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，© 维基百科贡献者。

详见 [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md)。

设计思路参考了开源项目 geo-sleuth、Geo-Guesser 与 Searching-skill：规则写进代码、似然比候选榜、按来源分级的证据、方法覆盖关卡、“机器先排序”（DINOv2 相似度排序）与 SIFT/RANSAC 核验。相似度模型为 DINOv2（Meta AI，Apache-2.0），使用以 `Xenova/dinov2-small` 发布的 ONNX 版本；它在运行时下载，本仓库不再分发。

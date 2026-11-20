# indoor-geolocator

[English](README.md) · **简体中文**

一个智能体技能（Agent Skill），根据**一张室内照片判断拍摄地点**：酒店客房、公寓、餐厅、商店、车站、博物馆、教室、车内等。它给出场所名称、街道地址、带误差半径的坐标，以及证据真正支持的置信度；同时留下一个整洁的案例文件夹，记录推理的每一步。

**项目主页与交互式演示：** https://ezharjan.github.io/indoor-geolocator/

附上照片并调用技能即可，无需任何提示词。回答使用用户的语言，格式如下（数值仅为示意）：

```
📍 <场所> — <街道地址，城市，国家>
   51.044560, -114.064700 (WGS84) ± 60 m · 层级：场所 · 置信度：中（MEDIUM）
依据：2–4 条决定性证据，各自注明来源与核实方式
备选：次优候选，以及区分二者的检验方法
未核实 / 局限：未能核实的内容及原因
案例文件夹：…/photo-geolocation（REPORT.md 含完整推理记录）
```

## 功能概览

技能为模型提供一套严格的工作流程和一个小巧的命令行工具箱（`scripts/igl.py`，需 Python 3.9+ 与 Pillow）。所有观察都记入同一份台账，排名与置信度由台账计算得出，而不是凭空断言。

1. **接收**：逐字节复制照片；读取 EXIF、GPS、XMP、IPTC、ICC、内嵌缩略图（可发现裁剪或编辑痕迹）、文件名模式、AI 与 C2PA 标记，并把 UTC 偏移映射到时区。
2. **第一印象**：在查看任何工具输出之前先记下，之后再被证实、修正或推翻（锚定防御）。
3. **机器感知**：
   - 多轮 OCR 与文字系统探测，并提示改用当地语言重新识别。
   - 二维码与条形码解析：EMV 支付码（商户名称与城市）、瑞士 QR 账单、SEPA、UPI、Wi-Fi、vCard、GS1 前缀。
   - 文本挖掘：电话号码（可精确到城市）、域名、价格与货币（含已停用货币）、纪年、邮编、计量单位、税务用语。
4. **视觉排查**，对照约 190 条线索的目录：
   - 固定标准：插座、开关、卫浴、暖气、窗户、安全标识、电梯检验证、楼层编号；
   - 产品、品牌、支付方式与认证标志；
   - 风格、图案、习俗以及宗教或节日装饰；
   - 制服、票据、收据等个人物品，只用来推断地点。
5. **国家交叉筛选**：基于 Unicode CLDR 与维基百科构建的离线数据表覆盖 250 个国家和地区，包括插头类型、货币、语言与文字、国际区号、行车方向、紧急电话、每周起始日、时钟制式、单位制与纸张规格。
6. **检索**：
   - 以图搜图：无头运行 Yandex 与 TinEye；Google Lens 与 Bing 在浏览器中完成。
   - 社交媒体：免密钥开放 API（Bluesky、Flickr 标签、Openverse、Mastodon、Lemmy），并为 Instagram、TikTok、X、Reddit、YouTube、小红书、抖音、微博、VK、Naver 等生成现成的搜索链接。
   - 约 50 个国家的房源与点评平台。
   - OpenStreetMap 候选枚举（支持共址查询）、Wikidata SPARQL 与 Wikimedia Commons。
7. **窗外景观与光线**：估算楼层，计算太阳方位角与高度角（NOAA 算法，与 NREL SPA 相差不超过 0.05°）、地标方位、朝拜方向（qibla），查询历史天气。
8. **核验**：
   - 比对之前先写好证伪检验；
   - 只比对不变特征（窗户、天花板、固定装置、窗外景观），参照独立的参考照片；
   - 一致性检查：时区、太阳、天气、季节与各项标准；
   - 重做决定性的一步，并为次优候选做最强论证。
9. **决策**：答案是排名第一的候选，其置信度由代码中的规则封顶；最后定稿并清理案例文件夹。

### 写进代码的准确性规则

- **状态上限**：线索的权重受获取方式限制：推断 ≤3、观察 ≤6、第三方报告 ≤10、元数据 ≤20、在放大裁剪图上读到的文字或计算结果 ≤50、与独立参考图像匹配 ≤100。
- **独立来源**：只有来自相互独立来源（图像、文字、元数据、网页、引擎、地图、参考图、几何）的一致才算数。五条装饰线索只算一个来源；顺着引擎的猜测去数据库里找到它，是循环论证，不是佐证。
- **排除**：只有附带文件的决定性证据才能排除候选。未列出不等于被排除：在国家层级，未列出的国家作为一个整体继续参与排名。
- **置信度上限**：HIGH 需要一条决定性线索、两个独立来源、至少 0.80 的份额且没有未解决的矛盾；在场所层级还需与参考图像匹配，或有来自两个来源的决定性线索。`answer` 会拒绝任何高于上限的置信度。
- **覆盖关卡**：13 项核心方法必须各自以 results、no_results 或 not_applicable 结束，`check` 才能通过。被拦截的服务绝不会被记为“无结果”。

## 安装

**claude.ai、Claude 桌面版与 Cowork**
1. 确认已开启代码执行（*Settings → Capabilities*）。
2. 打开 *Customize → Skills*，点击 **+**，选择 **+ Create skill → Upload a skill**，然后选择 `indoor-geolocator.zip`。
3. 附上照片并调用技能，或直接问“这是在哪里拍的？”。

压缩包顶层就是 `indoor-geolocator/` 文件夹，符合上传要求。

**Claude Code**：把 `indoor-geolocator/` 文件夹复制到 `~/.claude/skills/`（所有项目）或 `<项目>/.claude/skills/`（单个项目）。用 `/indoor-geolocator` 调用，或在分享室内照片时由 Claude 自动启用。

**其他智能体**（Codex、Gemini CLI、Cursor 等）：让智能体读取 `indoor-geolocator/SKILL.md` 即可。工具箱是普通的 Python 命令行程序。

**依赖**：必需 Pillow，Windows 上还需要 `tzdata`。其余依赖均为可选，只决定对应方法能否启用。

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow（Windows 另需 tzdata）
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV、phonenumbers、Playwright、HEIC、RapidOCR
playwright install chromium                                   # 自动以图搜图与网页快照
# OCR 引擎（推荐）：tesseract 及语言包
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # 检查本机可用与缺失的组件
```

## 直接使用工具箱

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # 新建案例文件夹 + 元数据 + 网格视图
$IGL note CASE "First impression: ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR、二维码/条形码、文本信号、排查切片
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL social search "Hotel Name City" --case CASE --sheet 12
$IGL geo poi --brand "Hampton" --tag tourism=hotel --area "Berlin" --case CASE --add site --parent C3
$IGL compare CASE --ref https://example.org/room.jpg
$IGL rank CASE ; $IGL answer CASE C12 --summary "..." ; $IGL check CASE ; $IGL finalize CASE
```

`$IGL <命令> -h` 可查看全部选项。Windows 上请用 `python` 代替 `python3`。南纬、西经坐标可直接输入（`--at -33.86,151.21`）。

## 输出内容

```
photo-geolocation/
├── REPORT.md       答案、各层级置信度、证据表、候选、时间线、方法、数据处理说明
├── result.json     同上内容的机器可读 JSON（schema igl.result/1）
├── case.json       完整台账：线索、候选、关联、排除、尝试记录、时间戳
├── input/          照片（逐字节原样）与 metadata.json
└── evidence/       仅保留台账引用的裁剪图、对比图与网页快照
```

临时文件（切片、缓存、下载）存放在 `.work/`，由 `finalize` 删除；未被引用的证据文件也会一并清除。已有的案例文件夹永远不会被覆盖。

## 隐私与负责任使用

- **不以人为目标**：不做人脸识别，不识别任何个人。
  - 服装、制服、胸牌与个人物品只用于推断地点。
  - 表观族裔只作为易带偏见的弱背景信息，绝不用作排除依据。
  - 社交媒体只搜索地点、文字、标签与照片本身，从不搜索人物或发帖者。
- **私人住宅**：如可识别为私人住宅且未说明用途，技能会询问一次用途；若无正当用途，只给到城市或街区层级。
- **脱敏**：报告不包含私人姓名与住宅地址；解码时自动隐去 Wi-Fi 密码、IBAN 与名片中的姓名。
- **上传**：以图搜图会把照片上传给第三方，报告会列出接收照片的引擎。优先使用不含人物的裁剪图；照片敏感时先征求同意。
- **服务规范**：遵守各服务的使用政策（Nominatim 每秒不超过 1 次请求、限定范围的 Overpass 查询、可识别的 User-Agent）。从不代任何人登录，不破解验证码，不批量抓取。可选用户密钥：`WIGLE_API_NAME` / `WIGLE_API_TOKEN` 用于 Wi-Fi SSID 查询；`IGL_USER_AGENT` 可设置自定义 User-Agent。

地理定位结果是基于证据权衡的估计，而非确定结论。据此行动前，请先查看置信度与“未核实”说明。

## 仓库结构

```
.
├── indoor-geolocator/          技能本体（安装的就是这个文件夹）
│   ├── SKILL.md                工作流程、硬性规则、回答格式
│   ├── LICENSE.txt             LICENSE 的副本（压缩包不含仓库根目录）
│   ├── requirements*.txt
│   ├── references/             线索目录、场景与检索手册、窗外与光线、核验、证据与置信度、来源与工具
│   ├── scripts/igl.py          命令行工具；模块位于 scripts/iglib/
│   └── data/                   countries.json、gs1_prefixes.json（含来源与许可证说明）
├── indoor-geolocator.zip       同一技能的上传用压缩包
├── build_skill_zip.py          重建并校验压缩包（每次修改技能后运行）
├── tools/build_data.py         维护工具：从 Unicode CLDR 与维基百科重建 data/
├── tests/                      离线测试（pytest；由 pytest.ini 指定）
├── docs/                       项目主页（GitHub Pages）及公开的演示案例
├── LICENSE
├── README.md                   英文版说明
└── README.zh-CN.md             简体中文版说明（本文件）
```

## 开发

```bash
python -m pytest                   # 离线测试：台账规则、置信度上限、解析器、几何计算与参考值比对
python tools/build_data.py         # 更新 data/（源数据缓存在 .data-src/；--offline 仅用缓存重建）
python build_skill_zip.py          # 技能文件夹有变动时重建压缩包；--check 只做校验
```

## 许可证

代码与文档以 [MIT 许可证](LICENSE) 发布。`indoor-geolocator/data/` 中的数据文件沿用其来源的许可证：
- Unicode CLDR 字段：[Unicode License v3](https://www.unicode.org/license.txt)。
- 维基百科衍生字段（插头类型、市电参数、行车方向、紧急电话、GS1 前缀）：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，© 维基百科贡献者。

详见 [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md)。

设计思路参考了开源项目 geo-sleuth、Geo-Guesser 与 Searching-skill：规则写进代码、似然比候选榜、按来源分级的证据，以及方法覆盖关卡。

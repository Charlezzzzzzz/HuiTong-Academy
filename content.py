# -*- coding: utf-8 -*-
"""会通书院 · 内容层。

本模块是全部中文内容的唯一真源：七席、十阶、三题、每题的完整会通脚本、
每席的署名筹码、全员共用的异议注处置筹码，以及参考鸣谢清单。
除标准库外不依赖任何模块，不读写文件，不联网。

名词口径以 GCCCE2027 稿件为准：
- 七席：立论、概念澄清、问难、证据、主持、异议记录、最终编辑。
- 十阶：材料导入、独立立论、讲授澄清、师友问难、证据核查、回应修订、
  主持归纳、异议登记、主稿编辑、成文后核义。
- “会通而不强同”只是现代设计原则，不是史料原话。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 七席
# ---------------------------------------------------------------------------

ROLES = [
    {
        "seat": 0,
        "id": "chair",
        "name": "守拙",
        "title": "主持代理",
        "duty": "定序、点名、归纳分歧；不代立论，不裁决",
        "glyph": "主持",
        "prop": "戒尺",
        "prop_id": "ruler",
        "pigment": "赭石",
        "color": "#8A5A3B",
    },
    {
        "seat": 1,
        "id": "speaker",
        "name": "砚秋",
        "title": "立论代理",
        "duty": "先独立成稿；主张须系于史料，并自陈其限",
        "glyph": "立论",
        "prop": "卷轴",
        "prop_id": "scroll",
        "pigment": "花青",
        "color": "#3F5A72",
    },
    {
        "seat": 2,
        "id": "clarifier",
        "name": "知白",
        "title": "概念澄清代理",
        "duty": "释义、区分概念、指出误读；不新增主张",
        "glyph": "澄清",
        "prop": "砚",
        "prop_id": "inkstone",
        "pigment": "石绿",
        "color": "#5C7A63",
    },
    {
        "seat": 3,
        "id": "challenger",
        "name": "砺之",
        "title": "问难代理",
        "duty": "引原话、指对象（主张/证据/前提/边界）；空问不入录",
        "glyph": "问难",
        "prop": "竹简",
        "prop_id": "slips",
        "pigment": "胭脂",
        "color": "#8A4A56",
    },
    {
        "seat": 4,
        "id": "evidence",
        "name": "竹隐",
        "title": "证据代理",
        "duty": "核出处、查反证、标支持与冲突",
        "glyph": "证据",
        "prop": "册",
        "prop_id": "ledger",
        "pigment": "黛青",
        "color": "#4B5566",
    },
    {
        "seat": 5,
        "id": "recorder",
        "name": "慎余",
        "title": "异议记录代理",
        "duty": "登记未决异议，注支持与冲突史料；不得静默删除",
        "glyph": "异议",
        "prop": "印",
        "prop_id": "seal",
        "pigment": "绛紫",
        "color": "#6B4A5E",
    },
    {
        "seat": 6,
        "id": "editor",
        "name": "编云",
        "title": "最终编辑代理",
        "duty": "合主稿、附异议注、保 trace 链",
        "glyph": "编辑",
        "prop": "笔",
        "prop_id": "brush",
        "pigment": "藤黄",
        "color": "#9A7B33",
    },
]

ROLE_BY_ID = {role["id"]: role for role in ROLES}
ROLE_BY_SEAT = {role["seat"]: role for role in ROLES}

# ---------------------------------------------------------------------------
# 十阶（稿件 §3.3 + 成文后核义）
# ---------------------------------------------------------------------------

STAGES = [
    {
        "order": 1,
        "id": "intake",
        "name": "材料导入",
        "brief": "冻结史料与任务，明示产出格式",
        "seal": "材料",
    },
    {
        "order": 2,
        "id": "draft",
        "name": "独立立论",
        "brief": "各自成稿，成稿前互不相见",
        "seal": "立论",
    },
    {
        "order": 3,
        "id": "clarify",
        "name": "讲授澄清",
        "brief": "先释其义，再议其理",
        "seal": "澄清",
    },
    {
        "order": 4,
        "id": "question",
        "name": "师友问难",
        "brief": "引原话、指对象，空问不入录",
        "seal": "问难",
    },
    {
        "order": 5,
        "id": "evidence",
        "name": "证据核查",
        "brief": "核出处，标支持与冲突",
        "seal": "核查",
    },
    {
        "order": 6,
        "id": "revise",
        "name": "回应修订",
        "brief": "逐条回应，改则留痕",
        "seal": "修订",
    },
    {
        "order": 7,
        "id": "moderate",
        "name": "主持归纳",
        "brief": "归纳分歧，不强求同",
        "seal": "归纳",
    },
    {
        "order": 8,
        "id": "ledger",
        "name": "异议登记",
        "brief": "未决异议入册，不得删除",
        "seal": "登记",
    },
    {
        "order": 9,
        "id": "compose",
        "name": "主稿编辑",
        "brief": "主稿与异议注同链",
        "seal": "编辑",
    },
    {
        "order": 10,
        "id": "verify",
        "name": "成文后核义",
        "brief": "检查论证强度、限定和证据归属",
        "seal": "核义",
    },
]

STAGE_BY_ID = {stage["id"]: stage for stage in STAGES}
STAGE_IDS = [stage["id"] for stage in STAGES]

# ---------------------------------------------------------------------------
# 三题：稿件三种任务类型各取一例
# ---------------------------------------------------------------------------

TOPICS = [
    {
        "id": "daofu",
        "title": "《学记》“道而弗牵”是否等于教师不介入",
        "short": "道而弗牵",
        "task_type": "思想解释",
        "packet": "P02、P08",
        "probe": "H2",
        "probe_label": "强制问难的检出效应",
        "default": True,
    },
    {
        "id": "bailudong",
        "title": "白鹿洞学规与会通程序如何约束主持权",
        "short": "白鹿洞学规",
        "task_type": "组织分析",
        "packet": "P04、P05、P08",
        "probe": "H1",
        "probe_label": "轮值主持的定调效应",
        "default": False,
    },
    {
        "id": "hetong",
        "title": "“和而不同”能否为异议保留提供依据",
        "short": "和而不同",
        "task_type": "争议比较",
        "packet": "P05、P06、P07、P08",
        "probe": "H4",
        "probe_label": "异议保留的制度依据",
        "default": False,
    },
]

TOPIC_IDS = [topic["id"] for topic in TOPICS]
TOPIC_BY_ID = {topic["id"]: topic for topic in TOPICS}


PLAIN_LANGUAGE_REPLACEMENTS = [
    ("今日只此一题", "今天只讨论这一题"),
    ("三条会约", "三条规则"),
    ("凡引史料，须标来源编号", "引用史料时要标来源编号"),
    ("问难须引原话、指对象", "提问要引用原文，并说明针对哪一条"),
    ("除此三件，不入正文", "除了这三份材料，其他内容不能写进正文"),
    ("今可互见", "现在可以互相看到彼此的初稿"),
    ("互见之后仍可改，但改须留痕", "看过彼此的初稿后可以修改，但必须记录修改原因"),
    ("先各自成稿，成稿前不相见", "先分别完成初稿，在初稿完成前不能看到别人的意见"),
    ("请澄清代理定其义", "请概念澄清席先把这个概念解释清楚"),
    ("君所定之义", "你刚才确定的意思"),
    ("君所定之分", "你刚才做出的区分"),
    ("君所定", "你刚才的选择"),
    ("君所追问", "你刚才追问的问题"),
    ("君所择", "你刚才的选择"),
    ("请答", "请回答"),
    ("三问入录", "三个问题已经记录"),
    ("入问难", "进入问难环节"),
    ("入册", "记入异议账本"),
    ("依君所定", "按你的选择"),
    ("依君所择", "按你的选择"),
    ("余二条附后", "另外两条放在后面作为补充"),
    ("余二条", "另外两条"),
    ("未决者不删", "未决问题不删除"),
    ("异议注置于何处", "异议说明放在哪里"),
    ("会毕", "本场会通结束"),
    ("散会", "会议结束"),
    ("诸君", "各位"),
    ("戒尺交下届", "主持权交给下一场"),
    ("主稿与异议注同链", "主稿和异议说明保留同一条证据链"),
    ("同者三，异者二", "有三点一致，也有两点分歧"),
    ("不强同", "不要求大家强行达成一致"),
    ("空问不入录", "没有明确对象的问题不记录"),
]


def plain_language(text: str) -> str:
    """把系统旁白和角色解释改成白话；材料原文由引用字段单独保留。"""
    result = text
    for source, target in PLAIN_LANGUAGE_REPLACEMENTS:
        result = result.replace(source, target)
    return result


def _b(stage: str, role: str | None, text: str, kind: str = "utterance") -> dict:
    """一条台词。role 为 None 时表示系统旁白。"""
    return {"stage": stage, "role": role, "text": plain_language(text), "kind": kind}


def _anchor(stage: str, name: str) -> dict:
    """用户回合的插入点。"""
    return {"stage": stage, "anchor": name}


# ---------------------------------------------------------------------------
# 三题脚本
# ---------------------------------------------------------------------------

SCRIPT = {
    # -- 思想解释：道而弗牵 ------------------------------------------------
    "daofu": [
        _b(
            "intake",
            None,
            "史料包 P02、P08｜任务类型：思想解释｜问题：《学记》“道而弗牵”是否等于教师不介入？"
            "｜产出：800–1200 字，含问题提出、证据分析、综合判断、未决问题。",
            "system",
        ),
        _b(
            "intake",
            "chair",
            "今日只此一题。三条会约：一，先各自成稿，成稿前不相见；"
            "二，凡引史料，须标来源编号；三，问难须引原话、指对象。",
        ),
        _b(
            "intake",
            "evidence",
            "材料冻结：P02_S01《学记》原文；P02_S02 注疏；P08_S01 历史边界。除此三件，不入正文。",
        ),
        _b(
            "draft",
            None,
            "独立立论：立论、概念澄清、问难三席各成一稿，互不相见。",
            "system",
        ),
        _b(
            "draft",
            "speaker",
            "C01 我主张：“道而弗牵”不是不介入，而是介入而不拽。“道”是示之以路，"
            "“牵”是牵逼；教师仍须开路，只是不代替学生走。依据 P02_S01“道而弗牵则和”，"
            "以及同句“开而弗达则思”。",
        ),
        _b(
            "draft",
            "clarifier",
            "C02 我先立三义：“道”为引导，“牵”为牵逼，“达”为代达。三字各有所指，"
            "不可把“弗牵”读成“弗教”。暂持：此句讲的是介入方式，不是介入有无。",
        ),
        _b(
            "draft",
            "challenger",
            "C03 我的初稿取相反方向：“弗牵”在句法上与“弗抑”“弗达”并列，"
            "三者都在削减教师动作；若只说“方式”，恐怕把强度问题化掉了。我保留“弱介入”读法。",
        ),
        _b("draft", "chair", "三稿已封存，今可互见。互见之后仍可改，但改须留痕。"),
        _b(
            "clarify",
            "clarifier",
            "先划边界：“牵”是拽着走，“抑”是压着走，“达”是替他说透。三者都不是“教”本身。",
        ),
        _b("clarify", None, "请澄清代理定其义。", "system"),
        _anchor("clarify", "signature"),
        _b("clarify", "speaker", "君所定之义，我记下了。我的主张须据此收窄：我说的是“不拽”，不是“不管”。"),
        _b(
            "clarify",
            "challenger",
            "我接受三义之分，但不接受由此推出“教师应更多介入”。分义只能清概念，不能定强度。",
        ),
        _b("clarify", "chair", "概念既清，入问难。"),
        _b("question", "chair", "问难依三则：引原话、指对象、可核查。空问不入录。"),
        _b(
            "question",
            "challenger",
            "Q01 引原话：“道而弗牵，强而弗抑，开而弗达”。三句连读，若“弗牵”只是方式，"
            "为何与“弗达”并列？“弗达”显然是不把话说完，属强度，不属方式。",
        ),
        _b(
            "question",
            "challenger",
            "Q02 指证据：C01 以“道而弗牵则和”证“介入而不拽”。但“和”是师生关系和顺，"
            "不是教师介入量的证据。此句能否承担你的结论？",
        ),
        _b(
            "question",
            "challenger",
            "Q03 指边界：若学生始终不发问、不思考，教师仍“弗牵”，是否等于放任？"
            "你的主张在什么条件下失效？",
        ),
        _b("question", "chair", "三问入录。请答。"),
        _b("question", None, "请择一问，深追到底。", "system"),
        _anchor("question", "signature"),
        _b("question", "chair", "君所追问，已并入 Q01–Q03。证据代理先核出处。"),
        _b(
            "evidence",
            "evidence",
            "E01 出处核对：P02_S01 三句连读，“道—强—开”为三事，“弗牵—弗抑—弗达”为三戒。"
            "原文未言“介入量”，只言“喻”。",
        ),
        _b(
            "evidence",
            "evidence",
            "E02 反证检索：P02_S02 注疏以“牵逼”释“牵”，与“喻”相对；但同段又说“开而弗达则思”，"
            "“思”是学生自得，不是教师不作为。",
        ),
        _b(
            "evidence",
            "evidence",
            "E03 边界材料：P08_S01 提醒，《学记》为汉人整理之文，不能直接当先秦课堂实录；"
            "以之证“教师角色”须降一格。",
        ),
        _b("evidence", None, "请择一条，先入证据册。", "system"),
        _anchor("evidence", "signature"),
        _b("evidence", "evidence", "依君所择，先录此条；余二条附后。"),
        _b("evidence", "chair", "支持者一，冲突者一，边界者一。请修订。"),
        _b(
            "revise",
            "speaker",
            "R01 受 Q02。“和”只能证关系状态，不能单独证介入量；我把 C01 的结论改为条件句："
            "在“喻”的教学观下，“道而弗牵”要求教师开路而不代行，强度须由“开而弗达”另证。",
        ),
        _b(
            "revise",
            "speaker",
            "R02 不受 Q03 的“放任”读法。原文“道”字本身含“示之路”，教师仍有方向责任；"
            "“弗牵”限制的是拽，不是退场。",
        ),
        _b(
            "revise",
            "clarifier",
            "R03 补一义：“喻”是譬喻、晓喻，不是放任。“弗牵”属于“喻”的方式，不属于“不教”。",
        ),
        _b("revise", "chair", "修订三处：结论降为条件句；“和”的证据降格；“喻”义补入。"),
        _b("revise", None, "请择一修订姿态。", "system"),
        _anchor("revise", "signature"),
        _b("revise", "chair", "君所择，已见修订。请归纳。"),
        _b(
            "moderate",
            "chair",
            "M01 同者三：一，“弗牵”不等于不教；二，“道”含示路；三，“和”是关系状态，不是介入量。",
        ),
        _b(
            "moderate",
            "chair",
            "M02 异者二：一，“弗牵”是方式还是强度；二，学生不发问时，教师责任如何落地。此二处不强同。",
        ),
        _b("moderate", None, "请择一归纳口径。", "system"),
        _anchor("moderate", "signature"),
        _b("moderate", "recorder", "依君所定，入册。"),
        _b(
            "ledger",
            "recorder",
            "I01 异议一：“弗牵”是否含强度义。原主张 C01：方式义；替代主张 C03：强度义；"
            "支持史料 P02_S01；冲突史料 P02_S02；状态：未决。",
        ),
        _b(
            "ledger",
            "recorder",
            "I02 异议二：学生不发问时的教师责任。原主张：教师仍须示路；"
            "替代主张：“弗牵”允许退场；支持史料 P08_S01；冲突史料 P02_S01；状态：未决。",
        ),
        _b(
            "ledger",
            "recorder",
            "trace：C01→Q02→E01→R01→M01→I01；C03→Q03→E03→I02。主稿与异议注共用此链。",
        ),
        _b("ledger", None, "异议注置于何处？", "system"),
        _anchor("ledger", "signature"),
        _anchor("ledger", "placement"),
        _b("ledger", "recorder", "已录。未决者不删，散会前复核一次。"),
        _b(
            "compose",
            "editor",
            "F01 主稿题《“道而弗牵”：方式、强度与教师责任》。结构：一、问题；二、三义之辨；"
            "三、证据与反证；四、条件句结论；五、未决二问。",
        ),
        _b(
            "compose",
            "editor",
            "异议注：I01 方式／强度之争，附 P02_S01、P02_S02；I02 学生不发问时之责任，附 P08_S01、P02_S01。"
            "正文不吞并异议。",
        ),
        _b(
            "compose",
            "editor",
            "trace 已并入 claim_source_map；修订摘要见 R01–R03；成本摘要另附。",
        ),
        _anchor("compose", "signature"),
        _anchor("compose", "placement"),
        _b(
            "compose",
            None,
            "不变量自检：I1 独立成稿先于互见；I2 主张皆系史料；I3 问难指对象；"
            "I4 未决异议未删；I5 主稿与异议注同链；I6 阶段无静默跳过。",
            "system",
        ),
        _b("compose", "chair", "会毕。同者三，异者二，未决二。会录存档，戒尺交下届。"),
    ],
    # -- 组织分析：白鹿洞学规 ----------------------------------------------
    "bailudong": [
        _b(
            "intake",
            None,
            "史料包 P04、P05、P08｜任务类型：组织分析｜问题：白鹿洞学规与会通的程序，"
            "如何约束主持权？｜产出：900–1200 字，含制度描述、权力分析、反例、未决问题。",
            "system",
        ),
        _b("intake", "chair", "今日三件材料并读。会约同前：先各自成稿；引文标号；问难指对象。"),
        _b(
            "intake",
            "evidence",
            "材料冻结：P04_S01《白鹿洞书院揭示》；P05_S01 会通记载；P08_S01 制度边界。",
        ),
        _b(
            "draft",
            None,
            "独立立论：立论、概念澄清、问难三席各成一稿，互不相见。",
            "system",
        ),
        _b(
            "draft",
            "speaker",
            "C01 我主张：会通用程序分散主持权——定序、点名、归纳三事分置，裁决不在主持；"
            "轮值是时间上的分散，问难是当场的力量，会录是事后的留痕。",
        ),
        _b(
            "draft",
            "clarifier",
            "C02 先分三权：议题权、程序权、裁决权。学规给的是价值与工夫的边界，"
            "会通给的是程序；两者不同层，不能互相代替。",
        ),
        _b(
            "draft",
            "challenger",
            "C03 我怀疑轮值。学规既定价值，轮值只换人不换框；主持仍可借“归纳”定调。"
            "程序约束可能只是形式。",
        ),
        _b("draft", "chair", "三稿互见。"),
        _b(
            "clarify",
            "clarifier",
            "学规五教，属价值；为学之序，属工夫；处事接物，属伦理。三者都不是会通议事规则。",
        ),
        _b("clarify", None, "请澄清代理定其义。", "system"),
        _anchor("clarify", "signature"),
        _b(
            "clarify",
            "speaker",
            "君所定之分，我接受。我的主张须补一句：会通的程序约束，只能约束程序，不能代替学规。",
        ),
        _b(
            "clarify",
            "challenger",
            "分层的代价是：若程序独立，它凭什么约束主持？我需要一个制度上的理由。",
        ),
        _b("clarify", "chair", "入问难。"),
        _b("question", "chair", "问难依三则：引原话、指对象、可核查。"),
        _b(
            "question",
            "challenger",
            "Q01 引 P05：会通有“主讲—问难—复讲”之序，但序由谁定？若主持可随时改序，轮值何益？",
        ),
        _b(
            "question",
            "challenger",
            "Q02 指证据：C01 以学规证“程序约束”，但学规是会规，会通是会通；"
            "两者在制度上是否同一层？",
        ),
        _b(
            "question",
            "challenger",
            "Q03 指边界：若山长兼任主持，轮值是否被行政权架空？",
        ),
        _b("question", "chair", "三问入录。"),
        _b("question", None, "请择一问，深追到底。", "system"),
        _anchor("question", "signature"),
        _b("question", "chair", "君所追问，已并入 Q01–Q03。证据代理先核出处。"),
        _b(
            "evidence",
            "evidence",
            "E01 P04_S01 学规列五教、为学之序、修身、处事、接物，属价值与工夫框架，"
            "未规定会通如何议事。",
        ),
        _b(
            "evidence",
            "evidence",
            "E02 P05_S01 记朱熹请陆九渊讲“义利之辨”，并书其说于石。会通能容异见，"
            "但议程仍由主持一方安排。",
        ),
        _b(
            "evidence",
            "evidence",
            "E03 P08_S01 提醒：书院制度跨宋元明清，不能以一时之制概全体；“轮值”是现代类比，史料未载。",
        ),
        _b("evidence", None, "请择一条，先入证据册。", "system"),
        _anchor("evidence", "signature"),
        _b("evidence", "evidence", "依君所择，先录此条；余二条附后。"),
        _b("evidence", "chair", "支持者一，冲突者一，边界者一。请修订。"),
        _b(
            "revise",
            "speaker",
            "R01 受 Q02。学规与会通分层：学规定价值，会通定程序；C01 不再以学规直接证程序。",
        ),
        _b(
            "revise",
            "speaker",
            "R02 Q01 只受一半。序由主持定，但主讲、问难、复讲有固定先后；"
            "改序须当众说明并入录，不能随时。",
        ),
        _b(
            "revise",
            "clarifier",
            "R03 补一义：“轮值”若只换主持、不换裁决权，则只是人事轮换，不是制度约束。",
        ),
        _b("revise", "chair", "修订三处：分层；改序入录；轮值须与裁决权分离。"),
        _b("revise", None, "请择一修订姿态。", "system"),
        _anchor("revise", "signature"),
        _b("revise", "chair", "君所择，已见修订。请归纳。"),
        _b(
            "moderate",
            "chair",
            "M01 同者三：一，学规与会通不同层；二，会通确有序；三，轮值在史料中无直接记载。",
        ),
        _b(
            "moderate",
            "chair",
            "M02 异者二：一，轮值能否约束“归纳权”；二，山长兼任主持时，程序是否失效。此二处不强同。",
        ),
        _b("moderate", None, "请择一归纳口径。", "system"),
        _anchor("moderate", "signature"),
        _b("moderate", "recorder", "依君所定，入册。"),
        _b(
            "ledger",
            "recorder",
            "I01 异议一：轮值是否只是形式。原主张：轮值分散主持权；替代主张：轮值只换人不换框；"
            "支持 P05_S01；冲突 P08_S01；状态：未决。",
        ),
        _b(
            "ledger",
            "recorder",
            "I02 异议二：山长兼任主持。原主张：程序仍可约束；替代主张：行政权架空程序；"
            "支持 P04_S01；冲突 P05_S01；状态：未决。",
        ),
        _b(
            "ledger",
            "recorder",
            "trace：C01→Q02→E01→R01→M01→I01；C03→Q01→E02→R02→I02。主稿与异议注共用此链。",
        ),
        _b("ledger", None, "异议注置于何处？", "system"),
        _anchor("ledger", "signature"),
        _anchor("ledger", "placement"),
        _b("ledger", "recorder", "已录。未决者不删。"),
        _b(
            "compose",
            "editor",
            "F01 主稿题《从白鹿洞学规到会通：程序如何约束主持权》。结构：一、问题；二、三权之分；"
            "三、学规与会通的分层；四、轮值的条件；五、未决二问。",
        ),
        _b(
            "compose",
            "editor",
            "异议注：I01 轮值之效，附 P05_S01、P08_S01；I02 山长兼任，附 P04_S01、P05_S01。正文不吞并异议。",
        ),
        _b(
            "compose",
            "editor",
            "trace 与 claim_source_map 已并链；修订摘要 R01–R03；成本摘要另附。",
        ),
        _anchor("compose", "signature"),
        _anchor("compose", "placement"),
        _b(
            "compose",
            None,
            "不变量自检：I1 独立成稿先于互见；I2 主张皆系史料；I3 问难指对象；"
            "I4 未决异议未删；I5 主稿与异议注同链；I6 阶段无静默跳过。",
            "system",
        ),
        _b("compose", "chair", "会毕。同者三，异者二，未决二。会录存档，戒尺交下届。"),
    ],
    # -- 争议比较：和而不同 ------------------------------------------------
    "hetong": [
        _b(
            "intake",
            None,
            "史料包 P05、P06、P07、P08｜任务类型：争议比较｜问题：“和而不同”能否为异议保留提供依据？"
            "｜产出：900–1200 字，含两说比较、转译限度、未决问题。",
            "system",
        ),
        _b("intake", "chair", "今日读四组材料。会约同前：先各自成稿；引文标号；问难指对象。"),
        _b(
            "intake",
            "evidence",
            "材料冻结：P05_S01 会通记载（朱陆“义利之辨”）；P06_S01《论语》原文；"
            "P06_S02《国语》《左传》“和”义；P07_S01 注疏；P08_S01 历史边界。",
        ),
        _b(
            "draft",
            None,
            "独立立论：立论、概念澄清、问难三席各成一稿，互不相见。",
            "system",
        ),
        _b(
            "draft",
            "speaker",
            "C01 我主张：“和而不同”可为异议保留提供规范依据。“和”以差异为条件，"
            "“同”以取消差异为代价；把异议删净，剩下的是“同”，不是“和”。",
        ),
        _b(
            "draft",
            "clarifier",
            "C02 先分三层：伦理德性（君子人格）、政治智慧（君臣相和）、制度程序（会通规则）。"
            "原文属前两层；第三层是转译，不是原文直推。",
        ),
        _b(
            "draft",
            "challenger",
            "C03 我反对直接转译。“和而不同”说差异共存，不说差异必须被记录、必须进入主稿。"
            "把“保留异议”说成孔子之意，是时代错置。",
        ),
        _b("draft", "chair", "三稿互见。"),
        _b(
            "clarify",
            "clarifier",
            "“和”是异质相济，“同”是同质相叠。“和实生物”讲生成，“若以水济水”讲不可食——"
            "都在说差异的功能，不在说记录的程序。",
        ),
        _b("clarify", None, "请澄清代理定其义。", "system"),
        _anchor("clarify", "signature"),
        _b(
            "clarify",
            "speaker",
            "君所定之分，我接受。我的主张降一格：不说“孔子要求记录异议”，"
            "只说“和而不同”为保留差异提供了规范理由。",
        ),
        _b(
            "clarify",
            "challenger",
            "降一格还不够。规范理由与制度义务之间，还差一个转译论证。",
        ),
        _b("clarify", "chair", "入问难。"),
        _b("question", "chair", "问难依三则：引原话、指对象、可核查。"),
        _b(
            "question",
            "challenger",
            "Q01 引原话：“君子和而不同，小人同而不和”。主语是君子小人，不是制度；"
            "如何从人格论推出程序论？",
        ),
        _b(
            "question",
            "challenger",
            "Q02 指证据：C01 引《国语》“和实生物，同则不继”，但史伯说的是万物生成，"
            "不是异议登记。此证据是否越界？",
        ),
        _b(
            "question",
            "challenger",
            "Q03 指边界：若异议本身基于错误史料，也要保留吗？“保留”是否等于“不改”？",
        ),
        _b("question", "chair", "三问入录。"),
        _b("question", None, "请择一问，深追到底。", "system"),
        _anchor("question", "signature"),
        _b("question", "chair", "君所追问，已并入 Q01–Q03。证据代理先核出处。"),
        _b(
            "evidence",
            "evidence",
            "E01 P06_S01《论语》原文；P06_S02《国语》“和实生物”、《左传》“若以水济水”。"
            "三处都在说差异的功能，未言记录制度。",
        ),
        _b(
            "evidence",
            "evidence",
            "E02 P07_S01 注疏本身即是“不同”的载体：历代注家并存，但注疏也会遮蔽原文。",
        ),
        _b(
            "evidence",
            "evidence",
            "E03 P05_S01 记朱陆之会，异见得存，是“和而不同”的一次实践；"
            "P08_S01 提醒，先秦“和同”之辨与书院会通相隔千年，制度转译须标明，不得径称古制。",
        ),
        _b("evidence", None, "请择一条，先入证据册。", "system"),
        _anchor("evidence", "signature"),
        _b("evidence", "evidence", "依君所择，先录此条；余二条附后。"),
        _b("evidence", "chair", "支持者一，冲突者一，边界者一。请修订。"),
        _b(
            "revise",
            "speaker",
            "R01 受 Q01。删去“孔子主张记录异议”，改为“和而不同提供规范理由，记录制度是后人的转译”。",
        ),
        _b(
            "revise",
            "speaker",
            "R02 受 Q03。保留不等于不改：异议须标状态（未决／已回应／已撤回），"
            "错误史料须注“证据不足”。",
        ),
        _b(
            "revise",
            "clarifier",
            "R03 Q02 只受一半。《国语》之喻可作类比，不作直证；我会在注中写明类比与直证之别。",
        ),
        _b("revise", "chair", "修订三处：降格；标状态；分类比与直证。"),
        _b("revise", None, "请择一修订姿态。", "system"),
        _anchor("revise", "signature"),
        _b("revise", "chair", "君所择，已见修订。请归纳。"),
        _b(
            "moderate",
            "chair",
            "M01 同者三：一，“和”以差异为条件；二，原文属人格与政治层；三，制度转译须标明。",
        ),
        _b(
            "moderate",
            "chair",
            "M02 异者二：一，错误史料的异议是否入册；二，“保留”与“不改”的边界。此二处不强同。",
        ),
        _b("moderate", None, "请择一归纳口径。", "system"),
        _anchor("moderate", "signature"),
        _b("moderate", "recorder", "依君所定，入册。"),
        _b(
            "ledger",
            "recorder",
            "I01 异议一：错误史料的异议是否保留。原主张：凡异议皆入册；"
            "替代主张：证据不足者标注而不删；支持 P06_S01；冲突 P08_S01；状态：未决。",
        ),
        _b(
            "ledger",
            "recorder",
            "I02 异议二：“保留”是否等于“不改”。原主张：保留即不改；"
            "替代主张：保留是留痕，不是拒改；支持 P07_S01；冲突 P08_S01；状态：未决。",
        ),
        _b(
            "ledger",
            "recorder",
            "trace：C01→Q01→E01→R01→M01→I01；C03→Q03→E03→R02→I02。主稿与异议注共用此链。",
        ),
        _b("ledger", None, "异议注置于何处？", "system"),
        _anchor("ledger", "signature"),
        _anchor("ledger", "placement"),
        _b("ledger", "recorder", "已录。未决者不删。"),
        _b(
            "compose",
            "editor",
            "F01 主稿题《“和而不同”与异议保留：一次制度转译的限度》。结构：一、问题；"
            "二、三层之分；三、两说比较；四、转译论证；五、未决二问。",
        ),
        _b(
            "compose",
            "editor",
            "异议注：I01 错误史料之异议，附 P06_S01、P08_S01；I02 保留与不改之辨，附 P07_S01、P08_S01。"
            "正文不吞并异议。",
        ),
        _b(
            "compose",
            "editor",
            "trace 与 claim_source_map 已并链；修订摘要 R01–R03；成本摘要另附。",
        ),
        _anchor("compose", "signature"),
        _anchor("compose", "placement"),
        _b(
            "compose",
            None,
            "不变量自检：I1 独立成稿先于互见；I2 主张皆系史料；I3 问难指对象；"
            "I4 未决异议未删；I5 主稿与异议注同链；I6 阶段无静默跳过。",
            "system",
        ),
        _b("compose", "chair", "会毕。同者三，异者二，未决二。会录存档，戒尺交下届。"),
    ],
}

# 每席的署名回合落在哪一阶段。用户在该阶段末尾行使一次角色判断。
SIGNATURE_STAGE = {
    0: "moderate",
    1: "revise",
    2: "clarify",
    3: "question",
    4: "evidence",
    5: "ledger",
    6: "compose",
}

# 每席在三题中的署名筹码。一题三句，必须与题目概念相扣。
SIGNATURE_CHIPS = {
    "daofu": {
        0: [
            "同者三，异者二；异者入未决，不作多数表决。",
            "以条件句收束：方式义与强度义并存，各注条件。",
            "留一问给下会：学生不发问时，教师是否仍“弗牵”。",
        ],
        1: [
            "全受：结论改条件句，“和”只作关系证据。",
            "部分受：受 Q02，不收 Q03；“道”仍含方向责任。",
            "以条件句受：“牵”取强度义则成立，取方式义则须补证。",
        ],
        2: [
            "“牵”释为牵逼：教师有方向，但不拽着走。",
            "“牵”与“达”对举：不拽，也不代达，留一步给学生。",
            "“牵”是强度词，不是有无词：问题不在教不教，在教到哪一步。",
        ],
        3: [
            "追问原话：“开而弗达”既是强度，“弗牵”为何不能也是强度？",
            "追问证据：“和”能证介入量，还是只能证关系状态？",
            "追问边界：学生不发问时，“弗牵”是否仍成立？",
        ],
        4: [
            "先入支持：“道而弗牵则和”可证方式，不足证强度。",
            "先入冲突：注疏“牵逼”与“弗达则思”并读，支持弱介入。",
            "先入边界：P08 的历史边界先立，再谈规范结论。",
        ],
        5: [
            "照录两造：C01 方式义／C03 强度义，各系史料，不裁断。",
            "以“未决”入册：注明支持与冲突各一条，留待下会。",
            "分条编号：I01 方式与强度，I02 学生不发问时之责任。",
        ],
        6: [
            "以未决收束：正文立条件句，文末列二问。",
            "以两说并列收束：方式义与强度义各占一节。",
            "以实践问题收束：把“学生不发问”留给读者判断。",
        ],
    },
    "bailudong": {
        0: [
            "同者三，异者二；轮值与山长兼任二事入未决。",
            "以条件句收束：轮值有效，须以裁决权分离为前提。",
            "留一问给下会：山长兼任主持时，程序是否仍有约束力。",
        ],
        1: [
            "全受：学规与会通分层，删去以学规直证程序。",
            "部分受：受 Q02，保留“会通有序”；改序须入录。",
            "以条件句受：若裁决权独立，则轮值有效；否则只余形式。",
        ],
        2: [
            "三权分立：议题权、程序权、裁决权，各有所属。",
            "两层分置：学规定价值，会通定程序。",
            "轮值只是人事，不是制度；须与裁决权分离并论。",
        ],
        3: [
            "追问程序：序由谁定，改序是否须当众说明并入录？",
            "追问层级：学规与会通是否同一制度层？",
            "追问边界：山长兼任主持时，轮值是否被行政权架空？",
        ],
        4: [
            "先入学规：P04 只列价值与工夫，未定议事程序。",
            "先入会通：P05 记陆九渊讲学，能容异见，议程仍由主持安排。",
            "先入边界：P08 提醒制度跨代，“轮值”是现代类比。",
        ],
        5: [
            "照录两造：轮值有效／轮值形式，各系史料，不裁断。",
            "以“未决”入册：注明史料未载轮值，留待下会。",
            "分条编号：I01 轮值之效，I02 山长兼任。",
        ],
        6: [
            "以条件收束：轮值有效，须以裁决权分离为前提。",
            "以两案并列：程序约束说／行政架空说，各占一节。",
            "以历史边界收束：先承认史料未载，再谈现代转译。",
        ],
    },
    "hetong": {
        0: [
            "同者三，异者二；错误史料与“保留”二事入未决。",
            "以条件句收束：保留是留痕，不是拒改。",
            "留一问给下会：错误史料的异议，是删、是注、还是并存。",
        ],
        1: [
            "全受：删去“孔子主张记录”，改为规范理由。",
            "部分受：受 Q01、Q03；Q02 只作类比，不作直证。",
            "以条件句受：若“保留”取留痕义，则结论成立。",
        ],
        2: [
            "三层之分：伦理德性、政治智慧、制度程序。",
            "“和”是异质相济，“同”是同质相叠。",
            "原文说差异的功能，不说记录的程序。",
        ],
        3: [
            "追问层级：人格论如何推出程序论？",
            "追问证据：《国语》之喻可作直证吗？",
            "追问边界：错误史料的异议也要保留吗？",
        ],
        4: [
            "先入原文：P06 三处皆言差异的功能，未言记录制度。",
            "先入注疏：P07 注疏并存，本身即“不同”的载体。",
            "先入边界：P08 隔千年，制度转译须标明。",
        ],
        5: [
            "照录两造：可直接转译／须降格转译，各系史料。",
            "以“未决”入册：错误史料之处置，留待下会。",
            "分条编号：I01 错误史料，I02 保留与不改。",
        ],
        6: [
            "以限度收束：规范理由成立，制度义务未证。",
            "以两说并列：直接转译／降格转译，各占一节。",
            "以未决收束：文末列错误史料与“保留”二问。",
        ],
    },
}

# 全员共用的异议注处置回合。所有非异议记录席在“异议登记”末尾行使。
PLACEMENT_CHIPS = [
    "附于正文之后，逐条编号，注明支持与冲突史料。",
    "随文夹注，落在被质疑的句子旁，正文不删。",
    "独立成篇，与主稿同链，不并入正文。",
]

# ---------------------------------------------------------------------------
# 界面文案（前端不写死任何用户可见中文）
# ---------------------------------------------------------------------------

UI = {
    "product_name": "会通书院",
    "gate_title": "会通书院",
    "gate_subtitle": "一扇门与七只蒲团",
    "gate_hint_desktop": "点锁拨码 · Enter 启",
    "gate_hint_touch": "轻触锁体 · 拨码开门",
    "start": "开讲",
    "leave": "起座",
    "again": "再听一场",
    "stage_hud": "第{order}·{name}",
    "stage_rail": "{order}·{name}",
    "panel_head": "会通",
    "seated_as": "你 · {glyph}·{name}",
    "chips_prompt": "请选择一个回应",
    "new_lines": "↓ 新消息",
    "network_break": "连接中断，请稍后继续",
    "retry": "重试",
    "session_lost": "本场会通已结束，可以重新开始",
    "restart": "重新开始",
    "seal_saved": "会录已保存",
    "ruler_handover": "主持权交给：{name}（下一场）",
    "setup_title": "设置口令",
    "code_label": "口令",
    "repeat_label": "复述",
    "hint_label": "提示语",
    "hint_placeholder": "如：四字，问山长",
    "setup_note": "口令只存其哈希，遗忘须删 data/config.json 重设。",
    "setup_submit": "保存",
    "unlock_submit": "打开",
    "unlock_error": "口令不正确（第 {n} 次）",
    "hint_prefix": "提示：{hint}",
    "wait_seconds": "请待 {n} 秒",
    "mismatch": "两次口令不一致",
    "code_invalid": "口令须为四位数字",
    "setup_exists": "口令已经设置，请输入原来的口令",
    "gate_locked": "入口还没有打开，请重新输入口令",
    "loading_title": "正在加载会通书院空间",
    "config_failed": "接口没有响应，请重试",
    "fallback_title": "会通书院",
    "fallback_text": "此机未开笔墨，暂以文字入席。",
    "fallback_three": "三维组件未取到，请检查网络或重试。",
    "fallback_seats": "择席入座",
    "noscript": "此页需启用 JavaScript。",
    "seat_hit": "入座：{glyph}·{name}",
    "dial_aria": "口令",
    "dial_error_seal": "误",
    "error_generic": "暂时出了问题，请再试一次。",
    "close": "关闭",
    "topic_prefix": "讨论主题",
    "topic_pick": "选择主题",
    "topic_meta": "{type} · {packet}",
    "probe_prefix": "机制",
    "you": "你",
    "me": "我",
    "couplet_right": "有问则问 有商量则商量",
    "couplet_left": "凡有所疑 专置册记录",
    "scene_help": "七只蒲团，用 Tab 选择",
    "code_ok": "口令已合",
    "session_busy": "座已满，请稍候",
    "session_busy_wait": "座已满，请待 {n} 秒",
    "seal_open": "启",
    "seal_seat": "入座",
    "seal_leave": "起",
    "seal_again": "再",
    "credits": "参考鸣谢",
    "credits_title": "参考鸣谢与出处",
    "credits_intro": "本项目只参考下列项目的思路与技法，未复制其源代码。",
    "credits_originality": "除按 MIT 许可证随附的 Three.js 外，本项目代码均为自写。",
    "credits_license": "许可证",
    "credits_borrow": "借鉴点",
    "credits_deps": "随附依赖",
    "credits_sources": "史料与文本",
    "credits_close": "收起",
    "numeral": ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"],
}

PACE = {"utterance": 2500, "system": 1200, "stage": 900, "user": 600, "choice": 600}

# ---------------------------------------------------------------------------
# 参考鸣谢
# ---------------------------------------------------------------------------

CREDITS = {
    "intro": "本项目只参考下列项目的思路与技法，未复制其源代码。",
    "originality": "除按 MIT 许可证随附的 Three.js 外，本项目代码均为自写；界面与文稿不含任何工具署名或生成水印。",
    "groups": [
        {
            "title": "水墨与三维渲染",
            "items": [
                {
                    "name": "23ag1/ink-wash-painting-skill",
                    "url": "https://github.com/23ag1/ink-wash-painting-skill",
                    "license": "未声明（仅参考思路）",
                    "borrow": "纸纹、湿边扩散、飞白笔触的参数与分层思路。",
                },
                {
                    "name": "jammyfu/xiangsheng-genealogy",
                    "url": "https://github.com/jammyfu/xiangsheng-genealogy",
                    "license": "MIT",
                    "borrow": "墨色精灵去彩边、按深度混入纸色的做法。",
                },
                {
                    "name": "sacshadow/3D_ChineseInkPaintingStyleShader",
                    "url": "https://github.com/sacshadow/3D_ChineseInkPaintingStyleShader",
                    "license": "MIT",
                    "borrow": "勾、皴、染三段式与轮廓飞白的管线结构。",
                },
                {
                    "name": "DCtheTall/webgl-landscape",
                    "url": "https://github.com/DCtheTall/webgl-landscape",
                    "license": "未声明（仅参考思路）",
                    "borrow": "三十行左右的纸色乘法后处理与色调压缩。",
                },
                {
                    "name": "TanShilongMario/InkPainting",
                    "url": "https://github.com/TanShilongMario/InkPainting",
                    "license": "MIT",
                    "borrow": "焦墨至烟墨的八级墨色与宣纸纹理参数。",
                },
                {
                    "name": "WishMelz/AquaInkGL",
                    "url": "https://github.com/WishMelz/AquaInkGL",
                    "license": "未声明（仅参考思路）",
                    "borrow": "开门时一次性的墨液扩散与分辨率分级。",
                },
                {
                    "name": "LingDong-/shan-shui-inf",
                    "url": "https://github.com/LingDong-/shan-shui-inf",
                    "license": "MIT",
                    "borrow": "变宽笔线、抖动笔迹与山水母题的几何生成。",
                },
            ],
        },
        {
            "title": "相机、空间与过场",
            "items": [
                {
                    "name": "rzx007/home-3d",
                    "url": "https://github.com/rzx007/home-3d",
                    "license": "未声明（仅参考思路）",
                    "borrow": "俯视正交机位、四段视图切换与飞行插值。",
                },
                {
                    "name": "yomotsu/camera-controls",
                    "url": "https://github.com/yomotsu/camera-controls",
                    "license": "MIT",
                    "borrow": "可 await 的相机过渡与取景框定。",
                },
                {
                    "name": "mrdoob/three.js",
                    "url": "https://github.com/mrdoob/three.js",
                    "license": "MIT",
                    "borrow": "随附 0.160.0 运行时；参考 pointer-lock 与胶囊视高。",
                },
                {
                    "name": "joris-db/ha-3d-floorplan",
                    "url": "https://github.com/joris-db/ha-3d-floorplan",
                    "license": "MIT",
                    "borrow": "按方向与距离插值，而非直接插值位置。",
                },
                {
                    "name": "tweenjs/tween.js",
                    "url": "https://github.com/tweenjs/tween.js",
                    "license": "MIT",
                    "borrow": "缓动曲线与串接过渡的写法。",
                },
            ],
        },
        {
            "title": "笔法、墨迹与转场",
            "items": [
                {
                    "name": "evoluteur/enso-maker",
                    "url": "https://github.com/evoluteur/enso-maker",
                    "license": "MIT",
                    "borrow": "四十余根笔毫、边缘先枯与飞白断笔。",
                },
                {
                    "name": "acamposuribe/p5.brush",
                    "url": "https://github.com/acamposuribe/p5.brush",
                    "license": "MIT",
                    "borrow": "水色晕染、颜料环与排线成面的算法。",
                },
                {
                    "name": "shin4/inkpond",
                    "url": "https://github.com/shin4/inkpond",
                    "license": "MIT",
                    "borrow": "墨晕转场、字形图集与降级策略。",
                },
                {
                    "name": "jiang4wqy/ink-slash",
                    "url": "https://github.com/jiang4wqy/ink-slash",
                    "license": "MIT",
                    "borrow": "收锋笔画、飞白迸溅与拖动命中。",
                },
                {
                    "name": "steveruizok/perfect-freehand",
                    "url": "https://github.com/steveruizok/perfect-freehand",
                    "license": "MIT",
                    "borrow": "由指针采样生成带压感的笔画轮廓。",
                },
                {
                    "name": "spite/THREE.MeshLine",
                    "url": "https://github.com/spite/THREE.MeshLine",
                    "license": "MIT",
                    "borrow": "沿线变宽、可渐显的墨线。",
                },
                {
                    "name": "airbate/shuimo-liuyun",
                    "url": "https://github.com/airbate/shuimo-liuyun",
                    "license": "MIT（仅本地化部分）",
                    "borrow": "Beer–Lambert 颜料叠色与纸纹。",
                },
                {
                    "name": "gl-transitions/gl-transitions",
                    "url": "https://github.com/gl-transitions/gl-transitions",
                    "license": "MIT（个别 BSD）",
                    "borrow": "全屏过渡的接口约定与噪声阈值擦除。",
                },
            ],
        },
        {
            "title": "多智能体会场",
            "items": [
                {
                    "name": "a16z-infra/ai-town",
                    "url": "https://github.com/a16z-infra/ai-town",
                    "license": "MIT",
                    "borrow": "气泡与转录分栏、只在贴底时自动滚动。",
                },
                {
                    "name": "joonspk-research/generative_agents",
                    "url": "https://github.com/joonspk-research/generative_agents",
                    "license": "Apache-2.0",
                    "borrow": "每席预分配一个气泡，只显隐与移动。",
                },
                {
                    "name": "JuniorXcoder/hermes-virtual-office",
                    "url": "https://github.com/JuniorXcoder/hermes-virtual-office",
                    "license": "MIT",
                    "borrow": "三维座位、CSS2D 说话气泡与单一状态机。",
                },
                {
                    "name": "Charonyuu/whatsmyagentdoing",
                    "url": "https://github.com/Charonyuu/whatsmyagentdoing",
                    "license": "MIT",
                    "borrow": "状态到体态的映射与按需加载三维场景。",
                },
                {
                    "name": "rockbenben/legend-talk",
                    "url": "https://github.com/rockbenben/legend-talk",
                    "license": "MIT",
                    "borrow": "圆桌轮次、主持归纳与议题卡快照。",
                },
                {
                    "name": "erickong/agent-roundtable",
                    "url": "https://github.com/erickong/agent-roundtable",
                    "license": "MIT",
                    "borrow": "无框架的发言人气泡与轮次骨架。",
                },
                {
                    "name": "XiaoLuoLYG/GOD",
                    "url": "https://github.com/XiaoLuoLYG/GOD",
                    "license": "Apache-2.0",
                    "borrow": "可寻址的回放步与中途注入。",
                },
            ],
        },
    ],
    "dependencies": [
        {
            "name": "Three.js 0.160.0",
            "url": "https://github.com/mrdoob/three.js",
            "license": "MIT",
            "borrow": "随项目分发的三维运行时（static/vendor/three.module.min.js）。",
        },
        {
            "name": "Google Fonts · Ma Shan Zheng",
            "url": "https://fonts.google.com/specimen/Ma+Shan+Zheng",
            "license": "SIL OFL 1.1",
            "borrow": "标题与印章的毛笔字形。",
        },
        {
            "name": "Google Fonts · Zhi Mang Xing",
            "url": "https://fonts.google.com/specimen/Zhi+Mang+Xing",
            "license": "SIL OFL 1.1",
            "borrow": "手写批注与旁白字形。",
        },
    ],
    "sources": [
        {
            "name": "《礼记·学记》",
            "url": "",
            "license": "公有领域",
            "borrow": "“道而弗牵，强而弗抑，开而弗达”及“和、易以思”之文。",
        },
        {
            "name": "《论语·子路》",
            "url": "",
            "license": "公有领域",
            "borrow": "“君子和而不同，小人同而不和”。",
        },
        {
            "name": "《国语·郑语》《左传·昭公二十年》",
            "url": "",
            "license": "公有领域",
            "borrow": "“和实生物，同则不继”与“若以水济水”。",
        },
        {
            "name": "《白鹿洞书院揭示》",
            "url": "",
            "license": "公有领域",
            "borrow": "五教、为学之序、修身、处事、接物之条。",
        },
    ],
}

# ---------------------------------------------------------------------------
# 脚本组装
# ---------------------------------------------------------------------------


def _chip_list(prefix: str, texts: list[str]) -> list[dict]:
    return [{"id": f"{prefix}{index + 1}", "text": text} for index, text in enumerate(texts)]


def build_script(topic_id: str, user_seat: int, mode: str = "production") -> list[dict]:
    """组装一次会通的全部条目。纯函数，同一参数恒返回相同结果。

    每席恰好两个 ``await_user``：该席的署名回合，以及异议注处置回合。
    异议记录席的处置回合落在主稿编辑阶段，其余六席落在异议登记阶段。
    """
    if topic_id not in TOPIC_IDS:
        raise ValueError("unknown topic")
    if mode not in {"learning", "production"}:
        raise ValueError("mode_invalid")
    if (
        not isinstance(user_seat, int)
        or isinstance(user_seat, bool)
        or not 0 <= user_seat < len(ROLES)
    ):
        raise ValueError("bad seat")

    entries: list[dict] = []
    seq = 0

    def add(
        stage_id: str,
        role_id: str | None,
        text: str,
        kind: str = "utterance",
        chips: list[dict] | None = None,
        await_user: bool = False,
        as_user: bool = False,
        human_prompt: bool = False,
        hint: str = "",
    ) -> None:
        nonlocal seq
        seq += 1
        seat = ROLE_BY_ID[role_id]["seat"] if role_id else None
        if role_id:
            role = ROLE_BY_ID[role_id]
            role_name = UI["you"] if as_user else role["name"]
            role_title = role["title"]
        else:
            role_name = None
            role_title = None
        entries.append(
            {
                "seq": seq,
                "stage": stage_id,
                "role_id": role_id,
                "seat": seat,
                "role_name": role_name,
                "role_title": role_title,
                "text": text,
                "kind": kind,
                "chips": chips if chips is not None else [],
                "await_user": await_user,
                "human_prompt": human_prompt,
                "hint": hint,
                "pacing_ms": PACE["choice"] if await_user else PACE.get(kind, PACE["utterance"]),
            }
        )

    def add_user(stage_id: str, prefix: str, texts: list[str]) -> None:
        role = ROLE_BY_SEAT[user_seat]
        if mode == "learning":
            add(
                stage_id,
                role["id"],
                "",
                kind="prompt",
                await_user=True,
                as_user=True,
                human_prompt=True,
                hint=f"请以“{role['name']}·{role['title']}”身份回应。可从以下方向展开：{'；'.join(texts)}",
            )
            return
        add(
            stage_id,
            role["id"],
            UI["chips_prompt"],
            kind="choice",
            chips=_chip_list(prefix, texts),
            await_user=True,
            as_user=True,
        )

    def add_role(stage_id: str, role_id: str, text: str) -> None:
        role = ROLE_BY_ID[role_id]
        if mode == "learning" and role["seat"] == user_seat:
            add(
                stage_id,
                role_id,
                "",
                kind="prompt",
                await_user=True,
                as_user=True,
                human_prompt=True,
                hint=f"请以“{role['name']}·{role['title']}”身份回应。提示内容：{text}",
            )
            return
        add(stage_id, role_id, text)

    for stage in STAGES:
        stage_id = stage["id"]
        add(stage_id, None, stage["name"], kind="stage")
        for beat in SCRIPT[topic_id]:
            if beat["stage"] != stage_id:
                continue
            anchor = beat.get("anchor")
            if anchor == "signature":
                if stage_id == SIGNATURE_STAGE[user_seat]:
                    add_user(stage_id, "s", SIGNATURE_CHIPS[topic_id][user_seat])
                continue
            if anchor == "placement":
                if stage_id == "ledger" and user_seat != 5:
                    add_user(stage_id, "p", PLACEMENT_CHIPS)
                elif stage_id == "compose" and user_seat == 5:
                    add_user(stage_id, "p", PLACEMENT_CHIPS)
                continue
            role_id = beat.get("role")
            if mode == "learning" and role_id and ROLE_BY_ID[role_id]["seat"] == user_seat:
                role = ROLE_BY_ID[role_id]
                add(
                    stage_id,
                    role_id,
                    "",
                    kind="prompt",
                    await_user=True,
                    as_user=True,
                    human_prompt=True,
                    hint=f"请以“{role['name']}·{role['title']}”身份回应。提示内容：{beat['text']}",
                )
                continue
            add(
                stage_id,
                role_id,
                beat["text"],
                kind=beat.get("kind", "utterance"),
            )

    # 成文后核义是编辑后的独立门控，不修改九阶脚本中的历史台词。
    # 它检查语义强度、必要限定、证据归属和异议承载位置，避免润色
    # 静默改变主张。该阶段没有额外的人类选择，结果写入 edit_audit。
    add("verify", None, "成文后核义", kind="stage")
    add_role(
        "verify",
        "evidence",
        "核义检查：逐条复核主稿中的主张、来源编号、必要限定和异议注位置。",
    )
    add_role(
        "verify",
        "editor",
        "编辑审计：记录任何论证强度变化；若删除限定或改变证据归属，标为待修订。",
    )
    add_role(
        "verify",
        "chair",
        "核义完成。会录同时保存主稿、异议账本和修订审计，供学习者回看。",
    )

    return entries


# ---------------------------------------------------------------------------
# 鸣谢文件生成
# ---------------------------------------------------------------------------


def render_credits_md() -> str:
    """按 CREDITS 生成 CREDITS.md，保证界面与文件同源。"""
    lines = [
        "# 参考鸣谢与出处",
        "",
        CREDITS["intro"],
        "",
        CREDITS["originality"],
        "",
    ]
    for group in CREDITS["groups"]:
        lines.append(f"## {group['title']}")
        lines.append("")
        for item in group["items"]:
            line = f"- **{item['name']}** — {item['license']}"
            if item.get("url"):
                line += f" — <{item['url']}>"
            lines.append(line)
            lines.append(f"  - 借鉴：{item['borrow']}")
        lines.append("")
    lines.append("## 随附依赖")
    lines.append("")
    for item in CREDITS["dependencies"]:
        line = f"- **{item['name']}** — {item['license']}"
        if item.get("url"):
            line += f" — <{item['url']}>"
        lines.append(line)
        lines.append(f"  - 用途：{item['borrow']}")
    lines.append("")
    lines.append("## 史料与文本")
    lines.append("")
    for item in CREDITS["sources"]:
        lines.append(f"- **{item['name']}** — {item['license']}")
        lines.append(f"  - 用途：{item['borrow']}")
    lines.append("")
    lines.append(
        "> 说明：原型台词中的史料编号对应稿件史料包，台词为体验演示而改写；"
        "正式引用以稿件附录所载版本为准。"
    )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="会通内容层工具")
    parser.add_argument(
        "--credits",
        metavar="PATH",
        help="生成 CREDITS.md 到指定路径",
    )
    args = parser.parse_args()
    if args.credits:
        Path(args.credits).write_text(render_credits_md(), encoding="utf-8")
        print(f"wrote {args.credits}")

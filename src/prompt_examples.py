def get_layer1_examples(domain: str):
    ex_json = {
        "taxonomy": {
            "levels_definition": [
                {
                    "code": "S1",
                    "description": "最低级；若包含子级使用 S1-1、S1-2…，数字越大重要性越高",
                },
                {
                    "code": "S2",
                    "description": "泄露可能造成轻微危害的数据，如一般个人或组织信息",
                    "sublevels": [
                        {
                            "code": "S2-1",
                            "description": "轻微敏感，泄露影响极小，如弱识别性个人信息",
                        },
                        {
                            "code": "S2-2",
                            "description": "中等敏感，泄露可能造成一定不便，如常规联系信息",
                        },
                        {
                            "code": "S2-3",
                            "description": "较高敏感但仍属 S2 范畴，如与业务活动有关的低风险标识",
                        },
                    ],
                },
                {
                    "code": "S3",
                    "description": "高敏；若包含子级使用 S3-1、S3-2…，数字越大重要性越高",
                },
                {
                    "code": "S4",
                    "description": "极高敏；若包含子级使用 S4-1、S4-2…，数字越大重要性越高",
                },
            ],
            "tree": [
                {
                    "level": 1,
                    "name": "基础设施",
                    "children": [
                        {
                            "level": 2,
                            "name": "公路交通基础设施",
                            "children": [
                                {
                                    "level": 3,
                                    "name": "公路",
                                    "children": [
                                        {
                                            "level": 4,
                                            "name": "路线",
                                            "children": [
                                                {
                                                    "level": 5,
                                                    "name": "基本信息",
                                                    "items": [
                                                        "路线编号",
                                                        "路线名称",
                                                        "起点名称",
                                                        "止点名称",
                                                        "起点桩号",
                                                        "止点桩号",
                                                        "起点行政区划代码",
                                                        "止点行政区划代码",
                                                        "路线经过行政区划",
                                                        "路线里程"
                                                    ]
                                                },
                                                {
                                                    "level": 5,
                                                    "name": "阻断信息",
                                                    "items": [
                                                        "受阻路段位置描述",
                                                        "阻断位置所属行政区划代码",
                                                        "现场描述",
                                                        "事件起始桩号",
                                                        "事件终止桩号",
                                                        "阻断发现时间",
                                                        "预计恢复时间",
                                                        "实际恢复时间",
                                                        "阻断原因",
                                                        "阻断类型",
                                                        "道路是否中断",
                                                        "上行或下行属性",
                                                        "桥梁代码",
                                                        "隧道代码",
                                                        "阻断影响里程",
                                                        "相邻省行政区划代码",
                                                        "处置措施名称",
                                                        "上报单位名称",
                                                        "联系电话",
                                                        "单位传真号码"
                                                    ]
                                                }
                                            ]
                                        },
                                        {
                                            "level": 4,
                                            "name": "路段",
                                            "children": [
                                                {
                                                    "level": 5,
                                                    "name": "基本信息",
                                                    "items": [
                                                        "路段编号",
                                                        "所属路线编号",
                                                        "所属路线名称",
                                                        "所属行政区划代码",
                                                        "起点名称",
                                                        "止点名称",
                                                        "起点桩号",
                                                        "止点桩号",
                                                        "里程",
                                                        "技术等级",
                                                        "是否城管路段",
                                                        "是否待贯通",
                                                        "桥梁名称",
                                                        "桥梁代码"
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "level": 3,
                                    "name": "桥梁",
                                    "children": [
                                        {
                                            "level": 4,
                                            "name": "基本信息"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ],
        },
        "glossary": [
            {
                "term": "路线编号",
                "definition": "公路路线的唯一标识编号",
                "synonyms": ["路线代码"],
            },
            {
                "term": "行政区划代码",
                "definition": "国家标准行政区划编码",
                "synonyms": ["区划代码"],
            },
            {
                "term": "桩号",
                "definition": "公路里程桩标识",
                "synonyms": ["里程桩"],
            }
        ],
    }
    return [
        {"role": "user", "content": "这是一个示例。请返回如下结构"},
        {"role": "assistant", "content": str(ex_json)},
    ]


def get_layer2_examples(domain: str):
    ex = {
        "domain": "finance",
        "source": "example.pdf",
        "extraction": [
            {
                "path": ["运营管理", "客户服务信息", "网络服务标识"],
                "citation": {"page": 12, "text": "网络服务标识包含IP、URL等"},
                "items": [
                    {
                        "name": "IP",
                        "level": "S2",
                        "conditions": ["客户网络标识"],
                        "exceptions": [],
                        "patterns": {
                            "keywords": ["IP", "互联网协议地址"],
                            "regex": ["\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b"],
                        },
                    },
                    {
                        "name": "URL",
                        "level": "S1-1",
                        "conditions": ["公开网页地址"],
                        "exceptions": [],
                        "patterns": {
                            "keywords": ["URL", "网址", "链接"],
                            "regex": ["https?://[^\\s]+"],
                        },
                    },
                ],
            },
            {
                "path": ["经营管理", "综合管理", "员工信息", "员工信息(非公开)"],
                "citation": {
                    "page": 8,
                    "text": "员工信息(非公开)包括电子邮箱、手机号等",
                },
                "items": [
                    {
                        "name": "电子邮箱(员工)",
                        "level": "S3",
                        "conditions": ["员工联系信息"],
                        "exceptions": [],
                        "patterns": {
                            "keywords": ["邮箱", "电子邮件"],
                            "regex": [
                                "(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"
                            ],
                        },
                    },
                    {
                        "name": "手机号(员工)",
                        "level": "S3",
                        "conditions": ["员工联系信息"],
                        "exceptions": [],
                        "patterns": {
                            "keywords": ["手机号", "联系电话"],
                            "regex": ["\\b1[3-9]\\d{9}\\b"],
                        },
                    },
                ],
            },
            {
                "path": ["客户", "个人", "基础身份信息", "身份标识"],
                "citation": {"page": 20, "text": "身份标识包括身份证号等"},
                "items": [
                    {
                        "name": "身份证号",
                        "level": "S3",
                        "conditions": ["个人唯一身份标识"],
                        "exceptions": [],
                        "patterns": {
                            "keywords": ["身份证", "身份证号"],
                            "regex": ["\\b[0-9]{17}[0-9Xx]\\b"],
                        },
                    }
                ],
            },
            {
                "path": ["客户", "个人", "基础身份信息"],
                "citation": {"page": 20, "text": "联系方式包括手机号等"},
                "items": [
                    {
                        "name": "手机号",
                        "level": "S2",
                        "conditions": ["个人联系方式"],
                        "exceptions": [],
                        "patterns": {
                            "keywords": ["手机号", "电话"],
                            "regex": ["\\b1[3-9]\\d{9}\\b"],
                        },
                    }
                ],
            },
            {
                "path": ["单位", "单位基本信息", "基本信息", "基本信息", "编码"],
                "citation": {"page": 5, "text": "单位基本信息包括统一社会信用代码"},
                "items": [
                    {
                        "name": "统一社会信用代码",
                        "level": "S1",
                        "conditions": ["公开可查询的单位标识"],
                        "exceptions": [],
                        "patterns": {
                            "keywords": ["统一社会信用代码", "信用代码"],
                            "regex": ["\\b[0-9A-Z]{18}\\b"],
                        },
                    }
                ],
            },
        ],
    }
    return [
        {"role": "user", "content": "示例：按可变层级路径返回最小数据项（路径为数组，允许3–5层，按实际停止）"},
        {"role": "assistant", "content": str(ex)},
    ]

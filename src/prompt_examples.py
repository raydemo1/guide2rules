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
                    "level1": "经营管理",
                    "children": [
                        {
                            "level2": "综合管理",
                            "children": [
                                {
                                    "level3": "员工信息",
                                    "children": [
                                        {"level4": "一般员工信息(公开)"},
                                        {"level4": "员工信息(非公开)"},
                                    ],
                                }
                            ],
                        }
                    ],
                },
                {
                    "level1": "运营管理",
                    "children": [
                        {
                            "level2": "客户服务信息",
                            "children": [
                                {
                                    "level3": "网络服务标识",
                                    "children": [{"level4": "IP"}],
                                }
                            ],
                        }
                    ],
                },
                {
                    "level1": "单位",
                    "children": [
                        {
                            "level2": "单位基本信息",
                            "children": [
                                {
                                    "level3": "基本信息",
                                    "children": [{"level4": "统一社会信用代码"}],
                                }
                            ],
                        }
                    ],
                },
            ],
        },
        "glossary": [
            {
                "term": "手机号",
                "definition": "移动电话号码",
                "synonyms": ["手机号码", "电话号"],
            },
            {
                "term": "身份证号",
                "definition": "居民身份证号码",
                "synonyms": ["身份证"],
            },
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
                "path": {
                    "level1": "运营管理",
                    "level2": "客户服务信息",
                    "level3": "网络服务标识",
                    "level4": "网络服务标识",
                },
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
                "path": {
                    "level1": "经营管理",
                    "level2": "综合管理",
                    "level3": "员工信息",
                    "level4": "员工信息(非公开)",
                },
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
                "path": {
                    "level1": "客户",
                    "level2": "个人",
                    "level3": "基础身份信息",
                    "level4": "身份标识",
                },
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
                "path": {
                    "level1": "客户",
                    "level2": "个人",
                    "level3": "基础身份信息",
                    "level4": "联系方式",
                },
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
                "path": {
                    "level1": "单位",
                    "level2": "单位基本信息",
                    "level3": "基本信息",
                    "level4": "基本信息",
                },
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
        {"role": "user", "content": "示例：按四级路径返回最小数据项"},
        {"role": "assistant", "content": str(ex)},
    ]

def get_layer1_examples(domain: str):
    ex_json = {
        "taxonomy": {
            "levels_definition": [
                {"code": "S1", "description": "最低级；示例：基础个人信息"},
                {"code": "S2", "description": "中等敏感；示例：个人倾向/政治面貌"},
                {"code": "S3", "description": "高敏；示例：资产/信贷记录"},
            ],
            "tree": [
                {
                    "level": 1,
                    "name": "个人信息",
                    "children": [
                        {
                            "level": 2,
                            "name": "个人基本资料",
                            "children": [
                                {
                                    "level": 3,
                                    "name": "个人基本情况信息",
                                    "items": [
                                        "婚姻状况",
                                        "性取向",
                                        "宗教信仰",
                                        "姓名（简体中文）",
                                        "姓名（繁体中文）",
                                        "姓名（英文）",
                                        "姓名（拼音）",
                                        "性别",
                                        "年龄",
                                        "出生日期/生日",
                                        "生肖",
                                        "星座",
                                        "国籍",
                                        "民族"
                                    ]
                                }
                            ]
                        },
                        {
                            "level": 2,
                            "name": "联系方式",
                            "children": [
                                {
                                    "level": 3,
                                    "name": "联系方式(个人)",
                                    "items": ["手机号", "邮箱", "住址"]
                                }
                            ]
                        },
                        {
                            "level": 2,
                            "name": "个人党政信息",
                            "items": ["党派所属"]
                        }
                    ]
                },
                {
                    "level": 1,
                    "name": "个人财产信息",
                    "children": [
                        {
                            "level": 2,
                            "name": "账户与资金信息",
                            "items": ["账户号", "账户余额", "交易流水记录"]
                        },
                        {
                            "level": 2,
                            "name": "个人信贷信息",
                            "items": ["个人还款信息"]
                        }
                    ]
                }
            ],
        },
    }
    ex_car = {
        "template_hint": {
            "add_level1": ["车联网业务数据"],
            "level2_under_car": [
                "环境感知类数据",
                "车辆工况类数据",
                "车控类数据",
                "基础属性类数据",
                "其他车联网数据",
                "应用服务类数据",
            ],
        },
        "taxonomy": {
            "levels_definition": [],
            "tree": [
                {
                    "level": 1,
                    "name": "车联网业务数据",
                    "children": [
                        {"level": 2, "name": "基础属性类数据", "items": ["VIN", "车型代码"]},
                        {"level": 2, "name": "车辆工况类数据", "items": ["车速", "转速", "电池SOC"]},
                        {"level": 2, "name": "环境感知类数据", "items": ["温度", "湿度", "气压"]},
                        {"level": 2, "name": "车控类数据", "items": ["控制指令ID", "执行结果码"]},
                        {"level": 2, "name": "应用服务类数据"},
                        {"level": 2, "name": "其他车联网数据"}
                    ]
                }
            ]
        },
        "audits": [
            {"path": ["车联网业务数据"], "action": "added", "reason": "domain_extension_hints"}
        ],
    }
    return [
        {"role": "user", "content": "这是一个示例。请返回如下结构"},
        {"role": "assistant", "content": str(ex_json)},
        {"role": "user", "content": "示例：在模板上进行车联网扩展"},
        {"role": "assistant", "content": str(ex_car)},
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
                            "keywords_cn": ["IP", "互联网协议地址"],
                            "keywords_en": ["ip"],
                            "regex": ["\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b"],
                        },
                    },
                    {
                        "name": "URL",
                        "level": "S1-1",
                        "conditions": ["公开网页地址"],
                        "exceptions": [],
                        "patterns": {
                            "keywords_cn": ["URL", "网址", "链接"],
                            "keywords_en": ["url", "link"],
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
                            "keywords_cn": ["邮箱", "电子邮件"],
                            "keywords_en": ["email", "mail"],
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
                            "keywords_cn": ["手机号", "电话", "联系电话"],
                            "keywords_en": ["phone", "tel", "mobile", "number"],
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
                            "keywords_cn": ["身份证", "身份证号"],
                            "keywords_en": ["id", "id_number"],
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
                            "keywords_cn": ["手机号", "电话"],
                            "keywords_en": ["phone", "tel", "mobile", "number"],
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
                            "keywords_cn": ["统一社会信用代码", "信用代码"],
                            "keywords_en": ["credit_code"],
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

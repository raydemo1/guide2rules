import re
from pathlib import Path

def read_df(path):
    import pandas as pd
    for hdr in (1, 0):
        try:
            df = pd.read_excel(path, header=hdr)
        except Exception:
            df = pd.read_excel(path, engine="openpyxl", header=hdr)
        cols = set(df.columns.astype(str))
        if {"字段名","字段类型","字段注释"}.issubset(cols):
            return df
    return df

def normalize(s):
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None

def detect_labels(name, comment, sample):
    name_l = (name or "").lower()
    comment_l = (comment or "").lower()
    sample_s = sample or ""
    sample_l = sample_s.lower()
    if any(k in comment_l + name_l for k in ["手机号","手机","mobile","phone"]):
        return ("个人信息","个人联系信息","手机号码","手机号(中国内地)")
    if any(k in comment_l + name_l for k in ["邮箱","email","mail"]):
        return ("个人信息","个人联系信息","邮箱","邮箱地址(中国内地)")
    if any(k in comment_l + name_l for k in ["身份证","id_card","identity"]):
        return ("个人信息","个人身份鉴别信息","身份证件信息","身份证号(中国内地)")
    if any(k in comment_l + name_l for k in ["订单编号","order_no","order"]):
        return ("个人信息","个人财产信息","个人交易信息","订单编号")
    if any(k in comment_l + name_l for k in ["qq","wechat","weixin","社交"]):
        return ("个人信息","个人联系信息","社交软件账号","qq")
    rx_cn_phone = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
    rx_email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    rx_id = re.compile(r"\b\d{17}[\dXx]\b")
    rx_order = re.compile(r"\border\d+\b")
    if rx_cn_phone.search(sample_l):
        return ("个人信息","个人联系信息","手机号码","手机号(中国内地)")
    if rx_email.search(sample_l):
        return ("个人信息","个人联系信息","邮箱","邮箱地址(中国内地)")
    if rx_id.search(sample_l):
        return ("个人信息","个人身份鉴别信息","身份证件信息","身份证号(中国内地)")
    if rx_order.search(sample_l):
        return ("个人信息","个人财产信息","个人交易信息","订单编号")
    return (None, None, None, None)

def evaluate_and_report(df, write_back_path=None, report_path=None):
    import pandas as pd
    preds_l1 = []
    preds_l2 = []
    preds_l3 = []
    preds_marker = []
    match_result = []
    for _, r in df.iterrows():
        l1,l2,l3,marker = detect_labels(normalize(r.get("字段名")), normalize(r.get("字段注释")), normalize(r.get("字段样本")))
        preds_l1.append(l1)
        preds_l2.append(l2)
        preds_l3.append(l3)
        preds_marker.append(marker)
        truth_m = normalize(r.get("数据标识"))
        pred_m = normalize(marker)
        match_result.append(1 if (truth_m is not None and pred_m is not None and truth_m == pred_m) else 0)
    df_pred = df.copy()
    df_pred["LLM数据标识"] = preds_marker
    df_pred["LLM匹配结果(1=成功,0=失败)"] = match_result

    truth_l1 = df_pred["1级分类"].apply(normalize)
    truth_l2 = df_pred["2级分类"].apply(normalize)
    truth_l3 = df_pred["3级分类"].apply(normalize)
    truth_marker = df_pred["数据标识"].apply(normalize)

    def acc_series(truth, pred):
        mask = truth.notna() & pd.Series(pred).notna()
        if mask.sum() == 0:
            return 0.0, 0, 0
        correct = (truth[mask].values == pd.Series(pred)[mask].values).sum()
        return correct / mask.sum(), int(correct), int(mask.sum())

    acc1, c1, n1 = acc_series(truth_l1, preds_l1)
    acc2, c2, n2 = acc_series(truth_l2, preds_l2)
    acc3, c3, n3 = acc_series(truth_l3, preds_l3)
    accm, cm, nm = acc_series(truth_marker, preds_marker)

    conf = pd.crosstab(truth_marker.fillna("<NA>"), pd.Series(preds_marker, name="LLM数据标识").fillna("<NA>"))

    by_conf = []
    for lvl in ["high","medium","low"]:
        sub = df_pred[df_pred["置信度"].astype(str).str.lower() == lvl]
        t = sub["数据标识"].apply(normalize)
        p = sub["LLM数据标识"].apply(normalize)
        mask = t.notna() & p.notna()
        total = int(mask.sum())
        correct = int((t[mask].values == p[mask].values).sum())
        by_conf.append({"置信度": lvl, "样本数": total, "准确数": correct, "准确率": (correct/total if total else 0.0)})
    by_conf_df = pd.DataFrame(by_conf)

    metrics = pd.DataFrame([
        {"指标": "LLM可识别样本数", "值": int(pd.Series(preds_marker).notna().sum())},
        {"指标": "1级分类准确率", "值": acc1, "正确数": c1, "对齐样本数": n1},
        {"指标": "2级分类准确率", "值": acc2, "正确数": c2, "对齐样本数": n2},
        {"指标": "3级分类准确率", "值": acc3, "正确数": c3, "对齐样本数": n3},
        {"指标": "数据标识准确率", "值": accm, "正确数": cm, "对齐样本数": nm},
    ])

    if write_back_path:
        try:
            with pd.ExcelWriter(write_back_path, engine="openpyxl") as w:
                df_pred.to_excel(w, index=False, sheet_name="Sheet1")
        except Exception:
            alt = str(Path(write_back_path).with_suffix(".with_llm.xlsx"))
            with pd.ExcelWriter(alt, engine="openpyxl") as w:
                df_pred.to_excel(w, index=False, sheet_name="Sheet1")
            write_back_path = alt
    if report_path:
        with pd.ExcelWriter(report_path, engine="openpyxl") as w:
            metrics.to_excel(w, index=False, sheet_name="总体指标")
            conf.to_excel(w, sheet_name="数据标识混淆矩阵")
            by_conf_df.to_excel(w, index=False, sheet_name="按置信度准确率")

    print("llm_labeled_total:", int(pd.Series(preds_marker).notna().sum()))
    print("acc_l1:", f"{acc1:.4f}")
    print("acc_l2:", f"{acc2:.4f}")
    print("acc_l3:", f"{acc3:.4f}")
    print("acc_marker:", f"{accm:.4f}")
    if write_back_path:
        print("xlsx_written:", write_back_path)
    if report_path:
        print("report_written:", report_path)

if __name__ == "__main__":
    src = Path("outputs/general/数据共享交换平台_测试环境_表结构测试数据_200 条(1).classified.xlsx")
    df = read_df(str(src))
    out_xlsx = str(src)
    report_xlsx = str(Path("outputs/general/eval_report.xlsx"))
    evaluate_and_report(df, write_back_path=out_xlsx, report_path=report_xlsx)

import sys
from pathlib import Path
import json

def read_df(xlsx_path):
    import pandas as pd
    try:
        return pd.read_excel(xlsx_path, header=1)
    except Exception:
        return pd.read_excel(xlsx_path, engine="openpyxl", header=1)

def detect_columns(columns):
    truth_keys = ["truth","gold","label_true","expected","人工","标注","gt","真实"]
    pred_keys = ["pred","class","label","规则","结果","分类","prediction","预测","final"]
    truth = [c for c in columns if any(k in c.lower() for k in truth_keys)]
    pred = [c for c in columns if any(k in c.lower() for k in pred_keys)]
    return truth, pred

def summarize(df):
    print("shape:", df.shape)
    print("columns:")
    for i, c in enumerate(df.columns):
        print(f"  {i}. {c}")
    print("dtypes:")
    print(df.dtypes.astype(str).to_string())
    print("head:")
    print(df.head(5).to_string(index=False))

def compute_accuracy(df, truth_col, pred_col):
    s1 = df[truth_col].astype(str).str.strip()
    s2 = df[pred_col].astype(str).str.strip()
    valid = (~s1.isna()) & (~s2.isna())
    total = int(valid.sum())
    correct = int((s1[valid] == s2[valid]).sum())
    acc = correct / total if total else 0.0
    print("accuracy_total:", total)
    print("accuracy_correct:", correct)
    print("accuracy:", f"{acc:.4f}")

def emit_rows_for_llm(df, text_cols, label_cols):
    rows = []
    for _, r in df.iterrows():
        item = {"text": {c: ("" if pd.isna(r[c]) else str(r[c])) for c in text_cols}}
        for c in label_cols:
            v = r[c]
            item[c] = None if pd.isna(v) else str(v)
        rows.append(item)
    print("llm_rows_json:")
    print(json.dumps(rows, ensure_ascii=False))

def export_llm_json(df, out_path):
    import pandas as pd
    cols = df.columns
    pick_text = []
    for c in cols:
        cl = c.lower()
        if any(k in cl for k in ["字段名","字段注释","字段样本","字段","注释","样本","表名","字段类型"]):
            pick_text.append(c)
    pick_labels = []
    for c in cols:
        cl = c.lower()
        if any(k in cl for k in ["1级分类","2级分类","3级分类","数据标识","分级","规则id","置信度","分类","结果"]):
            pick_labels.append(c)
    rows = []
    for _, r in df.iterrows():
        item = {"text": {c: (None if pd.isna(r[c]) else str(r[c])) for c in pick_text},
                "labels": {c: (None if pd.isna(r[c]) else str(r[c])) for c in pick_labels}}
        rows.append(item)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("exported:", out_path)

if __name__ == "__main__":
    args = sys.argv[1:]
    schema_only = False
    p = None
    for a in args:
        if a == "--schema-only":
            schema_only = True
        elif not a.startswith("--"):
            p = Path(a)
    if p is None:
        p = Path("outputs/general/数据共享交换平台_测试环境_表结构测试数据_200 条(1).classified.xlsx")
    if not p.exists():
        print("file_not_found:", str(p))
        sys.exit(1)
    df = read_df(str(p))
    summarize(df)
    truth_cols, pred_cols = detect_columns([c.lower() for c in df.columns])
    print("truth_candidates:", truth_cols)
    print("pred_candidates:", pred_cols)
    chosen_truth = None
    chosen_pred = None
    for c in df.columns:
        cl = c.lower()
        if chosen_truth is None and cl in truth_cols:
            chosen_truth = c
        if chosen_pred is None and cl in pred_cols:
            chosen_pred = c
    if chosen_truth and chosen_pred:
        compute_accuracy(df, chosen_truth, chosen_pred)
    if not schema_only:
        text_cols = []
        for c in df.columns:
            cl = c.lower()
            if any(k in cl for k in ["name","字段","描述","说明","comment","text","内容","实例","示例","值","type","类型","表"]):
                text_cols.append(c)
        label_cols = []
        for c in df.columns:
            cl = c.lower()
            if any(k in cl for k in ["label","分类","类别","类目","规则","结果","人工","标注"]):
                label_cols.append(c)
        try:
            import pandas as pd
            emit_rows_for_llm(df, text_cols[:5], label_cols[:2])
        except Exception:
            pass
    for a in args:
        if a.startswith("--export-llm-json="):
            out = a.split("=", 1)[1]
            export_llm_json(df, out)

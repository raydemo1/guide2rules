import os
import openpyxl

def main():
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "test", "data", "transportation", "sample.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["字段注释", "分类路径", "字段样本"]) 
    ws.append(["身份证号码", "", ""]) 
    ws.append(["驾驶证编号", "", ""]) 
    wb.save(path)
    print(path)

if __name__ == "__main__":
    main()

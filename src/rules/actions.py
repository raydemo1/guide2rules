from business_rules.actions import BaseActions, rule_action
from business_rules.fields import FIELD_TEXT


class ClassificationActions(BaseActions):
    def __init__(self, obj):
        self.obj = obj

    @rule_action(params={"level": FIELD_TEXT, "rule_id": FIELD_TEXT})
    def set_classification(self, level, rule_id):
        def rank(lv: str) -> int:
            s = (lv or "").strip().lower()
            if s.startswith("s1"):
                return 4
            if s.startswith("s2"):
                return 3
            if s.startswith("s3"):
                return 2
            if s.startswith("s4"):
                return 1
            return 0
        cur = self.obj.get("result_level") or ""
        if rank(level) >= rank(cur):
            self.obj["result_level"] = level
            self.obj["result_rule_id"] = rule_id

    @rule_action(params={"citation": FIELD_TEXT, "source": FIELD_TEXT})
    def append_audit(self, citation, source):
        audits = self.obj.get("audits") or []
        audits.append({"citation": citation, "source": source})
        self.obj["audits"] = audits

    @rule_action(params={"category": FIELD_TEXT})
    def set_suggested_category(self, category):
        self.obj["category_path"] = category

    @rule_action(params={"rule_id": FIELD_TEXT})
    def set_category_rule_id(self, rule_id):
        self.obj["result_rule_id"] = rule_id

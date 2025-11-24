from business_rules.actions import BaseActions, rule_action
from business_rules.fields import FIELD_TEXT


class ClassificationActions(BaseActions):
    def __init__(self, obj):
        self.obj = obj

    @rule_action(params={"level": FIELD_TEXT, "rule_id": FIELD_TEXT})
    def set_classification(self, level, rule_id):
        self.obj["result_level"] = level
        self.obj["result_rule_id"] = rule_id

    @rule_action(params={"citation": FIELD_TEXT, "source": FIELD_TEXT})
    def append_audit(self, citation, source):
        audits = self.obj.get("audits") or []
        audits.append({"citation": citation, "source": source})
        self.obj["audits"] = audits


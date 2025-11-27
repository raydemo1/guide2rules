from business_rules.variables import BaseVariables, string_rule_variable, numeric_rule_variable


class ClassificationVariables(BaseVariables):
    def __init__(self, obj):
        self.obj = obj

    @string_rule_variable()
    def field_name(self):
        return str(self.obj.get("field_name", ""))

    @string_rule_variable()
    def category_path(self):
        return str(self.obj.get("category_path", ""))

    @string_rule_variable()
    def value_text(self):
        return str(self.obj.get("value_text", ""))

    @string_rule_variable()
    def field_comment(self):
        return str(self.obj.get("field_comment", ""))

    @string_rule_variable()
    def table_name(self):
        return str(self.obj.get("table_name", ""))

    @string_rule_variable()
    def field_tokens(self):
        return str(self.obj.get("field_tokens", ""))

    @string_rule_variable()
    def table_tokens(self):
        return str(self.obj.get("table_tokens", ""))

    @numeric_rule_variable()
    def score(self):
        try:
            return float(self.obj.get("score", 0) or 0)
        except Exception:
            return 0.0

    @string_rule_variable()
    def hit_tags(self):
        hits = self.obj.get("hits") or []
        try:
            return " ".join([str(h) for h in hits if h])
        except Exception:
            return ""

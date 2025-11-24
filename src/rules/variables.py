from business_rules.variables import BaseVariables, string_rule_variable


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


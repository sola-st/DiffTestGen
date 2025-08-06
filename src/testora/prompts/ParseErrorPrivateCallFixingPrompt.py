class ParseErrorPrivateCallFixingPrompt:
    def __init__(self, code, error_messages):
        self.code = code
        self.error_messages = error_messages
        self.use_json_output = False

    def create_prompt(self):
        # TODO invalid cases occur. May need to provide more info.
        template = """
The following shows the Python code along with its static analysis results. Refine the code to ensure that:
It is parsable, and
It uses only the public API (i.e., avoid accessing or calling any functions or attributes that start with an underscore _).

```python
{test_code}
```

Runtime errors:

{error_messages}

Respond only with Python code wrapped into ```python ... ```. Make sure to preserve the given 'Round <number> Example <number> (<label>)' part if exists. Give no explanations.
"""


        return template.format(test_code=self.code, error_messages=self.error_messages)

    def parse_answer(self, raw_answer):
        code = ""
        in_code = False
        for line in raw_answer.split("\n"):
            if line.strip() == "```":
                break
            if in_code:
                code += line + "\n"
            if line == "```python" or line.startswith("import"):
                in_code = True
        return code

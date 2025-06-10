'''
Use the error messages as feedback.
Mainly with 2 ways to show the errors:
 * Traceback (most recent call last): .... \n<Error Type> ...  
 * try ... except ... <Error Type>, may with customized print line.

The two error report ways share the common valid error types:
 Exceptions --> The last line of the error message indicates what happened.
 * Built-in exceptions: https://docs.python.org/3/library/exceptions.html#bltin-exceptions

Questions:
 * Is the error message itself sufficient for fixing the error?
'''
# TODO answer the questions.

class RuntimeErrorsFixingPrompt:
    def __init__(self, code, error_messages):
        self.code = code
        self.error_messages = error_messages
        self.use_json_output = False

    def create_prompt(self):
        template = """
The following lists the Python code and its runtime errors, fix the errors.

```python
{test_code}
```

Runtime errors:

{error_messages}

Respond only with Python code wrapped into ```python ... ```. Give no explanations.
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
            if line == "```python" or line.startswith("import"): # is the 2nd condition necessary?
                in_code = True
        return code

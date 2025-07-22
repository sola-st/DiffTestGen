'''
Use the error messages as feedback.
Mainly with 2 ways to show the errors:
 *[Error message in console] 
    Traceback (most recent call last): .... \n<Error Type> ...  
 *[Error message in prints] 
    try ... except ... <Error Type>, may with customized print line.

The two error report ways share the common valid error types:
 Exceptions --> The last line of the error message indicates what happened.
 * Built-in exceptions: https://docs.python.org/3/library/exceptions.html#bltin-exceptions
'''

import re


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


def check_whether_error_exist(test_code, execution_output):
    error_exist = False
    # if error exists, extract the error message
    if "Traceback (most recent call last)" in execution_output:
        # output_lines = execution_output.splitlines()
        error_exist = True
    else:
        # errors may catched by excpets
        test_code_lines = test_code.splitlines()

        try_exist = False
        except_exist = False
        for line in test_code_lines:
            line = line.strip()
            if line.startswith("try:"):
                try_exist = True
            elif line.startswith("except"):
                assert try_exist == True
                except_exist = True
            elif except_exist == True and line.startswith("print"):
                # match the info in print line and execution_output
                # an example: print("Caught an error:", e)
                msg_prefix = line.split('",')[0].replace('print("', '')
                if msg_prefix in execution_output:
                    error_exist = True
                    break

    return error_exist

def extract_error_type_2_kinds(test_code, execution_output):
    # focus on both traceback and try-catched errors.
    error_type = None

    # if error exists, extract the error message
    if "Traceback (most recent call last)" in execution_output:
        output_lines:list = execution_output.splitlines()
        output_lines.reverse()
        for line in output_lines:
            error_type = re.findall(r'^(\S*Error)\b', line)
            if error_type:
                break
    else:
        # errors may catched by excpets
        test_code_lines = test_code.splitlines()

        try_exist = False
        except_exist = False
        except_line = ""
        for line in test_code_lines:
            line = line.strip()
            if line.startswith("try:"):
                try_exist = True
            elif line.startswith("except"):
                assert try_exist == True
                except_exist = True
                except_line = line
            elif except_exist == True and line.startswith("print"):
                # match the info in print line and execution_output
                # an example: print("Caught an error:", e)
                msg_prefix = line.split('",')[0].replace('print("', '')
                if msg_prefix in execution_output:
                    error_type = re.findall(r'\b\S*Error\b', except_line)
                    break

    return error_type

def extract_error_type(execution_output):
    # only focus on tracback reported errors.
    error_type = None

    # if error exists, extract the error message
    if "Traceback (most recent call last)" in execution_output:
        output_lines:list = execution_output.splitlines()
        output_lines.reverse()
        for line in output_lines:
            error_type = re.findall(r'^(\S*Error)\b', line)
            if error_type:
                break

    return error_type
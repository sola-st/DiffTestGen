class TestPythonBlockSeparatorPrompt:
    def __init__(self, combined_single_test):
        self.combined_single_test = combined_single_test
        self.use_json_output = False

    def create_prompt(self):
        template = """
This Python code combines several code usage examples together, seprate them.

{combined_single_test}

Pay attention to any reference lines, and make sure each example includes the ones it depends on.
Your task is to wrap each individual, separated example in its own separate Python code block using the following output format:

```python
# Example 1:
...
```
```python
# Example 2:
...
```
etc.

Respond only with the Python code blocks. Give no explanations.
"""

        return template.format(combined_single_test=self.combined_single_test)
    
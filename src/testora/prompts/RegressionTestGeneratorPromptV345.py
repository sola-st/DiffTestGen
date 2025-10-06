class RegressionTestGeneratorPromptV345:
    def __init__(self, project_name, fut_qualified_names, diff, old_context, new_context, old_tests=None, new_tests=None, call_graph_info=""):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        # 'X_context' and 'X_tests" r are "\n" separated strs

        # the following only provide the info when it is available
        self.changed_function_block = ""
        if fut_qualified_names:
            fut_qualified_names_str = ", ".join(fut_qualified_names)
            self.changed_function_block = (
                f"The diff affects the following functions: {fut_qualified_names_str}.\n"
                f"The following are the old and the new versions of these affected functions:\n"
                f"Old version:\n\n{old_context}\n\nNew version:\n\n{new_context}\n"
            )

        self.call_graph_block = ""
        if call_graph_info:
            self.call_graph_block = f"The following provides call graph information for the affected functions. This information can serve as a reference for understanding how to access or invoke the functions:\n{call_graph_info}"

        self.test_function_block = ""
        if old_tests or new_tests:
            self.test_function_block = (
                f"The diff includes some changed test functions, which may highly related to how the affected functions are accessed and tested."
                f"The following are the old and the new versions of these test functions:\n"
                f"Old version:\n\n{old_tests}\n\nNew version:\n\n{new_tests}\n"
            )

        self.use_json_output = False

    def create_prompt(self):
        template = """
Your task is to generate usage examples of the {project_name} project that expose behavioral differences introduced by the following diff:

{diff}

{changed_function_block}
{call_graph_block}
{test_function_block}
The usage examples you create should use only the public API of the {project_name} project. You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. Create usage examples that are diverse and cover a wide range of scenarios, e.g., by (not) passing optional parameters or using different APIs to achieve the same purpose.

Answer by giving two usage examples that cover normal usage scenarios and two usage examples that focus on corner cases (e.g., unusual values, such as None, NaN or empty lists).
Each example must be an executable piece of Python code, including all necessary imports.
Print all relevant values, including intermediate values, in a human-readable form.

If multiples examples are generated, do not combine them as a single Python code block. Instead, wrap each individual example in its own separate Python code block using the following output format:
```python
# Example 1:
...
```
```python
# Example 2:
...
```
etc.
"""

        return template.format(project_name=self.project_name,
                               diff=self.diff,
                               changed_function_block = self.changed_function_block,
                               call_graph_block = self.call_graph_block,
                               test_function_block = self.test_function_block)

    def remove_unnecessary_indentation(self, code):
        lines = code.split("\n")
        if len(lines) > 0:
            # find number of leading spaces in first line
            num_spaces = len(lines[0]) - len(lines[0].lstrip())
            if num_spaces > 0:
                return "\n".join([line[num_spaces:] for line in lines])
        return code

    def parse_answer(self, raw_answer):
        assert type(raw_answer) == list

        tests = []

        for answer in raw_answer:
            in_code = False
            next_test = ""
            for line in answer.split("\n"):
                if line.strip() == "```":
                    in_code = False
                    if next_test:
                        next_test = self.remove_unnecessary_indentation(next_test)
                        tests.append(next_test)
                        next_test = ""
                if in_code:
                    next_test += line + "\n"
                if line.strip() == "```python":
                    in_code = True

        return tests

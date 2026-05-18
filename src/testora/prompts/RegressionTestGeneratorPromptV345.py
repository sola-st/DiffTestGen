from testora import Config
from testora.util.Logs import Event, append_event


class RegressionTestGeneratorPromptV345:
    def __init__(self, project_name, fut_qualified_names, diff, old_context, new_context, old_tests=None, new_tests=None, call_graph_info=""):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        # 'X_context' and 'X_tests" r are "\n" separated strs

        # the following only provide the info when it is available
        self.changed_function_block = ""
        if Config.changed_function_body == True:
            if old_context or new_context: # at least one of the versions has the function body
                if old_context:
                    old_context = f"\n\n{old_context}"
                else:
                    old_context = "<The functions do not exist in the old code version.>"

                if new_context:
                    new_context = f"\n\n{new_context}"
                else:
                    new_context = "<The functions do not exist in the new code version.>"

                self.changed_function_block = (
                    f"The following are the old and the new versions of these affected functions:\n"
                    f"Old version: {old_context}\nNew version: {new_context}\n"
                )

        self.call_graph_block = ""
        if call_graph_info:
            self.call_graph_block = f"The following provides reference information on how to access or invoke the affected functions:\n{call_graph_info}"

        self.test_function_block = ""
        if Config.use_existing_tests == "pr-modified":
            if old_tests or new_tests:
                if old_tests:
                    old_tests = f"\n\n{old_tests}"
                else:
                    old_tests = "<The test functions do not exist in the old code version.>"

                if new_tests:
                    new_tests = f"\n\n{new_tests}"
                else:
                    new_tests = "<The test functions do not exist in the new code version.>"

                self.test_function_block = (
                    f"The diff includes some changed test functions, which may highly related to how the affected functions are accessed and tested."
                    f"The following are the old and the new versions of these test functions:\n"
                    f"Old version: {old_tests}\nNew version: {new_tests}\n"
                )

        self.use_json_output = False

    def create_prompt(self, default_len_limit=40000):
        template_prefix = """
Your task is to generate usage examples of the {project_name} project that expose behavioral differences introduced by the following diff:

{diff}
"""     
        template_postfix = """The usage examples you create should use only the public API of the {project_name} project. You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. Create usage examples that are diverse and cover a wide range of scenarios, e.g., by (not) passing optional parameters or using different APIs to achieve the same purpose.

Answer by giving ten usage examples that cover normal usage scenarios and ten usage examples that focus on corner cases (e.g., unusual values, such as None, NaN or empty lists).
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
        template_prefix_str = template_prefix.format(project_name=self.project_name, diff=self.diff)
        template_postfix_str = template_postfix.format(project_name=self.project_name)
        current_len = len(template_prefix_str) + len(template_postfix_str)

        # template part 1
        template_prompt = template_prefix_str
        if self.fut_qualified_names:
            fut_qualified_names_str = ", ".join(self.fut_qualified_names)
            affected_funcs = f"The diff affects the following functions: {fut_qualified_names_str}.\n"

            if (current_len + len(affected_funcs) <= default_len_limit):
                template_prompt += f"\n{affected_funcs}"
                current_len += len(affected_funcs)
            else:
                append_event(Event(pr_nb=0, message=f"Initial prompt fails to add info about changed function names. Current prompt length: {current_len}."))

        # template part 2
        # collect the available blocks until reaching len limit.
        if len(self.changed_function_block) > 0 and (current_len + len(self.changed_function_block) <= default_len_limit):
            template_prompt += f"\n{self.changed_function_block}"
            current_len += len(self.changed_function_block)
            append_event(Event(pr_nb=0, message=f"Initial prompt. Added info about changed function body. Current prompt length: {current_len}."))

        if len(self.call_graph_block) > 0:
            if current_len + len(self.call_graph_block) <= default_len_limit:
                template_prompt += f"\n{self.call_graph_block}"
                current_len += len(self.call_graph_block)
                append_event(Event(pr_nb=0, message=f"Initial prompt. Added info about call graph. Current prompt length: {current_len}."))

        if len(self.test_function_block) > 0 and (current_len + len(self.test_function_block) <= default_len_limit):
            template_prompt += f"\n{self.test_function_block}"
            current_len += len(self.test_function_block)
            append_event(Event(pr_nb=0, message=f"Initial prompt. Added info about test function body. Current prompt length: {current_len}."))

        # template part 3
        template_prompt += template_postfix_str

        return template_prompt

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

from testora.util.Logs import Event, append_event


class FeedbackTestGeneratorPromptV8:
    '''
    Given the covered lines and pre-round generated tests, let LLM generate some new tests that cover more changed lines.
    diff + test code + covered stmts (configuration 5_8_8).
    '''
    def __init__(self, project_name, fut_qualified_names, diff, all_covered_modified_stmts_info, old_tests=None, new_tests=None, selected_cg_info=""):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        # prompt 5-based: test code
        self.all_covered_modified_stmts_info = all_covered_modified_stmts_info 

        self.call_graph_block = ""
        if selected_cg_info:
            self.call_graph_block = f"The following provides reference information on how to access or invoke the uncovered affected functions:\n{selected_cg_info}"

        self.test_function_block = ""
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
Your task is to generate usage examples of the {project_name} project that expose behavioral differences introduced by the following diff, 
and achieve the highest possible coverage of the specified lines in both the old and new versions:

{diff}
""" 

        refer_test_block = """
The following is an existing usage example, provided to show how the affected functions or code under test can be accessed and used. 
Below the example are the old and the new versions of these affected functions. Some lines in these functions end with a comment: '# COVERED' indicates the line is covered by the existing example, '#TO_COVER' marks lines that should be covered by the newly generated usgae examples.
Since some # COVERED lines are near the # TO_COVER lines, you can use the existing example as a reference to understand how to invoke the relevant functionality. 
Write at least one new usage example to increase coverage of the # TO_COVER lines. If one example is not sufficient to cover all lines marked # TO_COVER, e.g., due to branching, add additional examples as needed.

{all_covered_modified_stmts_info}
"""

        template_postfix = """The usage examples you create should use only the public API of the {project_name} project. In other words, avoid accessing or calling any functions or attributes that start with an underscore (_) in the generated examples. You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. Create usage examples that are diverse and cover a wide range of scenarios, e.g., by (not) passing optional parameters or using different APIs to achieve the same purpose.
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
        refer_test_block_str = refer_test_block.format(all_covered_modified_stmts_info=self.all_covered_modified_stmts_info)
        template_postfix_str = template_postfix.format(project_name=self.project_name)
        current_len = len(template_prefix_str) + len(template_postfix_str) + len(refer_test_block_str)

        # template part 1
        template_prompt = template_prefix_str
        if self.fut_qualified_names:
            fut_qualified_names_str = ", ".join(self.fut_qualified_names)
            affected_funcs = f"The diff affects the following functions: {fut_qualified_names_str}.\n"

            if (current_len + len(affected_funcs) <= default_len_limit):
                template_prompt += f"\n{affected_funcs}"
                current_len += len(affected_funcs)
            else:
                append_event(Event(pr_nb=0, message=f"Feedback prompt fails to add info about changed function names. Current prompt length: {current_len}."))

        template_prompt += f"\n{refer_test_block_str}" # add to the prompt, no matter how long the prompt is at this point

        # template part 2
        # collect the available blocks until reaching len limit.
        if len(self.call_graph_block) > 0:
            if current_len + len(self.call_graph_block) <= default_len_limit:
                template_prompt += f"\n{self.call_graph_block}"
                current_len += len(self.call_graph_block)
                append_event(Event(pr_nb=0, message=f"Feedback prompt. Added info about selected call graph. Current prompt length: {current_len}."))

        if len(self.test_function_block) > 0 and (current_len + len(self.test_function_block) <= default_len_limit):
            template_prompt += f"\n{self.test_function_block}"
            current_len += len(self.test_function_block)
            append_event(Event(pr_nb=0, message=f"Feedback prompt. Added info about test function body. Current prompt length: {current_len}."))

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
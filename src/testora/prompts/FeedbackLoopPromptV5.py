class FeedbackTestGeneratorPromptV5:
    def __init__(self, project_name, fut_qualified_names, diff, all_uncovered_modified_stmts_info, old_context, new_context):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        self.expected_test_num = all_uncovered_modified_stmts_info # it is a int in this version, means the expected number of new tests
        self.old_context = old_context
        self.new_context = new_context
        self.use_json_output = False

    def create_prompt(self):
        template = """
Your task is to generate usage examples of the {project_name} project that expose behavioral differences introduced by the following diff, 
and achieve the highest possible coverage of the specified lines in both the old and new versions:

{diff}

The diff affects the following functions: {fut_qualified_names}. 
The following are the old versions of these affected functions. Comment lines containing # TO_COVER indicate that the next line of code is expected to be covered by the generated usage example(s), here expected to generate {expected_test_num} usage example(s).

Old version: 

{old_context}

New version:

{new_context}

The usage examples you create should use only the public API of the {project_name} project. In other words, avoid accessing or calling any functions or attributes that start with an underscore (_) in the generated examples. You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. Create usage examples that are diverse and cover a wide range of scenarios, e.g., by (not) passing optional parameters or using different APIs to achieve the same purpose.
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

        return template.format(diff=self.diff, project_name=self.project_name, 
                               fut_qualified_names=", ".join(self.fut_qualified_names),
                               expected_test_num=self.expected_test_num,
                               old_context = self.old_context,
                               new_context = self.new_context)

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
    
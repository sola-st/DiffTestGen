class FeedbackTestGeneratorPromptV8:
    '''
    Given the covered lines and pre-round generated tests, let LLM generate some new tests that cover more changed lines.
    diff + test code + covered stmts (configuration 1_8_8).
     * format of all_covered_modified_stmts_info: 
            Example # 1:
            {test_code}
            Corresponding covered lines:
            Old: {}
            New: {}
    '''
    def __init__(self, project_name, fut_qualified_names, diff, all_covered_modified_stmts_info, old_context, new_context):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        # test code and uncovered statements of both versions
        self.all_covered_modified_stmts_info = all_covered_modified_stmts_info 
        self.old_context = old_context
        self.new_context = new_context
        self.use_json_output = False

    def create_prompt(self):
        template = """
Your task is to generate usage examples of the {project_name} project that expose behavioral differences introduced by the following diff, 
and achieve the highest possible coverage of the specified lines in both the old and new versions:

{diff}

The diff affects the following functions: {fut_qualified_names}.

The following is an existing usage example, provided to show how the affected functions or code under test can be accessed and used. 
It also includes the lines of code covered in both the old and new versions, and the specified lines that are expected to covered.
Use the existing example as a reference for how to invoke the relevant functionality, write one or more (if necessary) new usage examples to increase coverage of the specified lines. 

{all_covered_modified_stmts_info}

The usage examples you create may use only the public API of the {project_name} project. You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. Create usage examples that are diverse and cover a wide range of scenarios, e.g., by (not) passing optional parameters or using different APIs to achieve the same purpose.
Each example must be an executable piece of Python code, including all necessary imports.
Print all relevant values, including intermediate values, in a human-readable form.

Wrap each individual example into Python code blocks by using the following output format:
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
                               all_covered_modified_stmts_info=self.all_covered_modified_stmts_info,
                               fut_qualified_names=", ".join(self.fut_qualified_names))

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
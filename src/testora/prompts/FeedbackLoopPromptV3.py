class FeedbackTestGeneratorPromptV3:
    '''
    Given the uncovered lines, let LLM generate some new tests that cover the lines.
    '''
    def __init__(self, project_name, fut_qualified_names, diff, all_uncovered_modified_lines_info:set,
                old_context:set, new_context:set):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        self.all_uncovered_modified_lines_info = all_uncovered_modified_lines_info # uncovered lines of both versions
        self.old_context = old_context
        self.new_context = new_context
        self.use_json_output = False

    def create_prompt(self):
        template = """
Your task is to generate usage examples of the {project_name} project that expose behavioral differences introduced by the following diff, 
and achieve the highest possible coverage of the specified lines in both the old and new versions:

{diff}

The diff affects the following functions: {fut_qualified_names}.

The following sets contains the old and new versions of the changed files, where each element consists of a file path and a list of its lines.

Old version: 

{old_context}

New version:

{new_context}

Each element of the following set starts with 'Specified lines that need to be covered' and follows the specified lines from both the old and new versions that need to be covered.
For each element, generate one corresponding usage example, i.e., here expected to generate {len} usage example(s).

{all_uncovered_modified_lines_info}

The usage examples you create may use only the public API of the {project_name} project. You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. Create usage examples that are diverse and cover a wide range of scenarios, e.g., by (not) passing optional parameters or using different APIs to achieve the same purpose.
Each example must be an executable piece of Python code, including all necessary imports.
Print all relevant values, including intermediate values, in a human-readable form.

Wrap each individual example into Python code blocks by using the following output format:
```python
# New Example 1:
...
```
```python
# New Example 2:
...
```
etc.
"""

        return template.format(diff=self.diff, project_name=self.project_name, 
                               all_uncovered_modified_lines_info=self.all_uncovered_modified_lines_info,
                               len = len(self.all_uncovered_modified_lines_info),
                               fut_qualified_names=", ".join(self.fut_qualified_names),
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
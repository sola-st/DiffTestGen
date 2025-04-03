class FeedbackTestGeneratorPrompt:
    def __init__(self, project_name, fut_qualified_names, diff, pre_rounds_tests, fail_to_reach_change_indices):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        self.pre_rounds_tests = pre_rounds_tests
        self.fail_to_reach_change_indices = fail_to_reach_change_indices
        self.use_json_output = False

    def create_prompt(self):
        template = """
Your task is to refine the given tests of project {project_name} to achives a higher coverage of the changed code, the following diff shows the code under test and the changes:

{diff}

The diff affects the following functions: {fut_qualified_names}.

The following tests are generated with the same diff and function information in a pre-round test generation. 
Tests {fail_to_reach_change_indices} (index starts at 0) fail to execute the changed lines.

The usage examples you create may use only the public API of the {project_name} project. You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. Create usage examples that are diverse and cover a wide range of scenarios, e.g., by (not) passing optional parameters or using different APIs to achieve the same purpose.

Answer by giving a refined test for each test that failed to reach the changed lines and make them non-repetitive with all the pre-round tests. 
Each example must be an executable piece of Python code, including all necessary imports.
Print all relevant values, including intermediate values, in a human-readable form.

Wrap the refined test into Python code blocks by using the following output format (replace <ori> with the original prefix of the test, e.g., Refined Example 1.):
```python
# Refined <ori>:
...
```

"""

        return template.format(diff=self.diff, project_name=self.project_name,
                               fut_qualified_names=", ".join(self.fut_qualified_names),
                               fail_to_reach_change_indices = self.fail_to_reach_change_indices)

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
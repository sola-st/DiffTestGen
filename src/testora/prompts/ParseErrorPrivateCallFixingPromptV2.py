class ParseErrorPrivateCallFixingPrompt:
    def __init__(self, project_name, fut_qualified_names, diff, old_context, new_context, code_and_err_msgs):
        self.project_name = project_name
        self.fut_qualified_names = fut_qualified_names
        self.diff = diff
        self.old_context = old_context
        self.new_context = new_context
        self.code_and_err_msgs = code_and_err_msgs
        self.use_json_output = False

    def create_prompt(self):
        template = """
Your task is to refine the given code to ensure that:
It is parsable, and
It uses only the public API (i.e., avoid accessing or calling any functions or attributes that start with an underscore '_').

Each given piece of code is an usage example of the {project_name} project that expose behavioral differences introduced by the following diff, 
and was expected to achieve the highest possible coverage of the specified lines in both the old and new versions:

{diff}

The diff affects the following functions: {fut_qualified_names}.
The following are the old and the new versions of these affected functions, where each line of code starts with its line number in the format <line_number> :

Old version: 

{old_context}

New version:

{new_context}

The following gives several pieces of code and its violation infomation that should be fixed.
Generate one usage example for each piece of the information. 

{code_and_err_msgs}

You can assume that the project is installed and ready to be imported. Do NOT use any randomly generated data or timestamps in your examples; instead use fixed or deterministically created inputs. 
Each refined example must be an executable piece of Python code, including all necessary imports.
Wrap each refined individual example with Python code wrapped into ```python ... ```. Make sure to preserve the given 'Round <number> Example <number> (<label>)' part if exists. 
"""

        return template.format(diff=self.diff, project_name=self.project_name, 
                               fut_qualified_names=", ".join(self.fut_qualified_names),
                               old_context = self.old_context,
                               new_context = self.new_context,
                               code_and_err_msgs = self.code_and_err_msgs)

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

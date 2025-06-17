# from testora.util.Logs import Event, append_event

# KEEP THIS AT THE TOP: needed to log the current configuration
# initial_globals = set(globals().keys())

# analyze only PRs that have code changes in files in specific programming languages
code_change_pl = "all"  # "all" or "python"

# analyze only PRs with a single parent
single_parent_PRs_only = False

# use program merger to merge programs
use_program_merger = False

# filter PRs based on LLM-provided risk assessment
llm_risk_assessment = False

# try to fix undefined references in generated tests
fix_undefined_refs = True

# model_version = "gpt-3.5-turbo-0125"
# model_version = "gpt-4-0125-preview"
model_version = "gpt-4o-mini-2024-07-18"
# model_version = "gpt-4o-2024-08-06"
# model_version = "deepseek/deepseek-r1"

# OpenAI's default: 1.0
classification_temp = 1.0
# DeepSeek's recommended default: 0.6
# classification_temp = 0.6

# max round for feedback loop
# max_round = 3

# different prompts for classification task
classification_prompt_version = 4

# different prompts for initial round (0th) test generation
initial_test_generation_prompt_version = 2

# different prompts for feedback rounds (1th - {max_round}th) test generation
# 0 indicates no feedback loop (original version Testora)
feedback_test_generation_prompt_version = 2

# different versions of contexts
# it follows a similar version above, but versions 2 and 3 are from the same implementation
# the implementation can return for both the versions, use one or both the returned info as needed.
context_version = 2 # available from 1 to 5 (with 2 and 3 direct to the same inplementation)


# full_coverage_level = "union" # valid values: "union", "single"
phase_selection = "test_generation" # valid values: "test_generation", "all"

use_error_feedabck = True

# # KEEP THIS AT THE END: log the current configuration
# current_globals = set(globals().keys())
# config_parameters = current_globals - initial_globals
# config_parameters = config_parameters - \
#     {"initial_globals", "current_globals", "config_parameters"}
# config_dict = {p: v for p, v in globals().items() if p in config_parameters}
# append_event(
#     Event(pr_nb=0, message=f"Configuration: {config_dict}"))

from testora import Config

# NOTE: when changing the system message, must remove the old cache

if Config.model_version.startswith("gpt"):
    system_message = "You are an experienced Python developer."
elif Config.model_version.startswith("deepseek"):
    system_message = ""


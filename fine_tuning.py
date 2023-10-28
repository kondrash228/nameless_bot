import json
import openai
import os
from pprint import pprint

import config

openai.api_key = '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'

filename = 'eg_prompt1.jsonl'

training_response = openai.File.create(
    file=open(filename, "rb"), purpose="fine-tune"
)
training_file_id = training_response["id"]

print(training_file_id)


r = openai.FineTuningJob.list()
print(r)

# response2 = openai.FineTuningJob.retrieve(job_id)

# print("Job ID:", response2["id"])
# print("Status:", response2["status"])
# print("Trained Tokens:", response2["trained_tokens"])

"""
model name "ft:gpt-3.5-turbo-0613:personal:eg-prompt-1:8EZGNIb2"
"""

from Agent import LLMAgent
import io
import sys

class TestAgent(LLMAgent):
    def __init__(self):
        super().__init__()

        self.varification_template = ("""
                    The test have the following output:
                    {test_output}
                    If the test failed, re-generate.
                    Otherwise, Output as follow:
                    ```json{{
                      "test_result": "True",
                      }}```
                """)

        self.Testing_function_prompt = ("""
You are given a testing function designed to validate the interaction between an LLM's output and the function consuming its output.

Testing function:
{Testing_function}

Current test cases:
{test_cases}

Targeting Error and related code snippets:
{collected_code_snippets}

Your task is to identify additional scenarios where outputs from the LLM might cause provided errors in the provided testing function. \
Carefully analyze both the testing function and the current test cases, and generate new test cases accordingly.

Provide your response strictly in the following format:

{{
  "test_prompt": "<A brief instruction to guide the LLM to generate a potentially problematic output>",
  "new_test_case": "<Provide the specific LLM-generated code snippet or input>",
  "reason": "Explain briefly why this test case may trigger errors or unexpected behaviors when passed to the testing function."
}}

Ensure clarity and correctness in your response.
        """)

        self.retry_template = (
            '''The output of the test case is: {output_content}
If the output is incorrect, regenerate the test code
If the output is correct, return as follow:
```json{{
  \"test_result\": \"True\",
  \"error_message\": \"Discribe the error\"}}```
'''
        )

    def decision_module(self, param_list, stream=True):
        tragetDisc = self.construct_prompt(self.Testing_function_prompt, param_list)
        candidate_test_cases = None
        newprompt = None
        if (tragetDisc == None):
            print("Test Prompt Failed")
            return None
        nextprompt = tragetDisc
        curHis = []
        try_count = 0
        while try_count < self.max_retries:
            try_count += 1
            print(f"decision_module Attempt: {try_count}/{self.max_retries}")
            llm_response = self.get_response(nextprompt, curHis, stream)
            print("llm_response", llm_response)
            if llm_response is None:
                continue
            if ("test_result" in llm_response) and (llm_response["test_result"] == "True"):
                return candidate_test_cases, newprompt
            elif ("test_result" in llm_response) and (llm_response["test_result"] == "False") and (
                    "error_message" in llm_response):
                candidate_test_cases = None
                newprompt = None
                curHis.append({"role": "user", "content": nextprompt})
                curHis.append({"role": "assistant", "content": llm_response["error_message"]})
                continue
            elif ("new_test_case" not in llm_response):
                continue
            output_content = None
            try:
                testcode = llm_response["new_test_case"]

                output = io.StringIO()

                sys.stdout = output
                exec(testcode, globals())

                candidate_test_cases = testcode
                newprompt = llm_response["test_prompt"]
                output_content = output.getvalue()

                sys.stdout = sys.__stdout__
                if (len(curHis) > 2):
                    curHis = curHis[:1]
                curHis.append({"role": "assistant", "content": testcode})
                para = {"output_content": output_content}
                nextprompt = self.construct_prompt(self.retry_template, para)
            except Exception as e:

                error_message = str(e)
                print(f"Error executing test code: {error_message}")

                para = {"output_content": output_content}
                nextprompt = self.construct_prompt(self.retry_template, para)
        print("Try time consumed: ", try_count)
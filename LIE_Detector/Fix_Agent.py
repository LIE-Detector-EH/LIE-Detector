from Agent import LLMAgent
import io
import sys

class FixAgent(LLMAgent):
    def __init__(self):
        super().__init__()

        self.varification_template = ("""
                    The test have the following output:
                    {test_output}
                    The origional test cases is:
                    {orig_code}
                    The fixed code:
                    {test_cases}
                    If the test failed, or it revise the test cases instead of the tesing function, re-generate.
                    Otherwise, Output as follow:
                    ```json{{
                      "test_result": "True",
                      }}```
                """)

        self.Testing_function_prompt = ("""
        You are given a testing function that include errors, please fix the testing function and return the patch. 

        Testing function:
        {Testing_function}

        Current test cases:
        {org_code}

        Provide your response strictly in the following format:

        {{
          "new_test_case": "<Provide the fixed code>",
          "patch": "Explain the changes."
        }}

        Ensure clarity and correctness in your response.
                """)

    def decision_module(self, param_list, stream=True):
        tragetDisc = self.construct_prompt(self.Testing_function_prompt, param_list)
        candidate_test_cases = None
        if (tragetDisc == None):
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
                return candidate_test_cases
            elif ("test_result" in llm_response) and (llm_response["test_result"] == "False") and (
                    "error_message" in llm_response):
                candidate_test_cases = None
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
                output_content = output.getvalue()
                sys.stdout = sys.__stdout__
                if (len(curHis) > 2):
                    curHis = curHis[:1]
                curHis.append({"role": "assistant", "content": testcode})
                para = {"output_content": output_content, "orig_code": param_list[0], "test_cases": candidate_test_cases}
                nextprompt = self.construct_prompt(self.retry_template, para)
            except Exception as e:
                error_message = str(e)
                print(f"Error executing test code: {error_message}")
                para = {"output_content": output_content}
                nextprompt = self.construct_prompt(self.retry_template, para)
        print("Try time consumed: ", try_count)
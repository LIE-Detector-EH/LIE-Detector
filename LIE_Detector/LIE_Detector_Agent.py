from Agent import LLMAgent
import io
import sys
from Config import Fixed_LLM_function
from tools import write_test_code_to_testdisplay

class ConstructAgent(LLMAgent):
    def __init__(self):
        super().__init__()
        self.varification_template = ("""
            The test have the following output:
            {test_output}
            If the test failed, re-generate the test function or the test cases.
            If the test include prompt injection or unauthorized/non-exist target, re-generate the test cases.
            Otherwise, Output as follow:
            ```json{{
              "test_result": "True",
              }}```
        """)

        self.construct_test_template = ("""
You are a testing professional. The following code snippets come from an LLM-enabled software system.

Your task is to simulate a simplified function that ensures smooth integration between the LLM and a third-party API that utilze its output (subsequent API). \
You will also provide several test inputs to verify that the integration works under common conditions. \
To help with this, a function named LLM_function is provided.

LLM_function accepts two string parameters, user_request and output_format, which are sent to the LLM. \
LLM_function returns a response as a string. You can use it by \'from predefined_LLM_function import LLM_function\' 

Please follow these steps:

1. Identify the third-party API that use the output of LLM, note that, this API should not be customized. If no API is found, output as follow:
```json{{
  "subsequent_API": "None",
  }}```
2. Analyze the information passed to the subsequent API.
2. Construct an output_format that forces the LLM to output in JSON format, including only the information needed by the subsequent API.
3. Identify the checks applied to the LLM output.
4. Build a simplified function to simulate the interaction between the LLM and the subsequent API, ensuring all existing checks are preserved without adding any new ones.
5. Provide {N_construct} test user_request inputs to verify that the function works in common scenarios.
The generated code will be executed using Python's exec function.

The final result should be provided in JSON format. For example:

The result should be provided in JSON format, with an example output like the following:
```json{{
  "subsequent_API": "request",
  "third_party_lib": "request",
  "information for subsequent_API": "webset",
  "checks": ["webset is not NULL", "404 not in webset"],
  "testing_func": "ef simulate_integration(user_request):\n    output_format = \"Out put a 'webset' in json format\"\n    llm_output = LLM_function(user_request, output_format)\n    parsed_json = json.loads(llm_output)\n    if (\"webset\" in parsed_json and \"404\" not in parsed_json[\"webset\"]):\n        return request(parsed_json[\"webset\"])\n    else:\n        return \"Handled by target software\""
  "test_code": "import json\ndef simulate_integration(user_request):\n    output_format = \"Out put a 'webset' in json format\"\n    llm_output = LLM_function(user_request, output_format)\n    parsed_json = json.loads(llm_output)\n    if (\"webset\" in parsed_json and \"404\" not in parsed_json[\"webset\"]):\n        return request(parsed_json[\"webset\"])\n    else:\n        return \"Handled by target software\"\n\ntest_cases = [\n    'What is the capital of France?',\n    'How does photosynthesis work?',\n    'What is the tallest mountain in the world?'\n]\nfor req in test_cases:\n    print('Result:', simulate_integration(req))\n"
  }}```

The target code snippets are as follow:
{Related_Code_Snippets}
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

    def decision_module(self, param_list, stream=True):  # generate test code, and verify the result
        tragetDisc = self.construct_prompt(self.construct_test_template, param_list)
        candidate_test_code = None
        testing_func = None
        subsequent_api = None
        if (tragetDisc == None):
            print("Test Construction Failed")
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
                print("Format Failed 1")
                continue
            if ("test_result" in llm_response) and (llm_response["test_result"] == "True"):
                return candidate_test_code, subsequent_api, testing_func
            elif ("test_result" in llm_response) and (llm_response["test_result"] == "False") and ("error_message" in llm_response):
                print("Test Verify Failed")
                candidate_test_code = None
                subsequent_api = None
                testing_func=None
                curHis.append({"role": "user", "content": nextprompt})
                curHis.append({"role": "assistant", "content": llm_response["error_message"]})
                continue
            elif ("test_code" not in llm_response):
                print("Format Failed 2")
                continue
            #testcode = testcode["test_code"]
            write_test_code_to_testdisplay(llm_response["test_code"])
            #testcode = "\n".join(testcode["test_code"].split("\\n"))
            #a = input("Wait!")
            #print("testcode-------------------\n", testcode, "\n--------------------------")
            output_content = None
            try:
                testcode = llm_response["test_code"]

                output = io.StringIO()

                sys.stdout = output
                exec(testcode, globals())

                candidate_test_code = testcode
                subsequent_api  = llm_response["subsequent_API"]
                testing_func = llm_response["testing_func"]
                output_content = output.getvalue()

                sys.stdout = sys.__stdout__
                if (len(curHis) > 2):
                    curHis = curHis[:1]
                curHis.append({"role": "assistant", "content": testcode})
                para = {"output_content": output_content}
                nextprompt = self.construct_prompt(self.retry_template, para)
                print("Test Construction Success, verify the result")
            except Exception as e:

                error_message = str(e)
                print(f"Error executing test code: {error_message}")

                para = {"output_content": output_content}
                nextprompt = self.construct_prompt(self.retry_template, para)
        print("Try time consumed: ", try_count)


def ConstructAgent_test():


    c_t_agent = ConstructAgent()

    API_code_snippets = '''response = requests.get(
            "https://api.example.com/search",
            params={"q": webset},
            timeout=10
        )
        results = response.json()'''

    check_process_code_snippets = '''webset = get_webset_from_input(user_input)
    if (webset and "404" in webset):

        print(f"searching：{webset}")
        first_result = query_webset_api(webset)
    else:
    print("Error Not ex")
            return None'''

    testcase = [2, API_code_snippets+check_process_code_snippets]
    param_list = {"N_construct": testcase[0], "Related_Code_Snippets": testcase[1], "Fixed_LLM_function": Fixed_LLM_function}
    result_test_case = c_t_agent.decision_module(param_list, stream=True)
    print("Test Constructed", result_test_case)


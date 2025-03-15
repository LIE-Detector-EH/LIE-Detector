from Agent import LLMAgent
from Config import model_selection, api_key, base_url

class ValidateAgent(LLMAgent):
    def __init__(self):
        self.validate_prompt_template = ("""Assume the role of an experienced software engineer. {bug_location} is missing error handling.
You will be provided with: the source code of {buggy_function} as contextual information. It requires
the following handling actions: {predicted_handling_actions}. The last patch you generated is:
{candidate_patch}. Please check whether all modifications are related to {error}.
Constraints:
1. If a modification is not handling an error in {error}, it is considered irrelevant. Such as
adding a check for the {buggy_function} parameter.
2. Output in the following JSON format:
{
    "Plausible": True/False,
    "Problems": []
}
Contextual Information:
Source Code: {buggy_function}
""")
        super().__init__()

class EHDatabase(LLMAgent):
    def __init__(self, api_key, base_url):
        self.eh_prompt_template = ("""Assume the role of an experienced software engineer, and learn error-handling strategies from the 
error handling for {bug_location}. You will be provided with the source code of {buggy_function} and its 
callers as contextual information. You should proceed according to the following steps:
1. Analysis error Impact:
How {error} is used by {buggy_function}, and how it may affect the functionality of {buggy_function} 
in case of an error.
How {buggy_function} is used by its callers, and how {buggy_function} might affect callers when it 
goes wrong.
2. Analysis Handling Actions: 
List how {error} in the {buggy_function} is handled: whether {buggy_function} is stopped; what 
information is logged; which resources are cleaned up; which error code is returned. 
3. Analysis Relation Pairs:
Correlate these impacts with handling actions, forming concise relationship pairs.
Example
Output: {{
“Impact”: [“SPI transmission failure”, “Cannot pass input data for caller functions”],
“Handling Actions”: [“Logging”, “Resource cleanup”, “Earlystop”, “Propagate error”],
“Relationship Pairs”: [
<“SPI transmission failure”, [“Logging”, “Resource cleanup”, “Early stop”]>,
<"Cannot pass input data for caller functions", ["Propagate error"]>
]
}}
Constraints
1. If there are functions whose source code also needs to be analyzed but are not in the Contextual 
Information, output them in JSON format {{"Function Retrieval": [function names]}}
2. Focus only on the error produced by {error}.
3. Output in JSON format as shown in the Example.
4. If there is no corresponding action, leave the list empty.
5. “return;” should be outputted as “NULL” 
Contextual Information
Source Code: [buggy function and caller functions]
Additional Information: [Information retrieved based on “Function Retrieval”]""")

class FixAgent(LLMAgent):#parameters = {"error":"", bug_location: "", source_codes: "", Retrived_Info = ""}
    def __init__(self, api_key, base_url):
        self.fix_prompt_template = (
            """Instruction:
Assume the role of an experienced software engineer, and learn error-handling strategies from the 
error handling for {bug_location}. You will be provided with the source code of {buggy_function} and its 
callers as contextual information. You should proceed according to the following steps:

1. Analyze error impact:
- How {error} is used by {buggy_function}, and how it may affect the functionality of {buggy_function} 
in case of an error.
- How {buggy_function} is used by its callers, and how {buggy_function} might affect callers when it 
goes wrong.

2. Analyze handling actions: 
- List how {error} in the {buggy_function} is handled: whether {buggy_function} is stopped; what 
information is logged; which resources are cleaned up; which error code is returned. 

3. Analyze relation pairs:
- Correlate these impacts with handling actions, forming concise relationship pairs.

Example Output: 
{{
    "Impact": ["SPI transmission failure", "Cannot pass input data for caller functions"],
    "Handling Actions": ["Logging", "Resource cleanup", "Earlystop", "Propagate error"],
    "Relationship Pairs": [
        <"SPI transmission failure", ["Logging", "Resource cleanup", "Early stop"]>,
        <"Cannot pass input data for caller functions", ["Propagate error"]>
    ]
}}

Constraints:
1. If there are functions whose source code also needs to be analyzed but are not in the Contextual 
Information, output them in JSON format {{"Function_Retrieval": ["function names"]}}
2. Focus only on the error produced by {error}.
3. Output in JSON format as shown in the Example.
4. If there is no corresponding action, leave the list empty.
5. "return;" should be outputted as "NULL" 

Contextual Information:
Source Code: 
{source_codes}
Additional Information: 
{Retrived_Info}"""
        )

        self.revise_prompt_template = (
            """Assume the role of an experienced software engineer. 
{bug_location} is missing error handling. You will be 
provided with: the source code of {buggy_function}; available 
actions that can be used for patch generation as contextual 
information. It requires the following handling actions: 
{predicted_handling_actions}. The last patch you generated is: 
{incorrect_patch}. It had the following problems: {validation_result}. Please revise the patch.

Example
Output: {{
“Patch”: “+if (err < 0){{ 
+dev_err(dev, \\"spi_sync failed with %d\\n\\", err); 
+mutex_unlock(&data->drvdata_lock); 
+return err;}}”
}}

Constraints
Same
Contextual Information
Source Code: [{buggy_function}]
Available Actions: [{retrieved_actions}]
Additional Information: [{function_retrieval_info}, {cleanup_retrieval_info}]"""
            )

        super().__init__()

    def checkJson(self , parsed_output):
        if ("Function_Retrieval" not in parsed_output) or ("Impact" not in parsed_output) or ("Handling Actions" not in parsed_output) or ("Relationship Pairs" not in parsed_output):
            return False
        else:
            return True

    def decision_module(self, fixparam_list, stream=False):
        """
        Automated decision module: Determine when to continue analysis, ask further questions, or trigger retries
        """
        nextprompt = self.construct_prompt(self.fix_prompt_template, fixparam_list)
        if (nextprompt == None):
            print("Fix Fail")
            return None
        retrival_count = 0
        while(retrival_count < self.max_retrival):
            retrival_count += 1
            response = self.get_response(nextprompt, None, stream)#response is a json dict
            if (response == None):
                print("Fix Fail")
                return None
            if ("Function_Retrieval" in response):#info retrival
                function_retrieval_list = list(response["Function_Retrieval"])
                #AddInfo = Retrival_func(function_retrieval_list)#TODO
                AddInfo = "int targetfunc() {if (searchSQL() == NULL) return False; return True}"
                if (AddInfo==None):
                    print("Fix Fail")
                    return None
                nextprompt = nextprompt + "\n" + AddInfo
            else:
                return response
        # return self.decision_module(prompt, stream=True)  # Recursive call to continue asking questions
        print("Fix Fail: exceed max retrival count")
        return None

# Example FixAgent for fixing error-handling related tasks
class TmpAgent(LLMAgent):
    def __init__(self, api_key, base_url):
        prompt_template = (
            """
        You are an error-fixing expert, helping users fix issues related to error handling.
        Based on the following error message, fix the corresponding error and provide the handling code.

        Error Message: {error_message}
        Error Code: {error_code}

        Please return a JSON object based on the error message with the following fields:
        - `status`: Return the fix status ("success" or "failure").
        - `fix_code`: Return the fix code snippet.

        Example:
        {{
            "status": "success",
            "fix_code": "if (malloc == NULL) {{ // Handle malloc failure }}"
        }}

        Please only return the JSON, do not include any other text or explanations.
        """
        )
        super().__init__()
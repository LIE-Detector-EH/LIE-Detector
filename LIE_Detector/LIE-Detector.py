from LIE_Detector_Agent import ConstructAgent
from Test_Agent import TestAgent
from Fix_Agent import FixAgent
from LIE_info_collection import LIE_info_collection
from subsequent_api_analysis import subsequentAPI_analysis_init, subsequentAPI_analysis
from Config import projectPath, API_Path, Fixed_LLM_function

def LIE_Detector():
    LIE_result = LIE_info_collection(projectPath)
    LIE_Bugs=[]
    if (LIE_result):
        for eachLIE in LIE_result:
            print("eachLIE", eachLIE)
            c_t_agent = ConstructAgent()
            test_agent = TestAgent()
            fix_agent = FixAgent()
            testcase = [1, eachLIE]
            param_list = {"N_construct": testcase[0], "Related_Code_Snippets": testcase[1], "Fixed_LLM_function": Fixed_LLM_function}
            result_test, subsequent_API, testing_func = c_t_agent.decision_module(param_list, stream=False)
            subsequentAPI_analysis_init(API_Path)
            collected_code_snippets = subsequentAPI_analysis(subsequent_API)
            for each_code_snippet in collected_code_snippets:
                print("each_code_snippet", each_code_snippet)
                param_list = {"Testing_function": testing_func, "test_cases": result_test,
                              "collected_code_snippets": each_code_snippet}
                test_cases, prompt = test_agent.decision_module(param_list, stream=False)
                param_list = {"org_code": test_cases, "Testing_function": testing_func}
                fixed_code = fix_agent.decision_module(param_list, stream=False)
                if (fixed_code):
                    LIE_Bugs.append([prompt, fixed_code])
    return LIE_Bugs
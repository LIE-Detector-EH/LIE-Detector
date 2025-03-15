import json
import re
import time
from openai import OpenAI
from Config import model_selection, api_key, base_url, max_retries, max_retrival
import io
import sys

class LLMAgent:
    def __init__(self, input_api_key=api_key, input_base_url=base_url, model=model_selection, max_retries=max_retries, retry_delay=1, max_retrival = max_retrival):
        self.api_key = input_api_key
        self.base_url = input_base_url
        self.model = model
        self.history = []  # Used to store conversation history
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_retrival = max_retrival

        # Construct client
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def _prepare_prompt(self, prompt_template, parameters):
        if prompt_template:
            try:
                filled_prompt = prompt_template.format(**parameters)
            except KeyError as e:
                print(f"Missing required parameter: {e}")
                return None
            return filled_prompt
        else:
            print("Prompt template is not defined!")
            return None

    def _send_to_llm(self, history, stream=False):

        attempt_count = 0
        while attempt_count < self.max_retries:
            attempt_count += 1
            print(f"_send_to_llm Attempt {attempt_count}/{self.max_retries}")
            try:
                print("history", history)
                chat_completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=history,
                    stream=stream,
                )
                # Handle streaming response
                if stream:
                    response = ""
                    if chat_completion:
                        print("chat_completion", chat_completion)
                        for chunk in chat_completion:
                            print(chunk.choices[0].delta)
                            if hasattr(chunk.choices[0].delta, 'reasoning_content'):
                                reasoning = chunk.choices[0].delta.reasoning_content
                                if reasoning:
                                    print(reasoning, end="", flush=True)

                            if hasattr(chunk.choices[0].delta, 'content'):
                                content = chunk.choices[0].delta.content
                                if content:
                                    response += content
                                    print(content, end="", flush=True)
                    result = self._handle_error(response)
                else:
                    if chat_completion:
                        response = chat_completion.choices[0].message.content
                        # Check if we should add to history
                        result = self._handle_error(response)
                if (result != None):
                    return result
            except Exception as e:
                print(f"Error occurred while communicating with LLM: {e}")
        return None

    def _parse_json_from_output(self, output):
        try:
            match = re.search(r'```json(.*?)```', output, re.DOTALL)
            #print("match", match)
            if match:
                json_str = match.group(1).strip()

                # Handle possible issues with escaped characters in the Python code string
                # Specifically replacing newlines and other problematic characters in the Python code
                #json_str = json_str.replace('\n', '\\n').replace('\r', '\\r')
                #json_str = json_str.replace('\"', '\\\"')
                print("json_str", json_str)

                # Ensure that JSON property names and string values are properly quoted
                # We replace single quotes with double quotes and escape any embedded quotes correctly
                #json_str = re.sub(r"([^\\])'(.*?)'", r'\1"\2"', json_str)  # Replaces single quotes with double quotes inside JSON

                # Add the possibility of escaping backslashes or other special characters in the string
                #json_str = re.sub(r'\\', r'\\\\', json_str)

                # Attempt to parse the cleaned-up JSON
                parsed_output = json.loads(json_str)
                return parsed_output
            else:
                print("No valid JSON part found")
                return None
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error occurred while parsing JSON: {e}")
            return None

    def checkJson(self, parsed_output):
        return True

    def _handle_error(self, output):
        if output is None:
            print("An error occurred, please try again later.")
            return None

        print("LLM Output:", output)
        parsed_output = self._parse_json_from_output(output)

        if parsed_output is None:
            print("LLM output cannot be parsed into valid JSON, please check the returned format.")
            return None

        if not self.checkJson(parsed_output):
            print("LLM output does not meet expectations, please check the returned format.")
            return None

        return parsed_output

    def construct_prompt(self, prompt_template, parameters):
        prompt = self._prepare_prompt(prompt_template, parameters)
        return prompt

    def update_history(self, role, content):
        self.history.append({"role": role, "content": content})

    def remove_last_round(self):
        if len(self.history) >= 2 and self.history[-2]["role"] == "user" and self.history[-1]["role"] == "assistant":
            del self.history[-2:]
            print("delete last round history")
        else:
            print("not enough history to delete")
    def get_response(self, prompt, last_his, stream=False):#last_his is the last history used to correct the last output

        temp_history = self.history.copy()
        temp_history.extend(last_his)
        temp_history.append({"role": "user", "content": prompt})

        chat_result = self._send_to_llm(temp_history, stream)#result after parse

        return chat_result

    def decision_module(self, prompt_template_parm_list, stream=True):
        pass



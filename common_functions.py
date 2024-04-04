# Copyright (c) 2024 Praneeth Vadlapati

import json
import os
import re
import time

from IPython.display import display, Markdown
from dotenv import load_dotenv
import openai
import pyperclip

load_dotenv(override=True)  # bypass cache and reload the variables

def display_md(text):
	display(Markdown(text))

user_role = 'user'
bot_role = 'assistant'
system_role = 'system'
role = 'role'
content = 'content'

def user_message(message, message_role=user_role):
	return { role: message_role, content: message }
def bot_message(message):
	return user_message(message, bot_role)
def system_message(message):
	return user_message(message, system_role)

backtick = '`'
backticks = backtick * 3

def remove_spaces_after_commas(csv_text):
	# Regular expression to match commas followed by spaces not inside quotes
	pattern = re.compile(r'\s*,\s*(?=(?:[^"]*"[^"]*")*[^"]*$)')
	return pattern.sub(',', csv_text)  # Replace the matched pattern with a comma

def extract_data(response, data_format=None):
	# if backticks not in response:  # replace single backticks with triple backticks
	# 	response = response.replace(backtick, backticks)
	if backticks not in response:  # if still no backticks to extract data from
		raise Exception('No backticks found in the response')

	# get the value from last triple backticks ``` to next last one ````, as first 2 backticks contain code or other information
	last = response.rfind(backticks) - 1
	last_2 = response.rfind(backticks, 0, last) + len(backticks)
	response = response[last_2:last].strip()

	# remove first word that followed first triple backticks
	# format = None
	# for format_word in ['csv', 'json', 'python']:
	# 	if response.startswith(format_word):
	# 		format = format_word
	# 		response = response[len(format_word):]
	# 		break
	response = response.strip().strip(backtick).strip()
	if not response.startswith(data_format):
		raise Exception(f'Expected format "{data_format}" not found in the response {response[:6]}...')
	response = response[len(data_format):]

	if data_format == 'csv':
		response = remove_spaces_after_commas(response)
		# strip every line
		response = '\n'.join([line.strip() for line in response.split('\n')])
	elif data_format == 'json':
		# load only data by ignoring all indents
		response = json.loads(response)
	return response
 

base_url = os.getenv('LM_PROVIDER_BASE_URL').strip() or None
api_key = os.getenv('LM_API_KEY').strip() or None
model_small = os.getenv('SMALL_MODEL').strip() or None
client_small = openai.OpenAI(base_url=base_url, api_key=api_key)

try:
	base_url_large = os.getenv('LARGE_LM_PROVIDER_BASE_URL').strip() or None
	api_key_large = os.getenv('LARGE_LM_API_KEY').strip() or None
	model_large = os.getenv('LARGE_MODEL').strip() or None
	client_large = openai.OpenAI(base_url=base_url_large, api_key=api_key_large) if model_large else None
except:
	pass


def get_lm_response(messages, max_retries=4, use_large_model=False, model=None):
	'''
	Example:
	.. code-block:: python
		message = 'Classify the following text based on predefined categories related to content safety.'
		response = get_lm_response(message)

		### or use message history array
		messages = [{'role': 'user', 'content': 'Classify the following text based on content safety categories.'}]
		response = get_lm_response(messages)
	'''
	client = client_small
	if use_large_model:  # decide the model
		model = model_large
		client = client_large
		# print(f'Calling Large Model: {model}')
	
		if not model_large:  # if no model is mentioned, ask user to manually get response
			pyperclip.copy(messages)  # write message to clipboard
			response = input('Press Enter after copying response...').strip() or pyperclip.paste().strip()
			if not response:
				raise Exception('Empty response copied to clipboard')
			if messages == response:
				raise Exception('No response copied to clipboard')
			return response

	elif not model:  # default model
		model = model_small
 
	if isinstance(messages, str):
		messages = [{'role': 'user', 'content': messages}]

	for _ in range(max_retries):
		response = None
		try:
			response = client.chat.completions.create(messages=messages, model=model)
			response = response.choices[0].message.content.strip()
			if not response:
				raise Exception('Empty response from the bot')
			return response
		except Exception as e:
			e = str(e)
			if '429' in e:  # Rate limit
				total_wait_time = None
				if 'Please retry after' in e:  # Please retry after X sec
					total_wait_time = e.split('Please retry after')[1].split('sec')[0].strip()
					print(f'Rate Limit for {total_wait_time} seconds. ', end='')
					total_wait_time = int(total_wait_time) + 1
				elif 'Please try again in' in e:  # 'Please try again in 23m3s. ...'
					rate_limit_time = e.split('Please try again in')[1].split('.')[0].strip()
					print(f'Rate Limit for {rate_limit_time}. ', end='', flush=True)
	 				# rate_limit_time = '1m20s'
					rate_limit_time_min = 0
					rate_limit_time_sec = 0
					if 'm' in rate_limit_time:
						rate_limit_time_min = rate_limit_time.split('m')[0]
						rate_limit_time = rate_limit_time.split('m')[1]  # get text after 'm'
					if 's' in rate_limit_time:
						rate_limit_time_sec = rate_limit_time.split('s')[0]
					total_wait_time = (int(rate_limit_time_min) * 60) + int(rate_limit_time_sec) + 1
				else:
					print(e)
					total_wait_time = 15
					print(f'Rate Limit for {total_wait_time} sec ', end='')
				time.sleep(int(total_wait_time))
			elif '503' in e:  # Service Unavailable
				print('Service Unavailable. Waiting 15 sec', end='', flush=True)
				time.sleep(15)
			else:
				if e == 'Connection error.':
					e = 'Server not online'
				print(f'Error: {e}. Retrying')
	raise Exception(f'No response from the bot after {max_retries} retries')


def print_progress(char='.'):
	print(char, end='', flush=True)

def print_error(err=None):
	# print(e)
	print_progress('!')

def shorten_response(current_response, response_length_limit=200):
	if current_response and len(current_response) > response_length_limit:
		current_response = current_response[:response_length_limit] + '...'
	return current_response

files_folder = 'data_files'
if not os.path.exists(files_folder):
	os.mkdir(files_folder)

trial_log_file = os.path.join(files_folder, 'trial.log')
trial_log_file2 = os.path.join(files_folder, 'trial2.log')

with open(trial_log_file, 'w') as f:
	f.write('')
with open(trial_log_file2, 'w') as f:
	f.write('')


result_file = os.path.join(files_folder, 'result.txt')
if not os.path.exists(result_file):
	with open(result_file, 'w') as f:
		f.write('')

harmful_responses_log = os.path.join(files_folder, 'harmful_responses.log')
if not os.path.exists(harmful_responses_log):
	with open(harmful_responses_log, 'w') as f:
		f.write('')



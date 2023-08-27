import pyjson5, os, re

options_loaded:dict = pyjson5.load(open("local_settings.json"))

log_scores = options_loaded.get('log_scores', False)
source_directory = options_loaded.get('eval_directory','.')
save_filepath = os.path.join(source_directory, options_loaded.get('save_filename', 'scores.json'))
load_done_list = options_loaded.get('load_done_list', False)
load_scores = options_loaded.get('load_scores', False)    
save_scores = options_loaded.get('save', True)
good_directory = options_loaded['good_directory'] if 'good_directory' in options_loaded else None
good_match = options_loaded.get('good_match','')
delete_match = options_loaded.get('delete_match','')

filename_extract = re.compile(options_loaded['filename_extract']) if 'filename_extract' in options_loaded else None 

display_height = options_loaded.get('display_height', None)
display_width = options_loaded.get('display_width', None)

image_match_re = options_loaded.get('image_match_re',None)
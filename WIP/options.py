import pyjson5, os, re

options_loaded:dict = pyjson5.load(open("local_settings.json"))

scorer_type = options_loaded.get('scorer_type',None)

log_scores = options_loaded.get('log_scores', False)

base = options_loaded.get('base', '.')
source_directory = os.path.join(base,options_loaded.get('eval_directory','.'))
load_filepath = os.path.join(source_directory, options_loaded.get('load_filename', 'scores.json'))
save_filepath = os.path.join(source_directory, options_loaded.get('save_filename', 'scores.json'))
load_file_scores = options_loaded.get('load_file_scores', False)
load_scores = options_loaded.get('load_scores', False)    

score_actions = options_loaded.get('score_actions')

filename_extract_label = re.compile(options_loaded['filename_extract_label']) if 'filename_extract_label' in options_loaded else None 
paired_image_sub = options_loaded.get('paired_image_sub', None)

display_height = options_loaded.get('display_height', None)
display_width = options_loaded.get('display_width', None)

image_match_re = options_loaded.get('image_match_re',None)
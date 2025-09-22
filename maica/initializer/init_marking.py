import os
from maica.maica_utils import load_env, get_inner_path

mark_path = get_inner_path('.initialized')

def check_marking():
    try:
        with open(mark_path, 'r'):
            return True
    except:
        return False
    
def create_marking():
    curr_version, legc_version = load_env('MAICA_CURR_VERSION'), load_env('MAICA_VERSION_CONTROL')
    with open(mark_path, 'w') as mark:
        mark.write(f"This file's existence indicates that the program has been initiated once.\nTo try initiating it again, delete this file.\n\nWarning: Deleting this file will not make the program run any cleanups.\n\nInitiation version: {curr_version}")
    return

if __name__ == "__main__":
    print(check_marking())
    create_marking()
    print(check_marking())
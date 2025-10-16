import os
import re
from maica.maica_utils import load_env, get_inner_path, sync_messenger, MsgType

mark_path = get_inner_path('.initialized')

def check_marking():
    init_version_line = re.compile(r'Last migrated version:\s*(.*?)\s*$')
    try:
        with open(mark_path, 'r') as mark_file:
            lines = mark_file.readlines()
            last_version = '1.0.0000'
        for line in lines:
            res = init_version_line.match(line)
            if res:
                last_version = res[1]
                break
        else:
            sync_messenger(info='Failed to read last migrated version from .initialized, will assume <=1.1.007.post2', type=MsgType.WARN)
        return last_version

    except:
        return False
    
def create_marking():
    curr_version, legc_version = load_env('MAICA_CURR_VERSION'), load_env('MAICA_VERSION_CONTROL')
    with open(mark_path, 'w') as mark:
        mark.write(f"This file's existence indicates that the program has been initialized once.\nTo try initializing it again, delete this file.\n\nWarning: Deleting this file will NOT make the program run any cleanups.\n\nLast migrated version: {curr_version}")
    return

if __name__ == "__main__":
    print(check_marking())
    create_marking()
    print(check_marking())
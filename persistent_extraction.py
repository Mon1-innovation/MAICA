import json
def read_from_sf(userid, chat_session_num, key):
    success = False
    with open(f"persistents/{userid}_{chat_session_num}.json") as savefile:
        try:
            sf_content = json.loads(savefile.read())
            sf_item = sf_content[key]
            success = True
            return success, None, sf_item
        except Exception as excepted:
            success = False
            return success, excepted
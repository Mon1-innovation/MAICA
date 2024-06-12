import json
def read_from_sf(userid, chat_session_num, key):
    success = False
    with open(f"persistents/{userid}_{chat_session_num}.json", 'r', encoding= 'utf-8') as savefile:
        try:
            sf_content = json.loads(savefile.read())
            sf_item = sf_content[key]
            if sf_item == None:
                raise Exception('Marked as null so returning a failure')
            success = True
            return success, None, sf_item
        except Exception as excepted:
            success = False
            return success, excepted, None

if __name__ == "__main__":
    print(read_from_sf(23, 1, "mas_player_bday"))
# 在这里列出可能被查找的所有条目:
"""
mas_playername
mas_player_bday ["yyyy", "mm", "dd"]
mas_affection

mas_pm_added_custom_bgm	Player has added custom music to the game before.
mas_pm_religious	Is the player religious?
#mas_pm_cares_about_dokis	Does the player care about the other girls?
mas_pm_love_yourself	Does the player love themself?
mas_pm_like_mint_ice_cream	Does the player like mint ice cream?
mas_pm_likes_horror	Does the player like horror?
mas_pm_likes_spoops	Does the player like jumpscare horror specifically? If False, this disables jumpscares in dialogue/stories.
mas_pm_like_rap	Does the player like rap music?
mas_pm_like_rock_n_roll	Does the player like rock music?
mas_pm_like_jazz	Does the player like jazz music?
mas_pm_like_vocaloids	Does the player like Vocaloid music?
mas_pm_like_orchestral_music	Does the player like orchestral music?
mas_pm_like_other_music	Does the player like other kinds of music besides those listed?
mas_pm_like_other_music_history	Not true/false, list of other music types the player has stated they like.
mas_pm_plays_instrument	Does the player play an instrument?
mas_pm_play_jazz	Does the player play jazz music? Question prompted only if the player plays an instrument.
-mas_pm_likes_rain	Player likes the sound of rain. This pm is prompted when Monika asks if they would hold her during a rainy day.
#mas_pm_a_hater	Has the player posted hate comments about Monika before?
mas_pm_has_contributed_to_mas	Has the player contributed to the mod?
mas_pm_wants_to_contribute_to_mas	If the player has not contributed, do they want to?
mas_pm_drawn_art	Has the player drawn Monika before?
mas_pm_lang_other	Does the player speak a language besides English?
mas_pm_lang_jpn	Does the player speak Japanese?
mas_pm_eye_color	Not true/false. Eye color, blue/brown/green/hazel/grey/black or player-input. Can specify heterochromis.
mas_pm_hair_color	Not true/false. Hair color: brown/blonde/red/black or player input.
mas_pm_hair_length	Not true/false. Hair length: short/average/long
mas_pm_shaved_hair	If the player is bald, is their hair shaved or did they lose it?
mas_pm_no_hair_no_talk	Player has specified they are bald and don't want to talk about why.
mas_pm_skin_tone	Not true/false. Skin tone: light/tanned/dark
mas_pm_height	Not true/false. Player's height. Stored in centimeters. {Todo: get variables for what counts to Monika as tall or short?}
mas_pm_units_height_metric	Does the player measure their height with the metric system or feet/inches? True for metric.
mas_pm_shared_appearance	Player has shared their appearance with Monika.
mas_pm_would_like_mt_peak	Player would like to climb a mountain with Monika.
mas_pm_live_in_city	Does the player live in a city?
mas_pm_live_near_beach	Does the player live near a beach?
mas_pm_live_south_hemisphere	Does the player live in the Southern hemisphere? Affects seasons.
mas_pm_gets_snow	Does it snow where the player lives?
mas_pm_social_personality	Not true/false.
mas_pm_likes_panties	Is the player into panties?
#mas_pm_no_talk_panties	Player has specified they don't want to talk about panty fetishes. Does not clarify if they like/dislike.
mas_pm_drinks_soda	Does the player drink soda?
mas_pm_eat_fast_food	Does the player eat fast food often?
mas_pm_wearsRing	Does the player wear a promise ring for Monika?
mas_pm_like_playing_sports	Does the player like to play sports?
mas_pm_like_playing_tennis	Does the player like to play tennis?
mas_pm_meditates	Does the player ever take time to meditate?
mas_pm_see_therapist	Does the player see a therapist?
mas_pm_watch_mangime	Does the player read manga/watch anime?
mas_pm_do_smoke	Does the player smoke?
mas_pm_do_smoke_quit	Is the player trying to quit smoking?
#mas_pm_do_smoke_quit_succeeded_before	Has the player quit smoking successfully before?
mas_pm_driving_can_drive	Can the player drive a car?
mas_pm_driving_learning	If the player cannot drive, are they learning?
mas_pm_driving_been_in_accident	Has the player been in a car accident while driving?
#mas_pm_driving_post_accident	If the player has been in an accident, do they still drive much?
mas_pm_donate_charity	Has the player donated to charity before?
mas_pm_volunteer_charity	Has the player volunteered for a charity before?
mas_pm_have_fam	Does the player have a family?
mas_pm_no_fam_bother	If the player does not have a family, does that bother them?
mas_pm_have_fam_mess	Is the player's family life messy/bad?
mas_pm_have_fam_mess_better	Not true/false. "YES"/"NO"/"MAYBE" if the player thinks things will get better with their family.
mas_pm_have_fam_sibs	Does the player have siblings?
mas_pm_no_talk_fam	The player has specified they do not want to talk about their family.
mas_pm_fam_like_monika	Does the player think their family would like Monika?
mas_pm_gone_to_prom	Did the player attend prom?
mas_pm_no_prom	Player has specified that their school did not have a prom.
mas_pm_prom_good	Did the player have a good time at prom?
#mas_pm_had_prom_date	Did the player have a prom date?
mas_pm_prom_monika	Player has specified they would have had a better time at prom if Monika was there.
mas_pm_prom_not_interested	Player has specified they were not interested in prom.
mas_pm_prom_shy	If the player was not interested in prom, is it because they were too shy?
mas_pm_has_been_to_amusement_park	Has the player ever been to an amusement park?
mas_pm_likes_travelling	Does the player like to travel?
mas_pm_had_relationships_many	Has the player had multiple relationships before Monika?
mas_pm_had_relationships_just_one	Has the player had just one relationship before Monika?
mas_pm_read_yellow_wp	Has the player read the story The Yellow Wallpaper?
mas_pm_monika_evil	Does the player think Monika's actions were evil?
mas_pm_monika_evil_but_ok	Player has specified that even though her actions were evil, they forgive/love her.
mas_pm_is_bullying_victim	Has the player been bullied?
mas_pm_has_bullied_people	Has the player bullied others before?
mas_pm_currently_bullied	Is the player currently being bullied?
mas_pm_has_friends	Does the player have friends?
mas_pm_few_friends	Player has specified they only have a few friends.
mas_pm_feels_lonely_sometimes	Does the player sometimes feel lonely?
mas_pm_listened_to_grad_speech	Has the player heard Monika's graduate speech? This is set to False if they ignored it.
#mas_grad_speech_timed_out	Set to true only if the player has ignored Monika's graduate speech twice.
mas_pm_liked_grad_speech	Did the player like Monika's graduation speech?
mas_pm_given_false_justice	Has the player been delivered false justice before?
#mas_pm_monika_deletion_justice	Does the player think that Monika being deleted by so many people was justice?
#mas_monika_deletion_justice_kidding	Monika believes player was teasing/joking when they said deleting her was justice.
mas_pm_would_come_to_spaceroom	Would the player take the chance to go to Monika's world? Set to None if they cannot answer.
mas_pm_owns_car	Does the player own a car?
mas_pm_owns_car_type	Not true/false. Type of vehicle player owns. For list of options, see monika_vehicle.
mas_pm_has_code_experience	Does the player have experience coding?
mas_pm_likes_poetry	Does the player like to read poetry?
mas_pm_likes_board_games	Does the player like board games?
mas_pm_works_out	Does the player work out much?
mas_pm_social_personality	Not true/false. Player's social personality. mas_SP_EXTROVERT/mas_SP_INTROVERT/mas_SP_AMBIVERT/mas_SP_UNSURE
mas_pm_likes_nature	Does the player like nature?
mas_pm_swear_frequency	Not true/false. Frequency of player's swearing: SF_OFTEN/SF_SOMETIMES/SF_NEVER
mas_gender == " "	"M" for male "F" for female and "X" for Gender Neutral

_mas_bday_said_happybday
_mas_f14_spent_f14
_mas_nye_spent_nye
_mas_player_bday_spent_time
_mas_d25_spent_d25
_mas_o31_tt_count


"""
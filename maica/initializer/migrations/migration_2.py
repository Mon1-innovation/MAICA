import asyncio
import os
from typing import *
from maica.maica_utils import *

upper_version = "1.2.000.rc2"

async def migrate():

    maica_pool = await ConnUtils.maica_pool()
    try:
        if maica_pool.db_type == 'mysql':
            await maica_pool.query_modify('ALTER TABLE `account_status` CHANGE `status` `status` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL; ')
            await maica_pool.query_modify('ALTER TABLE `account_status` CHANGE `preferences` `preferences` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL; ')
            await maica_pool.query_modify('ALTER TABLE `ms_cache` CHANGE `hash` `hash` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL; ')
            await maica_pool.query_modify('ALTER TABLE `ms_cache` CHANGE `content` `content` TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL; ')
            await maica_pool.query_modify("""
CREATE TABLE IF NOT EXISTS `mv_meta` (
  `vista_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `uuid` text NOT NULL,
  `timestamp` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`vista_id`)
)
                                        """)
        else:
            await maica_pool.query_modify("""
CREATE TABLE IF NOT EXISTS mv_meta (
  vista_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  uuid TEXT NOT NULL,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
                                        """)
            await maica_pool.query_modify("""
CREATE TRIGGER IF NOT EXISTS update_timestamp_mv_meta
AFTER UPDATE ON mv_meta
FOR EACH ROW
BEGIN
    UPDATE mv_meta
    SET timestamp = CURRENT_TIMESTAMP
    WHERE vista_id = OLD.vista_id;
END;
                                        """)

    except Exception as e:
        raise MaicaDbWarning(f'Couldn\'t alter lines LONGTEXT to TEXT and add table mv_meta: {str(e)}, maybe manually done already?') from e
    finally:
        await maica_pool.close()

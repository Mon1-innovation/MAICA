import asyncio
from maica_utils import DbPoolCoroutine, ConnUtils
from typing import *
from maica_utils import *

async def create_tables():

    AUTH_DB = load_env('AUTH_DB')
    MAICA_DB = load_env('MAICA_DB')

    basic_pool: DbPoolCoroutine = await ConnUtils.basic_pool()

    if basic_pool:
        # We have to create databases before tables
        result = await basic_pool.query_get("SHOW DATABASES", fetchall=True)
        curr_dbs = []; auth_created = False
        for curr_db in result:
            curr_dbs.append(curr_db[0])

        if not AUTH_DB in curr_dbs:
            print(f"AUTH_DB {AUTH_DB} does not exist, creating...")
            await basic_pool.query_modify(f"CREATE DATABASE IF NOT EXISTS {AUTH_DB}")
            auth_created = True
        else:
            print(f"AUTH_DB {AUTH_DB} exists, skipping...")

        if not MAICA_DB in curr_dbs:
            print(f"MAICA_DB {MAICA_DB} does not exist, creating...")
            await basic_pool.query_modify(f"CREATE DATABASE IF NOT EXISTS {MAICA_DB}")
        else:
            print(f"MAICA_DB {MAICA_DB} exists, skipping...")

    auth_pool = await ConnUtils.auth_pool(ro=False)
    maica_pool = await ConnUtils.maica_pool()

    auth_tables = [
"""
CREATE TABLE IF NOT EXISTS `users` (
`id` int(10) unsigned NOT NULL AUTO_INCREMENT,
`username` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
`nickname` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
`email` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
`is_email_confirmed` tinyint(1) NOT NULL DEFAULT '0',
`password` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""
    ]
    maica_tables = [
"""
CREATE TABLE IF NOT EXISTS `account_status` (
`user_id` int(11) NOT NULL,
`status` longtext DEFAULT NULL,
`preferences` longtext DEFAULT NULL,
PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE IF NOT EXISTS `cchop_archived` (
`archive_id` int(11) NOT NULL AUTO_INCREMENT,
`chat_session_id` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
`archived` int(11) DEFAULT NULL,
PRIMARY KEY (`archive_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE IF NOT EXISTS `chat_session` (
`chat_session_id` int(11) NOT NULL AUTO_INCREMENT,
`user_id` int(11) NOT NULL,
`chat_session_num` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
PRIMARY KEY (`chat_session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE IF NOT EXISTS `csession_archived` (
`archive_id` int(11) NOT NULL AUTO_INCREMENT,
`chat_session_id` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
PRIMARY KEY (`archive_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE IF NOT EXISTS `persistents` (
`persistent_id` int(11) NOT NULL AUTO_INCREMENT,
`user_id` int(11) NOT NULL,
`chat_session_num` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
`timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (`persistent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE IF NOT EXISTS `triggers` (
`trigger_id` int(11) NOT NULL AUTO_INCREMENT,
`user_id` int(11) NOT NULL,
`chat_session_num` int(11) NOT NULL,
`content` longtext DEFAULT NULL,
`timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (`trigger_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE IF NOT EXISTS `ms_cache` (
`spire_id` int(11) NOT NULL AUTO_INCREMENT,
`hash` longtext NOT NULL,
`content` longtext DEFAULT NULL,
`timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (`spire_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
    ]

    if auth_created:
        for table in auth_tables:
            print("Adding table to AUTH_DB...")
            await auth_pool.query_modify(table)
    else:
        print("Warning: AUTH_DB was not created by MAICA, so we're not writing anything for security reason.\nPlease make sure AUTH_DB is already ready for authentication.")

    for table in maica_tables:
        print("Adding table to MAICA_DB...")
        await maica_pool.query_modify(table)

if __name__ == "__main__":
    asyncio.run(create_tables())
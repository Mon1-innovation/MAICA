import asyncio
import aiomysql
from typing import *
from maica_utils import *

async def create_tables(maica_pool: DbPoolCoroutine):
    tables = [
"""
CREATE TABLE `account_status` (
  `user_id` int(11) NOT NULL,
  `status` longtext DEFAULT NULL,
  `preferences` longtext DEFAULT NULL,
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE `cchop_archived` (
  `archive_id` int(11) NOT NULL AUTO_INCREMENT,
  `chat_session_id` int(11) NOT NULL,
  `content` longtext DEFAULT NULL,
  `archived` int(11) DEFAULT NULL,
  PRIMARY KEY (`archive_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE `chat_session` (
  `chat_session_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `chat_session_num` int(11) NOT NULL,
  `content` longtext DEFAULT NULL,
  PRIMARY KEY (`chat_session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE `csession_archived` (
  `archive_id` int(11) NOT NULL AUTO_INCREMENT,
  `chat_session_id` int(11) NOT NULL,
  `content` longtext DEFAULT NULL,
  PRIMARY KEY (`archive_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE `persistents` (
  `persistent_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `chat_session_num` int(11) NOT NULL,
  `content` longtext DEFAULT NULL,
  `timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`persistent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE `triggers` (
  `trigger_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `chat_session_num` int(11) NOT NULL,
  `content` longtext DEFAULT NULL,
  `timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`trigger_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""",
"""
CREATE TABLE `ms_cache` (
  `spire_id` int(11) NOT NULL AUTO_INCREMENT,
  `hash` longtext NOT NULL,
  `content` longtext DEFAULT NULL,
  `timestamp` datetime on update CURRENT_TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`spire_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
    ]
    for table in tables:
        await maica_pool.query_modify(table)

import nest_asyncio
nest_asyncio.apply()
import asyncio
import aiomysql
from loadenv import load_env

class poolinit_instance():

    def __init__(
        self,
        host = load_env('DB_ADDR'), 
        user = load_env('DB_USER'),
        password = load_env('DB_PASSWORD'),
        authdb = load_env('AUTHENTICATOR_DB'),
        maicadb = load_env('MAICA_DB'),
        login = load_env('LOGIN_VERIFICATION'),
        test = False
    ):
        self.host, self.user, self.password, self.authdb, self.maicadb, self.login, self.test = host, user, password, authdb, maicadb, login, test
        asyncio.run(self.create_db())
        asyncio.run(self.create_pool())
        asyncio.run(self.create_tables())
    
    async def create_db(self):
        async with aiomysql.connect(host=self.host,user=self.user, password=self.password,db=None,autocommit=True) as basic_conn:
            async with basic_conn.cursor() as basic_cur:
                await basic_cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.maicadb}`")

    async def create_pool(self):
        self.loop = asyncio.get_event_loop()
        self.maicapool = await aiomysql.create_pool(host=self.host, user=self.user, password=self.password, loop=self.loop, db=self.maicadb, autocommit=True)
    
    async def send_modify(self, expression):
        pool = self.maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(expression)
                await conn.commit()
        return
    
    async def create_tables(self):
        pool = self.maicapool
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
"""
CREATE TABLE `account_status` (
  `crid_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `status` longtext,
  `preferences` longtext,
  PRIMARY KEY (`crid_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
                )
                await cur.execute(
"""
CREATE TABLE `cchop_archived` (
  `archive_id` int(11) NOT NULL AUTO_INCREMENT,
  `chat_session_id` int(11) NOT NULL,
  `content` longtext NOT NULL,
  `archived` int(11) DEFAULT NULL,
  PRIMARY KEY (`archive_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
                )
                await cur.execute(
"""
CREATE TABLE `chat_session` (
  `chat_session_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `chat_session_num` int(11) NOT NULL,
  `content` longtext NOT NULL,
  PRIMARY KEY (`chat_session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
                )
                await cur.execute(
"""
CREATE TABLE `csession_archived` (
  `archive_id` int(11) NOT NULL AUTO_INCREMENT,
  `chat_session_id` int(11) NOT NULL,
  `content` longtext NOT NULL,
  PRIMARY KEY (`archive_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
                )
                await cur.execute(
"""
CREATE TABLE `persistents` (
  `persistent_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `chat_session_num` int(11) NOT NULL,
  `content` longtext NOT NULL,
  PRIMARY KEY (`persistent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
                )
                await cur.execute(
"""
CREATE TABLE `triggers` (
  `trigger_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `chat_session_num` int(11) NOT NULL,
  `content` longtext NOT NULL,
  PRIMARY KEY (`trigger_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""
                )

if __name__ == "__main__":
    i = poolinit_instance()

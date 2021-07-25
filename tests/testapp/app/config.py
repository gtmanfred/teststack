import figenv


class Config(metaclass=figenv.MetaConfig):
    POSTGRES_MAIN_USER = 'testapp'
    POSTGRES_MAIN_PASSWORD = 'secret'
    POSTGRES_MAIN_HOST = 'localhost'
    POSTGRES_MAIN_PORT = 5432
    POSTGRES_MAIN_DBNAME = 'app'

    def SQLALCHEMY_DATABASE_URI(cls):
        return 'postgresql://{user}:{password}@{host}:{port}/{dbname}?sslmode=prefer'.format(
            user=cls.POSTGRES_MAIN_USER,
            password=cls.POSTGRES_MAIN_PASSWORD,
            host=cls.POSTGRES_MAIN_HOST,
            port=cls.POSTGRES_MAIN_PORT,
            dbname=cls.POSTGRES_MAIN_DBNAME,
        )

    CACHE_TYPE = 'RedisCache'
    REDIS_MAIN_HOST = 'localhost'
    REDIS_MAIN_PORT = 6379

    def CACHE_REDIS_URL(cls):
        return 'redis://@{host}:{port}/0'.format(
            host=cls.REDIS_MAIN_HOST,
            port=cls.REDIS_MAIN_PORT,
        )

import dotenv
import pydantic

dotenv.load_dotenv()


class Settings(pydantic.BaseSettings):
    service_name: str = 'django'
    core_channel_number: int
    external_server_port: int
    external_server_address: str

    internal_server_port: int
    internal_server_address: str

    jwt_secret_key: str
    jwt_algorithm: str

    local_files_root: str
    docker_files_root: str

    run_alembic: bool

    sql_dialect: str
    sql_user: str
    sql_password: str
    sql_host: str
    sql_port: str
    sql_database: str

    amqp_user: str
    amqp_password: str
    amqp_host: str
    amqp_port: int

    alembic_debug: bool = True
    auto_apply_migrations: bool = True
    is_first_start: bool = False

    local_files_root: str
    docker_files_root: str

    @property
    def files_root(self) -> str:
        if self.alembic_debug:
            return self.local_files_root
        else:
            return self.docker_files_root

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False


settings = Settings()

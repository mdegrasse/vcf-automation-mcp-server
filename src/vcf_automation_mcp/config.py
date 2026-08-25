from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VCFA_", env_file=".env", extra="ignore")

    base_url: str
    refresh_token: str
    # Tenant org name (e.g. the VM Apps org from Provider Management). Leave unset to
    # authenticate at the provider ("system") level instead of a tenant organization.
    org: str | None = None
    # Override the computed token endpoint if your instance's OAuth path differs from
    # the documented default (VCF Automation's token exchange path has varied across
    # releases/deployments).
    token_url: str | None = None
    verify_ssl: bool = True
    timeout: float = 30.0

    # Each VCF Automation service versions its API independently via ?apiVersion=.
    api_version_iaas: str = "2021-07-15"
    api_version_catalog: str = "2020-08-25"
    api_version_deployment: str = "2020-08-25"


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VCFA_MCP_", env_file=".env", extra="ignore")

    transport: Literal["stdio", "streamable-http"] = "streamable-http"
    host: str = "127.0.0.1"
    port: int = 8000
    bearer_token: str | None = None
    allowed_hosts: Annotated[list[str], NoDecode] = []

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value


def load_settings() -> Settings:
    return Settings()


def load_server_settings() -> ServerSettings:
    return ServerSettings()

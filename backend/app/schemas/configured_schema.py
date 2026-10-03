from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ConfiguredSchema(BaseModel):

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
    )

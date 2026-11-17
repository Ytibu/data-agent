from dataclasses import dataclass
from pathlib import Path
from omegaconf import OmegaConf

@dataclass
class UserInfo:
    name: str
    age: int
    height: float

@dataclass
class MyConfig:
    user: UserInfo
    fav: list[str]

config_path = Path(__file__).parents[2] / 'conf' / 'test_config.yaml'
context = OmegaConf.load(config_path)
structured = OmegaConf.structured(MyConfig)
merge = OmegaConf.merge(structured, context)

conf_to_object:UserInfo = OmegaConf.to_object(merge)

print(conf_to_object)
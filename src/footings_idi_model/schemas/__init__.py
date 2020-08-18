import os

import pandas as pd
import yaml

directory, filename = os.path.split(__file__)


def get_categories(df, name):
    return df[df["name"] == name]["allowed"].explode().to_list()


#########################################################################################
# disabled lives
#########################################################################################


with open(os.path.join(directory, "extract-disabled-lives.yaml")) as file:
    disabled_life_schema = yaml.safe_load(file)
df_disabled_life = pd.DataFrame.from_dict(disabled_life_schema["columns"])
disabled_life_columns = df_disabled_life["name"]

CAT_DIS_GENDER = get_categories(df_disabled_life, "GENDER")
CAT_DIS_IDI_OCCUPATION = get_categories(df_disabled_life, "IDI_OCCUPATION_CLASS")
CAT_DIS_IDI_CONTRACT = get_categories(df_disabled_life, "IDI_CONTRACT")
CAT_DIS_IDI_BENEFIT_PERIOD = get_categories(df_disabled_life, "IDI_BENEFIT_PERIOD")
CAT_DIS_IDI_MARKET = get_categories(df_disabled_life, "IDI_MARKET")
CAT_DIS_IDI_DIAGNOSIS_GRP = get_categories(df_disabled_life, "IDI_DIAGNOSIS_GRP")


#########################################################################################
# disabled lives
#########################################################################################


with open(os.path.join(directory, "extract-active-lives-base.yaml")) as file:
    active_lives_base_schema = yaml.safe_load(file)
active_lives_base_columns = pd.DataFrame.from_dict(active_lives_base_schema["columns"])[
    "name"
]

with open(os.path.join(directory, "extract-active-lives-riders.yaml")) as file:
    active_lives_rider_schema = yaml.safe_load(file)
active_lives_rider_columns = pd.DataFrame.from_dict(active_lives_rider_schema["columns"])[
    "name"
]

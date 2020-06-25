import numpy as np
import pandas as pd

from footings import create_dispatch_function

from ..schemas import disabled_life_columns, active_life_columns

#########################################################################################
# functions
#########################################################################################

create_frame = create_dispatch_function("create_frame", parameters=("extract_type",))


@create_frame.register(extract_type="disabled-lives")
def _(n):
    policy_ids = [f"M{i}" for i in range(1, n + 1)]
    claim_ids = [f"{p}C1" for p in policy_ids]
    frame = pd.DataFrame({"POLICY_ID": policy_ids, "CLAIM_ID": claim_ids})
    frame["COVERAGE_ID"] = "base"
    return frame


@create_frame.register(extract_type="active-lives")
def _(n):
    policy_ids = [f"M{i}" for i in range(1, n + 1)]
    frame = pd.DataFrame({"POLICY_ID": policy_ids})
    frame["COVERAGE_ID"] = "base"
    return frame


def sample_from_volume_tbl(frame, volume_tbl, seed):
    """Sample from volume table"""
    np.random.seed(seed)
    frame = frame.copy()
    volume_tbl = volume_tbl.copy()
    frame["WT"] = np.random.uniform(size=frame.shape[0])
    cols = set(frame.columns)
    frame.reset_index(inplace=True)
    cols_added = set(frame.columns) - cols
    frame.sort_values(["WT"], inplace=True)
    total_wt = sum(volume_tbl["WT"])
    volume_tbl["WT"] = volume_tbl["WT"].cumsum() / total_wt
    frame = pd.merge_asof(frame, volume_tbl, on=["WT"]).drop(["WT"], axis=1)
    frame.sort_values(list(cols_added), inplace=True)
    return frame.drop(list(cols_added), axis=1).reset_index(drop=True)


def add_benefit_amount(frame):
    "Add benefit amount" ""
    return frame.assign(BENEFIT_AMOUNT=100.0)


def _calculate_age(frame, low, high):
    return np.random.uniform(low=low, high=high, size=frame.shape[0])


def _calculate_termination_age(frame, base_age):
    # calculate termination age
    benefit_period = frame["IDI_BENEFIT_PERIOD"].values.astype(str)
    cond_list_1 = [np.char.endswith(benefit_period, "M")]
    choice_list_1 = [np.char.strip(benefit_period, "M")]
    years_add = np.select(cond_list_1, choice_list_1).astype(int) / 1200

    cond_list_2 = [
        np.char.find(benefit_period, "TO") >= 0,
        np.char.find(benefit_period, "LIFE") >= 0,
    ]
    choice_list_2 = [np.char.strip(benefit_period, "TO"), 120]
    end_year = np.select(cond_list_2, choice_list_2).astype(int) / 100

    cond_list_3 = [years_add > 0, end_year > 0]
    choice_list_3 = [base_age + years_add, end_year]
    return np.select(cond_list_3, choice_list_3)


calculate_ages = create_dispatch_function("calculate-ages", parameters=("extract_type",))


@calculate_ages.register(extract_type="disabled-lives")
def _(frame, seed):
    np.random.seed(seed)

    incurred_age = _calculate_age(frame, 0.25, 0.6)
    termination_age = _calculate_termination_age(frame, incurred_age)
    current_age = _calculate_age(frame, incurred_age, termination_age)

    # assign to frame
    frame["CURRENT_AGE"] = current_age * 100
    frame["INCURRED_AGE"] = incurred_age * 100
    frame["TERMINATION_AGE"] = termination_age * 100
    return frame


@calculate_ages.register(extract_type="active-lives")
def _(frame, seed):
    np.random.seed(seed)
    issue_age = _calculate_age(frame, 0.25, 0.6)
    frame["ISSUE_AGE"] = issue_age * 100
    frame["CURRENT_AGE"] = _calculate_age(frame, issue_age, 0.62) * 100
    return frame


def _birth_date_add_years(birth_dt, years):
    """Add years to birth date"""
    return pd.to_datetime(
        {
            "year": birth_dt.dt.year + years,
            "month": birth_dt.dt.month,
            "day": birth_dt.dt.day,
        }
    )


def _incurred_date_add_months(incurred_dt, months):
    """Add months to incurred date"""
    whole_years = months // 12
    months_remaining = months % 12
    months = incurred_dt.dt.month + months_remaining
    cross_year = months // 12
    months = np.select([months % 12 != 0, months % 12 == 0], [months % 12, 12])
    days = incurred_dt.dt.day
    cond_list = [
        (months == 2) & (days > 28),
        (months == 4) & (days > 30),
        (months == 6) & (days > 30),
        (months == 9) & (days > 30),
        (months == 11) & (days > 30),
    ]
    choice_list = [28, 30, 30, 30, 30]
    days = np.select(cond_list, choice_list, default=days)
    df = pd.DataFrame(
        {
            "year": incurred_dt.dt.year + whole_years + cross_year,
            "month": months,
            "day": days,
        }
    )

    return pd.to_datetime(df)


calculate_dates = create_dispatch_function(
    "calculate_dates", parameters=("extract_type",)
)


@calculate_dates.register(extract_type="disabled-lives")
def _(frame, as_of_dt):

    # calculate birth date
    days_from_birth = frame["CURRENT_AGE"].values * 365.25

    frame["BIRTH_DT"] = as_of_dt - pd.to_timedelta(days_from_birth, unit="D").round("D")
    # move any birth on leap year to the 28th
    leap_dts = (frame["BIRTH_DT"].dt.month == 2) & (frame["BIRTH_DT"].dt.day == 29)
    frame.loc[leap_dts, "BIRTH_DT"] = frame[leap_dts]["BIRTH_DT"] - pd.offsets.Day(1)

    # calculate incurred date
    frame["INCURRED_DT"] = (
        frame["BIRTH_DT"] + pd.to_timedelta(frame["INCURRED_AGE"] * 365.25, unit="D")
    ).dt.round("D")

    # calculate termination date for benefits with monthly benefit period
    frame_add_months = frame[frame["IDI_BENEFIT_PERIOD"].str[-1] == "M"]
    indexes = frame.index & frame_add_months.index
    frame.loc[indexes, "TERMINATION_DT"] = _incurred_date_add_months(
        frame_add_months["INCURRED_DT"],
        frame_add_months["IDI_BENEFIT_PERIOD"].str.replace("M", "").astype(int),
    )

    # calculate termination date for toage benefits
    frame_add_years = frame[frame["IDI_BENEFIT_PERIOD"].str[-1] != "M"]
    indexes = frame.index & frame_add_years.index
    frame.loc[indexes, "TERMINATION_DT"] = _birth_date_add_years(
        frame_add_years["BIRTH_DT"], frame_add_years["TERMINATION_AGE"].astype(int)
    )

    return frame.drop(["CURRENT_AGE", "INCURRED_AGE", "TERMINATION_AGE"], axis=1)


@calculate_dates.register(extract_type="active-lives")
def _(frame, as_of_dt):
    # calculate birth date
    days_from_birth = frame["CURRENT_AGE"].values * 365.25
    frame["BIRTH_DT"] = as_of_dt - pd.to_timedelta(days_from_birth, unit="D").round("D")

    # move any birth on leap year to the 28th
    leap_dts = (frame["BIRTH_DT"].dt.month == 2) & (frame["BIRTH_DT"].dt.day == 29)
    frame.loc[leap_dts, "BIRTH_DT"] = frame[leap_dts]["BIRTH_DT"] - pd.offsets.Day(1)

    # calculate issue date
    days_from_issue = frame["ISSUE_AGE"].values * 365.25
    frame["ISSUE_DT"] = as_of_dt - pd.to_timedelta(days_from_issue, unit="D").round("D")

    # calculate termination date for benefits with monthly benefit period
    cond_list = [
        (frame["IDI_BENEFIT_PERIOD"].str[:2] != "TO").values,
        (frame["IDI_BENEFIT_PERIOD"].str[-2:] == "65").values,
        (frame["IDI_BENEFIT_PERIOD"].str[-2:] == "67").values,
        (frame["IDI_BENEFIT_PERIOD"].str[-2:] == "70").values,
    ]

    choice_list = [
        _birth_date_add_years(frame["BIRTH_DT"], 65).values.astype(str),
        _birth_date_add_years(frame["BIRTH_DT"], 65).values.astype(str),
        _birth_date_add_years(frame["BIRTH_DT"], 67).values.astype(str),
        _birth_date_add_years(frame["BIRTH_DT"], 70).values.astype(str),
    ]

    frame["TERMINATION_DT"] = pd.to_datetime(np.select(cond_list, choice_list))

    return frame.drop(["CURRENT_AGE"], axis=1)


finalize_extract = create_dispatch_function(
    "finalize_extract", parameters=("extract_type",)
)


@finalize_extract.register(extract_type="disabled-lives")
def _(frame):
    frame["PAID_TO_DT"] = pd.NA
    return frame[disabled_life_columns]


@finalize_extract.register(extract_type="active-lives")
def _(frame):
    return frame[active_life_columns]
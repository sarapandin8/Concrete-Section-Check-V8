from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_TD_CURING_END_AGE_DAYS_KEY,
    CB_LOSS_TD_DEFAULTS_RESTORED_NOTICE_KEY,
    CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY,
    CB_LOSS_TD_FINAL_AGE_DAYS_KEY,
    CB_LOSS_TD_GROUT_AGE_DAYS_KEY,
    CB_LOSS_TD_LOAD_AGE_DAYS_KEY,
    CB_LOSS_TD_NO_LATER_EVENTS_CONFIRMED_KEY,
    CB_LOSS_TD_RH_PERCENT_KEY,
    CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
    DEFAULT_TD_CURING_END_AGE_DAYS,
    DEFAULT_TD_FALSEWORK_REMOVAL_AGE_DAYS,
    DEFAULT_TD_FINAL_AGE_DAYS,
    DEFAULT_TD_GROUT_AGE_DAYS,
    DEFAULT_TD_LOAD_AGE_DAYS,
    DEFAULT_TD_RH_PERCENT,
    default_crossbeam_prestress_loss_settings,
    restore_crossbeam_prestress_loss_project_state,
)


def test_general_practice_td_defaults_are_explicit():
    values = default_crossbeam_prestress_loss_settings()
    assert values["td_rh_percent"] == 75.0
    assert values["td_curing_end_age_days"] == 7.0
    assert values["td_load_age_days"] == 28.0
    assert values["td_grout_age_days"] == 28.0
    assert values["td_falsework_removal_age_days"] == 35.0
    assert values["td_final_age_days"] == 18250.0
    assert values["td_no_later_events_confirmed"] is False


def test_invalid_legacy_zero_schedule_is_migrated_without_confirming_no_events():
    state = {}
    metadata = {
        CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY: {
            "td_rh_percent": 1.0,
            "td_curing_end_age_days": 0.0,
            "td_load_age_days": 0.0,
            "td_grout_age_days": 0.0,
            "td_falsework_removal_age_days": 0.0,
            "td_final_age_days": 0.0,
            "td_no_later_events_confirmed": True,
        }
    }
    restore_crossbeam_prestress_loss_project_state(metadata, state)
    assert state[CB_LOSS_TD_RH_PERCENT_KEY] == DEFAULT_TD_RH_PERCENT
    assert state[CB_LOSS_TD_CURING_END_AGE_DAYS_KEY] == DEFAULT_TD_CURING_END_AGE_DAYS
    assert state[CB_LOSS_TD_LOAD_AGE_DAYS_KEY] == DEFAULT_TD_LOAD_AGE_DAYS
    assert state[CB_LOSS_TD_GROUT_AGE_DAYS_KEY] == DEFAULT_TD_GROUT_AGE_DAYS
    assert state[CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY] == DEFAULT_TD_FALSEWORK_REMOVAL_AGE_DAYS
    assert state[CB_LOSS_TD_FINAL_AGE_DAYS_KEY] == DEFAULT_TD_FINAL_AGE_DAYS
    assert state[CB_LOSS_TD_NO_LATER_EVENTS_CONFIRMED_KEY] is False
    assert state[CB_LOSS_TD_DEFAULTS_RESTORED_NOTICE_KEY] is True

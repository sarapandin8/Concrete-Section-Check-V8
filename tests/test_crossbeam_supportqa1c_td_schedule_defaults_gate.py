from concrete_pmm_pro.crossbeam.prestress_loss import (
    CB_LOSS_TD_CURING_END_AGE_DAYS_KEY,
    CB_LOSS_TD_DEFAULTS_RESTORED_NOTICE_KEY,
    CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY,
    CB_LOSS_TD_FINAL_AGE_DAYS_KEY,
    CB_LOSS_TD_GROUT_AGE_DAYS_KEY,
    CB_LOSS_TD_LOAD_AGE_DAYS_KEY,
    CB_LOSS_TD_NO_LATER_EVENTS_CONFIRMED_KEY,
    CB_LOSS_TD_RH_PERCENT_KEY,
    CB_LOSS_TD_INPUT_SETTINGS_KEY,
    CROSSBEAM_PRESTRESS_LOSS_METADATA_KEY,
    DEFAULT_TD_CURING_END_AGE_DAYS,
    DEFAULT_TD_FALSEWORK_REMOVAL_AGE_DAYS,
    DEFAULT_TD_FINAL_AGE_DAYS,
    DEFAULT_TD_GROUT_AGE_DAYS,
    DEFAULT_TD_LOAD_AGE_DAYS,
    DEFAULT_TD_RH_PERCENT,
    default_crossbeam_prestress_loss_settings,
    crossbeam_prestress_loss_settings_from_session_state,
    persist_crossbeam_td_input_settings,
    reset_crossbeam_td_input_settings,
    restore_crossbeam_prestress_loss_project_state,
)
from concrete_pmm_pro.ui import crossbeam_pages


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


def test_td_inputs_restore_from_durable_state_after_streamlit_widget_cleanup():
    state = {
        CB_LOSS_TD_RH_PERCENT_KEY: 82.0,
        CB_LOSS_TD_CURING_END_AGE_DAYS_KEY: 10.0,
        CB_LOSS_TD_LOAD_AGE_DAYS_KEY: 30.0,
        CB_LOSS_TD_GROUT_AGE_DAYS_KEY: 31.0,
        CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY: 40.0,
        CB_LOSS_TD_FINAL_AGE_DAYS_KEY: 36500.0,
        CB_LOSS_TD_NO_LATER_EVENTS_CONFIRMED_KEY: True,
    }
    persist_crossbeam_td_input_settings(state)
    durable = dict(state[CB_LOSS_TD_INPUT_SETTINGS_KEY])

    for key in (
        CB_LOSS_TD_RH_PERCENT_KEY,
        CB_LOSS_TD_CURING_END_AGE_DAYS_KEY,
        CB_LOSS_TD_LOAD_AGE_DAYS_KEY,
        CB_LOSS_TD_GROUT_AGE_DAYS_KEY,
        CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY,
        CB_LOSS_TD_FINAL_AGE_DAYS_KEY,
        CB_LOSS_TD_NO_LATER_EVENTS_CONFIRMED_KEY,
    ):
        state.pop(key, None)

    crossbeam_pages._initialize_crossbeam_td_session_defaults(
        state, default_crossbeam_prestress_loss_settings()
    )

    assert state[CB_LOSS_TD_RH_PERCENT_KEY] == 82.0
    assert state[CB_LOSS_TD_CURING_END_AGE_DAYS_KEY] == 10.0
    assert state[CB_LOSS_TD_LOAD_AGE_DAYS_KEY] == 30.0
    assert state[CB_LOSS_TD_GROUT_AGE_DAYS_KEY] == 31.0
    assert state[CB_LOSS_TD_FALSEWORK_REMOVAL_AGE_DAYS_KEY] == 40.0
    assert state[CB_LOSS_TD_FINAL_AGE_DAYS_KEY] == 36500.0
    assert state[CB_LOSS_TD_NO_LATER_EVENTS_CONFIRMED_KEY] is True
    assert state[CB_LOSS_TD_INPUT_SETTINGS_KEY] == durable


def test_project_metadata_uses_durable_td_inputs_when_widgets_are_off_page():
    state = {
        CB_LOSS_TD_INPUT_SETTINGS_KEY: {
            **default_crossbeam_prestress_loss_settings(),
            "td_rh_percent": 81.0,
            "td_final_age_days": 27375.0,
            "td_no_later_events_confirmed": True,
        }
    }

    metadata = crossbeam_prestress_loss_settings_from_session_state(state)

    assert metadata["td_rh_percent"] == 81.0
    assert metadata["td_final_age_days"] == 27375.0
    assert metadata["td_no_later_events_confirmed"] is True


def test_reset_td_defaults_preserves_unrelated_imported_event_state():
    state = {
        CB_LOSS_TD_RH_PERCENT_KEY: 66.0,
        CB_LOSS_TD_FINAL_AGE_DAYS_KEY: 36500.0,
        CB_LOSS_TD_NO_LATER_EVENTS_CONFIRMED_KEY: True,
        "crossbeam_ptloss4b3b_permanent_event_schedule": [{"Event": "PL1"}],
        "crossbeam_ptloss4b3a_later_fea_response_table": [{"Case Name": "SDL"}],
    }

    reset = reset_crossbeam_td_input_settings(state)

    assert reset["td_rh_percent"] == DEFAULT_TD_RH_PERCENT
    assert reset["td_final_age_days"] == DEFAULT_TD_FINAL_AGE_DAYS
    assert reset["td_no_later_events_confirmed"] is False
    assert state["crossbeam_ptloss4b3b_permanent_event_schedule"] == [{"Event": "PL1"}]
    assert state["crossbeam_ptloss4b3a_later_fea_response_table"] == [{"Case Name": "SDL"}]


def test_td_ui_uses_explicit_adoption_buttons_instead_of_a_checkbox():
    source = open("concrete_pmm_pro/ui/crossbeam_pages.py", encoding="utf-8").read()
    block = source.split("with time_dependent_tab:", 1)[1].split("with audit_tab:", 1)[0]

    assert "Permanent-load schedule adoption decision" in block
    assert "Confirm no later permanent events" in block
    assert "Revoke confirmation" in block
    assert '"Confirm that no later permanent-load event applies before final service"' not in block
    assert '"Reset to defaults"' in block

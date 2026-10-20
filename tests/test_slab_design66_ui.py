"""One primary command; proposal review cannot replace applied input results."""
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd

from concrete_pmm_pro.analysis import slab_design66 as design, slab_top65 as actual
from test_slab_top65_ui import app,clean


def test_proposal_is_folded_and_read_only_through_filters_and_report():
    test=app()
    with patch.object(design,'propose',wraps=design.propose) as solver:
        clean(test)
        before=deepcopy(test.session_state['section_parameters'])
        test.button(key='slab_shell55_aashto62_calculate').click();clean(test)
        assert solver.call_count==1
        result=test.session_state[design.RESULT_KEY]
        assert not result['reinforcement_proposal']['applied_to_project']
        assert test.session_state['section_parameters']==before
        assert any(e.label=='Suggested bar spacing · not applied' for e in test.expander)
        pd.testing.assert_frame_equal(result['summary'],test.session_state[actual.RESULT_KEY]['summary'])
        test.selectbox(key='slab_shell55_top65_chart').set_value('Station D/C');clean(test)
        test.button(key='slab_shell55_top65_prepare_report').click();clean(test)
        assert solver.call_count==1 and len(test.get('plotly_chart'))==1
        with ZipFile(BytesIO(test.session_state['slab_shell55_top65_report'][2])) as z:
            assert 'Current/Check_Summary.csv' in z.namelist()
            assert 'Proposal/Checked_Sections.csv' in z.namelist()


def test_ballast_form_reuses_existing_proposal_and_keeps_navigation():
    test=app()
    with patch.object(design,'propose',wraps=design.propose) as solver:
        clean(test)
        test.button(key='slab_shell55_aashto62_calculate').click();clean(test)
        test.number_input(key='slab_shell55_top65_ballast').set_value(500.)
        test.button(key='slab_shell55_aashto62_calculate').click();clean(test)
        assert solver.call_count==1
        assert test.session_state[design.RESULT_KEY]['proposal_reused']
        assert test.session_state['_nav_analysis_subpage']=='Slab Reinforcement'

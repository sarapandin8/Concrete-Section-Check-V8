"""Calculate once, then review one slab plan map with folded engineering trace."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.analysis.slab_code57 import FLEXURE_VIEW, MINIMUM_VIEW, REFERENCE_VIEWS, source_check_ledger
from concrete_pmm_pro.io.slab_shell_import import current_package
from concrete_pmm_pro.ui.commercial import render_page_header, render_metric_cards
from concrete_pmm_pro.visualization.slab_shell56 import ALL_CASES, VIEWS, element_envelope, plan_figure, view_column


def _number(value, digits=3):
    return f"{value:,.{digits}f}" if value is not None and math.isfinite(float(value)) else "Unavailable"


def _input_review():
    from concrete_pmm_pro.ui.slab_reinforcement import reinforcement_inventory
    with st.expander("Slab reinforcement / Input review",expanded=False):
        st.dataframe(reinforcement_inventory(st.session_state),hide_index=True,width="stretch",
            column_config={"As (mm²/m)":st.column_config.NumberColumn(format="%.1f")})
        st.caption("Physical top / bottom mats are read from the current project. Local CSI thickness controls bar depths; changing the girder Mn inclusion flag does not remove slab steel.")
        st.caption("Transverse bars are outside; longitudinal bars are inside. Edit the existing Section Builder / Slab mesh inputs to change provided reinforcement.")


def _trace(result, selected, *, view, case=ALL_CASES):
    column = view_column(view)
    known = selected.loc[selected[column].notna()]
    if view in REFERENCE_VIEWS and not known.empty:
        row = known.loc[known[column].idxmax()]
    elif view in REFERENCE_VIEWS:
        source = result['rows'] if case==ALL_CASES else result['rows'].loc[result['rows']['OutputCase']==case]
        row = source.loc[source['Field D/C'].idxmax()]
    else:
        row = known.loc[known[column].idxmax()] if not known.empty else pd.Series(result["governing"])
    steel = result["steel"]
    with st.expander("Calculation trace / Equations",expanded=False):
        st.markdown(f"**{view} · {row['OutputCase']} / {row['StepType']} · element {row.get('AreaElem',row.name)} · joint {row['Joint']}**")
        st.caption(f"X={row['X (m)']:.3f} m, Y={row['Y (m)']:.3f} m · local thickness {row['Thickness (mm)']:.2f} mm")
        st.markdown("**Checks at this exact source record**")
        st.dataframe(source_check_ledger(row),hide_index=True,width='stretch',
            column_config={'D/C':st.column_config.NumberColumn(format='%.3f')})
        st.dataframe(pd.DataFrame([
            {"Source":"CSI local axes","N1 (kN/m)":row['F11'],"N2 (kN/m)":row['F22'],"N12 (kN/m)":row['F12'],
                "M1 (kN·m/m)":row['M11'],"M2 (kN·m/m)":row['M22'],"M12 (kN·m/m)":row['M12'],"V1 (kN/m)":row['V13'],"V2 (kN/m)":row['V23']},
            {"Source":"Slab reinforcement axes","N1 (kN/m)":row['Nx'],"N2 (kN/m)":row['Ny'],"N12 (kN/m)":row['Nxy'],
                "M1 (kN·m/m)":row['Mx'],"M2 (kN·m/m)":row['My'],"M12 (kN·m/m)":row['Mxy'],"V1 (kN/m)":row['Vx'],"V2 (kN/m)":row['Vy']},
        ]),hide_index=True,width="stretch")
        st.latex(r"N_{ij}=\sum N_{ij,k},\qquad M_{ij}=-\sum z_kN_{ij,k}")
        st.caption("z is positive toward the physical slab top. The solver reconstructs all six N–M components at the shell midsurface; there is no force-reference translation.")
        st.latex(r"R_{s,i}=0.90 A_{s,i}f_{y,i},\qquad f_{c,field}=0.70(0.45f'_c)")
        st.caption("AASHTO 2020 component references: 5.5.4.2 and 5.8.2.5.3a. Adopting these limits in a distributed sandwich field is a stated modelling assumption, not certification of a complete STM.")
        st.caption(f"Deck f′c={steel.fc:g} MPa · adopted field compression limit={.7*.45*steel.fc:.3f} MPa · automatic face depth a={row['Face depth (mm)']:.3f} mm at both faces")
        ledger=[]
        for i,g in enumerate(engine.GROUPS):
            centre = row['Thickness (mm)']/2-steel.centre[i] if i%2==0 else -row['Thickness (mm)']/2+steel.centre[i]
            ledger.append({"Mat":g,"z (mm)":centre,"fy (MPa)":steel.fy[i],"As provided (mm²/m)":steel.area[i],
                "N–M tie (N/mm)":row[g+' force (N/mm)'],"Shear tie add. (N/mm)":row[g+' shear tie (N/mm)'],
                "Tie driver":'No tie demand' if row[g+' shear tie (N/mm)']+row[g+' force (N/mm)']<=1e-12 else 'Shear tie addition' if row[g+' shear tie (N/mm)']>row[g+' force (N/mm)']/engine.PHI_TIE else 'N–M field',
                "As required (mm²/m)":row[g+' As required (mm²/m)'],"D/C":row[g+' D/C'],
                "W–A bending reference (kN·m/m)":row[g+' WA (kN·m/m)']})
        st.dataframe(pd.DataFrame(ledger),hide_index=True,width="stretch")
        st.latex(r"A_{s,req,i}=\max\left[\frac{T_{NM,i}/\phi_s+\Delta T_{V,i}}{f_{y,i}},\ A_{s,shrinkage,i}\right]")
        st.caption("Areas in the equation are per unit width. Multiply mm²/mm by 1,000 for mm²/m. N–M and shear tie requirements share the same provided mat; resistance is not added twice.")
        st.latex(r"V_u=\sqrt{V_x^2+V_y^2},\qquad \Delta T_{V,x}=\frac{V_x^2+|V_xV_y|}{V_u\phi_v}\cot\theta")
        st.caption("Swap x/y for the transverse tie. This is a conservative orthogonal shear-tie screen based on 5.7.3.5, with no Vp/Vs credit. It supplements the N–M field; the combined 3D stress field is not validated by this gate.")
        st.caption(f"Shear: dv={row['Shear dv (mm)']:.2f} mm, β={row['Shear beta']:.4f}, tie angle={row['Shear tie angle (deg)']:.0f}°, strain bound={row['Shear strain bound']:.5f}, D/C={_number(row['Shear D/C'])}")
        st.caption("5.7.3.4.1: shallow normal-weight RC sections without principal axial tension use β=2. Otherwise the no-stirrup general screen uses εs=0.006 only if its conservative strain bound is within that limit; unknown applicability remains REVIEW. Aggregate-size credit is zero.")
        st.caption("Shrinkage/temperature minimum: 5.10.6, conservative infinite-width bound, fy credit ≤75 ksi, 0.11–0.60 in²/ft per face/direction. Shrinkage and the independent flexural-minimum sufficient screen are different checks. Bar maximum spacing: 5.10.3.2.")
        st.caption(f"Normalized six-component equilibrium residual: {row['Equilibrium residual']:.3g}. Finite face-depth/45° field search gives an admissible review field; As required is not a claim of globally minimum reinforcement.")
    with st.expander("Code flexure / Minimum reinforcement reference",expanded=view in REFERENCE_VIEWS):
        st.caption("Independent N=0 tension-mat-only RC strip, 1 m wide. Opposite-mat strength is not credited. Nonzero membrane actions remain coupled N–M review; the reference never overrides the field result.")
        st.caption(f"Source {row['OutputCase']} / {row['StepType']} · element {row.get('AreaElem',row.name)} · joint {row['Joint']}: {row['Code reference reason']}")
        data=[]
        for g in engine.GROUPS:
            data.append({'Mat':g,'Mu W–A (kN·m/m)':row[g+' WA (kN·m/m)'],
                'φMn reference (kN·m/m)':row[g+' reference phiMn (kN·m/m)'],
                'Tensile strain':row[g+' reference tensile strain'],
                'Reference D/C':row[g+' reference D/C'],'1.33Mu / φMn':row[g+' minimum sufficient D/C']})
        st.dataframe(pd.DataFrame(data),hide_index=True,width='stretch',column_config={
            'Mu W–A (kN·m/m)':st.column_config.NumberColumn(format='%.2f'),
            'φMn reference (kN·m/m)':st.column_config.NumberColumn(format='%.2f'),
            'Tensile strain':st.column_config.NumberColumn(format='%.5f'),
            'Reference D/C':st.column_config.NumberColumn(format='%.3f'),
            '1.33Mu / φMn':st.column_config.NumberColumn(format='%.3f')})
        st.latex(r"a=\frac{A_sf_y}{\alpha_1 f'_c b},\quad c=\frac{a}{\beta_1},\quad M_r=0.90 A_s f_y\left(d-\frac{a}{2}\right)")
        st.caption("AASHTO 2020 5.6.2.1 / 5.6.2.2 / 5.5.4.2: actual cover, α1 and β1; φ=0.90 only when the tensile strain meets the code tension-control limit. Unqualified resistance remains unavailable.")
        st.latex(r"M_r\ge1.33M_u\quad\Longrightarrow\quad M_r\ge\min(1.33M_u,M_{cr})")
        st.caption("5.6.3.3 sufficient minimum screen. Passing the stronger 1.33Mu branch is sufficient within this N=0 reference. Exceeding it is REVIEW: the lesser Mcr branch may still pass. No bar ultimate strength or cracking coefficient is invented. This screen does not increase the main As required or turn an N–M result into final code acceptance.")
    with st.expander("Source audit / Export results",expanded=False):
        st.caption(f"{result['source_rows']:,} concurrent source records checked in {result['seconds']:.2f} s. Source corners, Max/Min and original eight components are retained. No force peaks or support-end records are discarded.")
        st.caption("Engineering input changes hide old results. View/case selectors only read the stored calculation. Results are session-only and do not replace the girder Summary / Report checks.")
        export=selected.reset_index()
        export['Map view']=view
        export_columns=['AreaElem','Joint','OutputCase','StepType','X (m)','Y (m)','Thickness (mm)',
            'Field D/C','Concrete D/C','Shear D/C','Controlling check','Status','Map incomplete','Map view',
            'Code flexure reference D/C','Minimum sufficient screen D/C','Code flexure reference status',
            'Minimum sufficient screen status','Code reference reason',
            'F11','F22','F12','M11','M22','M12','V13','V23','Nx','Ny','Nxy','Mx','My','Mxy','Vx','Vy']
        for g in engine.GROUPS:
            export_columns += [g+' As required (mm²/m)',g+' D/C',g+' reference phiMn (kN·m/m)']
        st.download_button('Download element envelope · CSV',export[[c for c in export_columns if c in export]].to_csv(index=False).encode('utf-8-sig'),
            file_name='Deck_Slab_Element_Envelope.csv',mime='text/csv',key='slab_shell55_strength56_download')
        st.dataframe(result['coverage'],hide_index=True,width='stretch')
        st.download_button('Download all-case check summary · CSV',result['check_summary'].to_csv(index=False).encode('utf-8-sig'),
            file_name='Deck_Slab_Check_Summary.csv',mime='text/csv',key='slab_shell55_strength57_check_download')
    with st.expander("Method / Remaining checks",expanded=False):
        st.write(result['scope'])
        st.caption("Normal-weight, nonprestressed monolithic slab, straight bridge alignment and planar four-corner shell elements. Local support/connection peaks need a regional assessment before converting the displayed point requirements into buildable reinforcement.")
        st.caption("Wood–Armer is a bending-only reference. It does not replace the simultaneous membrane-plus-bending check, and imported ULS cases do not establish service cracking or fatigue performance.")


def render():
    render_page_header("Slab Reinforcement","Coupled N–M section review · existing top / bottom steel · all imported ULS cases",
        icon="SL",kicker="Analysis / Deck slab",badge="Section preview",accent="blue")
    st.caption("N–M field preview using AASHTO component limits, with separate shear screens. Full 3D N–M–V compatibility, anchorage and complete deck acceptance are not established by this check.")
    package=current_package(st.session_state)
    input_error=None
    try:
        engine.steel_from_state(st.session_state)
    except ValueError as exc:
        input_error=str(exc)
    controls=st.columns([2,1])
    with controls[0]:
        calculate=st.button("Calculate Slab Reinforcement",type="primary",key="slab_shell55_strength56_calculate",
            use_container_width=True,disabled=package is None or input_error is not None)
    with controls[1]:
        if st.button("Shell import / required files",key="slab_shell55_to_loads",use_container_width=True):
            st.session_state['_nav_active_workspace']='Loads'
            st.session_state['_nav_loads_subpage']='Slab Shell Results'
            st.rerun()
    if package is None:
        st.warning("Import the complete current shell package in Loads → Slab Shell Results.")
    if input_error:
        st.warning(input_error)
    result=engine.current(st.session_state)
    if calculate:
        bar=st.progress(0.,text="Recovering shell geometry / axes…")
        try:
            with st.spinner("Checking all supplied shell records…"):
                result=engine.calculate(st.session_state,progress=lambda done,total:bar.progress(done/total,text=f"Checked {done:,} / {total:,} records"))
            st.session_state[engine.RESULT_KEY]=result
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            st.session_state.pop(engine.RESULT_KEY,None)
            result=None
            st.error("Slab calculation unavailable: "+str(exc))
        finally:
            bar.empty()
    if result is None:
        if engine.RESULT_KEY in st.session_state:
            st.info("STALE — slab inputs or imported files changed. Calculate again to review current results.")
        else:
            st.info("NOT CALCULATED — press Calculate Slab Reinforcement to display the plan map and reinforcement checks.")
        _input_review()
        return
    gov=result['governing']
    failed=result['counts'].get('Preview FAIL',0);review=result['counts'].get('REVIEW',0)
    if result['incomplete']:
        st.warning('Partial source coverage: some case/step groups lack shell-corner records. Unavailable regions remain grey; the imported subset is not a complete deck envelope.')
    render_metric_cards([
        {"title":"All-case section review","value":result['status'],"detail":f"{failed:,} exceeded · {review:,} require review", "status":"danger" if failed else "warning" if review else "ready"},
        {"title":"Governing check D/C","value":_number(gov['Field D/C']),"detail":f"{gov['OutputCase']} / {gov['StepType']}","status":"info"},
        {"title":"Controlling check","value":gov['Controlling check'],"detail":f"X {gov['X (m)']:.3f} · Y {gov['Y (m)']:.3f} m · element {gov['AreaElem']}","status":"neutral"},
    ])
    if gov['Field D/C']>3:
        st.warning('High local shell demand at the reported source corner. Review the support / load-transfer region before converting point reinforcement requirements into a bar schedule; the calculation retains the original peak actions.')
    filters=st.columns([1,1])
    with filters[0]:
        view=st.selectbox("Result to review",VIEWS,key="slab_shell55_strength56_view")
    with filters[1]:
        options=[ALL_CASES,*sorted(result['rows']['OutputCase'].unique())]
        key='slab_shell55_strength56_case'
        if st.session_state.get(key) not in options:st.session_state[key]=options[0]
        case=st.selectbox("Load case to review",options,key=key)
    if view in REFERENCE_VIEWS:
        st.info("Independent code bending reference. Nonzero membrane forces and unqualified strain remain grey / REVIEW. The all-case N–M status above is unchanged.")
        source = result['rows'] if case==ALL_CASES else result['rows'].loc[result['rows']['OutputCase']==case]
        qualified = int(source[REFERENCE_VIEWS[view]].notna().sum())
        st.caption(f'{qualified:,} of {len(source):,} source records qualify for this N=0 reference. Unavailable reference ratios do not mean zero demand.')
        if view==MINIMUM_VIEW:
            st.caption('This is a sufficient 1.33Mu screen. Red means the stronger screen is exceeded; the lesser Mcr branch has not been evaluated, so minimum reinforcement remains REVIEW.')
    selected=element_envelope(result,view=view,case=case)
    fig=plan_figure(result,view=view,case=case)
    # Same local horizontal-scroll pattern as the accepted SLS53 charts.
    st.html('''<style>.slab56-chart-hint{display:none}
      @media screen and (max-width:760px){
        .st-key-slab_shell56_plot{overflow-x:auto;max-width:100%}
        .st-key-slab_shell56_plot [data-testid="stElementContainer"]:has([data-testid="stPlotlyChart"]),
        .st-key-slab_shell56_plot [data-testid="stPlotlyChart"]{min-width:860px}
        .slab56-chart-hint{display:block;color:#64748b;font-size:12px}
      }</style><div class="slab56-chart-hint">Scroll the map horizontally to view the full deck.</div>''')
    with st.container(key='slab_shell56_plot'):
        st.plotly_chart(fig,width="stretch",key="slab_shell55_strength56_plan",
            config={"displaylogo":False,"scrollZoom":False,
                "toImageButtonOptions":{"format":"png","filename":"Deck_Slab_Check","width":1440,"height":575,"scale":2}})
    st.caption("Element envelope = maximum source corner/case; no averaging or peak clipping. D/C = 1 is the check limit. Color spacing is logarithmic; the scale and hover show actual D/C. Grey denotes unresolved applicability or incomplete source coverage.")
    st.caption("The all-case status above is unchanged by graph filters. Required steel includes the selected N–M field, conservative shear-tie additions and shrinkage minimum; concrete/shear limits remain independent checks.")
    compact=result['summary'].copy()
    compact['Governing case']=compact['Case']+' / '+compact['Step']
    compact=compact[['Reinforcement','As provided (mm²/m)','As required (mm²/m)','D/C','Status','Governing case','X (m)','Y (m)']]
    st.dataframe(compact,hide_index=True,width="stretch",column_config={
        'As provided (mm²/m)':st.column_config.NumberColumn(format='%.1f'),
        'As required (mm²/m)':st.column_config.NumberColumn(format='%.1f'),
        'D/C':st.column_config.NumberColumn(format='%.3f'),'X (m)':st.column_config.NumberColumn(format='%.3f'),
        'Y (m)':st.column_config.NumberColumn(format='%.3f')})
    with st.expander('What controls / All-case check breakdown',expanded=False):
        st.caption('Steel rows check N–M plus shear ties; shrinkage and spacing are separate rows. Each check retains its governing concurrent source record. Counts are unique elements. Missing shear remains REVIEW even when the known subset passes.')
        st.dataframe(result['check_summary'],hide_index=True,width='stretch',
            column_config={'Peak D/C':st.column_config.NumberColumn(format='%.3f')})
        st.caption('Code reference coverage: '+', '.join(f'{key}: {value:,} records' for key,value in result['reference_counts'].items())+'. These reference states are separate from the coupled field states.')
    _trace(result,selected,view=view,case=case)
    _input_review()

"""Calculate once, then review one slab plan map with folded engineering trace."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from concrete_pmm_pro.analysis import slab_shell56 as engine
from concrete_pmm_pro.analysis import slab_review61 as sensitivity
from concrete_pmm_pro.visualization.slab_review61 import plan as study_plan
from concrete_pmm_pro.analysis.slab_connections59 import design_rows, INCLUDED, REASON, END_REASON
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


def _study_trace(study):
    with st.expander('Peak review / Zone averages · study',expanded=False):
        st.warning('REVIEW REQUIRED — peak labels and spatial means are sensitivity studies. They do not replace nominal checks, prove that a peak is erroneous, or verify local wheel, punching, connection or end-region design.')
        st.caption(f"One pass · {study['excluded_nodes']:,} physical nodes / {study['excluded_node_cases']:,} node/case/step groups · {study['excluded_records']:,} source records omitted from the study; {study['retained_records']:,} retained. Other cases at the same node remain unless independently flagged.")
        st.dataframe(study['comparison'],hide_index=True,width='stretch',column_config={c:st.column_config.NumberColumn(format='%.3f') for c in study['comparison'] if 'D/C' in c})
        st.markdown('**Fixed peak rule — no iterative trimming**')
        st.caption('In the same case/step: maximum individual-element magnitude at each shared joint, compared with retained one-ring mesh neighbours. Require at least four neighbours, an opposing collinear pair, a strict local maximum, ratio to neighbour median > 2.0 and modified score > 3.5. No D/C threshold or reinforcement strength enters the rule.')
        st.latex(r'I_{NM}=\max_{\pm}\|\mathbf N\pm6\mathbf M/h\|_F,\quad I_V=\sqrt{V_x^2+V_y^2}')
        st.latex(r'z^*=0.67448975\,(I-\operatorname{median}I_j)/\operatorname{MAD}(I_j)')
        st.caption('Symmetric tensor norm: xy is weighted twice; h is in m. These are force-magnitude heuristics, not code acceptance equations or a statistical validation of FEM errors. A numerical floor handles zero median/MAD.')
        st.dataframe(study['ledger'].head(100),hide_index=True,width='stretch')
        st.download_button('Download peak labels · CSV',study['ledger'].to_csv(index=False).encode('utf-8-sig'),file_name='Deck_Slab_Peak_Labels_Study.csv',mime='text/csv',key='slab61_peak_labels')
        excluded=study['source'].loc[study['source'][sensitivity.PEAK]]
        columns=['Area','AreaElem','Joint','OutputCase','StepType','StepNum','X (m)','Y (m)','F11','F22','F12','M11','M22','M12','V13','V23',*sensitivity.ACTIONS,'N–M field D/C','Shear D/C',sensitivity.PEAK,sensitivity.STUDY_INCLUDED]
        st.download_button('Download excluded peak source records · CSV',excluded[[c for c in columns if c in excluded]].to_csv(index=False).encode('utf-8-sig'),file_name='Deck_Slab_Excluded_Peaks_Study.csv',mime='text/csv',key='slab61_peak_source')
        if study['zone_error']:st.info('Zone averaging unavailable: '+study['zone_error'])
        else:
            st.markdown('**Zones — native Area segment × transverse mesh row**')
            st.caption('No merging across girder / diaphragm lines. Peak-labelled and previously excluded connection/end samples are omitted. Minimum thickness across each full zone controls resistance.')
            st.latex(r'\overline{\mathbf Q}=\frac{\sum_{retained}A_k\mathbf Q_k}{\sum_{retained}A_k},\quad\mathbf Q=(N_x,N_y,N_{xy},M_x,M_y,M_{xy},V_x,V_y)')
            st.caption('Aₖ integrates each corner shape function over projected plan area. All eight signed actions share weights, case and step. Recalculate D/C from mean actions; never average D/C. Omitted samples leave partial coverage; sign reversals may cancel. Both are recorded. This is not an equilibrated design-strip integration.')
            st.dataframe(study['zone_layout'].head(50),hide_index=True,width='stretch')
            st.download_button('Download zone means / coverage · CSV',study['zone_rows'].to_csv(index=False).encode('utf-8-sig'),file_name='Deck_Slab_Zone_Means_Study.csv',mime='text/csv',key='slab61_zone_source')
        st.caption('Sources and limitations: see SLAB_REVIEW61_NOTES_TH.md. CSI describes shared-joint variation and averaging limits; NIST modified-score guidance labels potential outliers, not structural errors.')


def _trace(result, selected, *, view, case=ALL_CASES):
    column = view_column(view)
    known = selected.loc[selected[column].notna()]
    source = design_rows(result)
    if case != ALL_CASES:
        source = source.loc[source['OutputCase']==case]
    if source.empty:
        st.info('No nominal slab records remain in this case outside the excluded connection lines / bearing end zones.')
        return
    if view in REFERENCE_VIEWS and not known.empty:
        row = known.loc[known[column].idxmax()]
    elif view in REFERENCE_VIEWS:
        row = source.loc[source['Field D/C'].idxmax()]
    else:
        row = known.loc[known[column].idxmax()] if not known.empty else source.loc[source['Field D/C'].idxmax()]
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
                "N–M tie (N/mm)":row[g+' force (N/mm)'],
                "As required (mm²/m)":row[g+' As required (mm²/m)'],"D/C":row[g+' D/C'],
                "W–A bending reference (kN·m/m)":row[g+' WA (kN·m/m)']})
        st.dataframe(pd.DataFrame(ledger),hide_index=True,width="stretch")
        st.latex(r"A_{s,req,i}=\max\left[\frac{T_{NM,i}}{0.90 f_{y,i}},\ A_{s,shrinkage,i}\right]")
        st.caption("Areas in the equation are per unit width. Multiply mm²/mm by 1,000 for mm²/m. These are N–M field requirements only. Transverse shear does not change these steel areas or the selected N–M field.")
        st.latex(r"V_u=\sqrt{V_x^2+V_y^2},\qquad (D/C)_V=V_u/(\phi_vV_c)")
        st.caption(f"Separate shear screen: dv={row['Shear dv (mm)']:.2f} mm, trial β={row['Shear beta']:.4f}, strain bound={row['Shear strain bound']:.5f}, D/C={_number(row['Shear D/C'])}; {row['Shear status']}.")
        st.caption("5.7.3.4.1: shallow normal-weight RC sections without principal axial tension use β=2. Otherwise the no-stirrup general screen uses εs=0.006 only if its conservative strain bound is within that limit; unknown applicability remains REVIEW. Aggregate-size credit is zero.")
        st.caption("Shear uses the independent geometric section-depth bound max[0.9(h−maximum bar-centre cover), 0.72h]. It does not claim that the selected N–M faces leave this much core reserve.")
        st.caption(f"Combined N–M–V: {row['Combined N–M–V status']}. Passing independent components does not qualify interaction. AUDIT58 removes the former unconditional full shear-tie additions at both faces; no replacement cracked-core capacity is inferred.")
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
        st.caption(f"{result['source_rows']:,} source records retained; {result.get('design_rows', result['source_rows']):,} nominal slab records checked in {result['seconds']:.2f} s. Excluded records retain their original actions and receive no design D/C.")
        st.caption("Engineering input changes hide old results. View/case selectors only read the stored calculation. Results are session-only and do not replace the girder Summary / Report checks.")
        export=selected.reset_index()
        export['Map view']=view
        export_columns=['AreaElem','Joint','OutputCase','StepType','X (m)','Y (m)','Thickness (mm)',
            'Design included','Design exclusion','Bearing end-zone','Excluded records','Nominal design records','Map excluded',
            'Field D/C','N–M field D/C','N–M field status','Concrete D/C','Shear D/C','Shear status',
            'Shear phiVc (kN/m)','Combined N–M–V status','Controlling check','Status','Map incomplete','Map view',
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
    with st.expander('Exclusions / Design-section locations', expanded=False):
        connections = result.get('connections', {})
        st.caption(connections.get('basis', 'No connection exclusion geometry available.'))
        st.caption('Connection rule: nodes on the imported lines are excluded (coordinate tolerance 0.02 mm). Bearing rule: all nodes from each physical deck end through its project bearing reference are excluded across the full deck width, including the bearing boundary. All remaining cases and Max/Min rows are retained. No D/C threshold or cross-connection averaging is used.')
        ends = connections.get('end_zones', {})
        if ends.get('active'):
            st.dataframe(pd.DataFrame(ends['zones']),hide_index=True,width='stretch')
            st.caption('Bearing offsets are read from the existing project settings, measured from the imported single-span slab ends. A centerline reference is not converted to an inside face when bearing length is unknown. End zones are an engineer-selected scope exclusion; local end-region design remains separate.')
        if connections.get('negative_moment_offset_mm') is not None:
            flange = connections['top_flange_mm']; offset = connections['negative_moment_offset_mm']
            st.caption(f'Top flange width {flange:g} mm · physical edge ±{flange/2:g} mm from girder CL · AASHTO deck negative-moment reference section ±{offset:g} mm: min(bf/3, 381 mm). Retained mesh nodes at and near the design section remain in the envelope.')
            st.caption('The negative-moment location is the highway-deck convention illustrated by FHWA Design Step 4.6 / AASHTO 4.6.2.1.6. It is a location reference, not a general N/M/V exemption or automatic railway-code acceptance. The app does not interpolate forces through an excluded node.')
        for note in connections.get('notes', []):
            st.info(note)
        lines = connections.get('lines', pd.DataFrame())
        if not lines.empty:
            st.dataframe(lines.drop(columns=['ID']), hide_index=True, width='stretch')
        raw = result['rows']
        raw = raw.loc[~raw[INCLUDED]] if INCLUDED in raw else raw.iloc[:0]
        if not raw.empty:
            columns = ['Area','AreaElem','Joint','OutputCase','StepType','StepNum','X (m)','Y (m)',REASON,END_REASON,
                       'F11','F22','F12','M11','M22','M12','V13','V23']
            st.download_button('Download excluded source actions · CSV',
                raw[[c for c in columns if c in raw]].to_csv(index=False).encode('utf-8-sig'),
                file_name='Deck_Slab_Excluded_Nodes.csv', mime='text/csv', key='slab_connection59_raw')
    with st.expander("Method / Remaining checks",expanded=False):
        st.write(result['scope'])
        st.caption("Normal-weight, nonprestressed monolithic slab, straight bridge alignment and planar four-corner shell elements. The nominal slab review excludes the identified connection nodes and project bearing end zones; end-region force transfer and detailing remain separate checks.")
        st.caption("Wood–Armer is a bending-only reference. It does not replace the simultaneous membrane-plus-bending check, and imported ULS cases do not establish service cracking or fatigue performance.")


def render():
    render_page_header("Slab Reinforcement","Coupled N–M section review · existing top / bottom steel · all imported ULS cases",
        icon="SL",kicker="Analysis / Deck slab",badge="Section preview",accent="blue")
    st.caption("N–M reinforcement and one-way shear are separate checks. Combined N–M–V remains REVIEW for nonzero shear; the displayed steel areas do not include a shear interaction allowance.")
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
            st.session_state.pop(sensitivity.RESULT_KEY,None)
            try:
                with st.spinner('Preparing peak review / zone sensitivity…'):
                    st.session_state[sensitivity.RESULT_KEY]=sensitivity.calculate(result)
            except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
                st.warning('Nominal results retained; sensitivity study unavailable: '+str(exc))
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
    nm_gov=result['nm_governing']
    shear_row=result['check_summary'].set_index('Check').loc['One-way shear']
    render_metric_cards([
        {"title":"Nominal slab component review","value":result['status'],"detail":f"{failed:,} exceeded · {review:,} require review", "status":"danger" if failed else "warning" if review else "ready"},
        {"title":"N–M field max D/C","value":_number(nm_gov['N–M field D/C']),"detail":f"{nm_gov['OutputCase']} / {nm_gov['StepType']} · element {nm_gov['AreaElem']}","status":"info"},
        {"title":"One-way shear screen D/C","value":_number(shear_row['Peak D/C']),"detail":f"{shear_row['Status']} · {int(shear_row['Review elements']):,} elements need review", "status":"neutral"},
    ])
    if result.get('excluded_rows', 0):
        st.caption(f"Excluded nodes: {result['excluded_nodes']:,} nodes / {result['excluded_rows']:,} source records. Graphs, required steel and D/C use the {result['design_rows']:,} retained nominal slab records.")
    ends = result.get('connections', {}).get('end_zones', {})
    if ends.get('active'):
        intervals = ' · '.join(f"{z['Side']} {z['From station (m)']:.3f}–{z['To station (m)']:.3f} m" for z in ends['zones'])
        st.caption('Bearing end zones excluded across the full deck width: '+intervals+f" · {ends['reference']} reference from existing project settings.")
    for note in result.get('connections', {}).get('notes', []):
        st.info(note)
    st.caption(f"Controlling known check: {gov['Controlling check']} · D/C {_number(gov['Field D/C'])} · {gov['OutputCase']} / {gov['StepType']} · X {gov['X (m)']:.3f}, Y {gov['Y (m)']:.3f} m · element {gov['AreaElem']}.")
    if gov['Field D/C']>3:
        st.warning('High demand remains at a retained slab corner outside the excluded connections and bearing end zones. Review this position and load case before selecting the reinforcement schedule.')
    study=sensitivity.current(st.session_state,result)
    filters=st.columns([1,1,1])
    with filters[0]:
        view=st.selectbox("Result to review",VIEWS,key="slab_shell55_strength56_view")
    with filters[1]:
        options=[ALL_CASES,*sorted(result['rows']['OutputCase'].unique())]
        key='slab_shell55_strength56_case'
        if st.session_state.get(key) not in options:st.session_state[key]=options[0]
        case=st.selectbox("Load case to review",options,key=key)
    with filters[2]:
        bases=sensitivity.BASES if study is not None and not study['zone_error'] else sensitivity.BASES[:2] if study is not None else [sensitivity.RAW]
        basis_key='slab61_review_basis'
        if st.session_state.get(basis_key) not in bases:st.session_state[basis_key]=sensitivity.RAW
        basis=st.selectbox('Review basis',bases,key=basis_key)
    is_study=basis!=sensitivity.RAW
    plotted=sensitivity.map_result(result,study,basis) if is_study else result
    if is_study:
        st.warning('Sensitivity study · REVIEW REQUIRED. Nominal status and maxima above remain unchanged. Filtered / mean D/C does not establish design acceptance.')
        prefix='Peaks excluded' if basis==sensitivity.FILTERED else 'Zone mean'
        compared=study['comparison'].set_index('Check')
        st.caption(f"Study all-case maxima · N–M {_number(compared.loc['N–M field',prefix+' max D/C'])} · one-way shear {_number(compared.loc['One-way shear',prefix+' max D/C'])}. Graph case filters do not change these all-case study maxima.")
    if view in REFERENCE_VIEWS:
        st.info("Independent code bending reference. Nonzero membrane forces and unqualified strain remain grey / REVIEW. The all-case N–M status above is unchanged.")
        source = design_rows(plotted)
        source = source if case==ALL_CASES else source.loc[source['OutputCase']==case]
        qualified = int(source[REFERENCE_VIEWS[view]].notna().sum())
        st.caption(f'{qualified:,} of {len(source):,} source records qualify for this N=0 reference. Unavailable reference ratios do not mean zero demand.')
        if view==MINIMUM_VIEW:
            st.caption('This is a sufficient 1.33Mu screen. Red means the stronger screen is exceeded; the lesser Mcr branch has not been evaluated, so minimum reinforcement remains REVIEW.')
    selected=element_envelope(plotted,view=view,case=case)
    fig=study_plan(result,study,basis=basis,view=view,case=case) if is_study else plan_figure(result,view=view,case=case)
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
    if is_study:
        st.caption(('Peak study: remaining original corners; purple crosses mark omitted node/case groups. ' if basis==sensitivity.FILTERED else 'Zone study: signed mean actions after peak screening, maximum case/step per zone. Diamond marks the sampling centroid. ')+
            'D/C is a numeric screen. Grey denotes unresolved / unavailable values. Original forces remain in the study audit.')
    else:
        st.caption("Element envelope = maximum retained corner/case, with connection nodes and bearing end zones excluded. Dotted lines locate connections; shaded end strips show the bearing exclusions. D/C = 1 is the check limit. Color spacing is logarithmic; hover shows actual D/C. Grey also denotes unresolved applicability, incomplete coverage or fully excluded elements.")
    st.caption("The all-case status above is unchanged by graph filters. Required steel includes the selected N–M field and shrinkage minimum only. Overall section maps the maximum known component; this is not a combined N–M–V resistance ratio.")
    if is_study:st.caption('Nominal reinforcement summary below: unchanged by the study view.')
    compact=result['summary'].copy()
    compact['Governing case']=compact['Case']+' / '+compact['Step']
    compact=compact[['Reinforcement','As provided (mm²/m)','As required (mm²/m)','D/C','Status','Governing case','X (m)','Y (m)']]
    st.dataframe(compact,hide_index=True,width="stretch",column_config={
        'As provided (mm²/m)':st.column_config.NumberColumn(format='%.1f'),
        'As required (mm²/m)':st.column_config.NumberColumn(format='%.1f'),
        'D/C':st.column_config.NumberColumn(format='%.3f'),'X (m)':st.column_config.NumberColumn(format='%.3f'),
        'Y (m)':st.column_config.NumberColumn(format='%.3f')})
    with st.expander('What controls / All-case check breakdown',expanded=False):
        st.caption('Steel rows check N–M only; shrinkage, spacing and shear are separate rows. Each check retains its governing concurrent source record. Counts are unique elements. Combined N–M–V remains REVIEW for nonzero V even when the independent components pass.')
        st.dataframe(result['check_summary'],hide_index=True,width='stretch',
            column_config={'Peak D/C':st.column_config.NumberColumn(format='%.3f')})
        st.caption('Code reference coverage: '+', '.join(f'{key}: {value:,} records' for key,value in result['reference_counts'].items())+'. These reference states are separate from the coupled field states.')
    if not is_study:_trace(result,selected,view=view,case=case)
    if study is not None:_study_trace(study)
    else:st.caption('Press Calculate Slab Reinforcement to prepare the current peak / zone study.')
    _input_review()

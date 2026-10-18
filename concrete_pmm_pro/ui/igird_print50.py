"""Print the displayed Shear workspace without rasterization or solver calls.

Native Plotly SVGs retain pixel widths when print media narrows the page.
Clone their existing vector layers into a viewBox at beforeprint; restore
the interactive originals at afterprint. Small tables use the shared CSP
escaped HTML table renderer for print, keeping the interactive screen table.
Only static application JavaScript is executed; no project text is code.
"""
import hashlib


SUPPORT = r'''
<style>
.csp50-print-table { display:none; }
@media print {
  body:has([class*="st-key-composite50_chart_"]) [data-testid="stSidebar"],
  body:has([class*="st-key-composite50_chart_"]) [data-testid="stHeader"] { display:none !important; }
  body:has([class*="st-key-composite50_chart_"]) [data-testid="stMain"] { margin:0 !important; }
  body:has([class*="st-key-composite50_chart_"]) [data-testid="stMainBlockContainer"] {
    padding:8px !important; max-width:100% !important;
  }
  [class*="st-key-composite50_table_"] [data-testid="stDataFrame"] { display:none !important; }
  .csp50-print-table { display:block !important; width:100%; }
  .csp50-print-table .cpmm-sls-print-table-shell { width:100%; overflow:visible; }
  .csp50-print-table table { width:100%; table-layout:fixed; border-collapse:collapse; }
  .csp50-print-table th, .csp50-print-table td {
    white-space:normal !important; overflow-wrap:anywhere; font-size:7pt; padding:3pt;
  }
  .csp50-live-plot { display:none !important; }
  .csp50-print-plot { width:100%; break-inside:avoid; }
  .csp50-print-plot svg { display:block; width:100%; height:auto; }
}
.csp50-print-plot { display:none; }
@media print { .csp50-print-plot { display:block; } }
</style>
<script>
(() => {
  if (window.__csp50PrintInstalled) return;
  window.__csp50PrintInstalled = true;
  const restore = () => {
    document.querySelectorAll('.csp50-print-plot').forEach(e => e.remove());
    document.querySelectorAll('.csp50-live-plot').forEach(e => e.classList.remove('csp50-live-plot'));
  };
  window.addEventListener('beforeprint', () => {
    restore();
    if (!document.querySelector('[class*="st-key-composite50_chart_"]')) return;
    document.querySelectorAll('[data-testid="stPlotlyChart"]').forEach((chart,index) => {
      const layers = [...chart.querySelectorAll('svg.main-svg')];
      if (!layers.length) return;
      const w = Number(layers[0].getAttribute('width'));
      const h = Number(layers[0].getAttribute('height'));
      if (!(w > 0 && h > 0)) return;
      const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
      svg.setAttribute('xmlns','http://www.w3.org/2000/svg');
      svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
      svg.setAttribute('preserveAspectRatio','xMidYMid meet');
      layers.forEach(layer => [...layer.children].forEach(child => svg.appendChild(child.cloneNode(true))));
      const ids = new Map();
      svg.querySelectorAll('[id]').forEach(e => {
        const id=e.id, replacement=`csp50-print-${index}-${id}`;
        ids.set(id,replacement);e.id=replacement;
      });
      svg.querySelectorAll('*').forEach(e => [...e.attributes].forEach(attr => {
        let value=attr.value.replace(/url\(#([^)]+)\)/g,(_,id)=>`url(#${ids.get(id)||id})`);
        if (value[0]==='#' && ids.has(value.slice(1))) value='#'+ids.get(value.slice(1));
        if (value!==attr.value) e.setAttribute(attr.name,value);
      }));
      const printed=document.createElement('div');printed.className='csp50-print-plot';
      // Streamlit reserves the original chart height. Never enlarge the SVG
      // on a wider paper size, which would overlap the following caption.
      printed.style.maxWidth=`${w}px`;
      printed.appendChild(svg);chart.after(printed);chart.classList.add('csp50-live-plot');
    });
  });
  window.addEventListener('afterprint',restore);
})();
</script>
'''


def install():
    import streamlit as st
    st.html(SUPPORT,unsafe_allow_javascript=True)


def key(member,part):
    return 'composite50_'+part+'_'+hashlib.sha256(str(member).encode()).hexdigest()[:12]


def table(frame,*,member,part):
    import streamlit as st
    from .analysis_page import _crossbeam_print_safe_table_html
    with st.container(key=key(member,'table_'+part)):
        st.dataframe(frame,hide_index=True,width='stretch')
        st.html('<div class="csp50-print-table">'+
            _crossbeam_print_safe_table_html(frame,label='Composite shear — '+part)+'</div>')

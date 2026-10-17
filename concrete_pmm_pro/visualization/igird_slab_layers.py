"""Schematic generated from the same COVER38 physical mat coordinates."""
from concrete_pmm_pro.analysis.igird_slab_layers import number


def sketch(layout):
    if not layout.get('active'):return ''
    t=number(layout['parameters'].get('Tslab_mm'))
    if t is None or t<=0:return ''
    scale=230/t;surface=50.;bottom=surface+230;items=[]
    for row in layout['rows']:
        face=row['Layer'];dt=row['Transverse diameter (mm)'];dl=row['Longitudinal diameter (mm)']
        zt=row['Transverse centre below top (mm)'];zl=row['Longitudinal centre below top (mm)']
        if zt is None:continue
        yt=surface+zt*scale;radius=max(2.,dt*scale/2)
        for x in (235,375,515):items.append(f'<circle cx="{x}" cy="{yt:.3f}" r="{radius:.3f}" fill="#c66a1c"/>')
        if zl is not None:
            yl=surface+zl*scale
            items.append(f'<line x1="205" x2="545" y1="{yl:.3f}" y2="{yl:.3f}" stroke="#26836c" stroke-width="{max(2.,dl*scale):.3f}"/>')
        c=row['Input transverse cover (mm)'];cl=row['Auto longitudinal cover (mm)']
        sy=surface if face=='Top' else bottom;edge=surface+(zt-dt/2 if face=='Top' else zt+dt/2)*scale
        items.append(f'<path d="M145 {sy:.3f} H190 M155 {sy:.3f} V{edge:.3f} M145 {edge:.3f} H225" fill="none" stroke="#2364a0" stroke-width="1.5"/>')
        texty=surface+15 if face=='Top' else bottom-6
        items.append(f'<text x="14" y="{texty:.3f}" fill="#2364a0">{face} cover {c:g} mm</text>')
        items.append(f'<text x="555" y="{texty:.3f}" fill="#26836c">Long. cover {cl:g} mm</text>')
    return f'''<svg data-slab-layer-guide="COVER38" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 350" role="img" aria-label="Slab transverse bars outside and longitudinal bars inside; top and bottom coordinates calculated from clear cover" style="width:100%;max-width:960px;background:#fff;font:13px Arial,sans-serif">
    <text x="14" y="23" fill="#143754" font-weight="700">Slab layer order — section along girder</text>
    <rect x="195" y="{surface}" width="360" height="230" fill="#eef4f9" stroke="#8494a7"/>
    {''.join(items)}
    <text x="205" y="310" fill="#c66a1c">● Transverse — outside</text><text x="420" y="310" fill="#26836c">━ Longitudinal — inside</text>
    <text x="14" y="337" fill="#637487">Crossed bars touch. Longitudinal cover = transverse cover + transverse bar diameter. Dimensions: mm.</text></svg>'''

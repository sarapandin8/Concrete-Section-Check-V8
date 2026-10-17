"""Explicit girder / contact / U-tie / slab transfer idealization.

N, mm, MPa; coordinates=(longitudinal, CSI2 up, CSI3=section x).
Slab has NO supports or external cut loads. All load enters the girder cut.
Concrete regions have separate nodes and cannot bridge the construction joint.
Only compression/friction contact and developed vertical U-legs cross it.
This boundary-value experiment is NOT a recovery of CSI Beam/Slab free bodies.
"""
from dataclasses import dataclass,replace
import math

import numpy as np
from scipy import sparse
from shapely.geometry import Polygon,Point
from shapely import constrained_delaunay_triangles

VERSION='IGIRDER.JOINT37'
PRODUCTION_VALIDATED=False


def number(v):
    try:r=float(v)
    except (ValueError,TypeError):raise ValueError('Finite numeric data required.') from None
    if isinstance(v,bool) or not math.isfinite(r):raise ValueError('Finite numeric data required; unknown is not zero.')
    return r


@dataclass
class Model:
    nodes:np.ndarray
    components:list
    B:sparse.csr_matrix
    bounds:np.ndarray
    A:sparse.csr_matrix
    limits:np.ndarray
    resource_labels:list
    labels:list
    kinds:list
    stiffness:np.ndarray
    initial:np.ndarray
    elements:list
    fixed_dofs:list
    end_nodes:list
    contacts:list
    dowels:list
    trace:dict


def triangulation(polygon,extra,*,step_mm=200.):
    """Constrained polygon mesh, inserting every real steel / contact point.

    Split ALL triangles sharing an inserted edge; no nonconvex-hull shortcut.
    Sum of triangle areas must reconstruct the original concrete area.
    """
    if polygon.geom_type!='Polygon' or polygon.interiors or not polygon.is_valid or polygon.is_empty:
        raise ValueError('One valid solid concrete polygon is required per component.')
    polygon=polygon.normalize()
    original=list(polygon.exterior.coords)[:-1];ring=[]
    for a,b in zip(original,original[1:]+original[:1]):
        count=max(1,math.ceil(math.dist(a,b)/step_mm))
        ring.extend([(a[0]+(b[0]-a[0])*i/count,a[1]+(b[1]-a[1])*i/count) for i in range(count)])
    poly=Polygon(ring);vertices=[];lookup={}
    def node(p):
        key=tuple(round(number(v),7) for v in p)
        if key not in lookup:lookup[key]=len(vertices);vertices.append(key)
        return lookup[key]
    triangles=[tuple(node(p) for p in list(t.exterior.coords)[:3]) for t in constrained_delaunay_triangles(poly).geoms]
    for xy in sorted(set(tuple(round(number(v),7) for v in xy) for xy in extra)):
        xy=tuple(number(v) for v in xy);point=Point(xy)
        if not polygon.buffer(1e-7).covers(point):raise ValueError(f'Steel / joint node {xy} lies outside its concrete component.')
        key=tuple(round(v,7) for v in xy)
        if key in lookup:continue
        i=node(xy);new=[];found=False
        for t in triangles:
            shape=Polygon([vertices[j] for j in t])
            if not shape.buffer(1e-8).covers(point):new.append(t);continue
            found=True
            for a,b in zip(t,t[1:]+t[:1]):
                if Polygon([vertices[a],vertices[b],vertices[i]]).area>1e-8:new.append((a,b,i))
        if not found:raise ValueError('Could not embed a steel / contact point in the concrete mesh.')
        triangles=new
    area=sum(Polygon([vertices[i] for i in t]).area for t in triangles)
    if abs(area-polygon.area)>1e-7*polygon.area:raise ValueError('Concrete triangulation lost / duplicated area.')
    return np.asarray(vertices),triangles,lookup


def expand_slab_layers(params,slab_inventory,*,left_mm,right_mm):
    """Preserve equivalent As from Section Builder, distributed across Be.

    Nonintegral strip counts are tributary integration weights, not fabricated
    physical bars. Development/continuity declarations remain explicit gates.
    """
    result=[];width=right_mm-left_mm
    for layer,record in zip(('top','bottom'),slab_inventory):
        spacing=number(params['deck_long_rebar_'+layer+'_spacing_mm'])
        if spacing<=0 or width<=0:raise ValueError('Positive slab width / longitudinal spacing required.')
        count=max(2,math.ceil(width/spacing))
        for i in range(count):
            result.append({**record,'label':f'{layer} slab longitudinal / strip {i+1}/{count}',
                'kind':'slab_longitudinal','x_mm':left_mm+(i+.5)*width/count,
                'area_mm2':record['area_mm2']/count,'capacity_N':record['capacity_N']/count,
                'integration_basis':'Equivalent As over assigned Be, not an inferred physical strand/bar count.'})
    return result


def u_path(*,centre,top,a,F,B,D,db,tail,levels,arc_steps=4):
    """A continuous physical U with outward 90-degree top hooks.

    Interface has two distinct concrete faces. The steel crosses a short 2db
    bridge, rather than tying both concrete faces to one shared displacement.
    Intermediate embedded nodes expose transfer to the slab mats and cage.
    Perfect embedded bond is an explicit hypothesis, not a bond-strength check.
    """
    r=(D+db)/2.;yb=top-F;yt=top+B-r-db/2.;points=[]
    def add(p):
        p=(float(p[0]),float(p[1]))
        if not points or math.dist(points[-1],p)>1e-7:points.append(p)
    add((centre-a/2-r-tail,yt+r));add((centre-a/2-r,yt+r))
    for angle in np.linspace(math.pi/2,0,arc_steps+1):add((centre-a/2-r+r*math.cos(angle),yt+r*math.sin(angle)))
    ys=sorted(set([yb,yt,top-db,top+db,*[float(y) for y in levels if yb<y<yt and abs(y-top)>db],*np.linspace(yb,top-db,12).tolist()]))
    for y in reversed(ys):add((centre-a/2,y))
    for angle in np.linspace(math.pi,1.5*math.pi,arc_steps+1):add((centre-a/2+r+r*math.cos(angle),yb+r*math.sin(angle)))
    add((centre+a/2-r,yb-r))
    for angle in np.linspace(-math.pi/2,0,arc_steps+1):add((centre+a/2-r+r*math.cos(angle),yb+r*math.sin(angle)))
    for y in ys:add((centre+a/2,y))
    for angle in np.linspace(math.pi,math.pi/2,arc_steps+1):add((centre+a/2+r+r*math.cos(angle),yt+r*math.sin(angle)))
    add((centre+a/2+r+tail,yt+r))
    return points


def build(*,girder,slab,origin,girder_fc,slab_fc,girder_E,slab_E,hoop,bars,slab_longitudinal,
          transverse,detail,dowel,contact_width_mm,mu,interface_cap_MPa,pitch_mm=200.,nominal=False):
    girder=girder.normalize();slab=slab.normalize()
    p=number(pitch_mm);fg,fs,eg,es=map(number,(girder_fc,slab_fc,girder_E,slab_E))
    width=number(contact_width_mm);mu=number(mu);icap=number(interface_cap_MPa)
    if min(p,fg,fs,eg,es,width,icap)<=0 or mu<0:raise ValueError('Positive material / geometry data and nonnegative friction required.')
    if mu>1.5:raise ValueError('Interface friction is outside this model scope.')
    sf,cf=(1.,1.) if nominal else (.9,.7)
    db=number(dowel['Diameter_mm']);sd=number(dowel['Spacing_mm']);fyd=min(number(dowel['fy_MPa']),60*6.894757293168)
    if min(db,sd,fyd)<=0 or number(dowel['Legs'])!=2:raise ValueError('Exactly two known U-legs required; they are not added a second time as stirrups.')
    a=number(detail['row_spacing_mm']);F=number(detail['girder_ld_available_mm'])
    B=number(detail['slab_ldh_available_mm']);D=number(detail['hook_inside_bend_mm']);tail=number(detail['hook_tail_mm'])
    top=girder.bounds[3];centre=girder.centroid.x
    radius=(D+db)/2.;anchor_top=top+B-radius-db/2.;anchor_bottom=top-F
    legs=[centre-a/2,centre+a/2]
    if min(a,F,B,D,tail)<=0 or a<2*radius:raise ValueError('U geometry does not fit the proposed bend / leg centres.')
    xmin=centre-width/2;xmax=centre+width/2
    xs=sorted(set([xmin,xmax,centre,*legs,*np.linspace(xmin,xmax,5).tolist()]))
    if xmin<slab.bounds[0]-1e-8 or xmax>slab.bounds[2]+1e-8:raise ValueError('Contact width exceeds the assigned slab strip.')
    cover=number(hoop['cover_mm']);dg=number(hoop['Diameter_mm']);sg=number(hoop['Spacing_mm']);fyg=min(number(hoop['fy_MPa']),75*6.894757293168)
    inset=girder.buffer(-(cover+dg/2),join_style=2)
    if inset.geom_type!='Polygon' or inset.is_empty:raise ValueError('Girder hoop inset is unavailable.')
    rv=list(inset.exterior.coords)[:-1];ring=[]
    for u,v in zip(rv,rv[1:]+rv[:1]):
        count=max(1,math.ceil(math.dist(u,v)/200.))
        ring.extend([(u[0]+(v[0]-u[0])*i/count,u[1]+(v[1]-u[1])*i/count) for i in range(count)])
    across=[]
    for layer in ('top','bottom'):
        raw=transverse[layer];d,s,c,fy=[number(raw[k]) for k in ('Diameter_mm','Spacing_mm','Clear_cover_mm','fy_MPa')]
        if min(d,s,c,fy)<=0:raise ValueError('Top and bottom transverse slab mesh must be explicit.')
        y=slab.bounds[3]-c-d/2 if layer=='top' else slab.bounds[1]+c+d/2
        if not slab.bounds[1]<y<slab.bounds[3]:raise ValueError('Transverse slab layer is outside the slab.')
        across.append({'layer':layer,'y':y,'db':d,'spacing':s,'fy':fy})
    slab_x=sorted(set([slab.bounds[0],slab.bounds[2],*xs,*[float(b['x_mm']) for b in slab_longitudinal]]))
    path=u_path(centre=centre,top=top,a=a,F=F,B=B,D=D,db=db,tail=tail,
        levels=[r['y'] for r in across]+[b['y_mm'] for b in slab_longitudinal]+[u[1] for u in ring])
    gextra=[*ring,*[(b['x_mm'],b['y_mm']) for b in bars],*[(x,top) for x in xs],*[xy for xy in path if xy[1]<top]]
    sextra=[*[(b['x_mm'],b['y_mm']) for b in slab_longitudinal],*[(x,top) for x in xs],*[(x,anchor_top) for x in legs],
        *[(x,r['y']) for r in across for x in slab_x],*[xy for xy in path if xy[1]>top]]
    mesh={}
    for name,poly,extra in [('girder',girder,gextra),('slab',slab,sextra)]:mesh[name]=triangulation(poly,extra)
    nodes=[];components=[];ids={}
    oy=number(origin['target_y_mm']);oz=number(origin.get('target_local3_mm',0.))
    for name,(points,tris,lookup) in mesh.items():
        for k in range(3):
            for i,(x,y) in enumerate(points):
                ids[name,k,i]=len(nodes);nodes.append((k*p,y-oy,x-oz));components.append(name)
    nodes=np.array(nodes);cells=[];cell_component=[];cell_volume=[];incidence={}
    for name,(points,triangles,lookup) in mesh.items():
        for k in range(2):
            for tri in triangles:
                lower=[ids[name,k,i] for i in tri];upper=[ids[name,k+1,i] for i in tri]
                vol=Polygon([points[i] for i in tri]).area*p
                if vol<=1e-8:raise ValueError('Degenerate concrete prism.')
                idx=len(cells);cells.append(lower+upper);cell_component.append(name);cell_volume.append(vol)
                # Both diagonal directions in every prism face; a one-sided
                # tetrahedral edge net would introduce artificial chirality.
                edges=[(i,j) for i in lower for j in upper]
                for plane in (lower,upper):edges.extend((plane[i],plane[j]) for i in range(3) for j in range(i+1,3))
                for edge in edges:incidence.setdefault(tuple(sorted(edge)),[]).append(idx)
    cell_volume=np.array(cell_volume);limits=[cf*.45*(fg if c=='girder' else fs)*v for c,v in zip(cell_component,cell_volume)]
    resource_labels=[f'{c} concrete cell {i}' for i,c in enumerate(cell_component)]
    colrows=[];colcols=[];colvals=[];arows=[];acols=[];avals=[];bounds=[];labels=[];kinds=[];stiffness=[];initial=[];elements=[]
    def element(label,kind,i,j,lo,hi,k,*,direction=None,resource=None,N0=0.):
        m=len(labels);vector=nodes[j]-nodes[i];length=float(np.linalg.norm(vector));unit=vector/length if direction is None else np.array(direction,dtype=float)
        for node,sign in ((i,1.),(j,-1.)):
            for q,value in enumerate(unit):
                if value:colrows.append(3*node+q);colcols.append(m);colvals.append(sign*float(value))
        if resource:
            for r,v in resource.items():arows.append(r);acols.append(m);avals.append(v)
        bounds.append((float(lo),float(hi)));labels.append(label);kinds.append(kind);stiffness.append(float(k));initial.append(float(N0))
        elements.append({'i':i,'j':j,'length_mm':length,'kind':kind,'component':components[i] if components[i]==components[j] else 'joint'})
        return m
    for (i,j),cells in sorted(incidence.items()):
        L=float(np.linalg.norm(nodes[j]-nodes[i]));name=components[i];fc=fg if name=='girder' else fs;ec=eg if name=='girder' else es
        volume=float(cell_volume[cells].sum());cap=cf*.45*fc*volume/L
        element(f'{name} strut {i}/{j}','concrete',i,j,-cap,0.,ec*volume/(15*L*L),resource={r:-L/len(cells) for r in cells})
    def at(name,k,xy):return ids[name,k,mesh[name][2][tuple(round(number(v),7) for v in xy)]]
    # Real points for longitudinal steel; no equivalent row at x=0 for M2.
    steel_ledger=[]
    for name,table in [('girder',bars),('slab',slab_longitudinal)]:
        for bar in table:
            area=number(bar['area_mm2']);cap=number(bar['capacity_N']);xy=(bar['x_mm'],bar['y_mm'])
            if area<=0 or cap<0:raise ValueError('Steel area and developed force are invalid.')
            E=number(bar.get('development',{}).get('Es_MPa',195000. if bar.get('kind')=='prestress' else 200000.))
            N0=0.
            # Retain the specified physical post-loss Pe even if the supplied
            # development ceiling is inconsistent. compatible_state must then
            # block the reference, rather than silently reducing known Pe.
            if bar.get('kind')=='prestress':N0=area*number(bar['fpe_MPa'])*number(bar.get('development',{}).get('transfer_factor',1.))
            for k in range(2):
                m=element(bar['label']+f' / bay {k}',bar.get('kind','ordinary'),at(name,k,xy),at(name,k+1,xy),0.,sf*cap,E*area/p,N0=N0)
                steel_ledger.append({'element':m,'label':bar['label'],'area_mm2':area,'capacity_N':sf*cap,'initial_N':N0,'x_mm':bar['x_mm'],'y_mm':bar['y_mm'],'component':name})
    for k in range(3):
        weight=.5 if k in (0,2) else 1.
        area=math.pi*dg*dg/4*p/sg*weight
        for u,v in zip(ring,ring[1:]+ring[:1]):
            i,j=at('girder',k,u),at('girder',k,v);L=np.linalg.norm(nodes[j]-nodes[i])
            element(f'girder hoop {k}/{u}','hoop',i,j,0.,sf*area*fyg,200000*area/L)
        for r in across:
            area=math.pi*r['db']**2/4*p/r['spacing']*weight
            for x1,x2 in zip(slab_x,slab_x[1:]):
                i,j=at('slab',k,(x1,r['y'])),at('slab',k,(x2,r['y']))
                element(f"{r['layer']} slab transverse {k}/{x1}",'slab_transverse',i,j,0.,sf*area*r['fy'],200000*area/(x2-x1))
    contacts=[];dowels=[]
    for k in range(3):
        weight=.5 if k in (0,2) else 1.
        for index,x in enumerate(xs):
            left=xmin if index==0 else .5*(xs[index-1]+x);right=xmax if index==len(xs)-1 else .5*(x+xs[index+1])
            area=(right-left)*p*weight;i=at('girder',k,(x,top));j=at('slab',k,(x,top))
            # Numerical secant regularization, NOT a calibrated bond/slip law.
            kn=min(eg,es)*area/db;kt=.1*kn
            normal=element(f'joint contact normal {k}/{index}','contact_normal',i,j,-cf*.45*min(fg,fs)*area,0.,kn,direction=[0,1,0])
            L=sf*icap*area
            qx=element(f'joint contact longitudinal {k}/{index}','contact_shear',i,j,-L,L,kt,direction=[1,0,0])
            qz=element(f'joint contact transverse {k}/{index}','contact_shear',i,j,-L,L,kt,direction=[0,0,1])
            # Inscribed octagon: cannot exceed circular Coulomb friction OR
            # the independent code interface-stress ceiling. Cohesion = 0.
            for facet in range(8):
                angle=(facet+.5)*math.pi/4
                for m,v in ((normal,mu*math.cos(math.pi/8)),(qx,math.cos(angle)),(qz,math.sin(angle))):
                    arows.append(len(limits));acols.append(m);avals.append(v)
                limits.append(0.);resource_labels.append(f'contact friction cone {k}/{index}/{facet}')
                for m,v in ((qx,math.cos(angle)),(qz,math.sin(angle))):arows.append(len(limits));acols.append(m);avals.append(v)
                limits.append(L*math.cos(math.pi/8));resource_labels.append(f'contact stress ceiling {k}/{index}/{facet}')
            contacts.append({'plane':k,'x_mm':x,'normal':normal,'qx':qx,'qz':qz,'area_mm2':area,'girder_node':i,'slab_node':j,'kn_N_per_mm':kn,'kt_N_per_mm':kt})
        area=math.pi*db*db/4*p/sd*weight
        for segment,(xy1,xy2) in enumerate(zip(path,path[1:])):
            c1='girder' if xy1[1]<top else 'slab';c2='girder' if xy2[1]<top else 'slab'
            i,j=at(c1,k,xy1),at(c2,k,xy2);L=float(np.linalg.norm(nodes[j]-nodes[i]))
            m=element(f'U-dowel plane {k} / segment {segment}','dowel',i,j,0.,sf*area*fyd,200000*area/L)
            if c1!=c2:
                # A physical U has ONE crossing per leg. Recover the force on
                # the slab, accounting for the reversed left-hand bar path.
                side=1 if xy1[0]<centre else 2
                gn=i if c1=='girder' else j;sn=j if c2=='slab' else i
                dowels.append({'plane':k,'leg':side,'element':m,'area_mm2':area,'single_leg_capacity_N':sf*area*fyd,
                    'girder_node':gn,'slab_node':sn,'hook_node':at('slab',k,(legs[side-1],anchor_top))})
    if len(dowels)!=6:raise ValueError('Continuous U topology must cross the interface exactly twice per plane.')
    n=len(nodes);m=len(labels)
    Bmat=sparse.csr_matrix((colvals,(colrows,colcols)),shape=(3*n,m));Amat=sparse.csr_matrix((avals,(arows,acols)),shape=(len(limits),m))
    fixed=[3*ids['girder',0,i]+q for i in range(len(mesh['girder'][0])) for q in range(3)]
    end=[ids['girder',2,i] for i in range(len(mesh['girder'][0]))]
    volumes={name:float(cell_volume[np.array(cell_component)==name].sum()) for name in ('girder','slab')}
    for name,poly in [('girder',girder),('slab',slab)]:
        if abs(volumes[name]-poly.area*2*p)>1e-6*poly.area*2*p:raise ValueError('Concrete prismatic volume partition failed.')
    trace={'version':VERSION,'boundary':'Girder-only load entry and girder-only support; slab ends are free. Local transfer experiment, not recovered CSI component loading.',
        'pitch_mm':p,'planes':3,'nominal':nominal,'steel_factor':sf,'concrete_factor':cf,'mu':mu,'cohesion':0.,
        'origin':dict(origin),'girder_area_mm2':girder.area,'slab_area_mm2':slab.area,'concrete_volumes_mm3':volumes,
        'girder_fc_MPa':fg,'slab_fc_MPa':fs,
        'prismatic_cells':len(cell_volume),'nodes':n,'members':m,'contact_area_mm2':sum(c['area_mm2'] for c in contacts),
        'longitudinal_ledger':steel_ledger,'U_leg_anchor_top_y_mm':anchor_top,'U_leg_anchor_bottom_y_mm':anchor_bottom,
        'U_geometry':{'A_mm':a,'B_mm':B,'D_mm':D,'C_mm':tail,'F_mm':F,'db_mm':db,'radius_mm':radius},'U_path_xy_mm':path,
        'girder_polygon_xy_mm':list(girder.exterior.coords),'slab_polygon_xy_mm':list(slab.exterior.coords),'hoop_xy_mm':ring,
        'slab_transverse_layers':across,'contact_x_mm':xs,'concrete_cell_count':len(cell_volume),
        'limitations':['Concrete trace/volume yield domain is assumed; actual nodal faces / splitting / confinement remain unverified.',
            'Conditional slab transverse anchorage/continuity beyond the assigned strip is not established by Be or by bar crossings.',
            'Perfect bond at embedded steel nodes; the continuous U is one physical supply, not additional independent leg/return/tail capacities. Bond and nodal anchorage remain unverified.',
            'Secant springs kn=Emin*Ac/db and kt=0.1kn are numerical assumptions, not measured joint properties.',
            'Associated friction-cone flow has dilation; compatibility is mathematical within this assumed law, not validated physical slip prediction.',
            'A local prismatic transfer experiment cannot establish whole-member composite Tn or a full-span design envelope.']}
    return Model(nodes,components,Bmat,np.array(bounds),Amat,np.array(limits),resource_labels,labels,kinds,np.array(stiffness),np.array(initial),elements,fixed,end,contacts,dowels,trace)


def without(model,*kinds):
    """Ablation of physical supplies; retain identical concrete / boundary mesh."""
    bounds=model.bounds.copy();initial=model.initial.copy()
    for i,kind in enumerate(model.kinds):
        if kind in kinds:bounds[i]=[0.,0.];initial[i]=0.
    return replace(model,bounds=bounds,initial=initial,trace={**model.trace,'disabled_supplies':list(kinds)})


def slab_entry(model):
    """Pure roll-transfer experiment, not an actual CSI component load split."""
    last=2*model.trace['pitch_mm']
    end=[i for i,c in enumerate(model.components) if c=='slab' and abs(model.nodes[i,0]-last)<1e-7]
    return replace(model,end_nodes=end,trace={**model.trace,
        'boundary':'SLAB-ENTRY / GIRDER-SUPPORT transfer experiment. Only the declared benchmark load is applied; no actual CSI Beam/Slab loading is inferred.'})


def factored(model):
    """Design-domain supply factors, separate from nominal material stiffness.

    Initial post-loss Pe is NEVER multiplied by a resistance factor.
    """
    if not model.trace.get('nominal'):raise ValueError('Supply factors may only be applied once to a nominal model.')
    bounds=model.bounds.copy();limits=model.limits.copy()
    for i,kind in enumerate(model.kinds):bounds[i]*=.7 if kind in ('concrete','contact_normal') else .9
    for i,label in enumerate(model.resource_labels):
        if 'concrete cell' in label:limits[i]*=.7
        elif label.startswith('contact stress ceiling'):limits[i]*=.9
    ledger=[{**r,'capacity_N':.9*r['capacity_N']} for r in model.trace.get('longitudinal_ledger',[])]
    dowels=[{**r,'single_leg_capacity_N':.9*r['single_leg_capacity_N']} for r in model.dowels]
    return replace(model,bounds=bounds,limits=limits,dowels=dowels,trace={**model.trace,'nominal':False,'steel_factor':.9,'concrete_factor':.7,'longitudinal_ledger':ledger})

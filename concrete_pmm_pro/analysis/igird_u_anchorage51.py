"""Measured U/hook and slab-layer anchorage planes; no invented STM node.

The joint plane and the exit of an extended nodal zone are different critical
sections (AASHTO 2020 5.8.2.4.2). A mat elevation is a candidate inspection
plane, NOT a located node face. This module neither reduces nor increases the
nominal LP strength and cannot qualify a closed torsion cage.
"""
import math

VERSION = 'IGIRDER.COMPOSITE51.nodal-anchorage-planes'


def positive(value, name, *, zero=False):
    if isinstance(value, bool):
        raise ValueError('Known finite ' + name + ' required.')
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError('Known finite ' + name + ' required.') from None
    if not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError('Known finite ' + name + ' required.')
    return value


def evaluate(*, detail, params, slab_thickness_mm, slab_bottom_y_mm, db_mm, spacing_mm,
             anchorage, inventory, calculation):
    """Read existing measured geometry; all distances are above the joint.

    Hook available length is measured to the OUTSIDE of the bend. E stays the
    user-entered depth below the slab top. No hook orientation, enclosure of a
    mat, nodal face area, or transverse physical bar position is inferred.
    """
    t = positive(slab_thickness_mm, 'slab thickness')
    bottom_y = float(slab_bottom_y_mm)
    if isinstance(slab_bottom_y_mm, bool) or not math.isfinite(bottom_y):
        raise ValueError('Known slab bottom ordinate required.')
    db = positive(db_mm, 'U diameter')
    spacing = positive(spacing_mm, 'U spacing')
    B = positive(detail.get('slab_ldh_available_mm'), 'hook outside height')
    D = positive(detail.get('hook_inside_bend_mm'), 'inside bend diameter')
    required = positive(anchorage.get('hook_required_mm'), 'standard hook development')
    if B >= t:
        raise ValueError('Hook outside must lie inside the slab.')
    radius = (D + db) / 2
    tangent = B - radius - db / 2
    if tangent <= 0:
        raise ValueError('Hook leaves no straight U leg above the interface.')
    latest_exit = B - required
    rows = []
    for face in ('top', 'bottom'):
        mat = (detail.get('slab_transverse_mesh') or {}).get(face) or {}
        diameter = positive(mat.get('Diameter_mm'), face + ' transverse diameter')
        cover = positive(mat.get('Clear_cover_mm'), face + ' transverse cover', zero=True)
        distance = cover + diameter / 2
        z = t-distance if face == 'top' else distance
        if not 0 < z < t:
            raise ValueError('Transverse layer must lie inside the slab.')
        rows.append(_plane(face + ' transverse', z, B, tangent, required, latest_exit))
        # Read the position actually used by the section model. Never infer
        # longitudinal bars at an arbitrary x or override the layer resolver.
        # Section Builder material labels can omit top/bottom. Reconcile the
        # known cover with the ACTUAL y position in the analysis inventory.
        dl = positive(params.get('deck_long_rebar_' + face + '_diameter_mm'), face + ' longitudinal diameter')
        cl = positive(params.get('deck_long_rebar_' + face + '_cover_mm'), face + ' longitudinal cover', zero=True)
        long_distance = cl + dl / 2
        long_z = t-long_distance if face == 'top' else long_distance
        if not 0 < long_z < t:
            raise ValueError('Longitudinal layer must lie inside the slab.')
        if not any(b.get('component') == 'slab' and
                   math.isclose(float(b['y_mm'])-bottom_y, long_z, abs_tol=1e-6)
                   for b in inventory):
            raise ValueError('Slab longitudinal cover does not match the analysis inventory: ' + face)
        rows.append(_plane(face + ' longitudinal', long_z, B, tangent, required, latest_exit))
    forces = []
    supply = calculation.get('supplies') or {}
    ceiling = positive(supply.get('u_leg_N_per_mm'), 'U force ceiling', zero=True)
    for action in ('V', 'T', 'VT', 'V_fixed_MN', 'T_fixed_MN'):
        witness = calculation.get(action) or {}
        values = witness.get('U_force_each_N_per_mm')
        if not witness.get('ready') or values is None:
            continue
        if len(values) != 2:
            raise ValueError('Exactly two U-leg force values required.')
        for side, value in zip(('left', 'right'), values):
            force = positive(value, 'U witness force', zero=True)
            forces.append({'witness':action, 'leg':side,
                'force_at_model_capacity_kN_per_bar':force*spacing/1000,
                'ceiling_kN_per_bar':ceiling*spacing/1000,
                'force_N_per_mm':force})
    return {'version':VERSION, 'status':'NODAL TRANSFER UNVERIFIED',
        'slab_thickness_mm':t, 'hook_depth_E_mm':t-B,
        'hook_outside_above_joint_mm':B, 'hook_horizontal_centre_above_joint_mm':B-db/2,
        'straight_leg_top_above_joint_mm':tangent,
        'hook_required_mm':required, 'latest_fully_developed_exit_above_joint_mm':latest_exit,
        'planes':rows, 'U_forces':forces,
        'interface_hook_dimension_status':anchorage.get('status'),
        'actual_node_face_area_mm2':None, 'actual_node_exit_above_joint_mm':None,
        'hook_orientation_verified':False, 'torsion_enclosure_verified':False,
        'accepted_composite_capacity':None, 'changes_nominal_resistance':False,
        'basis':'AASHTO LRFD 9th Edition 2020: 5.8.2.4.2, 5.10.8.2.4a and 5.10.8.2.6d. Full-yield standard tension-hook length, without beneficial confinement/excess-steel modifiers.',
        'interpretation':'Mat-plane checks are conditional geometry screens, not actual STM node checks or proof that a hook encloses a longitudinal bar. A plane shortfall does not alone demonstrate structural failure. The node exit, strut geometry/face areas, local splitting and anchorage still need a consistent stress field.',
        'force_level':'Witness forces are at the solved nominal capacity for each ray, not a recovered force in the actual structure. N/mm times U spacing in mm gives N per bar; two legs are not added twice.'}


def _plane(name, z, B, tangent, required, latest_exit):
    available = B-z
    straight = 0 <= z <= tangent
    return {'plane':name, 'above_joint_mm':z,
        'hook_available_from_plane_mm':available if straight else None,
        'signed_hook_outside_minus_plane_mm':available,
        'hook_required_mm':required,
        'on_straight_U_leg':straight,
        'full_yield_hook_length_at_this_plane':available >= required-1e-8 if straight else None,
        'exit_drop_from_plane_needed_mm':max(0., z-latest_exit) if straight else None,
        'screen':'PLANE ABOVE STRAIGHT LEG' if not straight else
                 'LENGTH AVAILABLE AT PLANE' if available >= required-1e-8 else
                 'NODE EXIT MUST BE BELOW PLANE'}

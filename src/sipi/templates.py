# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""PCB cross-section templates with rectangular or tapered signal conductors. All lengths are in metres."""

from __future__ import annotations

import math
from dataclasses import replace
from numbers import Real

from .crosssection import CrossSection, Layer, Trace

__all__ = ['microstrip', 'stripline', 'coupled_microstrip', 'grounded_coplanar', 'coated_microstrip',
           'asymmetric_coupled_microstrip', 'asymmetric_coupled_stripline',
           'asymmetric_coupled_layered_stripline',
           'coplanar_stripline', 'coupled_coplanar_stripline',
           'offset_stripline', 'coupled_stripline', 'broadside_stripline',
           'coupled_grounded_coplanar', 'layered_stripline', 'coupled_layered_stripline',
           'layered_broadside_stripline',
           'layered_coplanar_stripline', 'coupled_layered_coplanar_stripline',
           'coupled_coated_microstrip',
           'coated_grounded_coplanar', 'coupled_coated_grounded_coplanar',
           'unbacked_coplanar', 'coupled_unbacked_coplanar',
           'coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar',
           'conformal_coated_microstrip', 'coupled_conformal_coated_microstrip',
           'conformal_coated_grounded_coplanar', 'coupled_conformal_coated_grounded_coplanar',
           'conformal_coated_unbacked_coplanar', 'coupled_conformal_coated_unbacked_coplanar',
           'with_surface_mask']


def _positive(name, value, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    if value < 0 or (value == 0 and not zero):
        raise ValueError(f'{name} must be {">= 0" if zero else "> 0"}')
    return float(value)


def _surface(width, substrate_height, eps_r, thickness, tan_delta, air_height, box_width):
    w = _positive('width', width)
    h = _positive('substrate_height', substrate_height)
    t = _positive('thickness', thickness, zero=True)
    air = 10*h + t if air_height is None else _positive('air_height', air_height)
    box = max(20*h, 4*w) if box_width is None else _positive('box_width', box_width)
    layers = [Layer('substrate', h, _positive('eps_r', eps_r),
                    _positive('tan_delta', tan_delta, zero=True)), Layer('air', air)]
    return w, h, t, box, layers


def microstrip(*, width, substrate_height, eps_r, thickness=0.0, tan_delta=0.0,
               air_height=None, box_width=None, top_width=None):
    """One surface trace above a grounded substrate; open top and side walls."""
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    return CrossSection(layers, [Trace('signal', 0.0, w, h, t, top_width=top_width)], box)


def stripline(*, width, plane_spacing, eps_r, thickness=0.0, tan_delta=0.0,
              box_width=None, top_width=None):
    """Trace centred between two ground planes in a homogeneous dielectric.

    plane_spacing is the full distance between the planes, including copper.
    """
    w = _positive('width', width)
    b = _positive('plane_spacing', plane_spacing)
    t = _positive('thickness', thickness, zero=True)
    box = max(12*b, 4*w) if box_width is None else _positive('box_width', box_width)
    return CrossSection([Layer('dielectric', b, _positive('eps_r', eps_r),
                               _positive('tan_delta', tan_delta, zero=True))],
                        [Trace('signal', 0.0, w, (b-t)/2, t, top_width=top_width)], box, top='ground')


def coupled_microstrip(*, width, gap, substrate_height, eps_r, thickness=0.0,
                       tan_delta=0.0, air_height=None, box_width=None, top_width=None):
    """Equal-width surface pair with edge-to-edge gap and a bottom ground."""
    gap = _positive('gap', gap)
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    if box_width is None:
        box = max(box, 4*(2*w+gap))
    offset = (w+gap)/2
    return CrossSection(layers, [Trace('positive', -offset, w, h, t, top_width=top_width),
                                Trace('negative', offset, w, h, t, top_width=top_width)], box)


def asymmetric_coupled_microstrip(*, left_width, right_width, gap, substrate_height, eps_r,
                                 left_thickness=0.0, right_thickness=0.0, tan_delta=0.0,
                                 air_height=None, box_width=None,
                                 left_top_width=None, right_top_width=None):
    """Unequal surface traces over a ground plane, positive left and negative right.

    gap separates bottom edges. Both traces start at the substrate surface;
    the entire bottom-width span is centred at x=0. Top widths and thicknesses
    are independent. Default air is 10 substrate heights plus the larger
    thickness; default box is max(20 heights, 4 total spans). Geometry guards
    reject overlaps and clipping. No exchange symmetry or eigenmodes are assumed.
    """
    left = _positive('left_width', left_width)
    right = _positive('right_width', right_width)
    gap = _positive('gap', gap)
    lt = _positive('left_thickness', left_thickness, zero=True)
    rt = _positive('right_thickness', right_thickness, zero=True)
    _, h, _, box, layers = _surface(max(left, right), substrate_height, eps_r,
                                    max(lt, rt), tan_delta, air_height, box_width)
    if box_width is None:
        box = max(box, 4*(left+gap+right))
    return CrossSection(layers,
        [Trace('positive', -(gap+right)/2, left, h, lt, top_width=left_top_width),
         Trace('negative', (gap+left)/2, right, h, rt, top_width=right_top_width)], box)


def grounded_coplanar(*, width, gap, ground_width, substrate_height, eps_r,
                     thickness=0.0, tan_delta=0.0, air_height=None, box_width=None, top_width=None):
    """Surface signal with finite coplanar grounds and a bottom ground plane.

    gap is the edge-to-edge signal/ground spacing on each side. ground_width
    is finite and must be enlarged separately to check ground truncation.
    """
    gap = _positive('gap', gap)
    gw = _positive('ground_width', ground_width)
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    if box_width is None:
        box = max(box, w+2*gap+2*gw+4*h)
    offset = (w+gw)/2+gap
    return CrossSection(layers, [Trace('signal', 0.0, w, h, t, top_width=top_width),
                                Trace('ground_left', -offset, gw, h, t, ground=True),
                                Trace('ground_right', offset, gw, h, t, ground=True)], box)


def coupled_grounded_coplanar(*, width, gap, ground_gap, ground_width,
                             substrate_height, eps_r, thickness=0.0, tan_delta=0.0,
                             air_height=None, box_width=None, top_width=None):
    """Equal-width surface pair between finite coplanar grounds, over a ground plane.

    gap separates the two signal bottom edges. ground_gap separates each outer
    signal bottom edge from its adjacent ground. There is no central ground.
    Both grounds are rectangular and share the signals' thickness. Only the
    signals use top_width. All four conductors lie on the substrate surface.
    Ground width and open-domain size require separate convergence checks.
    """
    gap = _positive('gap', gap)
    gg = _positive('ground_gap', ground_gap)
    gw = _positive('ground_width', ground_width)
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    if box_width is None:
        box = max(box, 2*w+gap+2*gg+2*gw+4*h)
    offset = (w+gap)/2
    ground_offset = w+gap/2+gg+gw/2
    return CrossSection(layers,
        [Trace('positive', -offset, w, h, t, top_width=top_width),
         Trace('negative', offset, w, h, t, top_width=top_width),
         Trace('ground_left', -ground_offset, gw, h, t, ground=True),
         Trace('ground_right', ground_offset, gw, h, t, ground=True)], box)


def _unbacked_coplanar(base, lower_air_height):
    lower = (10*base.layers[0].thickness if lower_air_height is None else
             _positive('lower_air_height', lower_air_height))
    section = CrossSection([Layer('lower_air', lower), *base.layers],
                           [replace(t, y=t.y+lower) for t in base.traces],
                           base.width, bottom='open',
                           dielectric_regions=[replace(r, vertices=tuple((x,y+lower) for x,y in r.vertices))
                                               for r in base.dielectric_regions])
    if section.dielectric_regions:
        _check_conformal_resolution(section)
    return section


def unbacked_coplanar(*, width, gap, ground_width, substrate_height, eps_r,
                     thickness=0.0, tan_delta=0.0, air_height=None,
                     lower_air_height=None, box_width=None, top_width=None):
    """Surface signal and finite coplanar grounds, with no backing ground plane.

    A finite substrate lies between lower and upper air regions. All outer
    boundaries are open; the two coplanar ground traces define the reference.
    gap separates signal bottom edges from grounds. Only the signal can taper.
    lower_air_height defaults to ten substrate heights and needs convergence.
    """
    base = grounded_coplanar(width=width, gap=gap, ground_width=ground_width,
        substrate_height=substrate_height, eps_r=eps_r, thickness=thickness,
        tan_delta=tan_delta, air_height=air_height, box_width=box_width, top_width=top_width)
    return _unbacked_coplanar(base, lower_air_height)


def coupled_unbacked_coplanar(*, width, gap, ground_gap, ground_width,
                             substrate_height, eps_r, thickness=0.0, tan_delta=0.0,
                             air_height=None, lower_air_height=None,
                             box_width=None, top_width=None):
    """Equal surface pair between finite coplanar grounds without a backing plane.

    gap separates signal bottom edges; ground_gap separates the outer signal
    edges from the grounds. No central ground. Lower air separates the finite
    substrate from the open bottom boundary. Grounds remain rectangular.
    """
    base = coupled_grounded_coplanar(width=width, gap=gap, ground_gap=ground_gap,
        ground_width=ground_width, substrate_height=substrate_height, eps_r=eps_r,
        thickness=thickness, tan_delta=tan_delta, air_height=air_height,
        box_width=box_width, top_width=top_width)
    return _unbacked_coplanar(base, lower_air_height)


def _coated_coplanar(base, coating_height, coating_eps_r, coating_tan_delta, air_height):
    height = _positive('coating_height', coating_height)
    if height <= max(t.thickness for t in base.traces):
        raise ValueError('coating_height must exceed the conductor thickness')
    coating = Layer('coating', height, _positive('coating_eps_r', coating_eps_r),
                    _positive('coating_tan_delta', coating_tan_delta, zero=True))
    air = base.layers[1] if air_height is None else Layer('air', _positive('air_height', air_height))
    return CrossSection([base.layers[0], coating, air], base.traces, base.width)


def coated_grounded_coplanar(*, width, gap, ground_width, substrate_height, eps_r,
                            coating_height, coating_eps_r, thickness=0.0, tan_delta=0.0,
                            coating_tan_delta=0.0, air_height=None, box_width=None,
                            top_width=None):
    """One signal and finite coplanar grounds in a flat full-width coating.

    gap is signal-bottom-edge to ground-edge on each side. coating_height
    starts at the substrate, includes all metal and must exceed thickness.
    air_height starts above the coating. Only the signal has optional taper.
    """
    # Validate the uncoated scaffold with its automatic air clearance; the
    # requested air height belongs above the coating, not above the substrate.
    base = grounded_coplanar(width=width, gap=gap, ground_width=ground_width,
        substrate_height=substrate_height, eps_r=eps_r, thickness=thickness,
        tan_delta=tan_delta, air_height=None, box_width=box_width, top_width=top_width)
    return _coated_coplanar(base, coating_height, coating_eps_r, coating_tan_delta, air_height)


def coupled_coated_grounded_coplanar(*, width, gap, ground_gap, ground_width,
                                    substrate_height, eps_r, coating_height, coating_eps_r,
                                    thickness=0.0, tan_delta=0.0, coating_tan_delta=0.0,
                                    air_height=None, box_width=None, top_width=None):
    """A surface pair between finite coplanar grounds, all in a planar coating.

    gap separates signal bottom edges; ground_gap separates outer signal
    bottom edges from the grounds. No central ground. Coating spans the whole
    box and includes copper height; air starts above it. Grounds stay rectangular.
    """
    base = coupled_grounded_coplanar(width=width, gap=gap, ground_gap=ground_gap,
        ground_width=ground_width, substrate_height=substrate_height, eps_r=eps_r,
        thickness=thickness, tan_delta=tan_delta, air_height=None,
        box_width=box_width, top_width=top_width)
    return _coated_coplanar(base, coating_height, coating_eps_r, coating_tan_delta, air_height)


def coated_unbacked_coplanar(*, width, gap, ground_width, substrate_height, eps_r,
                            coating_height, coating_eps_r, thickness=0.0, tan_delta=0.0,
                            coating_tan_delta=0.0, air_height=None, lower_air_height=None,
                            box_width=None, top_width=None):
    """One coated signal between finite coplanar grounds, without a backing plane.

    A finite substrate separates lower air from the full-width planar coating.
    coating_height includes metal and exceeds thickness; upper air starts above
    it. All outer boundaries are open. Only the signal can taper.
    """
    base = coated_grounded_coplanar(width=width, gap=gap, ground_width=ground_width,
        substrate_height=substrate_height, eps_r=eps_r, coating_height=coating_height,
        coating_eps_r=coating_eps_r, thickness=thickness, tan_delta=tan_delta,
        coating_tan_delta=coating_tan_delta, air_height=air_height,
        box_width=box_width, top_width=top_width)
    return _unbacked_coplanar(base, lower_air_height)


def coupled_coated_unbacked_coplanar(*, width, gap, ground_gap, ground_width,
                                    substrate_height, eps_r, coating_height, coating_eps_r,
                                    thickness=0.0, tan_delta=0.0, coating_tan_delta=0.0,
                                    air_height=None, lower_air_height=None,
                                    box_width=None, top_width=None):
    """Coated equal pair between finite grounds, with air below the substrate.

    gap is signal-to-signal; ground_gap is outer-signal-to-ground clearance.
    Dimensions use bottom edges, only signals taper, and no central ground or
    backing plane is added. Upper air starts above the planar coating.
    """
    base = coupled_coated_grounded_coplanar(width=width, gap=gap, ground_gap=ground_gap,
        ground_width=ground_width, substrate_height=substrate_height, eps_r=eps_r,
        coating_height=coating_height, coating_eps_r=coating_eps_r,
        thickness=thickness, tan_delta=tan_delta, coating_tan_delta=coating_tan_delta,
        air_height=air_height, box_width=box_width, top_width=top_width)
    return _unbacked_coplanar(base, lower_air_height)


def _check_conformal_resolution(section):
    """Reject unresolved features before automatic meshing; never snap a gap."""
    tolerance = 1e-12*max(section.width, section.height)
    features = [layer.thickness for layer in section.layers]
    features.extend(r.minimum_dimension for r in section.dielectric_regions)
    features.append(section.height-max(r._shape.bounds[3] for r in section.dielectric_regions))
    for trace in section.traces:
        features.extend((trace.width, trace.width if trace.top_width is None else trace.top_width))
        if trace.thickness > 0:
            features.append(trace.thickness)
    if min(features) <= tolerance:
        raise ValueError('conformal coating features must exceed 1e-12 times the box scale; '
                         'increase the unresolved film, gap, air or metal dimension')


def _conformal_coated(base, coating_thickness, coating_eps_r, coating_tan_delta, air_height):
    """Union a planar film and exact straight-side offset envelopes."""
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    from .polygons import DielectricRegion

    d = _positive('coating_thickness', coating_thickness)
    eps = _positive('coating_eps_r', coating_eps_r)
    loss = _positive('coating_tan_delta', coating_tan_delta, zero=True)
    h, half = base.layers[0].thickness, base.width/2
    thickness = max(trace.thickness for trace in base.traces)
    air = base.layers[1].thickness if air_height is None else _positive('air_height', air_height)
    if not (h+d > h and h+thickness+d > h+thickness):
        raise ValueError('coating_thickness cannot be resolved at the substrate/trace height')
    shapes = [box(-half, h, half, h+d)]
    for trace in base.traces:
        top = trace.width if trace.top_width is None else trace.top_width
        if top > trace.width:
            raise ValueError('conformal coating requires top_width <= width; overhangs are unsupported')
        if trace.thickness == 0:
            continue  # A thin strip has no raised surface; the film is planar.
        # For side slope s=(width-top)/(2*t), delta=d/(sqrt(1+s*s)+s).
        # The half-angle form avoids subtracting nearly equal large numbers.
        delta = d*math.tan(.5*math.atan2(trace.thickness, (trace.width-top)/2))
        left, right = trace.x-trace.width/2-delta, trace.x+trace.width/2+delta
        if left < -half or right > half:
            raise ValueError('conformal coating extends outside box_width; increase the box')
        shapes.append(Polygon([(left,h+d), (right,h+d),
            (trace.x+top/2+delta,h+trace.thickness+d),
            (trace.x-top/2-delta,h+trace.thickness+d)]))
    # Remove exactly collinear seam vertices after unions. Positive-width air
    # slits remain intact; no tolerance-based simplification or snapping.
    coating = unary_union(shapes).simplify(0, preserve_topology=True)
    if coating.geom_type != 'Polygon' or coating.interiors or coating.is_empty or not coating.is_valid:
        raise ValueError('conformal coating must form one simple region without enclosed air pockets')
    region = DielectricRegion('coating', tuple(coating.exterior.coords)[:-1], eps, loss)
    section = CrossSection([base.layers[0], Layer('air', thickness+d+air)],
                           base.traces, base.width, dielectric_regions=[region])
    if section.height <= coating.bounds[3]:
        raise ValueError('air_height cannot be resolved above the conformal coating')
    _check_conformal_resolution(section)
    return section


def conformal_coated_microstrip(*, width, substrate_height, eps_r,
                               coating_thickness, coating_eps_r, thickness=0.0,
                               tan_delta=0.0, coating_tan_delta=0.0,
                               air_height=None, box_width=None, top_width=None):
    """One trace with a straight-sided, mitered conformal dielectric film.

    coating_thickness is normal to the substrate, trace top and sloping sides;
    corner offsets meet at miters. Only rectangles or narrowing-top trapezoids
    are supported. Upper air starts above the highest coated trace. This is
    not a meniscus, rounded-corner or measured deposition model.
    """
    base = microstrip(width=width, substrate_height=substrate_height, eps_r=eps_r,
        thickness=thickness, tan_delta=tan_delta, air_height=None,
        box_width=box_width, top_width=top_width)
    return _conformal_coated(base, coating_thickness, coating_eps_r, coating_tan_delta, air_height)


def coupled_conformal_coated_microstrip(*, width, gap, substrate_height, eps_r,
                                       coating_thickness, coating_eps_r, thickness=0.0,
                                       tan_delta=0.0, coating_tan_delta=0.0,
                                       air_height=None, box_width=None, top_width=None):
    """Equal surface pair with a mitered normal-thickness dielectric film.

    gap is the signal bottom-edge spacing. Meeting coating envelopes are
    united as one material; no enclosed air pocket or implicit box clipping.
    Top widths may not exceed bottom widths. Upper air starts above the film.
    """
    base = coupled_microstrip(width=width, gap=gap, substrate_height=substrate_height,
        eps_r=eps_r, thickness=thickness, tan_delta=tan_delta, air_height=None,
        box_width=box_width, top_width=top_width)
    return _conformal_coated(base, coating_thickness, coating_eps_r, coating_tan_delta, air_height)


def conformal_coated_grounded_coplanar(*, width, gap, ground_width, substrate_height,
                                      eps_r, coating_thickness, coating_eps_r,
                                      thickness=0.0, tan_delta=0.0, coating_tan_delta=0.0,
                                      air_height=None, box_width=None, top_width=None):
    """Normal-thickness mitered film over one signal and both finite grounds.

    A bottom ground plane remains. gap is signal-to-ground bottom-edge spacing;
    only the signal can taper. Upper air starts above the highest film surface.
    The film covers the substrate, signal and rectangular coplanar grounds.
    """
    base = grounded_coplanar(width=width, gap=gap, ground_width=ground_width,
        substrate_height=substrate_height, eps_r=eps_r, thickness=thickness,
        tan_delta=tan_delta, air_height=None, box_width=box_width, top_width=top_width)
    return _conformal_coated(base, coating_thickness, coating_eps_r, coating_tan_delta, air_height)


def coupled_conformal_coated_grounded_coplanar(*, width, gap, ground_gap, ground_width,
                                              substrate_height, eps_r, coating_thickness,
                                              coating_eps_r, thickness=0.0, tan_delta=0.0,
                                              coating_tan_delta=0.0, air_height=None,
                                              box_width=None, top_width=None):
    """Coated equal signal pair between finite grounds above a backing plane.

    gap is signal-to-signal and ground_gap outer-signal-to-ground clearance.
    All bottom-edge dimensions are preserved; there is no central ground.
    Normal-thickness mitered film covers signals and both rectangular grounds.
    """
    base = coupled_grounded_coplanar(width=width, gap=gap, ground_gap=ground_gap,
        ground_width=ground_width, substrate_height=substrate_height, eps_r=eps_r,
        thickness=thickness, tan_delta=tan_delta, air_height=None,
        box_width=box_width, top_width=top_width)
    return _conformal_coated(base, coating_thickness, coating_eps_r, coating_tan_delta, air_height)


def conformal_coated_unbacked_coplanar(*, width, gap, ground_width, substrate_height,
                                      eps_r, coating_thickness, coating_eps_r,
                                      thickness=0.0, tan_delta=0.0, coating_tan_delta=0.0,
                                      air_height=None, lower_air_height=None,
                                      box_width=None, top_width=None):
    """Coated signal and finite grounds, with air below the substrate.

    The mitered film covers every trace and the substrate top. All outer
    boundaries are open; only the coplanar grounds define the reference.
    Lower air defaults to ten substrate heights. No backing plane is added.
    """
    base = conformal_coated_grounded_coplanar(width=width, gap=gap,
        ground_width=ground_width, substrate_height=substrate_height, eps_r=eps_r,
        coating_thickness=coating_thickness, coating_eps_r=coating_eps_r,
        thickness=thickness, tan_delta=tan_delta, coating_tan_delta=coating_tan_delta,
        air_height=air_height, box_width=box_width, top_width=top_width)
    return _unbacked_coplanar(base, lower_air_height)


def coupled_conformal_coated_unbacked_coplanar(*, width, gap, ground_gap, ground_width,
                                              substrate_height, eps_r, coating_thickness,
                                              coating_eps_r, thickness=0.0, tan_delta=0.0,
                                              coating_tan_delta=0.0, air_height=None,
                                              lower_air_height=None, box_width=None,
                                              top_width=None):
    """Coated signal pair and finite grounds without a backing plane.

    gap is signal-to-signal, ground_gap outer-signal-to-ground. All signals
    and rectangular grounds receive the same normal-thickness mitered film.
    Lower air translates the substrate, conductors and local film together.
    """
    base = coupled_conformal_coated_grounded_coplanar(width=width, gap=gap,
        ground_gap=ground_gap, ground_width=ground_width, substrate_height=substrate_height,
        eps_r=eps_r, coating_thickness=coating_thickness, coating_eps_r=coating_eps_r,
        thickness=thickness, tan_delta=tan_delta, coating_tan_delta=coating_tan_delta,
        air_height=air_height, box_width=box_width, top_width=top_width)
    return _unbacked_coplanar(base, lower_air_height)


def coated_microstrip(*, width, substrate_height, eps_r, coating_height,
                      coating_eps_r, thickness=0.0, tan_delta=0.0,
                      coating_tan_delta=0.0, air_height=None, box_width=None,
                      top_width=None):
    """Surface trace in a planar dielectric coating, with air above it.

    coating_height is measured from the substrate surface and must exceed the
    conductor thickness. Thus the coating fills both sides and the space above
    the trace up to a flat surface. It is not a conformal or meniscus mask model.
    """
    w, h, t, box, layers = _surface(width, substrate_height, eps_r, thickness,
                                   tan_delta, air_height, box_width)
    height = _positive('coating_height', coating_height)
    if height <= t:
        raise ValueError('coating_height must exceed the conductor thickness')
    coating = Layer('coating', height, _positive('coating_eps_r', coating_eps_r),
                    _positive('coating_tan_delta', coating_tan_delta, zero=True))
    return CrossSection([layers[0], coating, layers[1]],
                        [Trace('signal', 0.0, w, h, t, top_width=top_width)], box)


def coupled_coated_microstrip(*, width, gap, substrate_height, eps_r, coating_height,
                              coating_eps_r, thickness=0.0, tan_delta=0.0,
                              coating_tan_delta=0.0, air_height=None, box_width=None,
                              top_width=None):
    """Equal-width surface pair embedded in a flat, full-width coating layer.

    gap separates signal bottom edges. coating_height starts at the substrate
    surface and includes copper; it must exceed thickness. air_height starts
    above the coating, not the substrate. This is not a conformal mask model.
    """
    gap = _positive('gap', gap)
    base = coated_microstrip(width=width, substrate_height=substrate_height, eps_r=eps_r,
        coating_height=coating_height, coating_eps_r=coating_eps_r, thickness=thickness,
        tan_delta=tan_delta, coating_tan_delta=coating_tan_delta, air_height=air_height,
        box_width=box_width, top_width=top_width)
    trace = base.traces[0]
    offset = (trace.width+gap)/2
    box = max(base.width,4*(2*trace.width+gap)) if box_width is None else base.width
    return CrossSection(base.layers,
        [Trace('positive',-offset,trace.width,trace.y,trace.thickness,top_width=top_width),
         Trace('negative',offset,trace.width,trace.y,trace.thickness,top_width=top_width)], box)


def offset_stripline(*, width, plane_spacing, trace_height, eps_r, thickness=0.0,
                     tan_delta=0.0, box_width=None, top_width=None):
    """One trace between ground planes, with explicit bottom-face height."""
    base = stripline(width=width, plane_spacing=plane_spacing, eps_r=eps_r,
                    thickness=thickness, tan_delta=tan_delta, box_width=box_width,
                    top_width=top_width)
    y = _positive('trace_height', trace_height)
    return CrossSection(base.layers, [Trace('signal', 0, width, y, thickness, top_width=top_width)],
                        base.width, top='ground')


def coupled_stripline(*, width, gap, plane_spacing, eps_r, thickness=0.0,
                     tan_delta=0.0, box_width=None, top_width=None, trace_height=None):
    """Edge-coupled equal-width pair between two planes; gap is at the bottom face."""
    gap = _positive('gap', gap)
    base = stripline(width=width, plane_spacing=plane_spacing, eps_r=eps_r,
                    thickness=thickness, tan_delta=tan_delta, box_width=box_width,
                    top_width=top_width)
    y = base.traces[0].y if trace_height is None else _positive('trace_height', trace_height)
    offset = (width+gap)/2
    box_width = max(base.width, 4*(2*width+gap)) if box_width is None else base.width
    return CrossSection(base.layers,
        [Trace('positive', -offset, width, y, thickness, top_width=top_width),
         Trace('negative', offset, width, y, thickness, top_width=top_width)], box_width, top='ground')


def asymmetric_coupled_stripline(*, left_width, right_width, gap, plane_spacing, eps_r,
                                left_thickness=0.0, right_thickness=0.0, tan_delta=0.0,
                                box_width=None, left_top_width=None, right_top_width=None):
    """Unequal buried pair, each conductor's vertical midpoint halfway between planes.

    Positive is left, negative right; the total bottom-width span is centred at
    x=0. Gap separates the horizontal bottom-width extents. Individual bottom
    heights are (plane_spacing-thickness)/2, so unequal thicknesses do not share
    a bottom face. Top widths are independent. No exchange/eigenmode symmetry is
    assumed. The homogeneous dielectric touches both grounded planes; sides are
    insulated. Geometry guards reject contact, overlap or clipping.
    """
    left = _positive('left_width', left_width)
    right = _positive('right_width', right_width)
    gap = _positive('gap', gap)
    lt = _positive('left_thickness', left_thickness, zero=True)
    rt = _positive('right_thickness', right_thickness, zero=True)
    base = stripline(width=max(left, right), plane_spacing=plane_spacing, eps_r=eps_r,
                    thickness=max(lt, rt), tan_delta=tan_delta, box_width=box_width)
    box = max(base.width, 4*(left+gap+right)) if box_width is None else base.width
    height = base.height
    return CrossSection(base.layers,
        [Trace('positive', -(gap+right)/2, left, (height-lt)/2, lt, top_width=left_top_width),
         Trace('negative', (gap+left)/2, right, (height-rt)/2, rt, top_width=right_top_width)],
        box, top='ground')


def coplanar_stripline(*, width, gap, ground_width, plane_spacing, trace_height, eps_r,
                      thickness=0.0, tan_delta=0.0, box_width=None, top_width=None):
    """One buried trace with finite side grounds between two reference planes.

    Uniform dielectric; planes at y=0 and plane_spacing; open side boundaries.
    trace_height is the bottom-face height, excluding copper thickness. gap is
    signal-to-ground bottom-edge clearance. Both rectangular grounds share the
    signal's height and thickness. top_width affects only the signal. Ground
    width is a physical dimension; box width is a separate outer-domain choice.
    """
    gap = _positive('gap', gap); gw = _positive('ground_width', ground_width)
    base = offset_stripline(width=width, plane_spacing=plane_spacing, trace_height=trace_height,
        eps_r=eps_r, thickness=thickness, tan_delta=tan_delta, box_width=box_width, top_width=top_width)
    trace = base.traces[0]; offset = (trace.width+gw)/2+gap
    box = max(base.width, trace.width+2*gap+2*gw+4*base.height) if box_width is None else base.width
    return CrossSection(base.layers,
        [trace, Trace('ground_left', -offset, gw, trace.y, trace.thickness, ground=True),
         Trace('ground_right', offset, gw, trace.y, trace.thickness, ground=True)], box, top='ground')


def coupled_coplanar_stripline(*, width, gap, ground_gap, ground_width, plane_spacing,
                              trace_height, eps_r, thickness=0.0, tan_delta=0.0,
                              box_width=None, top_width=None):
    """Equal buried signal pair and finite outer grounds between two planes.

    gap separates signal bottom edges; ground_gap separates each outer signal
    bottom edge from its adjacent ground. No central ground is inserted. All
    four traces share the explicit bottom-face trace_height and thickness.
    Uniform dielectric, grounded top/bottom and open sides. Signal top_width
    may taper; grounds stay rectangular and all grounds share one PEC potential.
    """
    gg = _positive('ground_gap', ground_gap); gw = _positive('ground_width', ground_width)
    y = _positive('trace_height', trace_height)
    base = coupled_stripline(width=width, gap=gap, plane_spacing=plane_spacing, eps_r=eps_r,
        thickness=thickness, tan_delta=tan_delta, box_width=box_width, top_width=top_width, trace_height=y)
    left, right = base.traces
    offset = right.x+right.width/2+gg+gw/2
    box = max(base.width, 2*(offset+gw/2)+4*base.height) if box_width is None else base.width
    return CrossSection(base.layers,
        [left, right, Trace('ground_left', -offset, gw, y, left.thickness, ground=True),
         Trace('ground_right', offset, gw, y, left.thickness, ground=True)], box, top='ground')


def broadside_stripline(*, width, gap, plane_spacing, eps_r, thickness,
                       offset=0.0, tan_delta=0.0, box_width=None):
    """Vertical pair centred between planes; gap is metal-to-metal, offset is signed.

    The lower/upper traces are named positive/negative. Rectangular conductors
    have equal positive thickness. The entire box has one homogeneous dielectric.
    """
    gap = _positive('gap', gap)
    t = _positive('thickness', thickness)
    if isinstance(offset, bool) or not isinstance(offset, Real) or not math.isfinite(offset):
        raise ValueError('offset must be a finite real number')
    base = stripline(width=width, plane_spacing=plane_spacing, eps_r=eps_r,
                    thickness=t, tan_delta=tan_delta, box_width=box_width)
    box_width = max(base.width, 4*(width+abs(offset))) if box_width is None else base.width
    return CrossSection(base.layers,
        [Trace('positive', -offset/2, width, plane_spacing/2-gap/2-t, t),
         Trace('negative', offset/2, width, plane_spacing/2+gap/2, t)], box_width, top='ground')


def layered_broadside_stripline(*, width, gap, lower_height, upper_height,
                               lower_eps_r, gap_eps_r, upper_eps_r, thickness,
                               offset=0.0, lower_tan_delta=0.0, gap_tan_delta=0.0,
                               upper_tan_delta=0.0, box_width=None):
    """Broadside rectangular pair with three explicit dielectric layers.

    lower_height/upper_height are metal-to-outer-plane clearances, excluding
    copper. gap is the inner metal-face separation. Both traces have the same
    positive width/thickness. The layer interfaces meet the inner metal faces;
    the lower/upper layers include the corresponding copper thickness. The
    lower positive trace is centred at -offset/2, the upper negative at +offset/2.
    No symmetry or independent differential/common mode is assumed.
    """
    w = _positive('width', width)
    g = _positive('gap', gap)
    lower = _positive('lower_height', lower_height)
    upper = _positive('upper_height', upper_height)
    t = _positive('thickness', thickness)
    if isinstance(offset, bool) or not isinstance(offset, Real) or not math.isfinite(offset):
        raise ValueError('offset must be a finite real number')
    offset = float(offset)
    total = lower+upper+g+2*t
    box = max(12*total, 4*(w+abs(offset))) if box_width is None else _positive('box_width', box_width)
    layers = [Layer('lower', lower+t, _positive('lower_eps_r', lower_eps_r),
                    _positive('lower_tan_delta', lower_tan_delta, zero=True)),
              Layer('gap', g, _positive('gap_eps_r', gap_eps_r),
                    _positive('gap_tan_delta', gap_tan_delta, zero=True)),
              Layer('upper', upper+t, _positive('upper_eps_r', upper_eps_r),
                    _positive('upper_tan_delta', upper_tan_delta, zero=True))]
    return CrossSection(layers,
        [Trace('positive', -offset/2, w, lower, t),
         Trace('negative', offset/2, w, lower+t+g, t)], box, top='ground')


def layered_stripline(*, width, lower_height, upper_height, lower_eps_r, upper_eps_r,
                      thickness=0.0, lower_tan_delta=0.0, upper_tan_delta=0.0,
                      box_width=None, top_width=None):
    """Trace at a two-dielectric interface between two grounded planes.

    lower_height is the bottom-plane to interface/trace-bottom distance.
    upper_height is the interface to top-plane distance, INCLUDING copper.
    Copper extends into the upper dielectric; its top clearance is
    upper_height - thickness. Each dielectric has its own permittivity/loss.
    """
    w = _positive('width', width)
    low = _positive('lower_height', lower_height)
    high = _positive('upper_height', upper_height)
    t = _positive('thickness', thickness, zero=True)
    if t >= high:
        raise ValueError('thickness must be below upper_height to clear the top ground')
    box = max(12*(low+high), 4*w) if box_width is None else _positive('box_width', box_width)
    layers = [Layer('lower', low, _positive('lower_eps_r', lower_eps_r),
                    _positive('lower_tan_delta', lower_tan_delta, zero=True)),
              Layer('upper', high, _positive('upper_eps_r', upper_eps_r),
                    _positive('upper_tan_delta', upper_tan_delta, zero=True))]
    return CrossSection(layers, [Trace('signal', 0.0, w, low, t, top_width=top_width)],
                        box, top='ground')


def coupled_layered_stripline(*, width, gap, lower_height, upper_height, lower_eps_r,
                              upper_eps_r, thickness=0.0, lower_tan_delta=0.0,
                              upper_tan_delta=0.0, box_width=None, top_width=None):
    """Equal-width edge-coupled pair at the layered_stripline dielectric interface.

    gap is between signal bottom edges. Both traces extend into the upper
    dielectric. There is no averaging of permittivities or layer thicknesses.
    """
    gap = _positive('gap', gap)
    base = layered_stripline(width=width, lower_height=lower_height, upper_height=upper_height,
        lower_eps_r=lower_eps_r, upper_eps_r=upper_eps_r, thickness=thickness,
        lower_tan_delta=lower_tan_delta, upper_tan_delta=upper_tan_delta,
        box_width=box_width, top_width=top_width)
    trace = base.traces[0]
    offset = (trace.width+gap)/2
    box = max(base.width, 4*(2*trace.width+gap)) if box_width is None else base.width
    return CrossSection(base.layers,
        [Trace('positive', -offset, trace.width, trace.y, trace.thickness, top_width=top_width),
         Trace('negative', offset, trace.width, trace.y, trace.thickness, top_width=top_width)],
        box, top='ground')


def asymmetric_coupled_layered_stripline(*, left_width, right_width, gap,
                                        lower_height, upper_height, lower_eps_r, upper_eps_r,
                                        left_thickness=0.0, right_thickness=0.0,
                                        lower_tan_delta=0.0, upper_tan_delta=0.0,
                                        box_width=None, left_top_width=None, right_top_width=None):
    """Unequal pair with both bottom faces at a two-dielectric interface.

    Copper extends into the upper layer; upper_height includes copper and each
    thickness must be smaller than it. Positive is left, negative right. The
    full bottom-width span is centred horizontally and gap is between those
    horizontal extents. Materials are not averaged; exchange symmetry and
    independent even/odd modes are not assumed. Both outer planes are grounded.
    """
    left = _positive('left_width', left_width)
    right = _positive('right_width', right_width)
    gap = _positive('gap', gap)
    lt = _positive('left_thickness', left_thickness, zero=True)
    rt = _positive('right_thickness', right_thickness, zero=True)
    base = layered_stripline(width=max(left, right), lower_height=lower_height,
        upper_height=upper_height, lower_eps_r=lower_eps_r, upper_eps_r=upper_eps_r,
        thickness=max(lt, rt), lower_tan_delta=lower_tan_delta,
        upper_tan_delta=upper_tan_delta, box_width=box_width)
    y = base.traces[0].y
    box = max(base.width, 4*(left+gap+right)) if box_width is None else base.width
    return CrossSection(base.layers,
        [Trace('positive', -(gap+right)/2, left, y, lt, top_width=left_top_width),
         Trace('negative', (gap+left)/2, right, y, rt, top_width=right_top_width)], box, top='ground')


def layered_coplanar_stripline(*, width, gap, ground_width, lower_height, upper_height,
                              lower_eps_r, upper_eps_r, thickness=0.0,
                              lower_tan_delta=0.0, upper_tan_delta=0.0,
                              box_width=None, top_width=None):
    """Single buried coplanar signal at a two-dielectric interface.

    lower_height ends at the metal bottom face; upper_height includes copper.
    gap is the signal-to-ground bottom-edge clearance. Finite rectangular side
    grounds share the signal height/thickness and the plane reference potential.
    Signal top_width may taper. Physical ground width and open-side box width
    are independent dimensions; the two dielectric coefficients are not averaged.
    """
    gap = _positive('gap', gap); gw = _positive('ground_width', ground_width)
    base = layered_stripline(width=width, lower_height=lower_height, upper_height=upper_height,
        lower_eps_r=lower_eps_r, upper_eps_r=upper_eps_r, thickness=thickness,
        lower_tan_delta=lower_tan_delta, upper_tan_delta=upper_tan_delta,
        box_width=box_width, top_width=top_width)
    trace = base.traces[0]; offset = (trace.width+gw)/2+gap
    box = max(base.width, 2*(offset+gw/2)+4*base.height) if box_width is None else base.width
    return CrossSection(base.layers,
        [trace, Trace('ground_left', -offset, gw, trace.y, trace.thickness, ground=True),
         Trace('ground_right', offset, gw, trace.y, trace.thickness, ground=True)], box, top='ground')


def coupled_layered_coplanar_stripline(*, width, gap, ground_gap, ground_width,
                                      lower_height, upper_height, lower_eps_r, upper_eps_r,
                                      thickness=0.0, lower_tan_delta=0.0, upper_tan_delta=0.0,
                                      box_width=None, top_width=None):
    """Equal buried coplanar pair at a two-dielectric interface.

    gap separates signal bottom edges; ground_gap is each outer signal-to-ground
    bottom-edge clearance. No central ground is inserted. Copper extends from
    lower_height into the upper dielectric; upper_height includes that copper.
    All traces share height/thickness; side grounds are rectangular, signal
    top_width may taper, and both planes and side grounds share one PEC potential.
    """
    gg = _positive('ground_gap', ground_gap); gw = _positive('ground_width', ground_width)
    base = coupled_layered_stripline(width=width, gap=gap, lower_height=lower_height,
        upper_height=upper_height, lower_eps_r=lower_eps_r, upper_eps_r=upper_eps_r,
        thickness=thickness, lower_tan_delta=lower_tan_delta, upper_tan_delta=upper_tan_delta,
        box_width=box_width, top_width=top_width)
    left, right = base.traces; offset = right.x+right.width/2+gg+gw/2
    box = max(base.width, 2*(offset+gw/2)+4*base.height) if box_width is None else base.width
    return CrossSection(base.layers,
        [left, right, Trace('ground_left', -offset, gw, left.y, left.thickness, ground=True),
         Trace('ground_right', offset, gw, left.y, left.thickness, ground=True)], box, top='ground')


def with_surface_mask(section, *, thickness, eps_r, tan_delta=0.0, gap_fill_height=0.0):
    """Add a polygonal mask to coplanar finite rectangular/tapered surface traces.

    Offset top and side faces by thickness, with straight mitred corners (mitre
    limit 5). Clip only below the common bottom face. Optional gap_fill_height
    fills the whole box width from that face upwards. No curvature, meniscus or
    manufacturing prediction is implied. Regions are named mask, or mask_1,...
    ordered left to right when disconnected. Ground traces are coated too.
    Existing local regions are preserved and must not overlap the new mask.
    """
    from shapely.geometry import box
    from shapely.ops import unary_union
    from .polygons import DielectricRegion, trace_shape, _pieces
    if not isinstance(section, CrossSection):
        raise TypeError('section must be a CrossSection')
    t = _positive('thickness', thickness)
    fill = _positive('gap_fill_height', gap_fill_height, zero=True)
    if any(not isinstance(trace, Trace) or trace.thickness <= 0 for trace in section.traces):
        raise ValueError('surface mask requires finite rectangular or tapered traces')
    y = section.traces[0].y
    if any(trace.y != y for trace in section.traces):
        raise ValueError('surface mask traces must share one bottom face height')
    if y not in section.interfaces():
        raise ValueError('surface mask requires a layer interface at the trace bottom')
    half = section.width/2
    coatings = [trace_shape(trace).buffer(t, join_style='mitre', mitre_limit=5)
                for trace in section.traces]
    if fill > 0:
        coatings.append(box(-half, y, half, y+fill))
    shape = unary_union(coatings)
    # Retain the entire lateral/top extent so the section validator rejects
    # out-of-box coatings instead of silently cutting their physical thickness.
    xmin, _, xmax, ymax = shape.bounds
    shape = shape.intersection(box(xmin, y, xmax, ymax))
    parts = sorted(_pieces(shape), key=lambda p:p.bounds)
    if any(part.interiors for part in parts):
        raise ValueError('mask topology contains holes; supply explicit simple regions')
    regions = [DielectricRegion('mask' if len(parts)==1 else f'mask_{i+1}',
                                list(part.exterior.coords)[:-1], eps_r, tan_delta)
               for i,part in enumerate(parts)]
    return CrossSection(section.layers, section.traces, section.width,
                        bottom=section.bottom, top=section.top, sides=section.sides,
                        dielectric_regions=(*section.dielectric_regions, *regions))

"""
Roto & RotoPaint Hotbox — Nuke 16+ / PySide6 (W_Hotbox Compatible)
==================================================================
Hotkey : ` (backtick)
Behavior:
  - Roto active (No spline selected)        -> 6 Spline Type pills.
  - Roto active (Spline translation box)    -> Right: 6 Spline Types | Left: 4 Opacity-Off Keyframers (-1f, +1f, -5f, +5f).
  - RotoPaint active                        -> Right: Paint Tools    | Left: Paint Sources (FG, BG, BG1-3).
  - Keeps working when the artist edits an open Roto/RotoPaint but DAG selection vanishes.
  - Uses editing callbacks + last active Roto + selected shapes and Viewer context.
  - Clicking an unrelated node, working over DAG without selection, or closing
    active Roto Properties -> W_Hotbox.

Tip: Hold SHIFT while clicking to apply multiple options (e.g. both -1f and +1f)
     without closing the hotbox.
"""

import math
import re
import sys
import nuke
import nuke.rotopaint as rp

from PySide6.QtCore import (
    Qt, QPointF, QRectF, QTimer, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QRadialGradient, QLinearGradient,
    QFont, QPainterPath, QCursor,
)
from PySide6.QtWidgets import QWidget, QApplication


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

ACTIVE_NODE_CLASSES = ("Roto", "RotoPaint")
NUKE_HOTKEY = "`"

CANVAS     = 480
RADIUS     = 148
HUB_RADIUS = 42.0
ITEM_W     = 128
ITEM_H     = 48

_DEFAULT_TOOLBOX_BODY = (
    "{ selectAll str 1 ssx 1 ssy 1 sf 1 } "
    "{ createBezier str 1 ssx 1 ssy 1 sf 1 sb 1 tt 4 } "
    "{ createBezierCusped str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ createBSpline str 1 ssx 1 ssy 1 sf 1 sb 1 tt 5 } "
    "{ createEllipse str 1 ssx 1 ssy 1 sf 1 sb 1 tt 6 } "
    "{ createRectangle str 1 ssx 1 ssy 1 sf 1 sb 1 tt 7 } "
    "{ createRectangleCusped str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ createOpenSpline str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ brush str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ eraser src 2 str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ clone src 1 str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ reveal src 3 str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ dodge src 1 str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ burn src 1 str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ blur src 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ sharpen src 1 str 1 ssx 1 ssy 1 sf 1 sb 1 } "
    "{ smear src 1 str 1 ssx 1 ssy 1 sf 1 sb 1 }"
)

# 1A. ROTO MENU (When NO spline is selected — full 360° layout)
ROTO_SPLINE_ONLY_ITEMS = (
    {
        "kind":        "tool",
        "label":       "Bezier",
        "value":       "createBezier",
        "angle":       330,
        "accent":      "#E8A838",
        "description": "Smooth cubic spline",
        "key_label":   "1",
        "qt_key":      Qt.Key.Key_1,
    },
    {
        "kind":        "tool",
        "label":       "Cusped Bezier",
        "value":       "createBezierCusped",
        "angle":       30,
        "accent":      "#FFB74D",
        "description": "Sharp corner spline",
        "key_label":   "2",
        "qt_key":      Qt.Key.Key_2,
    },
    {
        "kind":        "tool",
        "label":       "B-Spline",
        "value":       "createBSpline",
        "angle":       90,
        "accent":      "#4FC3F7",
        "description": "Uniform spline",
        "key_label":   "3",
        "qt_key":      Qt.Key.Key_3,
    },
    {
        "kind":        "tool",
        "label":       "Open Spline",
        "value":       "createOpenSpline",
        "angle":       150,
        "accent":      "#81D4FA",
        "description": "Unclosed curve",
        "key_label":   "4",
        "qt_key":      Qt.Key.Key_4,
    },
    {
        "kind":        "tool",
        "label":       "Rectangle",
        "value":       "createRectangle",
        "angle":       210,
        "accent":      "#CE93D8",
        "description": "4-point quad spline",
        "key_label":   "5",
        "qt_key":      Qt.Key.Key_5,
    },
    {
        "kind":        "tool",
        "label":       "Ellipse",
        "value":       "createEllipse",
        "angle":       270,
        "accent":      "#A5D6A7",
        "description": "Circular/oval spline",
        "key_label":   "6",
        "qt_key":      Qt.Key.Key_6,
    },
)

# 1B. ROTO MENU (When a Spline IS Selected — Right: Spline Types | Left: Opacity Off)
ROTO_WITH_SELECTED_SPLINE_ITEMS = (
    # ── RIGHT SIDE: SPLINE TYPES (angles 25° to 155°) ───────────────────────
    {
        "kind":        "tool",
        "label":       "Bezier",
        "value":       "createBezier",
        "angle":       25,
        "accent":      "#E8A838",
        "description": "Smooth cubic spline",
        "key_label":   "1",
        "qt_key":      Qt.Key.Key_1,
    },
    {
        "kind":        "tool",
        "label":       "Cusped Bezier",
        "value":       "createBezierCusped",
        "angle":       51,
        "accent":      "#FFB74D",
        "description": "Sharp corner spline",
        "key_label":   "2",
        "qt_key":      Qt.Key.Key_2,
    },
    {
        "kind":        "tool",
        "label":       "B-Spline",
        "value":       "createBSpline",
        "angle":       77,
        "accent":      "#4FC3F7",
        "description": "Uniform spline",
        "key_label":   "3",
        "qt_key":      Qt.Key.Key_3,
    },
    {
        "kind":        "tool",
        "label":       "Open Spline",
        "value":       "createOpenSpline",
        "angle":       103,
        "accent":      "#81D4FA",
        "description": "Unclosed curve",
        "key_label":   "4",
        "qt_key":      Qt.Key.Key_4,
    },
    {
        "kind":        "tool",
        "label":       "Rectangle",
        "value":       "createRectangle",
        "angle":       129,
        "accent":      "#CE93D8",
        "description": "4-point quad spline",
        "key_label":   "5",
        "qt_key":      Qt.Key.Key_5,
    },
    {
        "kind":        "tool",
        "label":       "Ellipse",
        "value":       "createEllipse",
        "angle":       155,
        "accent":      "#A5D6A7",
        "description": "Circular/oval spline",
        "key_label":   "6",
        "qt_key":      Qt.Key.Key_6,
    },

    # ── LEFT SIDE: SELECTED SPLINE OPACITY OFF (angles 222° to 318°) ────────
    {
        "kind":        "opacity_off",
        "label":       "Off Prev (-1f)",
        "offset":      -1,
        "angle":       318,
        "accent":      "#FF7043",
        "description": "Key cur -> 0 @ -1f",
        "key_label":   "7",
        "qt_key":      Qt.Key.Key_7,
    },
    {
        "kind":        "opacity_off",
        "label":       "Off Next (+1f)",
        "offset":      1,
        "angle":       286,
        "accent":      "#FFA726",
        "description": "Key cur -> 0 @ +1f",
        "key_label":   "8",
        "qt_key":      Qt.Key.Key_8,
    },
    {
        "kind":        "opacity_off",
        "label":       "Off Prev (-5f)",
        "offset":      -5,
        "angle":       254,
        "accent":      "#EC407A",
        "description": "5f fade-in from -5f",
        "key_label":   "9",
        "qt_key":      Qt.Key.Key_9,
    },
    {
        "kind":        "opacity_off",
        "label":       "Off Next (+5f)",
        "offset":      5,
        "angle":       222,
        "accent":      "#AB47BC",
        "description": "5f fade-out to +5f",
        "key_label":   "0",
        "qt_key":      Qt.Key.Key_0,
    },
)

# 2. ROTOPAINT MENU: Right Side = Paint Tools | Left Side = Paint Sources
ROTOPAINT_ITEMS = (
    # ── RIGHT SIDE: TOOLS ───────────────────────────────────────────────────
    {
        "kind":        "tool",
        "label":       "Brush",
        "value":       "brush",
        "angle":       25,
        "accent":      "#4FC3F7",
        "description": "Paint stroke",
        "key_label":   "1",
        "qt_key":      Qt.Key.Key_1,
    },
    {
        "kind":        "tool",
        "label":       "Clone",
        "value":       "clone",
        "angle":       51,
        "accent":      "#E8A838",
        "description": "Offset clone brush",
        "key_label":   "2",
        "qt_key":      Qt.Key.Key_2,
    },
    {
        "kind":        "tool",
        "label":       "Reveal",
        "value":       "reveal",
        "angle":       77,
        "accent":      "#81C784",
        "description": "Reveal from source",
        "key_label":   "3",
        "qt_key":      Qt.Key.Key_3,
    },
    {
        "kind":        "tool",
        "label":       "Eraser",
        "value":       "eraser",
        "angle":       103,
        "accent":      "#E57373",
        "description": "Erase strokes",
        "key_label":   "4",
        "qt_key":      Qt.Key.Key_4,
    },
    {
        "kind":        "tool",
        "label":       "Blur",
        "value":       "blur",
        "angle":       129,
        "accent":      "#9575CD",
        "description": "Filter blur brush",
        "key_label":   "5",
        "qt_key":      Qt.Key.Key_5,
    },
    {
        "kind":        "tool",
        "label":       "Bezier",
        "value":       "createBezier",
        "angle":       155,
        "accent":      "#FFD54F",
        "description": "Bezier spline shape",
        "key_label":   "6",
        "qt_key":      Qt.Key.Key_6,
    },

    # ── LEFT SIDE: PAINT SOURCES ────────────────────────────────────────────
    {
        "kind":        "source",
        "label":       "Source: FG",
        "value":       "fg",
        "src_index":   0,
        "angle":       325,
        "accent":      "#26A69A",
        "description": "Foreground input",
        "key_label":   "7",
        "qt_key":      Qt.Key.Key_7,
    },
    {
        "kind":        "source",
        "label":       "Source: BG",
        "value":       "bg",
        "src_index":   1,
        "angle":       298,
        "accent":      "#26C6DA",
        "description": "Background default",
        "key_label":   "8",
        "qt_key":      Qt.Key.Key_8,
    },
    {
        "kind":        "source",
        "label":       "Source: BG 1",
        "value":       "bg1",
        "src_index":   2,
        "angle":       270,
        "accent":      "#42A5F5",
        "description": "bg1 input pipe",
        "key_label":   "9",
        "qt_key":      Qt.Key.Key_9,
    },
    {
        "kind":        "source",
        "label":       "Source: BG 2",
        "value":       "bg2",
        "src_index":   3,
        "angle":       242,
        "accent":      "#5C6BC0",
        "description": "bg2 input pipe",
        "key_label":   "0",
        "qt_key":      Qt.Key.Key_0,
    },
    {
        "kind":        "source",
        "label":       "Source: BG 3",
        "value":       "bg3",
        "src_index":   4,
        "angle":       215,
        "accent":      "#AB47BC",
        "description": "bg3 input pipe",
        "key_label":   "-",
        "qt_key":      Qt.Key.Key_Minus,
    },
)


# ─────────────────────────────────────────────────────────────────────────────
# Node Inspection, Selection Detection & Opacity Keyframing
# ─────────────────────────────────────────────────────────────────────────────

# Keep track of the Roto/RotoPaint the artist last worked on.
# Nuke's DAG node selection is NOT the same as the active Viewer editing tool.
_last_edit_roto_name = None
_context_timer = None
_context_callbacks_installed = False


def _node_identity(node):
    """Get a stable lookup key: Nuke can return different Python wrappers for a node."""
    try:
        return node.fullName()
    except (RuntimeError, AttributeError):
        try:
            return node.name()
        except (RuntimeError, AttributeError):
            return None


def _same_node(a, b):
    return a is not None and b is not None and _node_identity(a) == _node_identity(b)


def _remember_editing_node(node):
    global _last_edit_roto_name
    try:
        if node is not None and node.Class() in ACTIVE_NODE_CLASSES:
            _last_edit_roto_name = _node_identity(node)
    except (RuntimeError, AttributeError):
        pass


def _forget_editing_node():
    global _last_edit_roto_name
    _last_edit_roto_name = None


def _get_remembered_roto():
    """Forget stale node references when the user deletes or closes a Roto."""
    if not _last_edit_roto_name:
        return None
    try:
        node = nuke.toNode(_last_edit_roto_name)
        if node is not None and node.Class() in ACTIVE_NODE_CLASSES and node.shown():
            return node
    except (RuntimeError, AttributeError, ValueError):
        pass
    _forget_editing_node()
    return None


def _on_roto_knob_changed():
    """Track the actually edited node, even when its DAG selection disappears.

    Nuke's showPanel pseudo-knob fires when Properties are opened. Curves and
    toolbox updates often occur from the Viewer while painting/drawing.
    Ignore unrelated knob changes to avoid stealing the active editing target.
    """
    try:
        node = nuke.thisNode()
        knob = nuke.thisKnob()
        name = knob.name() if knob is not None else ''
        if not node.shown():
            return
        if name in (
            'showPanel', 'curves', 'toolbox', 'toolbar_paint_source',
            'paint_source', 'toolbar_roto', 'opacity',
        ):
            _remember_editing_node(node)
        elif name == 'selected' and bool(node['selected'].value()):
            _remember_editing_node(node)
    except (RuntimeError, AttributeError, KeyError):
        pass


def _poll_node_selection():
    """Catch the initial click on a Roto before focus moves into the Viewer.

    Qt timer runs only in Nuke's GUI thread and does not modify the script.
    Explicitly selecting a *different* node cancels the remembered Roto.
    Deselection by itself keeps the remembered Roto editing context intact.
    """
    try:
        selected = nuke.selectedNodes()
        if not selected:
            return
        if all(n.Class() in ACTIVE_NODE_CLASSES for n in selected):
            for node in selected:
                if node.shown():
                    _remember_editing_node(node)
                    return
            _remember_editing_node(selected[0])
        else:
            _forget_editing_node()
    except (RuntimeError, AttributeError):
        pass


def _get_viewer_input_node():
    """Viewer's input is supporting evidence, not the Roto editing target."""
    try:
        viewer = nuke.activeViewer()
        if viewer is None:
            return None
        index = viewer.activeInput()
        if index is None or index < 0:
            return None
        return viewer.node().input(index)
    except (RuntimeError, ValueError, AttributeError):
        return None


def _pointer_is_in_node_graph():
    """Only suppress the unselected-node hotbox when the *mouse* is over DAG.

    QApplication.focusWidget() was unreliable for this purpose: even while
    working in the Viewer, Nuke can retain keyboard focus on a DAG widget.
    """
    try:
        widget = QApplication.widgetAt(QCursor.pos())
        while widget is not None:
            signature = (
                str(widget.objectName()) + ' ' +
                str(widget.metaObject().className())
            ).lower()
            if ('nodegraph' in signature or 'node graph' in signature or
                    'dag' in signature):
                return True
            widget = widget.parentWidget()
    except (RuntimeError, AttributeError):
        pass
    return False


def _get_open_roto_nodes():
    """Find Roto/RotoPaint nodes with open Properties, including in groups."""
    try:
        # Root explicitly: the hotkey can run from the Viewer, outside DAG scope.
        nodes = nuke.allNodes(group=nuke.root(), recurseGroups=True)
    except (RuntimeError, TypeError, AttributeError):
        try:
            nodes = nuke.root().nodes()
        except (RuntimeError, AttributeError):
            return []

    result = []
    for node in nodes:
        try:
            if node.Class() in ACTIVE_NODE_CLASSES and node.shown():
                result.append(node)
        except RuntimeError:
            continue
    return result


def _get_active_preferred_node():
    """Resolve a currently edited Roto/paint WITHOUT needing DAG selection.

    1. An explicit DAG selection overrides remembered context.
    2. With no DAG selection, a keystroke over Node Graph runs W_Hotbox.
    3. A selected spline in one open Roto Properties panel is strong evidence.
    4. Otherwise use the recent Roto editing target, even if Viewing Read/plate.
    5. Prefer a Viewer-connected Roto with open Properties, or a unique open
       Roto/RotoPaint panel as a safe fallback.
    6. If nothing identifies the active editing node, use W_Hotbox.
    """
    try:
        selected = nuke.selectedNodes()
    except RuntimeError:
        selected = []

    if selected:
        if not all(n.Class() in ACTIVE_NODE_CLASSES for n in selected):
            _forget_editing_node()
            return None
        viewed = _get_viewer_input_node()
        for node in selected:
            if _same_node(node, viewed) and node.shown():
                _remember_editing_node(node)
                return node
        for node in selected:
            if node.shown():
                _remember_editing_node(node)
                return node
        _remember_editing_node(selected[0])
        return selected[0]

    # Mouse-position checks are more reliable than QApplication.focusWidget.
    # When a user presses backtick over the Viewer/Properties, stay in Roto mode.
    if _pointer_is_in_node_graph():
        return None

    open_roto = _get_open_roto_nodes()
    if not open_roto:
        _forget_editing_node()
        return None

    # A single actively selected spline is especially useful when selection is
    # only in the Viewer spline list, not in the DAG.
    spline_targets = []
    for node in open_roto:
        try:
            if _get_selected_splines(node):
                spline_targets.append(node)
        except (RuntimeError, AttributeError):
            pass
    if len(spline_targets) == 1:
        _remember_editing_node(spline_targets[0])
        return spline_targets[0]

    remembered = _get_remembered_roto()
    if remembered is not None:
        # Verify it is still among currently open panels.
        for node in open_roto:
            if _same_node(node, remembered):
                return node

    viewed = _get_viewer_input_node()
    for node in open_roto:
        if _same_node(node, viewed):
            _remember_editing_node(node)
            return node

    if len(open_roto) == 1:
        _remember_editing_node(open_roto[0])
        return open_roto[0]

    return None


def debug_hotbox_context():
    """Run in Nuke Script Editor if Roto isn't being detected, then copy output."""
    try:
        selected = [(n.name(), n.Class()) for n in nuke.selectedNodes()]
        open_panels = [(n.name(), n.Class()) for n in _get_open_roto_nodes()]
        viewed = _get_viewer_input_node()
        chosen = _get_active_preferred_node()
        print('[SplineHotbox] selected nodes:', selected)
        print('[SplineHotbox] open roto panels:', open_panels)
        print('[SplineHotbox] remembered editor:', _last_edit_roto_name)
        print('[SplineHotbox] Viewer input:', _node_identity(viewed))
        print('[SplineHotbox] pointer in Node Graph:', _pointer_is_in_node_graph())
        print('[SplineHotbox] chosen editor:', _node_identity(chosen))
    except Exception as exc:
        print('[SplineHotbox] diagnostic error:', exc)


def _get_selected_splines(node):
    """
    Return a list of currently selected Roto splines (rp.Shape instances)
    where the Viewer transform/translation box is active.
    """
    curve_knob = node.knob("curves")
    if curve_knob is None:
        return []
    try:
        selected = curve_knob.getSelected()
        return [
            item for item in selected
            if isinstance(item, rp.Shape) or hasattr(item, "getAttributes")
            and not isinstance(item, rp.Layer)
        ]
    except Exception:
        return []


def _get_current_tool_name(node):
    toolbox = node.knob("toolbox")
    if toolbox is None:
        return ""
    try:
        raw = toolbox.toScript().strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1].strip()
        if raw:
            return raw.split()[0].strip()
    except Exception:
        pass
    return ""


def _get_current_paint_source(node):
    knob = node.knob("toolbar_paint_source") or node.knob("paint_source")
    if knob is None:
        return ""
    try:
        return str(knob.value()).lower().replace(" ", "").strip()
    except Exception:
        return ""


def _set_toolbox_tool(node, tool_id):
    toolbox = node.knob("toolbox")
    if toolbox is None:
        return

    raw = toolbox.toScript().strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1].strip()

    brace_pos = raw.find("{")
    if brace_pos != -1:
        settings_block = raw[brace_pos:]
        new_script = f"{tool_id} {settings_block}"
    else:
        new_script = f"{tool_id} {{ {_DEFAULT_TOOLBOX_BODY} }}"

    toolbox.fromScript(new_script)


def _set_paint_source(node, source_token, src_index):
    for kname in ("toolbar_paint_source", "paint_source"):
        knob = node.knob(kname)
        if knob is None:
            continue
        try:
            values = list(knob.values())
            matched = False
            target_norm = source_token.lower().replace(" ", "")
            for idx, v in enumerate(values):
                v_norm = str(v).lower().replace(" ", "")
                if v_norm == target_norm or v_norm.endswith(target_norm):
                    knob.setValue(idx)
                    matched = True
                    break
            if not matched and 0 <= src_index < len(values):
                knob.setValue(src_index)
        except Exception:
            try:
                knob.setValue(src_index)
            except Exception:
                pass

    toolbox = node.knob("toolbox")
    if toolbox is not None:
        raw = toolbox.toScript().strip()
        if raw:
            active_tool = _get_current_tool_name(node) or "clone"
            pattern = rf"(\{{\s*{re.escape(active_tool)}\b[^}}]*?\bsrc\s+)\d+"
            updated, count = re.subn(pattern, rf"\g<1>{src_index}", raw)
            if count > 0:
                toolbox.fromScript(updated)


def _set_curve_key(opc_curve, attrs, frame, value):
    """Set or overwrite a keyframe on a Roto shape's 'opc' AnimCurve."""
    f_time = float(frame)
    f_val  = float(value)
    try:
        # Remove any existing key at this exact frame to prevent duplicates
        for idx in range(opc_curve.getNumberOfKeys() - 1, -1, -1):
            key_time = opc_curve.getKey(idx).time
            if abs(key_time - f_time) < 1e-4:
                opc_curve.removeKey(key_time)
    except Exception:
        pass

    try:
        opc_curve.addKey(f_time, f_val)
    except Exception:
        pass

    try:
        attrs.set(f_time, "opc", f_val)
    except Exception:
        pass


def _keyframe_selected_splines_opacity_off(node, frame_offset):
    """
    Keyframe all selected Roto splines:
      - Current frame (f)          -> current opacity value (or 1.0 if <= 0)
      - Target frame (f + offset)  -> 0.0
    Wrapped in nuke.Undo so Ctrl+Z undoes the operation in a single step.
    """
    shapes = _get_selected_splines(node)
    if not shapes:
        return

    cur_frame    = int(nuke.frame())
    target_frame = cur_frame + int(frame_offset)
    curve_knob   = node.knob("curves")
    op_knob      = node.knob("opacity")

    undo = nuke.Undo()
    undo.begin(f"Roto Spline Opacity Off ({frame_offset:+d}f)")
    try:
        for shape in shapes:
            attrs = shape.getAttributes()
            cur_val = float(attrs.getValue(float(cur_frame), "opc"))
            if cur_val <= 0.0:
                cur_val = 1.0

            opc_curve = attrs.getCurve("opc")
            if opc_curve is not None:
                _set_curve_key(opc_curve, attrs, cur_frame, cur_val)
                _set_curve_key(opc_curve, attrs, target_frame, 0.0)

        # Also sync the node's top-level opacity knob so the Properties bin UI updates immediately
        if op_knob is not None:
            try:
                cur_knob_val = float(op_knob.getValueAt(cur_frame))
                if cur_knob_val <= 0.0:
                    cur_knob_val = 1.0
                if not op_knob.isAnimated():
                    op_knob.setAnimated()
                op_knob.setValueAt(cur_knob_val, cur_frame)
                op_knob.setValueAt(0.0, target_frame)
            except Exception:
                pass

        if curve_knob is not None:
            curve_knob.changed()
    finally:
        undo.end()


def _is_opacity_zero_at_offset(shapes, frame_offset):
    """
    Return True if the selected spline(s) have an explicit keyframe of 0.0
    at (current_frame + frame_offset).
    """
    if not shapes:
        return False
    target_frame = float(int(nuke.frame()) + int(frame_offset))
    try:
        for shape in shapes:
            attrs = shape.getAttributes()
            opc_curve = attrs.getCurve("opc")
            if opc_curve is None or opc_curve.getNumberOfKeys() == 0:
                return False
            val = float(attrs.getValue(target_frame, "opc"))
            has_key = any(
                abs(opc_curve.getKey(i).time - target_frame) < 1e-4
                for i in range(opc_curve.getNumberOfKeys())
            )
            if not (has_key and abs(val) < 1e-4):
                return False
        return True
    except Exception:
        return False


def _apply_hotbox_item(node, item):
    try:
        if not node.shown():
            node.showControlPanel()

        kind = item["kind"]
        if kind == "tool":
            _set_toolbox_tool(node, item["value"])
        elif kind == "source":
            _set_paint_source(node, item["value"], item["src_index"])
        elif kind == "opacity_off":
            _keyframe_selected_splines_opacity_off(node, item["offset"])
    except Exception as exc:
        nuke.warning(f"[SplineHotbox] Error applying '{item['label']}': {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Hotbox UI Widget
# ─────────────────────────────────────────────────────────────────────────────

class SplineHotbox(QWidget):
    """Frameless radial hotbox for Roto (splines + selected spline opacity) & RotoPaint."""

    _FONT_HUB   = QFont("DejaVu Sans Mono", 7, QFont.Weight.Bold)
    _FONT_SIDE  = QFont("DejaVu Sans Mono", 7, QFont.Weight.Bold)
    _FONT_LABEL = QFont("DejaVu Sans Mono", 9, QFont.Weight.Bold)
    _FONT_SUB   = QFont("DejaVu Sans Mono", 6)
    _FONT_KEY   = QFont("DejaVu Sans Mono", 7, QFont.Weight.Bold)

    def __init__(self, roto_node):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._node             = roto_node
        self._is_rotopaint     = roto_node.Class() == "RotoPaint"
        self._selected_splines = [] if self._is_rotopaint else _get_selected_splines(roto_node)
        self._has_sel_spline   = len(self._selected_splines) > 0
        self._hovered          = -1
        self._closing          = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(CANVAS, CANVAS)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._cx = self._cy = CANVAS * 0.5
        self._center_pt = QPointF(self._cx, self._cy)
        self._hub_rect = QRectF(
            self._cx - HUB_RADIUS, self._cy - HUB_RADIUS,
            HUB_RADIUS * 2.0, HUB_RADIUS * 2.0,
        )

        self._scrim_grad = QRadialGradient(self._cx, self._cy, CANVAS * 0.5)
        self._scrim_grad.setColorAt(0.00, QColor(10, 10, 16, 225))
        self._scrim_grad.setColorAt(0.50, QColor(10, 10, 16, 165))
        self._scrim_grad.setColorAt(1.00, QColor(10, 10, 16, 0))

        self._hub_grad = QRadialGradient(self._cx, self._cy, HUB_RADIUS)
        self._hub_grad.setColorAt(0.0, QColor(62, 62, 82))
        self._hub_grad.setColorAt(1.0, QColor(20, 20, 30))

        if self._is_rotopaint:
            raw_defs = ROTOPAINT_ITEMS
        elif self._has_sel_spline:
            raw_defs = ROTO_WITH_SELECTED_SPLINE_ITEMS
        else:
            raw_defs = ROTO_SPLINE_ONLY_ITEMS

        self._items = self._build_cached_items(raw_defs)
        self._active_indices = self._detect_active_indices()

        self.setWindowOpacity(0.0)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(105)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _build_cached_items(self, raw_defs):
        items = []
        cur_frame = int(nuke.frame())

        for idx, base_meta in enumerate(raw_defs):
            meta = dict(base_meta)

            # Dynamically display exact frame numbers on opacity keyframe buttons
            if meta["kind"] == "opacity_off":
                target_f = cur_frame + int(meta["offset"])
                meta["description"] = f"f{cur_frame} -> f{target_f} = 0"

            rad = math.radians(meta["angle"])
            ic = QPointF(
                self._cx + RADIUS * math.sin(rad),
                self._cy - RADIUS * math.cos(rad),
            )
            rect = QRectF(
                ic.x() - ITEM_W * 0.5,
                ic.y() - ITEM_H * 0.5,
                ITEM_W,
                ITEM_H,
            )
            path = QPainterPath()
            path.addRoundedRect(rect, 10.0, 10.0)

            items.append({
                "meta":       meta,
                "index":      idx,
                "center":     ic,
                "rect":       rect,
                "path":       path,
                "accent":     QColor(meta["accent"]),
                "label_rect": QRectF(rect.x() + 14, rect.y() + 3, rect.width() - 20, rect.height() * 0.52),
                "sub_rect":   QRectF(rect.x() + 14, rect.y() + rect.height() * 0.52, rect.width() - 20, rect.height() * 0.44),
                "key_rect":   QRectF(rect.x() + 6, rect.y(), 16, rect.height()),
                "dot_center": QPointF(rect.right() - 9, rect.top() + 9),
            })
        return items

    def _detect_active_indices(self):
        active = set()
        cur_tool = _get_current_tool_name(self._node).lower()
        cur_src  = _get_current_paint_source(self._node)

        for item in self._items:
            meta = item["meta"]
            kind = meta["kind"]
            if kind == "tool" and cur_tool == meta["value"].lower():
                active.add(item["index"])
            elif kind == "source" and cur_src == meta["value"].lower():
                active.add(item["index"])
            elif kind == "opacity_off" and _is_opacity_zero_at_offset(self._selected_splines, meta["offset"]):
                active.add(item["index"])
        return active

    def _hit_index(self, pos):
        for item in self._items:
            if item["rect"].contains(pos):
                return item["index"]

        dx = pos.x() - self._cx
        dy = pos.y() - self._cy
        dist = math.hypot(dx, dy)
        if dist <= HUB_RADIUS or dist > (RADIUS + ITEM_W * 0.7):
            return -1

        compass_deg = (math.degrees(math.atan2(dx, -dy)) + 360.0) % 360.0
        best_idx = -1
        best_diff = 360.0
        for item in self._items:
            diff = abs((compass_deg - item["meta"]["angle"] + 180.0) % 360.0 - 180.0)
            if diff < best_diff:
                best_diff = diff
                best_idx = item["index"]
        return best_idx if best_diff <= 28.0 else -1

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setBrush(QBrush(self._scrim_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(0, 0, CANVAS, CANVAS))

        p.setPen(QPen(QColor(255, 255, 255, 20), 1.0, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(self._center_pt, float(RADIUS), float(RADIUS))

        # Draw split hemisphere headers when in RotoPaint OR when a Roto spline is selected
        if self._is_rotopaint or self._has_sel_spline:
            p.setPen(QPen(QColor(255, 255, 255, 28), 1.0, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(self._cx, 36), QPointF(self._cx, CANVAS - 36))

            p.setFont(self._FONT_SIDE)
            left_title  = "PAINT SOURCES" if self._is_rotopaint else "SPLINE OPACITY (0)"
            right_title = "PAINT TOOLS"   if self._is_rotopaint else "SPLINE TYPES"
            left_col    = QColor(130, 200, 220, 185) if self._is_rotopaint else QColor(255, 145, 115, 200)

            p.setPen(left_col)
            p.drawText(QRectF(self._cx - 185, 18, 165, 18), Qt.AlignmentFlag.AlignCenter, left_title)
            p.setPen(QColor(235, 190, 110, 185))
            p.drawText(QRectF(self._cx + 20, 18, 165, 18), Qt.AlignmentFlag.AlignCenter, right_title)

        for item in self._items:
            col = QColor(item["accent"])
            is_hov = item["index"] == self._hovered
            col.setAlpha(175 if is_hov else 50)
            p.setPen(QPen(col, 1.4 if is_hov else 1.0))
            p.drawLine(self._center_pt, item["center"])

        p.setBrush(QBrush(self._hub_grad))
        p.setPen(QPen(QColor(255, 255, 255, 45), 1.0))
        p.drawEllipse(self._center_pt, HUB_RADIUS, HUB_RADIUS)

        p.setFont(self._FONT_HUB)
        p.setPen(QColor(195, 195, 220, 225))
        if self._is_rotopaint:
            hub_title = "ROTO\nPAINT"
        elif self._has_sel_spline:
            count = len(self._selected_splines)
            name = getattr(self._selected_splines[0], "name", "SPLINE")
            hub_title = f"{name[:8]}\n({count} SEL)" if count > 1 else f"SPLINE\n{name[:8]}"
        else:
            hub_title = "ROTO\nSPLINE"
        p.drawText(self._hub_rect, Qt.AlignmentFlag.AlignCenter, hub_title)

        for item in self._items:
            self._draw_pill(p, item)

    def _draw_pill(self, p, item):
        idx     = item["index"]
        meta    = item["meta"]
        rect    = item["rect"]
        path    = item["path"]
        accent  = item["accent"]
        hovered = idx == self._hovered
        current = idx in self._active_indices

        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if hovered:
            bg.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 230))
            bg.setColorAt(1.0, QColor(accent.red() // 2, accent.green() // 2, accent.blue() // 2, 210))
        elif current:
            bg.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 85))
            bg.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 45))
        else:
            bg.setColorAt(0.0, QColor(34, 34, 48, 228))
            bg.setColorAt(1.0, QColor(20, 20, 30, 228))

        p.setBrush(QBrush(bg))
        if hovered:
            p.setPen(QPen(accent, 1.8))
        elif current:
            bc = QColor(accent)
            bc.setAlpha(165)
            p.setPen(QPen(bc, 1.2, Qt.PenStyle.DashLine))
        else:
            p.setPen(QPen(QColor(255, 255, 255, 32), 1.0))

        p.drawPath(path)

        if hovered:
            gc = QColor(accent)
            gc.setAlpha(42)
            p.setPen(QPen(gc, 7.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        p.setFont(self._FONT_LABEL)
        p.setPen(QColor(255, 255, 255, 255 if hovered else 215))
        p.drawText(item["label_rect"], Qt.AlignmentFlag.AlignCenter, meta["label"])

        p.setFont(self._FONT_SUB)
        p.setPen(QColor(215, 215, 235, 195 if hovered else 120))
        p.drawText(item["sub_rect"], Qt.AlignmentFlag.AlignCenter, meta["description"])

        if current:
            dc = QColor(accent)
            dc.setAlpha(240)
            p.setBrush(QBrush(dc))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(item["dot_center"], 3.8, 3.8)

        p.setFont(self._FONT_KEY)
        p.setPen(QColor(255, 255, 255, 155 if hovered else 70))
        p.drawText(item["key_rect"], Qt.AlignmentFlag.AlignVCenter, meta["key_label"])

    def mouseMoveEvent(self, event):
        hovered = self._hit_index(event.position())
        if hovered != self._hovered:
            self._hovered = hovered
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_index(event.position())
            if idx >= 0:
                keep_open = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                self._confirm(idx, keep_open=keep_open)
                return
        self._dismiss()

    def keyPressEvent(self, event):
        key = event.key()
        keep_open = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        for item in self._items:
            if key == item["meta"]["qt_key"]:
                self._confirm(item["index"], keep_open=keep_open)
                return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._hovered >= 0:
            self._confirm(self._hovered, keep_open=keep_open)
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_QuoteLeft):
            self._dismiss()

    def focusOutEvent(self, _event):
        self._dismiss()

    def _confirm(self, index, keep_open=False):
        if self._closing:
            return
        _apply_hotbox_item(self._node, self._items[index]["meta"])
        self._active_indices = self._detect_active_indices()
        self.update()

        if not keep_open:
            self._closing = True
            QTimer.singleShot(60, self.close)

    def _dismiss(self):
        if self._closing:
            return
        self._closing = True
        self._anim.stop()
        self._anim.setDuration(80)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.close)
        self._anim.start()


# ─────────────────────────────────────────────────────────────────────────────
# W_Hotbox Coexistence & Context Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_active_hotbox   = None
_orig_w_show     = None
_w_hotbox_hooked = False


def _is_w_hotbox_visible():
    w_mod = sys.modules.get("W_hotbox")
    if w_mod is not None:
        inst = getattr(w_mod, "hotboxInstance", None)
        if inst is not None:
            try:
                return bool(inst.isVisible())
            except RuntimeError:
                pass
    return False


def _invoke_w_hotbox(*args, **kwargs):
    global _orig_w_show

    if _orig_w_show is not None:
        _orig_w_show(*args, **kwargs)
        return

    w_mod = sys.modules.get("W_hotbox")
    if w_mod is None:
        try:
            import W_hotbox as w_mod
        except ImportError:
            w_mod = None

    if w_mod is not None and hasattr(w_mod, "showHotbox"):
        fn = getattr(w_mod, "showHotbox")
        if fn is not _trigger_hotbox:
            fn(*args, **kwargs)
            return

    for menu_path in (
        "Edit/W_hotbox/Open W_hotbox",
        "Edit/W_Hotbox/Open W_Hotbox",
    ):
        item = nuke.menu("Nuke").findItem(menu_path)
        if item is not None:
            item.invoke()
            return


def _open_spline_hotbox(node):
    global _active_hotbox

    cursor_pos = QCursor.pos()
    hotbox = SplineHotbox(node)
    hotbox.move(cursor_pos.x() - CANVAS // 2, cursor_pos.y() - CANVAS // 2)
    hotbox.show()
    hotbox.raise_()
    hotbox.activateWindow()
    hotbox.setFocus(Qt.FocusReason.PopupFocusReason)

    _active_hotbox = hotbox


def _trigger_hotbox(*args, **kwargs):
    global _active_hotbox

    if args or kwargs or _is_w_hotbox_visible():
        _invoke_w_hotbox(*args, **kwargs)
        return

    if _active_hotbox is not None:
        try:
            if _active_hotbox.isVisible():
                _active_hotbox._dismiss()
                return
        except RuntimeError:
            pass
        _active_hotbox = None

    node = _get_active_preferred_node()
    if node is not None:
        _open_spline_hotbox(node)
    else:
        _invoke_w_hotbox()


def _hook_w_hotbox_and_shortcut():
    global _orig_w_show, _w_hotbox_hooked

    w_mod = sys.modules.get("W_hotbox")
    if w_mod is None:
        try:
            import W_hotbox as w_mod
        except ImportError:
            w_mod = None

    if w_mod is not None and hasattr(w_mod, "showHotbox") and not _w_hotbox_hooked:
        orig = getattr(w_mod, "showHotbox")
        if orig is not _trigger_hotbox:
            _orig_w_show = orig
            setattr(w_mod, "showHotbox", _trigger_hotbox)
            _w_hotbox_hooked = True

    w_item = (
        nuke.menu("Nuke").findItem("Edit/W_hotbox/Open W_hotbox")
        or nuke.menu("Nuke").findItem("Edit/W_Hotbox/Open W_Hotbox")
    )
    if w_item is not None:
        nuke.menu("Nuke").addCommand(
            "Edit/W_hotbox/Open W_hotbox",
            _trigger_hotbox,
            NUKE_HOTKEY,
            shortcutContext=2,
        )
    else:
        nuke.menu("Nuke").addCommand(
            "Edit/Roto Spline Hotbox",
            _trigger_hotbox,
            NUKE_HOTKEY,
            shortcutContext=2,
        )


def register():
    global _context_timer, _context_callbacks_installed

    if not _context_callbacks_installed:
        for node_class in ACTIVE_NODE_CLASSES:
            nuke.addKnobChanged(_on_roto_knob_changed, nodeClass=node_class)
        _context_callbacks_installed = True

    if _context_timer is None:
        _context_timer = QTimer()
        _context_timer.setInterval(250)
        _context_timer.timeout.connect(_poll_node_selection)
        _context_timer.start()

    _poll_node_selection()
    _hook_w_hotbox_and_shortcut()
    QTimer.singleShot(0, _hook_w_hotbox_and_shortcut)


try:
    register()
except Exception:
    pass
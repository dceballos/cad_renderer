import math

from components.config import PANEL_DIRECTION_PARAM_NAME


def find_asin(value):
    """
    Compute arcsin if value is between -1 and 1, otherwise clamp it to -1 or 1.
    There are cases where the value us 1.0000000000002 and rounding might not work as intended always, so this
    function will handle it

    Args:
    value (float): The input value

    Returns:
    float: The arcsin of the input value if it's between -1 and 1, otherwise -1 or 1.
    """
    if value <= -1:
        return -math.pi / 2  # arcsin(-1) = -pi/2
    elif value >= 1:
        return math.pi / 2  # arcsin(1) = pi/2
    else:
        return math.asin(value)


def has_muntin_parts(raw_params):
    """
    Checks if the input params contains any muntin_parts within "frames" or "panels".

    Args:
        raw_params (dict): raw params.

    Returns:
        bool: True if muntin_parts are found within "frames" or "panels", False otherwise.
    """

    if 'frames' in raw_params:
        for frame in raw_params['frames']:
            if 'muntin_parts' in frame and frame['muntin_parts']:
                return True
    if 'panels' in raw_params:
        for panel in raw_params['panels']:
            if 'muntin_parts' in panel and panel['muntin_parts']:
                return True
    for key, value in raw_params.items():
        if isinstance(value, dict):
            if has_muntin_parts(value):
                return True
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if has_muntin_parts(item):
                        return True
    return False


def find_muntin_label_offset_multipliers(raw_params):
    """
    Adds muntin_label_offset_multiplier_x and muntin_label_offset_multiplier_y attributes to 'panels' with more
    than one muntin_part levels. to handle labels for muntins in multiple panels

    It also returns the max x and y offset to calculate extra padding needed for the canvas frame

    Args:
        raw_params (dict): JSON data.

    Returns:
        dict: JSON data with added attributes 'muntin_label_offset_multiplier_y' and 'muntin_label_offset_multiplier_x'.
        max_labels_x: count of labels on x axis
        max_labels_y = count of labels on y axis
    """
    max_labels_x = 1
    max_labels_y = 1

    def process_frame(frame):

        def calculate_rank_x(panel, prev_coord):
            nonlocal max_labels_x
            nonlocal rank_x

            if panel['coordinates']['x'] > prev_coord:
                rank_x += 1

                if rank_x > max_labels_x:
                    max_labels_x = rank_x

            return rank_x

        def calculate_rank_y(panel, prev_coord):
            nonlocal max_labels_y
            nonlocal rank_y
            if panel['coordinates']['y'] > prev_coord:
                rank_y += 1

                if rank_y > max_labels_y:
                    max_labels_y = rank_y
            return rank_y

        if 'panels' in frame:
            frame['panels'] = sorted(frame['panels'], key=lambda x: x['coordinates']['x'])
            prev_x = 0
            rank_x = 0
            for panel in frame['panels']:
                if 'muntin_parts' in panel and len(panel['muntin_parts']) > 1:
                    rank_x = calculate_rank_x(panel, prev_x)
                    panel['muntin_label_offset_multiplier_x'] = rank_x
                    prev_x = panel['coordinates']['x']

            frame['panels'] = sorted(frame['panels'], key=lambda x: x['coordinates']['y'])
            prev_y = 0
            rank_y = 0
            for panel in frame['panels']:
                if 'muntin_parts' in panel and len(panel['muntin_parts']) > 1:
                    rank_y = calculate_rank_y(panel, prev_y)
                    panel['muntin_label_offset_multiplier_y'] = rank_y
                    prev_y = panel['coordinates']['y']

        for inner_frame in frame.get('frames', []):
            process_frame(inner_frame)

        return frame

    for frame in raw_params.get('frames', []):
        process_frame(frame)

    process_frame(raw_params)

    return max_labels_x, max_labels_y


def _extract_panel_identity(panel):
    if isinstance(panel, str):
        return {"name": panel}

    if isinstance(panel, dict):
        payload = panel
    else:
        payload = getattr(panel, 'raw_params', {}) if hasattr(panel, 'raw_params') else {}

    return {
        "node_path": payload.get("node_path"),
        "node_uuid": payload.get("node_uuid") or payload.get("uuid"),
        "name": payload.get("name")
    }


def _node_matches_panel_identity(node, identity):
    if not isinstance(node, dict):
        return False

    node_path = node.get("node_path")
    node_uuid = node.get("node_uuid") or node.get("uuid")
    node_name = node.get("name")

    if identity.get("node_path") and node_path:
        return str(identity["node_path"]) == str(node_path)

    if identity.get("node_uuid") and node_uuid:
        return str(identity["node_uuid"]) == str(node_uuid)

    if identity.get("name"):
        return str(identity["name"]) == str(node_name)

    return False


def _find_panel_path(tree, panel):
    identity = _extract_panel_identity(panel)
    if not any(identity.values()):
        return None

    def _search(node, path):
        if isinstance(node, list):
            for item in node:
                result = _search(item, path)
                if result:
                    return result
            return None

        if not isinstance(node, dict):
            return None

        current_path = path + [node]
        if _node_matches_panel_identity(node, identity):
            return current_path

        for child in node.get('children', []):
            result = _search(child, current_path)
            if result:
                return result

        return None

    return _search(tree, [])


def _parameter_value(node, parameter_name):
    if not isinstance(node, dict):
        return None

    for parameter in node.get("parameters", []):
        if parameter.get("name") == parameter_name:
            return parameter.get("value_name")

    return None


def _find_node_by_name(tree, panel_name):
    if isinstance(tree, dict):
        if tree.get('name') == panel_name:
            return tree

        for child in tree.get('children', []):
            result = _find_node_by_name(child, panel_name)
            if result:
                return result
    elif isinstance(tree, list):
        for item in tree:
            result = _find_node_by_name(item, panel_name)
            if result:
                return result

    return None


def get_panel_direction_from_tree(tree, panel):
    panel_path = _find_panel_path(tree, panel)
    if panel_path:
        for node in reversed(panel_path):
            value = _parameter_value(node, PANEL_DIRECTION_PARAM_NAME)
            if value:
                return value
        return None

    panel_name = panel if isinstance(panel, str) else _extract_panel_identity(panel).get("name")
    if panel_name:
        node = _find_node_by_name(tree, panel_name)
        value = _parameter_value(node, PANEL_DIRECTION_PARAM_NAME) if node else None
        if value:
            return value

    return None


def get_panel_muntin_shape_from_tree(tree, panel):
    panel_path = _find_panel_path(tree, panel)
    if panel_path:
        for node in reversed(panel_path):
            if node.get('panel_type', '') == 'panel':
                return node.get('muntin_shape', {})
        return None

    panel_name = panel if isinstance(panel, str) else _extract_panel_identity(panel).get("name")
    if panel_name:
        node = _find_node_by_name(tree, panel_name)
        if node and node.get('panel_type', '') == 'panel':
            return node.get('muntin_shape', {})

    return None


def find_shape_max_min_differences(sides):
    max_x = float('-inf')
    max_y = float('-inf')
    min_x = float('inf')
    min_y = float('inf')

    for side in sides:
        points = [side['start_point'], side['end_point']]
        for x, y in points:
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y

    return max_x - min_x, max_y - min_y

def scale_point(point, scale_factor):
    """
    point: [x,y]
    scale_factor: int
    """
    return [coord * scale_factor for coord in point]

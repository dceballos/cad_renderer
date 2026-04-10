import itertools
import math
from copy import deepcopy
from functools import cached_property

import cairo

from components.config import SLIDING_DOOR_PRODUCT_CATEGORY_ID, PULL_TYPE_PARAM_NAME
from components.helpers.arrow import Arrow
from components.helpers.bezier import offset_bezier_curve
from components.helpers.direction_angle import DirectionAngle
from components.muntin import Muntin
from components.top_view.utils import get_pull_type, get_pull_handle_location, get_frame_parameter_value
from components.utils import get_panel_direction_from_tree, find_shape_max_min_differences, scale_point, get_panel_muntin_shape_from_tree
from enums.colors import Colors


class Panel:
    LABELS_PER_FRAME = 1
    LABELS_PER_PANEL = 2

    def __init__(self, x=0.0, y=0.0, parent_panel=None, raw_params=None, scale_factor=5):
        self._context = None

        self.x = x
        self.y = y
        self.parent_panel = parent_panel
        self.raw_params = raw_params

        self.panel_type = raw_params['panel_type']

        if raw_params.get('name'):
            self.name = raw_params['name']
        elif raw_params['panel_type'] == 'panel':
            self.name = 'panel'
        else:
            self.name = 'frame'

        self.move_direction = raw_params.get('move_direction')
        self.scale_factor = scale_factor

        self.child_panels = []
        self._size_labels = []

    @property
    def width(self):
        return self.raw_params['width']

    @property
    def height(self):
        return self.raw_params['height']

    @property
    def dlo_width(self):
        return self.raw_params['dlo_width']

    @property
    def dlo_height(self):
        return self.raw_params['dlo_height']

    @property
    def scaled_width(self):
        return self.width * self.scale_factor

    @property
    def scaled_height(self):
        return self.height * self.scale_factor

    @property
    def scaled_dlo_width(self):
        return self.dlo_width * self.scale_factor

    @property
    def scaled_dlo_height(self):
        return self.dlo_height * self.scale_factor

    @property
    def raw_child_panels(self):
        return self.raw_params.get('panels') or []

    @property
    def raw_child_frames(self):
        return self.raw_params.get('frames') or []

    @property
    def muntin_parameters(self):
        return self.raw_params.get('muntin_parameters') or {}

    @property
    def constructor_data(self):
        if self.parent_panel:
            return self.parent_panel.constructor_data

        return self.raw_params.get('constructor_data', {})

    @cached_property
    def _subunit_coordinates(self):
        """Walk up the rendering hierarchy to find this panel's subunit coordinates."""
        panel = self
        while panel:
            if panel.raw_params.get('name') == 'subunit':
                return panel.raw_params.get('coordinates', {})
            panel = panel.parent_panel
        return None

    def _subunit_has_param(self, param_name):
        """Check if this panel's subunit in constructor_data has the given parameter."""
        coords = self._subunit_coordinates
        if not coords:
            return True  # no subunit hierarchy, allow lookup

        tree = self.constructor_data
        for child in tree.get('children', []):
            pos = child.get('position', {})
            if pos.get('x') == coords.get('x') and child.get('panel_type') in ('subunit', 'unit'):
                return get_frame_parameter_value(child, param_name) is not None

        return False

    @cached_property
    def panel_direction(self):
        return get_panel_direction_from_tree(self.constructor_data, self)

    @cached_property
    def pull_handle_size(self):
        if not self._subunit_has_param(PULL_TYPE_PARAM_NAME):
            return ''
        pull_type = get_pull_type(self.constructor_data, self)
        if not pull_type:
            return ''
        elif pull_type.endswith('24"'):
            return 24
        elif pull_type.endswith('60"'):
            return 60
        elif pull_type.endswith('84"'):
            return 84
        else:
            return ''

    @cached_property
    def pull_handle_location(self):
        if not self._subunit_has_param(PULL_TYPE_PARAM_NAME):
            return None
        pull_handle_location = get_pull_handle_location(self.constructor_data, self)
        if pull_handle_location:
            return pull_handle_location.lower()
        else:
            return None

    @property
    def is_sliding_assembly(self):
        def find_product_category_id(node):
            av = node.get("assembly_version") or {}
            product_category_id = av.get("product_category_id")
            if product_category_id:
                return product_category_id
            for child in node.get("children", []):
                result = find_product_category_id(child)
                if result:
                    return result
            return None

        product_category_id = find_product_category_id(self.constructor_data)
        return product_category_id == SLIDING_DOOR_PRODUCT_CATEGORY_ID

    @property
    def muntin_parts(self):
        return self.raw_params.get('muntin_parts') or []

    @property
    def assembly_sides(self):
        try:
            if not isinstance(self.raw_params.get('panel_shape', {}), dict):
                return []
            return self.raw_params.get('panel_shape', {}).get('sides', [])
        except:
            # return empty list if there is any unexpected structure for shape
            return []

    @property
    def muntin_shape(self):
        try:
            return get_panel_muntin_shape_from_tree(self.constructor_data, self)
        except Exception:
            return None

    @property
    def draw_muntin_label(self):
        if self.parent_panel:
            return self.parent_panel.draw_muntin_label

        return self.raw_params.get('draw_muntin_label', False)

    def group_by_rows(self, raw_panels):
        sort_by = lambda _: f"{_['coordinates']['y']}_{_['coordinates']['x']}"
        group_by = lambda _: _['coordinates']['y']

        _sorted = sorted(raw_panels, key=sort_by)
        return {k: list(v) for k, v in itertools.groupby(_sorted, key=group_by)}

    def get_normalized_child_frame(self, raw_frame):
        from services.normalization_service import NormalizationService

        siblings = [_ for _ in self.raw_child_frames if raw_frame['coordinates']['y'] == _['coordinates']['y']]

        scaled_total_child_width = sum([_['width'] * self.scale_factor for _ in siblings])

        if self.scaled_width < scaled_total_child_width:
            factor = self.scaled_width / scaled_total_child_width
            service = NormalizationService(width_factor=factor, height_factor=1)

            return service.run(deepcopy(raw_frame))
        else:
            return raw_frame

    def get_normalized_child_panel(self, raw_panel):
        from services.normalization_service import NormalizationService

        are_coordinates_specified = any(_['coordinates'] for _ in self.raw_child_panels if 'coordinates' in _)

        if are_coordinates_specified:
            row_panels = [_ for _ in self.raw_child_panels if _['coordinates']['y'] == raw_panel['coordinates']['y']]
            scaled_total_child_width = sum([_['width'] * self.scale_factor for _ in row_panels])

            scaled_total_child_height = 0
            for row, row_panels in self.group_by_rows(self.raw_child_panels).items():
                scaled_total_child_height += max(_['height'] for _ in row_panels) * self.scale_factor

            invalid_condition_1 = self.scaled_dlo_width < scaled_total_child_width
            invalid_condition_2 = self.scaled_dlo_height < scaled_total_child_height

            width_factor = 1
            height_factor = 1

            if invalid_condition_1:
                width_factor = self.scaled_width / scaled_total_child_width

            if invalid_condition_2:
                height_factor = self.scaled_height / scaled_total_child_height

            service = NormalizationService(width_factor=width_factor, height_factor=height_factor)

            return service.run(deepcopy(raw_panel))
        else:
            scaled_total_child_width = sum([_['width'] * self.scale_factor for _ in self.raw_child_panels])
            scaled_total_child_height = sum([_['height'] * self.scale_factor for _ in self.raw_child_panels])

            invalid_condition_1 = self.child_panels_layout == 'horizontal' and self.scaled_width < scaled_total_child_width
            invalid_condition_2 = self.child_panels_layout == 'vertical' and self.scaled_height < scaled_total_child_height

            if invalid_condition_1 or invalid_condition_2:
                if self.child_panels_layout == 'horizontal':
                    factor = self.scaled_width / scaled_total_child_width
                    service = NormalizationService(width_factor=factor, height_factor=1)
                else:
                    factor = self.scaled_height / scaled_total_child_height
                    service = NormalizationService(width_factor=1, height_factor=factor)

                return service.run(deepcopy(raw_panel))
            else:
                return raw_panel

    @property
    def child_panels_layout(self):
        return self.guess_orientation(
            frame_width=self.width,
            frame_height=self.height,
            raw_child_panels=self.raw_child_panels
        )

    def _draw_panel_beziers(self, outer_points, inner_points):
        if self.parent_panel:
            x = self.parent_panel.x
            y = self.parent_panel.y
        else:
            return

        for segment in outer_points:
            if segment.get('offset_value', None):
                offset_points = offset_bezier_curve(segment, segment.get('offset_value', 0),
                                                    segment.get('sample_points', 1000))
                intersection_indices = segment['intersection_indices']
                intersection_points = segment['intersection_points']

                offset_points = offset_points[min(intersection_indices):max(intersection_indices) + 1]

                self.context.move_to(x + self.scale_factor * offset_points[0][0],
                                     y + self.scale_factor * offset_points[0][1])

                try:
                    first_intersection = intersection_points[intersection_indices.index(min(intersection_indices))]
                    last_intersection = intersection_points[intersection_indices.index(max(intersection_indices))]

                    self.context.line_to(x + self.scale_factor * first_intersection[0],
                                         y + self.scale_factor * first_intersection[1])
                except:
                    pass

                # Draw lines connecting the offset Bézier points
                for point in offset_points[1:]:
                    self.context.line_to(x + self.scale_factor * point[0], y + self.scale_factor * point[1])

                try:
                    self.context.line_to(x + self.scale_factor * last_intersection[0],
                                         y + self.scale_factor * last_intersection[1])
                except:
                    pass

                # Stroke the path (draw the lines)
                self.context.stroke()

            else:
                p1 = scale_point(segment['p1'], self.scale_factor)
                p2 = scale_point(segment['p2'], self.scale_factor)
                b1 = scale_point(segment['b1'], self.scale_factor)
                b2 = scale_point(segment['b2'], self.scale_factor)

                # Move to the start point
                self.context.move_to(x + p1[0], y + p1[1])

                # Draw the Bezier curve
                self.context.curve_to(x + b1[0], y + b1[1], x + b2[0], y + b2[1],
                                      x + p2[0], y + p2[1])
                self.context.stroke()

        # DRAW DLO
        self.context.set_dash([3, 3])
        self.context.set_line_width(1)

        if self.parent_panel:
            x = self.parent_panel.x
            y = self.parent_panel.y

        for segment in inner_points:

            if segment.get('offset_value', None):
                offset_points = offset_bezier_curve(segment, segment.get('offset_value', 0),
                                                    segment.get('sample_points', 1000))
                intersection_indices = segment['intersection_indices']

                offset_points = offset_points[min(intersection_indices):max(intersection_indices) + 1]

                self.context.move_to(x + self.scale_factor * offset_points[0][0],
                                     y + self.scale_factor * offset_points[0][1])

                # Draw lines connecting the offset Bézier points
                for point in offset_points[1:]:
                    self.context.line_to(x + self.scale_factor * point[0], y + self.scale_factor * point[1])

                # Stroke the path (draw the lines)
                self.context.stroke()
            p1 = scale_point(segment['p1'], self.scale_factor)
            p2 = scale_point(segment['p2'], self.scale_factor)
            b1 = scale_point(segment['b1'], self.scale_factor)
            b2 = scale_point(segment['b2'], self.scale_factor)

            # Move to the start point
            self.context.move_to(x + p1[0], y + p1[1])

            # Draw the Bezier curve
            self.context.curve_to(x + b1[0], y + b1[1], x + b2[0], y + b2[1],
                                  x + p2[0], y + p2[1])
            self.context.stroke()

        self.context.set_dash([])

    def _draw_frame(self):
        if self.name == 'unit':
            return

        self.context.save()
        self.context.set_source_rgba(*Colors.BLACK)

        if self.name == 'opening':
            self.context.set_dash([3, 3])
            self.context.set_line_width(1)
        else:
            self.context.set_line_width(2)

        if self.assembly_sides:
            # max_x, max_y = find_shape_max_min_differences(self.assembly_sides)

            # Iterate over the sides and draw each line
            for side in self.assembly_sides:

                outer_points = side.get('segments', {}).get('outer_points', [])

                if outer_points:
                    for segment in outer_points:
                        p1 = scale_point(segment['p1'], self.scale_factor)
                        p2 = scale_point(segment['p2'], self.scale_factor)
                        b1 = scale_point(segment['b1'], self.scale_factor)
                        b2 = scale_point(segment['b2'], self.scale_factor)

                        # Move to the start point
                        self.context.move_to(self.x + p1[0], self.y + p1[1])

                        # Draw the Bezier curve
                        self.context.curve_to(self.x + b1[0], self.y + b1[1], self.x + b2[0], self.y + b2[1],
                                              self.x + p2[0], self.y + p2[1])
                        self.context.stroke()


                else:

                    start_point = side['start_point']
                    end_point = side['end_point']

                    # Scale the points
                    scaled_start_point = [coord * self.scale_factor for coord in start_point]
                    scaled_end_point = [coord * self.scale_factor for coord in end_point]

                    # y_offset = (max_y * self.scale_factor - self.scaled_height) / 2
                    # x_offset = (max_x * self.scale_factor - self.scaled_width) / 2
                    #
                    # y_offset = 0 if y_offset < 0 else y_offset
                    # x_offset = 0 if x_offset < 0 else x_offset

                    x_offset = 0
                    y_offset = 0

                    # Move to the start point and draw a line to the end point
                    self.context.move_to(self.x - x_offset + scaled_start_point[0],
                                         self.y - y_offset + scaled_start_point[1])
                    self.context.line_to(self.x - x_offset + scaled_end_point[0],
                                         self.y - y_offset + scaled_end_point[1])

                    self.context.stroke()
        else:
            self.context.rectangle(self.x, self.y, self.scaled_width, self.scaled_height)
            self.context.stroke()

        if self.raw_params.get('has_louver'):
            self.context.set_line_width(5)
            self.context.set_source_rgba(0.5, 0.5, 0.5, 0.5)

            start_y = self.y
            while start_y < self.scaled_height:
                start_y += 10
                self.context.move_to(self.x, start_y)
                self.context.line_to(self.x + self.scaled_width, start_y)
                self.context.stroke()

        self.context.restore()

    def _draw_panel(self):
        self.context.save()

        self.context.set_source_rgba(*Colors.BLACK)
        self.context.set_line_width(1)

        if self.assembly_sides:

            # Iterate over the sides and draw each line
            for side in self.assembly_sides:

                outer_points = side.get('segments', {}).get('outer_points', [])

                if outer_points:
                    inner_points = side.get('segments', {}).get('inner_points', [])
                    try:
                        if outer_points:
                            self._draw_panel_beziers(outer_points, inner_points)
                    except Exception as e:
                        print('Encountered error while drawing bezier panel curves')
                        print(e)

                else:

                    if not side.get('start_point', None):
                        return

                    max_x, max_y = find_shape_max_min_differences(self.assembly_sides)

                    start_point = side['start_point']
                    end_point = side['end_point']

                    # Scale the points
                    scaled_start_point = [coord * self.scale_factor for coord in start_point]
                    scaled_end_point = [coord * self.scale_factor for coord in end_point]

                    if self.parent_panel:
                        x = self.parent_panel.x
                        y = self.parent_panel.y
                    else:
                        y_offset = (max_y * self.scale_factor - self.scaled_height) / 2
                        x_offset = (max_x * self.scale_factor - self.scaled_width) / 2

                        y_offset = 0 if y_offset < 0 else y_offset
                        x_offset = 0 if x_offset < 0 else x_offset

                        x = self.x - x_offset
                        y = self.y - y_offset

                    # Move to the start point and draw a line to the end point
                    self.context.move_to(x + scaled_start_point[0], y + scaled_start_point[1])
                    self.context.line_to(x + scaled_end_point[0], y + scaled_end_point[1])

                    self.context.stroke()
        else:
            self.context.rectangle(self.x, self.y, self.scaled_width, self.scaled_height)
            self.context.stroke()

            if self.pull_handle_size and self.pull_handle_location:
                self.context.set_line_width(3)
                self.context.set_source_rgb(0.3, 0.3, 0.3)

                # Calculate the vertical center of the panel
                panel_center_y = self.y + self.scaled_height / 2

                if self.pull_handle_location == 'left':
                    handle_x = self.x + 2 * self.scale_factor

                    # Calculate handle_y_start to center the handle vertically
                    handle_y_start = panel_center_y - (self.pull_handle_size / 2) * self.scale_factor
                    handle_y_end = panel_center_y + (self.pull_handle_size / 2) * self.scale_factor

                    self.context.move_to(handle_x, handle_y_start)
                    self.context.line_to(handle_x, handle_y_end)

                    self.context.rectangle(handle_x, handle_y_start + 3.75 * self.scale_factor, 1.6 * self.scale_factor,
                                           1.6 * self.scale_factor)

                    self.context.rectangle(handle_x, handle_y_end - 5.35 * self.scale_factor, 1.6 * self.scale_factor,
                                           1.6 * self.scale_factor)

                elif self.pull_handle_location == 'right':
                    handle_x = self.x + self.scaled_width - 2 * self.scale_factor

                    # Calculate handle_y_start to center the handle vertically
                    handle_y_start = panel_center_y - (self.pull_handle_size / 2) * self.scale_factor
                    handle_y_end = panel_center_y + (self.pull_handle_size / 2) * self.scale_factor

                    self.context.move_to(handle_x, handle_y_start)
                    self.context.line_to(handle_x, handle_y_end)

                    self.context.rectangle(handle_x - 1.6 * self.scale_factor,
                                           handle_y_start + 3.75 * self.scale_factor, 1.6 * self.scale_factor,
                                           1.6 * self.scale_factor)

                    self.context.rectangle(handle_x - 1.6 * self.scale_factor, handle_y_end - 5.35 * self.scale_factor,
                                           1.6 * self.scale_factor,
                                           1.6 * self.scale_factor)

                self.context.stroke()
                # reset thickness and color
                self.context.set_line_width(1)
                self.context.set_source_rgb(0, 0, 0)
            
        self.context.restore()

    def _draw_panel_dlo(self):
        self.context.save()

        dlo_x_offset = (self.scaled_width - self.scaled_dlo_width) / 2
        dlo_y_offset = (self.scaled_height - self.scaled_dlo_height) / 2

        self.context.set_source_rgba(*Colors.BLACK)
        self.context.set_line_width(0.5)
        self.context.rectangle(self.x + dlo_x_offset, self.y + dlo_y_offset, self.scaled_dlo_width,
                               self.scaled_dlo_height)

        self.context.stroke()

        # DRAW PANEL DIRECTION
        if self.is_sliding_assembly:
            # normal arrow code
            arrow_x = self.x + dlo_x_offset + self.scaled_dlo_width / 2
            arrow_y = self.y + dlo_y_offset + self.scaled_dlo_height / 2

            minimum_length = min(self.scaled_height, self.scaled_width)
            arrow = Arrow(minimum_length / 10, minimum_length / 13)

            if self.panel_direction == 'left-right':
                gap = max(8, minimum_length * 0.04)
                arrow.draw(self.context, arrow_x, arrow_y + gap, 'right')
                arrow.draw(self.context, arrow_x, arrow_y - gap, 'left')
            else:
                arrow.draw(self.context, arrow_x, arrow_y, self.panel_direction)
        else:
            # draw > direction on panel dlo for operable/hinges
            DirectionAngle.draw(self.context, self.x + dlo_x_offset, self.y + dlo_y_offset, self.scaled_dlo_width,
                                self.scaled_dlo_height, self.panel_direction)

        self.context.restore()

        # DRAW MUNTIN
        Muntin(panel_object=self).draw_muntin()

    def _draw_child_frames(self):
        sort_by = lambda _: f"{_['coordinates']['y']}_{_['coordinates']['x']}"
        group_by = lambda _: _['coordinates']['y']

        raw_frames = sorted(self.raw_child_frames, key=sort_by)
        row__w__frames = {k: list(v) for k, v in itertools.groupby(raw_frames, key=group_by)}

        initial_x_offset = (self.scaled_width - self.scaled_dlo_width) / 2
        initial_y_offset = (self.scaled_height - self.scaled_dlo_height) / 2

        y1 = self.y + initial_y_offset
        for row, _frames in row__w__frames.items():
            x1 = self.x + initial_x_offset

            normalized_raw_frames = [self.get_normalized_child_frame(raw_frame=_) for _ in _frames]

            for raw_frame in normalized_raw_frames:
                frame = Panel(
                    x=x1,
                    y=y1,
                    parent_panel=self,
                    raw_params=raw_frame
                ).set_context(self.context).draw()
                self.child_panels.append(frame)

                x1 += frame.scaled_width

            y1 += max([_['height'] * self.scale_factor for _ in _frames])

    def _draw_child_panels(self):
        are_coordinates_specified = any(_['coordinates'] for _ in self.raw_child_panels if 'coordinates' in _)
        if are_coordinates_specified:
            self._draw_child_panels__by_coordinates()
        else:
            self._draw_child_panels__by_names()

    def _draw_child_panels__by_coordinates(self):
        normalized_raw_child_panels = [self.get_normalized_child_panel(raw_panel=_) for _ in self.raw_child_panels]

        sort_by = lambda _: f"{_['coordinates']['y']}_{_['coordinates']['x']}"
        group_by = lambda _: _['coordinates']['y']

        sorted_normalized_raw_child_panels = sorted(normalized_raw_child_panels, key=sort_by)
        row__w__panels = {k: list(v) for k, v in itertools.groupby(sorted_normalized_raw_child_panels, key=group_by)}

        sum_of_max_heights = sum(max(_['height'] for _ in row_panels) for row_panels in row__w__panels.values())

        # scaled_total_normalized_child_width = max_sum_of_widths_per_row * self.scale_factor
        scaled_total_normalized_child_height = sum_of_max_heights * self.scale_factor

        # x_offset = (self.scaled_dlo_width - scaled_total_normalized_child_width) / 2
        y_offset = (self.scaled_dlo_height - scaled_total_normalized_child_height) / 2

        sum_of_max_heights = 0
        for row_number, row_panels in row__w__panels.items():
            widths_sum = sum(_['width'] for _ in row_panels) * self.scale_factor
            x_offset = (self.scaled_dlo_width - widths_sum) / 2

            new_child_panel_instances = []
            for panel in row_panels:
                panel = Panel(
                    x=self.x + x_offset + sum(_.scaled_width for _ in new_child_panel_instances),
                    y=self.y + y_offset + sum_of_max_heights,
                    parent_panel=self,
                    raw_params=panel
                ).set_context(self.context).draw()

                new_child_panel_instances.append(panel)

            self.child_panels += new_child_panel_instances

            sum_of_max_heights += max(_.scaled_height for _ in new_child_panel_instances)

    def _draw_child_panels__by_names(self):
        normalized_raw_child_panels = [self.get_normalized_child_panel(raw_panel=_) for _ in self.raw_child_panels]

        scaled_total_normalized_child_width = sum([_['width'] * self.scale_factor for _ in normalized_raw_child_panels])
        scaled_total_normalized_child_height = sum(
            [_['height'] * self.scale_factor for _ in normalized_raw_child_panels])

        x_offset, y_offset = 0, 0
        if self.child_panels_layout == 'horizontal':
            x_offset = (self.scaled_width - scaled_total_normalized_child_width) / 2
        elif self.child_panels_layout == 'vertical':
            y_offset = (self.scaled_height - scaled_total_normalized_child_height) / 2

        previous_panel = None
        for normalized_child_panel in sorted(normalized_raw_child_panels, key=lambda _: _['name'],
                                             reverse=self.child_panels_layout == 'vertical'):
            if self.child_panels_layout == 'horizontal':
                y_offset = (self.scaled_height - normalized_child_panel['height'] * self.scale_factor) / 2
            elif self.child_panels_layout == 'vertical':
                x_offset = (self.scaled_width - normalized_child_panel['width'] * self.scale_factor) / 2

            if previous_panel:
                if self.child_panels_layout == 'horizontal':
                    x_offset += previous_panel.scaled_width
                elif self.child_panels_layout == 'vertical':
                    y_offset += previous_panel.scaled_height
            elif not previous_panel:
                if self.child_panels_layout == 'horizontal' and self.scaled_width < scaled_total_normalized_child_width:
                    x_offset = 0
                elif self.child_panels_layout == 'vertical' and self.scaled_height < scaled_total_normalized_child_height:
                    y_offset = 0

            panel = Panel(
                x=self.x + x_offset,
                y=self.y + y_offset,
                parent_panel=self,
                raw_params=normalized_child_panel
            ).set_context(self.context).draw()

            self.child_panels.append(panel)

            previous_panel = panel

    def _draw_size_labels(self, _type='primary'):
        """
        :param _type: primary/dlo
        """
        from components.size_label import SizeLabel

        if _type == 'primary':
            width_label = SizeLabel(panel=self, label_type='width')
            height_label = SizeLabel(panel=self, label_type='height')
            width_label.draw()
            height_label.draw()
            self._size_labels.append(width_label)
            self._size_labels.append(height_label)
        elif _type == 'dlo' and self.panel_type == 'panel':
            dlo_width_label = SizeLabel(panel=self, label_type='dlo_width')
            dlo_height_label = SizeLabel(panel=self, label_type='dlo_height')
            dlo_width_label.draw()
            dlo_height_label.draw()
            self._size_labels.append(dlo_width_label)
            self._size_labels.append(dlo_height_label)

    def _draw_move_direction(self):
        self.context.save()

        arrow_angle = math.pi
        arrow_length = 0
        arrow_x, arrow_y = 0, 0

        dlo_x_offset = (self.scaled_width - self.scaled_dlo_width) / 2
        dlo_y_offset = (self.scaled_height - self.scaled_dlo_height) / 2

        if self.move_direction == 'left':
            arrow_angle = math.pi

            arrow_x = self.x + dlo_x_offset + self.scaled_dlo_width
            arrow_y = self.y + dlo_y_offset + self.scaled_height / 2

        elif self.move_direction == 'up':
            arrow_angle = math.pi / 2

            arrow_x = self.x + dlo_x_offset + self.scaled_dlo_width / 2
            arrow_y = self.y + dlo_y_offset

        elif self.move_direction == 'down':
            arrow_angle = - math.pi / 2

            arrow_x = self.x + dlo_x_offset + self.scaled_dlo_width / 2
            arrow_y = self.y + dlo_y_offset + self.scaled_dlo_height

        elif self.move_direction == 'right':
            arrow_angle = 0

            arrow_x = self.x + dlo_x_offset
            arrow_y = self.y + dlo_y_offset + self.scaled_height / 2

        if self.move_direction in ['left', 'right']:
            arrow_length = self.scaled_dlo_width * 0.1
        elif self.move_direction in ['up', 'down']:
            arrow_length = self.scaled_dlo_height * 0.1

        arrowhead_angle = math.pi / 6
        arrowhead_length = arrow_length / 2.25

        self.context.set_source_rgba(0, 0, 0, 1)

        self.context.move_to(arrow_x, arrow_y)  # move to center of canvas

        self.context.rel_line_to(arrow_length * math.cos(arrow_angle), arrow_length * math.sin(arrow_angle))
        self.context.rel_move_to(-arrowhead_length * math.cos(arrow_angle - arrowhead_angle),
                                 -arrowhead_length * math.sin(arrow_angle - arrowhead_angle))
        self.context.rel_line_to(arrowhead_length * math.cos(arrow_angle - arrowhead_angle),
                                 arrowhead_length * math.sin(arrow_angle - arrowhead_angle))
        self.context.rel_line_to(-arrowhead_length * math.cos(arrow_angle + arrowhead_angle),
                                 -arrowhead_length * math.sin(arrow_angle + arrowhead_angle))

        self.context.set_line_width(1)
        self.context.stroke()

        self.context.restore()

    # def _scale_child_panels(self):
    #     ###
    #     #
    #     ###
    #     total_children_width = sum([_['width'] for _ in self.raw_child_panels])
    #
    #     if self.width >= total_children_width:
    #         return None
    #
    #     ratio = self.width / total_children_width
    #
    #     for child_panel in self.raw_child_panels:
    #         child_panel['width'] = child_panel['width'] * ratio
    #         child_panel['height'] = child_panel['height'] * ratio
    #         child_panel['dlo_width'] = child_panel['dlo_width'] * ratio
    #         child_panel['dlo_height'] = child_panel['dlo_height'] * ratio
    #
    #     for child_frame in self.raw_child_frames:
    #         child_frame['width'] = child_frame['width'] * ratio
    #         child_frame['height'] = child_frame['height'] * ratio

    @classmethod
    def guess_orientation(cls, frame_width, frame_height, raw_child_panels):
        ###
        # Guesses if the panels layout is vertical or horizontal
        ###

        # this logic determines if the panel layout is vertical or horizontal
        total_child_width = sum([_['width'] for _ in raw_child_panels])
        total_child_height = sum([_['height'] for _ in raw_child_panels])

        delta__width_w_child_total = abs(frame_width - total_child_width)
        delta__height_w_child_total = abs(frame_height - total_child_height)
        delta__width_w_child_max = abs(frame_width - max([_['width'] for _ in raw_child_panels]))
        delta__height_w_child_max = abs(frame_height - max([_['height'] for _ in raw_child_panels]))

        meta_delta__width = abs(delta__width_w_child_total - delta__width_w_child_max)
        meta_delta__height = abs(delta__height_w_child_total - delta__height_w_child_max)

        if meta_delta__width > meta_delta__height:
            # width has a bigger sparse so this criteria suits better to guess the orientation
            orientation = 'horizontal' if delta__width_w_child_total < delta__width_w_child_max else 'vertical'
        else:
            # height has a bigger sparse so this criteria suits better to guess the orientation
            orientation = 'vertical' if delta__height_w_child_total < delta__height_w_child_max else 'horizontal'

        return orientation

    def draw(self):
        if self.raw_params.get('panels', []):
            self._draw_child_panels()
        elif self.raw_params.get('frames', []):
            self._draw_child_frames()

        if self.panel_type == 'frame':
            self._draw_frame()
        elif self.panel_type == 'panel':
            self._draw_panel()
            if not self.assembly_sides:
                self._draw_panel_dlo()

        if not self.parent_panel:
            for child_panel in self.child_panels:
                child_panel._draw_size_labels(_type='dlo')

            for child_panel in self.child_panels:
                child_panel._draw_size_labels(_type='primary')

            self._draw_size_labels(_type='primary')

        if self.move_direction:
            self._draw_move_direction()

        return self

    @property
    def context(self) -> cairo.Context:
        if not self._context:
            raise NotImplementedError

        return self._context

    def set_context(self, context):
        """
        Sets a context to draw a panel onto
        """
        self._context = context

        return self

    @property
    def size_labels(self):
        child_panels_labels = list(itertools.chain(*[_._size_labels for _ in self.child_panels]))

        return self._size_labels + child_panels_labels

import pygame
import math
#turn = t(angle)
#forward = (distance)
#arc = a(radius/angle)
move_coefficient = 1
arc_coefficient = 0.34
speed = 100
# how much you want wasd to move the robot (per wasd)
move_step = 5

# Robot dimensions in robot-local units. The board and drive code use mm, so
# these LEGO-style units are converted at 10 mm per unit for drawing.
ROBOT_LENGTH = 15
ROBOT_WIDTH = 21.5
ARM_WIDTH = 15
ARM_LENGTH_RETRACTED = 8
ARM_LENGTH_EXTENDED = 12
BOX_WIDTH = 23
BOX_LENGTH_RETRACTED = 1
BOX_LENGTH_EXTENDED = 13
ROBOT_UNIT_MM = 10

ARM_MAX_ANGLE = 150
BOX_MAX_ANGLE = 185

command_string = "f120, t90, f650, t90, f150, lu, ld, ae, ar"
command_string.strip()

command_split = command_string.split(',')
commands = []
for com in command_split:
    com = com.strip()
    if '/' in com:
        vals = com.split('/')
        if len(vals) == 2:
            commands.append(['arc', int(vals[0][1:]), int(vals[1])])
    elif len(com) > 1 and com[0] == 't':
        value = int(com[1:])
        commands.append(['turn', value])
    elif len(com) > 1 and com[0] == 'f':
        value = int(com[1:])
        commands.append(['forward', value])
    elif com == 'lu':
        commands.append(['lift_up', 0])
    elif com == 'ld':
        commands.append(['lift_down', 1])
    elif com == 'ar':
        commands.append(['arm_retract', 0])
    elif com == 'ae':
        commands.append(['arm_extend', 1])
    elif com == 'br':
        commands.append(['box_retract', 0])
    elif com == 'be':
        commands.append(['box_extend', 1])


pygame.init()
WIN_W, WIN_H = 800, 600
WIN = pygame.display.set_mode((WIN_W, WIN_H))
CLOCK = pygame.time.Clock()

# Board 
BOARD_W, BOARD_H = 2362, 1143  # mm
board = pygame.image.load("WRO-MAP.jpg")
aspect = BOARD_W / BOARD_H
if WIN_W / WIN_H > aspect:
    h = WIN_H
    w = int(h * aspect)
else:
    w = WIN_W
    h = int(w / aspect)
board = pygame.transform.smoothscale(board, (w, h))
bx, by = (WIN_W - w) // 2, (WIN_H - h) // 2
SCALE = min(w / BOARD_W, h / BOARD_H)

POINTS = [] # appends point when user presses p

def mm_to_px(x, y):
    return int(bx + x * SCALE), int(by + h - y * SCALE)

def px_to_mm(px, py):
    return (px - bx) / SCALE, (by + h - py) / SCALE

def units_to_mm(value):
    return value * ROBOT_UNIT_MM

def clamp(value, low, high):
    return max(low, min(high, value))

# Robot dimensions (mm)
BODY_W_MM = units_to_mm(ROBOT_WIDTH)
BODY_H_MM = units_to_mm(ROBOT_LENGTH)

R_MM = 50
R = int(R_MM * SCALE)
x, y = mm_to_px(250, 265)
angle = 90
progress, cmd_i = 0, 0

dragging = False
rotating = False
drag_offset = (0, 0)

# UI
FONT = pygame.font.SysFont(None, 20)

class Stop:
    HOLD = "hold"
    COAST = "coast"
    BRAKE = "brake"


class LinearMechanismMotor:
    def __init__(self, name, retracted_length, extended_length, max_angle):
        self.name = name
        self.retracted_length = retracted_length
        self.extended_length = extended_length
        self.max_angle = max_angle
        self.angle = 0

    @property
    def length(self):
        travel = self.extended_length - self.retracted_length
        return self.retracted_length + travel * (self.angle / self.max_angle)

    @property
    def extension(self):
        return self.length - self.retracted_length

    @property
    def deployed(self):
        return self.extension > 0.01

    def run_angle(self, speed, angle, then=Stop.HOLD, wait=True):
        self.angle = clamp(self.angle + angle, 0, self.max_angle)
        return self.angle

    def reset(self):
        self.angle = 0


arm = LinearMechanismMotor(
    "front arm",
    ARM_LENGTH_RETRACTED,
    ARM_LENGTH_EXTENDED,
    ARM_MAX_ANGLE,
)
box = LinearMechanismMotor(
    "box",
    BOX_LENGTH_RETRACTED,
    BOX_LENGTH_EXTENDED,
    BOX_MAX_ANGLE,
)
arm_extension = arm.extension
box_extension = box.extension


def update_mechanism_state():
    global arm_extension, box_extension
    arm_extension = arm.extension
    box_extension = box.extension


def local_to_screen(local_x, local_y):
    """Robot-local coordinates: +x is robot right, +y is robot front."""
    rad = math.radians(angle)
    right_x, right_y = math.sin(rad), math.cos(rad)
    front_x, front_y = math.cos(rad), -math.sin(rad)
    px = x + (right_x * local_x + front_x * local_y) * ROBOT_UNIT_MM * SCALE
    py = y + (right_y * local_x + front_y * local_y) * ROBOT_UNIT_MM * SCALE
    return px, py


def local_rect_points(x_min, x_max, y_min, y_max):
    return [
        local_to_screen(x_min, y_min),
        local_to_screen(x_max, y_min),
        local_to_screen(x_max, y_max),
        local_to_screen(x_min, y_max),
    ]


def polygon_bounds(points):
    min_x = min(px for px, py in points)
    max_x = max(px for px, py in points)
    min_y = min(py for px, py in points)
    max_y = max(py for px, py in points)
    return pygame.Rect(int(min_x), int(min_y), int(max_x - min_x) + 1, int(max_y - min_y) + 1)


def draw_local_rect(surface, x_min, x_max, y_min, y_max, fill, outline):
    points = local_rect_points(x_min, x_max, y_min, y_max)
    pygame.draw.polygon(surface, fill, points)
    pygame.draw.polygon(surface, outline, points, 2)
    return points


def draw_polygon_label(points, label, color):
    cx = sum(px for px, py in points) / len(points)
    cy = sum(py for px, py in points) / len(points)
    text = FONT.render(label, True, color)
    WIN.blit(text, text.get_rect(center=(cx, cy)))


def get_robot_collision_polygons():
    body = local_rect_points(
        -ROBOT_WIDTH / 2,
        ROBOT_WIDTH / 2,
        -ROBOT_LENGTH / 2,
        ROBOT_LENGTH / 2,
    )
    front_arm = local_rect_points(
        -ARM_WIDTH / 2,
        ARM_WIDTH / 2,
        ROBOT_LENGTH / 2,
        ROBOT_LENGTH / 2 + arm.length,
    )
    rear_box = local_rect_points(
        -BOX_WIDTH / 2,
        BOX_WIDTH / 2,
        -ROBOT_LENGTH / 2 - box.length,
        -ROBOT_LENGTH / 2,
    )
    return [body, front_arm, rear_box]


def draw_robot():
    update_mechanism_state()
    overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)

    polygons = []
    polygons.append(draw_local_rect(
        overlay,
        -ROBOT_WIDTH / 2,
        ROBOT_WIDTH / 2,
        -ROBOT_LENGTH / 2,
        ROBOT_LENGTH / 2,
        (0, 0, 255, 150),
        (0, 0, 120, 255),
    ))
    front_arm = draw_local_rect(
        overlay,
        -ARM_WIDTH / 2,
        ARM_WIDTH / 2,
        ROBOT_LENGTH / 2,
        ROBOT_LENGTH / 2 + arm.length,
        (0, 200, 0, 95),
        (0, 120, 0, 255),
    )
    polygons.append(front_arm)
    rear_box = draw_local_rect(
        overlay,
        -BOX_WIDTH / 2,
        BOX_WIDTH / 2,
        -ROBOT_LENGTH / 2 - box.length,
        -ROBOT_LENGTH / 2,
        (255, 170, 0, 60),
        (170, 95, 0, 255),
    )
    polygons.append(rear_box)

    front_start = local_to_screen(0, 0)
    front_end = local_to_screen(0, ROBOT_LENGTH / 2)
    pygame.draw.line(overlay, (255, 0, 0, 255), front_start, front_end, 3)
    WIN.blit(overlay, (0, 0))
    draw_polygon_label(front_arm, "front arm", (0, 100, 0))
    draw_polygon_label(rear_box, "box", (135, 75, 0))

    bounds = polygon_bounds(polygons[0])
    for poly in polygons[1:]:
        bounds = bounds.union(polygon_bounds(poly))
    return bounds


def display_measurement():
    if len(POINTS) != 2:
        return
    (x1, y1), (x2, y2) = POINTS
    mm1_x, mm1_y = px_to_mm(x1, y1)
    mm2_x, mm2_y = px_to_mm(x2, y2)
    distance = math.hypot(mm2_x - mm1_x, mm2_y - mm1_y)
    text = FONT.render(f"{distance:.1f} mm", True, (128, 0, 128))
    label_x = (x1 + x2 - text.get_width()) // 2
    label_y = (y1 + y2 - text.get_height()) // 2
    WIN.blit(text, (label_x, label_y))


def display_points():
    for point in POINTS:
        pygame.draw.circle(WIN, (80, 0, 100), point, 5)


def draw_debug_overlay():
    pose_x_mm, pose_y_mm = px_to_mm(x, y)
    lines = [
        f"pose: x={pose_x_mm:.0f} mm y={pose_y_mm:.0f} mm heading={angle:.1f}",
        f"arm length={arm.length:.1f} units extension={arm_extension:.1f}",
        f"box length={box.length:.1f} units extension={box_extension:.1f}",
    ]
    panel_w = 330
    panel_h = 18 * len(lines) + 8
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (255, 255, 255, 185), (0, 0, panel_w, panel_h))
    for i, line in enumerate(lines):
        txt = FONT.render(line, True, (0, 0, 0))
        panel.blit(txt, (6, 5 + i * 18))
    WIN.blit(panel, (10, WIN_H - panel_h - 10))


def reset_mechanisms():
    arm.reset()
    box.reset()
    update_mechanism_state()


def load_mechanism_test_routine():
    global commands, cmd_i, progress, waiting, started
    reset_mechanisms()
    commands = [
        ['arm_retract', 0],
        ['box_retract', 0],
        ['arm_extend', 1],
        ['arm_retract', 0],
        ['box_extend', 1],
        ['box_retract', 0],
    ]
    cmd_i, progress = 0, 0
    waiting = False
    started = True

def move(cmd, val, x, y, angle, prog):
    if cmd == 'forward':
        val = val[0]
        remaining = abs(val) - prog
        step = min(5, remaining)
        direction = 1 if val > 0 else -1
        x += math.cos(math.radians(angle)) * step * SCALE * move_coefficient * direction
        y -= math.sin(math.radians(angle)) * step * SCALE * move_coefficient * direction
        prog += step
    elif cmd == 'turn':
        val = val[0]
        step = min(2, abs(val - prog))
        angle += step if val < 0 else -step
        prog += step
    elif cmd == 'arc':
        radius, degrees = val 
        remaining = abs(degrees) - prog
        step_deg = min(2, remaining)
        clockwise = True if degrees > 0 else False
        direction = -1 if clockwise else 1

        # Move along the circular arc
        angle_rad = math.radians(angle)
        cx = x - radius * math.sin(angle_rad) * direction * arc_coefficient
        cy = y - radius * math.cos(angle_rad) * direction * arc_coefficient

        new_angle = angle + step_deg * direction
        new_angle_rad = math.radians(new_angle)

        x = cx + radius * math.sin(new_angle_rad) * direction * arc_coefficient
        y = cy + radius * math.cos(new_angle_rad) * direction * arc_coefficient

        # Keep movement angle for position
        angle = new_angle

        # Use separate variable for drawing rotation
        draw_angle = angle - 2 * step_deg * direction 
        prog += step_deg

    return x, y, angle, prog

run = True
waiting = False
started = False
while run:
    CLOCK.tick(speed)
    WIN.fill((200, 200, 200))
    WIN.blit(board, (bx, by))

    # Draw robot and get its rect for interaction when not started
    robot_rect = draw_robot()

    # Draw UI when not started (You can remove this once you are used to it)
    if not started:
        instr_lines = [
            "PREPARE ROBOT:",
            "Left-drag = move",
            "Right-drag = rotate",
            "Mouse wheel = rotate",
            "R = toggle front arm",
            "B = toggle rear box",
            "T = mechanism test routine",
            "SPACE = run next move"
        ]
        for i, line in enumerate(instr_lines):
            txt = FONT.render(line, True, (0, 0, 0))
            WIN.blit(txt, (10, 10 + i * 18))

        # Start btn
        start_rect = pygame.Rect(WIN_W - 110, 10, 100, 30)
        pygame.draw.rect(WIN, (100, 200, 100), start_rect)
        start_txt = FONT.render("START (S)", True, (0, 0, 0))
        WIN.blit(start_txt, (WIN_W - 90, 18))

    display_measurement()
    display_points()
    draw_debug_overlay()
    pygame.display.flip()

    if started:
        if cmd_i < len(commands) and not waiting:
            cmd, val = commands[cmd_i][0], commands[cmd_i][1:]
            if cmd == 'lift_up' or cmd == 'lift_down':
                if bool(val[0]):
                    arm.run_angle(300, ARM_MAX_ANGLE)
                else:
                    arm.run_angle(500, -ARM_MAX_ANGLE)
                update_mechanism_state()
                waiting = True
            elif cmd == 'arm_extend' or cmd == 'arm_retract':
                arm.run_angle(500, ARM_MAX_ANGLE if cmd == 'arm_extend' else -ARM_MAX_ANGLE)
                update_mechanism_state()
                waiting = True
            elif cmd == 'box_extend' or cmd == 'box_retract':
                box.run_angle(500, BOX_MAX_ANGLE if cmd == 'box_extend' else -BOX_MAX_ANGLE)
                update_mechanism_state()
                waiting = True
            else:
                x, y, angle, progress = move(cmd, val, x, y, angle, progress)
                if progress >= abs(val[1] if cmd == 'arc' else val[0]):
                    waiting = True

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            run = False
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            # Restart simulation
            x, y = mm_to_px(250, 265)
            angle = 90
            progress, cmd_i = 0, 0
            waiting = False
            started = False
            dragging = False
            rotating = False
            reset_mechanisms()
        elif e.type == pygame.KEYDOWN and not started:
            if e.key == pygame.K_SPACE:
                started = True
            if e.key == pygame.K_r:
                arm.run_angle(500, -ARM_MAX_ANGLE if arm.deployed else ARM_MAX_ANGLE)
                update_mechanism_state()
            if e.key == pygame.K_b:
                box.run_angle(500, -BOX_MAX_ANGLE if box.deployed else BOX_MAX_ANGLE)
                update_mechanism_state()
            if e.key == pygame.K_t:
                load_mechanism_test_routine()
            if e.key == pygame.K_w:
                y -= move_step
            elif e.key == pygame.K_s:
                y += move_step
            elif e.key == pygame.K_a:
                x -= move_step
            elif e.key == pygame.K_d:
                x += move_step
            elif e.key == pygame.K_LEFT:
                angle = (angle + 45) % 360
            elif e.key == pygame.K_RIGHT:
                angle = (angle - 45) % 360
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE and waiting:
            cmd_i, progress = cmd_i + 1, 0
            waiting = False

        if e.type == pygame.MOUSEBUTTONDOWN:
            mx, my = e.pos
            if not started and e.button == 1 and robot_rect.collidepoint((mx, my)):
                dragging = True
                drag_offset = (x - mx, y - my)
            elif not started and (e.button == 3 or e.button == 2) and robot_rect.collidepoint((mx, my)):
                rotating = True
            elif not started and e.button == 1 and 'start_rect' in locals() and start_rect.collidepoint((mx, my)):
                started = True
        elif e.type == pygame.MOUSEBUTTONUP:
            if e.button == 1:
                dragging = False
            if e.button == 3 or e.button == 2:
                rotating = False
        elif e.type == pygame.MOUSEMOTION:
            mx, my = e.pos
            if not started and dragging:
                x = mx + drag_offset[0]
                y = my + drag_offset[1]
            elif not started and rotating:
                dx = mx - x
                dy = my - y
                angle = math.degrees(math.atan2(-dy, dx))
        elif not started and e.type == pygame.MOUSEWHEEL:
            angle -= e.y * 5

        elif e.type == pygame.KEYDOWN and e.key == pygame.K_p:
            # see how many points are already in p
            mouse_pos = pygame.mouse.get_pos()
            if len(POINTS) == 0:
                POINTS.append(mouse_pos)
            elif len(POINTS) == 1:
                POINTS.append(mouse_pos)
            elif len(POINTS) == 2:
                POINTS.pop(0)
                POINTS.append(mouse_pos)
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_PERIOD:
            POINTS.clear()

        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                arm.run_angle(500, -ARM_MAX_ANGLE if arm.deployed else ARM_MAX_ANGLE)
                update_mechanism_state()
            if e.key == pygame.K_b:
                box.run_angle(500, -BOX_MAX_ANGLE if box.deployed else BOX_MAX_ANGLE)
                update_mechanism_state()

    if not started:
        continue


pygame.quit()

print("\n===== COPY BELOW TO YOUR SCRIPT =====\n")
for com in commands:
    if com[0] == 'forward':
        print(f'await db.straight({com[1]})')
    elif com[0] == 'turn':
        print(f'await db.turn({com[1]})')
    elif com[0] == 'arc':
        print(f'await db.arc({com[1]}, {com[2]})')
    elif com[0] == 'lift_up':
        print(f'await arm.run_angle(500,-500)')
    elif com[0] == 'lift_down':
        print(f'await arm.run_angle(300,500)')
    elif com[0] == 'arm_retract':
        print(f'await arm.run_angle(500,{ARM_MAX_ANGLE})')
    elif com[0] == 'arm_extend':
        print(f'await arm.run_angle(500,-{ARM_MAX_ANGLE})')
    elif com[0] == 'box_retract':
        print(f'await box.run_angle(500,{BOX_MAX_ANGLE})')
    elif com[0] == 'box_extend':
        print(f'await box.run_angle(500,-{BOX_MAX_ANGLE})')
print("\n===== END COPY BLOCK =====\n")

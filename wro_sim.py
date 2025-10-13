import pygame
import math
#turn = t(angle)
#forward = (distance)
#arc = a(radius/angle)
move_coefficient = 1
arc_coefficient = 0.34
speed = 100
# how much you want wasd to move the robot
move_step = 5

command_string = "a500/90, f200, t90"
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


pygame.init()
WIN_W, WIN_H = 800, 600
WIN = pygame.display.set_mode((WIN_W, WIN_H))
CLOCK = pygame.time.Clock()

# --- Board ---
BOARD_W, BOARD_H = 2362, 1143  # mm
board = pygame.image.load("board.jpg")
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

def mm_to_px(x, y):
    return int(bx + x * SCALE), int(by + h - y * SCALE)

# --- Robot ---
R_MM = 50
R = int(R_MM * SCALE)
x, y = mm_to_px(250, 265)
angle = 90
progress, cmd_i = 0, 0

# Pre-start interaction state
dragging = False
rotating = False
drag_offset = (0, 0)

# UI
FONT = pygame.font.SysFont(None, 20)

def draw_robot():
    rect_w = R * 3.5
    rect_h = R * 4
    
    # Create rectangle surface with red line included
    surface = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
    
    # Draw body (semi-transparent blue)
    pygame.draw.rect(surface, (0, 0, 255, 120), (0, 0, rect_w, rect_h))
    
    # Draw red line from center toward front
    center_x, center_y = rect_w // 2, rect_h // 2
    ex = center_x + rect_w / 2
    ey = center_y  # pointing "up"
    pygame.draw.line(surface, (255, 0, 0), (center_x, center_y), (ex, ey), 3)
    
    # Rotate rectangle + line to the RIGHT instead of left
    rotated = pygame.transform.rotozoom(surface, angle, 1)  # <-- flip sign here
    rot_rect = rotated.get_rect(center=(int(x), int(y)))
    WIN.blit(rotated, rot_rect.topleft)
    return rot_rect


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
        radius, degrees = val  # val = [radius, degrees]
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
        draw_angle = angle - 2 * step_deg * direction  # rotates opposite
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
            "Click STAART or any key to begin"
        ]
        for i, line in enumerate(instr_lines):
            txt = FONT.render(line, True, (0, 0, 0))
            WIN.blit(txt, (10, 10 + i * 18))

        # Start button
        start_rect = pygame.Rect(WIN_W - 110, 10, 100, 30)
        pygame.draw.rect(WIN, (100, 200, 100), start_rect)
        start_txt = FONT.render("START (S)", True, (0, 0, 0))
        WIN.blit(start_txt, (WIN_W - 90, 18))

    pygame.display.flip()

    if started:
        if cmd_i < len(commands) and not waiting:
            cmd, val = commands[cmd_i][0], commands[cmd_i][1:]
            x, y, angle, progress = move(cmd, val, x, y, angle, progress)
            if progress >= abs(val[1] if cmd == 'arc' else val[0]):
                waiting = True  # enter wait mode

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
        elif e.type == pygame.KEYDOWN and not started:
            # Allow keyboard start (Space or S)
            if e.key == pygame.K_SPACE:
                started = True
            if e.key == pygame.K_w:
                y -= move_step
            elif e.key == pygame.K_s:
                y += move_step
            elif e.key == pygame.K_a:
                x -= move_step
            elif e.key == pygame.K_d:
                x += move_step
            # Left/right arrow for 45-degree rotation
            elif e.key == pygame.K_LEFT:
                angle = (angle + 45) % 360
            elif e.key == pygame.K_RIGHT:
                angle = (angle - 45) % 360
        elif e.type == pygame.KEYDOWN and waiting:
            cmd_i, progress = cmd_i + 1, 0
            waiting = False

        # pre start moving and turning
        if not started:
            if e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = e.pos
                # reft click: start dragging if on robot
                if e.button == 1 and robot_rect.collidepoint((mx, my)):
                    dragging = True
                    drag_offset = (x - mx, y - my)
                # right click: start rotating if on robot
                elif (e.button == 3 or e.button == 2) and robot_rect.collidepoint((mx, my)):
                    rotating = True
                # rlick start button
                elif e.button == 1 and 'start_rect' in locals() and start_rect.collidepoint((mx, my)):
                    started = True
            elif e.type == pygame.MOUSEBUTTONUP:
                if e.button == 1:
                    dragging = False
                if e.button == 3 or e.button == 2:
                    rotating = False
            elif e.type == pygame.MOUSEMOTION:
                mx, my = e.pos
                if dragging:
                    x = mx + drag_offset[0]
                    y = my + drag_offset[1]
                elif rotating:
                    # angle = degrees(atan2(-(mousey - y), (mousex - x)))
                    dx = mx - x
                    dy = my - y
                    angle = math.degrees(math.atan2(-dy, dx))
            elif e.type == pygame.MOUSEWHEEL:
                # scroll up/down to rotate
                angle -= e.y * 5

    if not started:
        continue


pygame.quit()

# Print commands after simulation ends
print("\n===== COPY BELOW TO YOUR SCRIPT =====\n")
for com in commands:
    if (com[0] == 'forward'):
        print(f'await db.straight({com[1]})')
    elif (com[0] == 'turn'):
        print(f'await db.turn({com[1]})')
    elif (com[0] == 'arc'):
        print(f'await db.arc({com[1]}, {com[2]})')
print("\n===== END COPY BLOCK =====\n")

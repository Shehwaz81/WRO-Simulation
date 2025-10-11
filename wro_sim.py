import pygame
import math
#turn = t(angle)
#forward = (distance)
#arc = a(radius/angle)
move_coefficient = 1
arc_coefficient = 0.33
speed = 100

command_string = "f550,t90,f100"
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
x, y = mm_to_px(250, 250)
angle = 90
progress, cmd_i = 0, 0

def draw_robot():
    rect_w = R * 3.5
    rect_h = R * 4
    
    # Create rectangle surface with red line included
    surface = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
    
    # Draw body
    pygame.draw.rect(surface, (0, 0, 255), (0, 0, rect_w, rect_h))
    
    # Draw red line from center toward front
    center_x, center_y = rect_w // 2, rect_h // 2
    ex = center_x + rect_w / 2
    ey = center_y  # pointing "up"
    pygame.draw.line(surface, (255, 0, 0), (center_x, center_y), (ex, ey), 3)
    
    # Rotate rectangle + line to the RIGHT instead of left
    rotated = pygame.transform.rotozoom(surface, angle, 1)  # <-- flip sign here
    rot_rect = rotated.get_rect(center=(int(x), int(y)))
    WIN.blit(rotated, rot_rect.topleft)




coefficient = 0.70
arc_coefficient = 0.33

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

# --- Loop ---
# --- Loop ---
run = True
waiting = False # flag to wait after each command
while run:
    CLOCK.tick(speed)
    WIN.fill((200,200,200))
    WIN.blit(board, (bx, by))
    
    if cmd_i < len(commands) and not waiting:
        cmd, val = commands[cmd_i][0], commands[cmd_i][1:]
        x, y, angle, progress = move(cmd, val, x, y, angle, progress)
        if progress >= abs(val[1] if cmd == 'arc' else val[0]):
            waiting = True  # enter wait mode

    draw_robot()
    pygame.display.flip()
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            run = False
        elif e.type == pygame.KEYDOWN and waiting:
            # Press any key to continue to next command
            cmd_i, progress = cmd_i+1, 0
            waiting = False

pygame.quit()

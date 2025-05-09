import pygame, sys, time, random, math

# ----- Initialization -----
pygame.init()
WIDTH, HEIGHT = 800, 600
FPS = 60
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("🥒 Pickle Clicker")
clock = pygame.time.Clock()

# ----- Colors & Fonts -----
WHITE     = (255,255,255)
BTN_BG    = (100,200,100)
BTN_HOV   = (120,220,120)
FONT      = pygame.font.SysFont("Arial", 20)
BIG_FONT  = pygame.font.SysFont("Arial", 32)

# ----- Game State -----
pickle_count           = 0.0
base_pickles_per_click = 1
click_lvl              = 0
CLICK_BASE_COST        = 50
CLICK_GROWTH           = 1.15

# Buff state
click_multiplier = 1.0
pps_multiplier   = 1.0
buff_end_time    = 0.0

# Generators
generators = [
    {"name":"Jar",     "base":100,    "growth":1.15, "pps":1,     "count":0, "cost":100.0},
    {"name":"Farm",    "base":1_000,  "growth":1.17, "pps":10,    "count":0, "cost":1_000.0},
    {"name":"Factory", "base":10_000, "growth":1.20, "pps":100,   "count":0, "cost":10_000.0},
    {"name":"Plant",   "base":100_000,"growth":1.22, "pps":1_000, "count":0, "cost":100_000.0},
]

game_won        = False
spawn_accum     = 0.0
falling_pickles = []
falling_golds   = []
FALL_RATE_FACTOR = 0.2  # fewer background pickles

# Next golden spawn time
time_now = time.time()
next_golden_time = time_now + random.uniform(45, 90)

# ----- Helper Functions -----
def click_cost():
    return CLICK_BASE_COST * (CLICK_GROWTH ** click_lvl)

def total_pps():
    return sum(g["pps"] * g["count"] for g in generators)

WHITE = (255,255,255)
GOLD  = (255,215,0)

def render_gradient_text(surf, text, font, pos, t, speed=0.5):
    """
    Draws `text` at `pos` on `surf`, with a scrolling white→gold gradient.
    - t: time in seconds (e.g. pygame.time.get_ticks()/1000)
    - speed: how fast the gradient scrolls (cycles per second)
    """
    x, y = pos
    # Precompute widths
    widths = [font.size(c)[0] for c in text]
    total = sum(widths)
    cum = 0
    for i, c in enumerate(text):
        w = widths[i]
        # relative position [0..1)
        rel = (cum/total + (t*speed) % 1) % 1
        # lerp white→gold
        color = (
            int(WHITE[0] + (GOLD[0]-WHITE[0]) * rel),
            int(WHITE[1] + (GOLD[1]-WHITE[1]) * rel),
            int(WHITE[2] + (GOLD[2]-WHITE[2]) * rel),
        )
        ch = font.render(c, True, color)
        surf.blit(ch, (x + cum, y))
        cum += w

# ----- Falling Sprites -----
try:
    base_fall_img = pygame.image.load("pickle.png").convert_alpha()
except:
    base_fall_img = pygame.Surface((40,40), pygame.SRCALPHA)
    pygame.draw.circle(base_fall_img, (100,200,100), (20,20), 20)
fall_img = pygame.transform.smoothscale(base_fall_img, (40,40))

try:
    base_gold_img = pygame.image.load("golden_pickle.png").convert_alpha()
except:
    base_gold_img = pygame.Surface((40,40), pygame.SRCALPHA)
    pygame.draw.circle(base_gold_img, (255,215,0), (20,20), 20)
gold_img = pygame.transform.smoothscale(base_gold_img, (40,40))

class FallingPickle:
    def __init__(self):
        self.x = random.uniform(0, WIDTH)
        self.y = -20
        self.speed = random.uniform(100, 200)
        self.angle = random.uniform(0, 360)
        self.ang_vel = random.uniform(-90, 90)
    def update(self, dt):
        self.y += self.speed * dt
        self.angle = (self.angle + self.ang_vel * dt) % 360
    def draw(self, surf):
        img = pygame.transform.rotate(fall_img, self.angle)
        rect = img.get_rect(center=(self.x, self.y))
        surf.blit(img, rect)

class FallingGold:
    def __init__(self):
        self.x = random.uniform(0, WIDTH)
        self.y = -20
        self.speed = random.uniform(50, 100)
        self.angle = 0
        self.ang_vel = random.uniform(-180, 180)
        self.rect = pygame.Rect(0,0,40,40)
    def update(self, dt):
        self.y += self.speed * dt
        self.angle = (self.angle + self.ang_vel * dt) % 360
    def draw(self, surf):
        img = pygame.transform.rotate(gold_img, self.angle)
        rect = img.get_rect(center=(self.x, self.y))
        self.rect = rect
        surf.blit(img, rect)

# ----- UI Classes -----
class Button:
    def __init__(self, text, pos, size, callback):
        self.text, self.callback = text, callback
        self.base_col, self.hover_col = BTN_BG, BTN_HOV
        self.rect = pygame.Rect(pos, size)
        self.hovered = False
        self.anim = 0.0
    def handle_event(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button==1 and self.hovered:
            self.callback()
    def update(self, dt):
        target = 1.0 if self.hovered else 0.0
        self.anim += (target - self.anim)*dt*10
    def draw(self, surf):
        scale = 1 + 0.05 * self.anim
        w,h = self.rect.size
        sw,sh = int(w*scale), int(h*scale)
        x = self.rect.centerx - sw//2
        y = self.rect.centery - sh//2
        col = tuple(int(self.base_col[i] + (self.hover_col[i]-self.base_col[i])*self.anim) for i in range(3))
        r = pygame.Rect(x,y,sw,sh)
        pygame.draw.rect(surf, col, r, border_radius=8)
        for idx,line in enumerate(self.text.split("\n")):
            txt_surf = FONT.render(line, True, WHITE)
            ly = r.y + 10 + idx*(FONT.get_height()+2)
            surf.blit(txt_surf, (r.x + (r.width-txt_surf.get_width())//2, ly))

class Shop:
    def __init__(self):
        self.open = False
        self.x = WIDTH
        self.w = 300
        self.build()
    def build(self):
        self.buttons = []
        def buy_click():
            global pickle_count, click_lvl, base_pickles_per_click
            cost = click_cost()
            if pickle_count >= cost:
                pickle_count -= cost
                click_lvl += 1
                base_pickles_per_click += 1
                self.build()
        txt = f"Click +1\nCost: {int(click_cost()):,}"
        self.buttons.append(Button(txt, (self.x+50, 100), (200, 60), buy_click))
        for i, g in enumerate(generators):
            def mkbuy(i=i):
                global pickle_count
                gen = generators[i]
                if pickle_count >= gen["cost"]:
                    pickle_count -= gen["cost"]
                    gen["count"] += 1
                    gen["cost"] = gen["base"]*(gen["growth"]**gen["count"])
                    self.build()
            txt = (f"{g['name']} x{g['count']} +{g['pps']} PPS\n"
                   f"Cost: {int(g['cost']):,}")
            y = 180 + i*80
            self.buttons.append(Button(txt, (self.x+50, y), (200, 60), mkbuy))
    def toggle(self):
        self.open = not self.open
        self.build()
    def handle_event(self, e):
        if self.open:
            for b in self.buttons:
                b.handle_event(e)
    def update(self, dt):
        target = WIDTH - self.w if self.open else WIDTH
        self.x += (target - self.x)*dt*8
        for b in self.buttons:
            b.rect.x = self.x+50
            b.update(dt)
    def draw(self, surf):
        panel = pygame.Surface((self.w, HEIGHT), pygame.SRCALPHA)
        panel.fill((30,30,30,230))
        surf.blit(panel, (self.x,0))
        if self.open:
            for b in self.buttons:
                b.draw(surf)

# ----- Load Main Pickle -----
try:
    main_img = pygame.image.load("pickle.png").convert_alpha()
except:
    main_img = pygame.Surface((150,150), pygame.SRCALPHA)
    pygame.draw.circle(main_img, (100,200,100), (75,75), 75)
pickle_rect = main_img.get_rect(center=(WIDTH//2, HEIGHT//2 - 30))
click_anim = 0.0

shop = Shop()
shop_btn = Button("Shop", (WIDTH-90,20), (80,40), shop.toggle)

# ----- Main Loop -----
last_tick = time.time()
while True:
    dt = clock.tick(FPS)/1000.0
    now = time.time()

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        shop_btn.handle_event(e)
        shop.handle_event(e)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if pickle_rect.collidepoint(e.pos):
                pickle_count += base_pickles_per_click * click_multiplier
                click_anim = 1.0
            for gold in falling_golds[:]:
                if gold.rect.collidepoint(e.pos):
                    click_multiplier = 4.0
                    pps_multiplier = 2.0
                    buff_end_time = now + 15
                    falling_golds.remove(gold)

    # continuous accumulation
    pickle_count += total_pps() * pps_multiplier * dt

    # buff expiration
    if now >= buff_end_time:
        click_multiplier = 1.0
        pps_multiplier = 1.0

    # spawn normal pickles
    spawn_accum += total_pps() * FALL_RATE_FACTOR * dt
    while spawn_accum >= 1.0:
        falling_pickles.append(FallingPickle())
        spawn_accum -= 1.0
    for fp in falling_pickles[:]:
        fp.update(dt)
        if fp.y > HEIGHT+20:
            falling_pickles.remove(fp)

    # spawn golden pickles
    if now >= next_golden_time:
        falling_golds.append(FallingGold())
        next_golden_time = now + random.uniform(45, 90)
    for gold in falling_golds[:]:
        gold.update(dt)
        if gold.y > HEIGHT+20:
            falling_golds.remove(gold)

    # win check
    if not game_won and pickle_count >= 1e6:
        game_won = True
        print("🎉 You’ve amassed 1,000,000 pickles! 🎉")

    shop_btn.update(dt)
    shop.update(dt)
    click_anim += (0.0 - click_anim)*dt*8

    # Dynamic gradient background with clamped values
    t = pygame.time.get_ticks()/1000.0
    c1 = [30 + 20*math.sin(t*0.1), 30 + 20*math.sin(t*0.1+2), 50 + 20*math.sin(t*0.1+4)]
    c2 = [10 + 20*math.sin(t*0.1+1), 10 + 20*math.sin(t*0.1+3), 30 + 20*math.sin(t*0.1+5)]
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = max(0, min(255, int(c1[0] + (c2[0] - c1[0]) * ratio)))
        g = max(0, min(255, int(c1[1] + (c2[1] - c1[1]) * ratio)))
        b = max(0, min(255, int(c1[2] + (c2[2] - c1[2]) * ratio)))
        pygame.draw.line(screen, (r, g, b), (0, y), (WIDTH, y))

    # draw sprites
    for fp in falling_pickles: fp.draw(screen)
    for gold in falling_golds: gold.draw(screen)

    # glow effect
    if now < buff_end_time:
        phase = pygame.time.get_ticks() / 300
        glow_r = 80 + 20 * math.sin(phase)
        glow_a = 120 + 80 * math.sin(phase * 1.5)
        glow_surf = pygame.Surface((int(glow_r*2), int(glow_r*2)), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255,255,0, int(glow_a)), (int(glow_r), int(glow_r)), int(glow_r))
        screen.blit(glow_surf, (pickle_rect.centerx - glow_r, pickle_rect.centery - glow_r))

    # draw main pickle
    scale = 1 + 0.1 * click_anim
    pw, ph = pickle_rect.size
    img = pygame.transform.smoothscale(main_img, (int(pw*scale), int(ph*scale)))
    screen.blit(img, img.get_rect(center=pickle_rect.center))

    # draw stats (with gradient when buff is active)
    if now < buff_end_time:
        t = pygame.time.get_ticks() / 1000.0
        render_gradient_text(screen,
            f"Pickles: {int(pickle_count):,}",
            BIG_FONT, (20,20), t, speed=0.3)
        render_gradient_text(screen,
            f"PPC: {base_pickles_per_click} x{int(click_multiplier)}   PPS: {int(total_pps() * pps_multiplier):,}",
            FONT,    (20,60), t, speed=0.3)
    else:
        screen.blit(BIG_FONT.render(f"Pickles: {int(pickle_count):,}", True, WHITE), (20,20))
        screen.blit(FONT.render(f"PPC: {base_pickles_per_click} x{int(click_multiplier)}   PPS: {int(total_pps() * pps_multiplier):,}", True, WHITE), (20,60))


    # draw UI on top
    shop.draw(screen)
    shop_btn.draw(screen)

    pygame.display.flip()

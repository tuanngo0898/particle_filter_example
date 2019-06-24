import random
from draw import *
import time
import bisect
import numpy as np
from matplotlib import pyplot as plt 

"""
# Smaller maze
"""
maze_data = ( ( 2, 0, 1, 0, 0 ),
              ( 0, 0, 0, 0, 1 ),
              ( 1, 1, 1, 0, 0 ),
              ( 1, 0, 0, 0, 0 ),
              ( 0, 0, 2, 0, 1 ))


# 0 - empty square
# 1 - occupied square
# 2 - occupied square with a beacon at each corner, detectable by the robot

# maze_data = ( ( 1, 1, 0, 0, 2, 0, 0, 0, 0, 1 ),
#               ( 1, 2, 0, 0, 1, 1, 0, 0, 0, 0 ),
#               ( 0, 1, 1, 0, 0, 0, 0, 1, 0, 1 ),
#               ( 0, 0, 0, 0, 1, 0, 0, 1, 1, 2 ),
#               ( 1, 1, 0, 1, 1, 2, 0, 0, 1, 0 ),
#               ( 1, 1, 1, 0, 1, 1, 1, 0, 2, 0 ),
#               ( 2, 0, 0, 0, 0, 0, 0, 0, 0, 0 ),
#               ( 1, 2, 0, 1, 1, 1, 1, 0, 0, 0 ),
#               ( 0, 0, 0, 0, 1, 0, 0, 0, 1, 0 ),
#               ( 0, 0, 1, 0, 0, 2, 1, 1, 1, 0 ))

PARTICLE_COUNT = 500
ROBOT_HAS_COMPASS = True

def add_noise(level, *coords):
    return [x + np.random.uniform(-level, level) for x in coords]

def add_little_noise(*coords):
    return add_noise(0.1, *coords)

def add_some_noise(*coords):
    return add_noise(0.1, *coords)

# This is just a gaussian kernel I pulled out of my hat, to transform
# values near to robbie's measurement => 1, further away => 0
sigma2 = 0.1 ** 2
def w_gauss(a, b):
    error = a - b
    g = math.e ** -(error ** 2 / (2 * sigma2))
    return g

# ------------------------------------------------------------------------
class WeightedDistribution(object):
    def __init__(self, state):
        accum = 0.0
        
        # new particle consist of particle which have p.w > 0
        self.state = [p for p in state if p.w > 0]

        # accumulated distribution
        self.distribution = []
        for x in self.state:
            accum += x.w
            self.distribution.append(accum)

    def pick(self):
        try:
            return self.state[bisect.bisect_left(self.distribution, np.random.uniform(0, 1))]
        except IndexError:
            # Happens when all particles are improbable w=0
            return None

# ------------------------------------------------------------------------
class Particle(object):
    def __init__(self, x, y, heading=None, w=1, noisy=False):
        if heading is None:
            heading = random.uniform(0, 360)
        if noisy:
            x, y, heading = add_some_noise(x, y, heading)

        self.x = x
        self.y = y
        self.h = heading
        self.w = w

    def __repr__(self):
        return "(%f, %f, w=%f)" % (self.x, self.y, self.w)

    @property
    def xy(self):
        return self.x, self.y

    @property
    def xyh(self):
        return self.x, self.y, self.h

    @classmethod
    def create_random(cls, count, maze):
        return [cls(*maze.random_free_place()) for _ in range(0, count)]

    def read_sensor(self, maze):
        """
        Find distance to nearest beacon.
        """
        return maze.distance_to_nearest_beacon(*self.xy)

    def advance_by(self, speed, checker=None, noisy=False):
        h = self.h
        if noisy:
            speed, h = add_little_noise(speed, h)
            h += random.uniform(-0.1, 0.1) # needs more noise to disperse better
        r = math.radians(h)
        dx = math.sin(r) * speed
        dy = math.cos(r) * speed
        if checker is None or checker(self, dx, dy):
            self.move_by(dx, dy)
            return True
        return False

    def move_by(self, x, y):
        self.x += x
        self.y += y


# ------------------------------------------------------------------------
class Robot(Particle):
    speed = 0.2

    def __init__(self, maze):
        super(Robot, self).__init__(*maze.random_free_place(), heading=90)
        self.chose_random_direction()
        self.step_count = 0

    def chose_random_direction(self):
        heading = random.uniform(0, 360)
        self.h = heading

    def read_sensor(self, maze):
        """
        Poor robot, it's sensors are noisy and pretty strange,
        it only can measure the distance to the nearest beacon(!)
        and is not very accurate at that too!
        """
        return add_little_noise(super(Robot, self).read_sensor(maze))[0]

    def move(self, maze):
        """
        Move the robot. Note that the movement is stochastic too.
        """
        while True:
            self.step_count += 1
            if self.advance_by(self.speed, noisy=True,
                checker=lambda r, dx, dy: maze.is_free(r.x+dx, r.y+dy)):
                break
            # Bumped into something or too long in same direction,
            # chose random new direction
            self.chose_random_direction()

# ------------------------------------------------------------------------

# ------------------------------------------------------------------------
def compute_mean_point(particles):
    """
    Compute the mean for all particles that have a reasonably good weight.
    This is not part of the particle filter algorithm but rather an
    addition to show the "best belief" for current position.
    """

    m_x, m_y, m_count = 0, 0, 0
    for p in particles:
        # m_count += p.w
        m_x += p.x * p.w
        m_y += p.y * p.w

    if len(particles) == 0:
        return -1, -1, False

    m_x /= len(particles)
    m_y /= len(particles)

    # Now compute how good that mean is -- check how many particles
    # actually are in the immediate vicinity
    m_count = 0
    for p in particles:
        if world.distance(p.x, p.y, m_x, m_y) < 1:
            m_count += 1

    return m_x, m_y, m_count > PARTICLE_COUNT * 0.95

world = Maze(maze_data)
world.draw()

# initial distribution assigns each particle an equal probability
particles = Particle.create_random(PARTICLE_COUNT, world)
print
print("particles: ")
for i in range(5): print(particles[i])
print
print(str(PARTICLE_COUNT) + " random particles")
print("each consist of position information: x,y and weight for particle: w")
print

robbie = Robot(world)

m_x, m_y, m_confident = compute_mean_point(particles)
print("m_x: " + str(m_x))
print("m_y: " + str(m_y))
print("m_confident: " + str(m_confident))

# ---------- Show current state ----------
world.show_particles(particles)
world.show_mean(m_x, m_y, m_confident)
world.show_robot(robbie)

t = time.time()

while True:
    ################################################ Predict new state ################################################
    # ---------- Move things ----------
    old_heading = robbie.h
    robbie.move(world)
    d_h = robbie.h - old_heading

    # Move particles according to my belief of movement (this may
    # be different than the real movement, but it's all I got)
    for p in particles:
        p.h += d_h # in case robot changed heading, swirl particle heading too
        p.advance_by(robbie.speed)

    ################################################ Take a measurement by reading robbie's sensor ################################################
    r_d = robbie.read_sensor(world)

    ################################################ Estimate new paricle ################################################
    # Update particle base on previous state and measaurement
    # Update particle weight according to how good every particle matches
    # robbie's sensor reading
    for p in particles:
        if world.is_free(*p.xy):
            p_d = p.read_sensor(world)
            p.w = w_gauss(r_d, p_d)
        else:
            p.w = 0

    print
    print("Estimated particles: ")
    for i in range(5): print(particles[i])

    ################################################ Resampling ################################################
    # ---------- Shuffle particles ----------
    new_particles = []

    # Normalise weights
    nu = sum(p.w for p in particles)
    if nu:
        for p in particles:
            p.w = p.w / nu
    print("Normalized weight particles")
    for i in range(5): print(particles[i])

    # create a weighted distribution, for fast picking
    dist = WeightedDistribution(particles)

    for _ in particles:
        p = dist.pick()
        if p is None:  # No pick b/c all totally improbable
            new_particle = Particle.create_random(1, world)[0]
        else:
            new_particle = Particle(p.x, p.y,
                    heading=robbie.h if ROBOT_HAS_COMPASS else p.h,
                    noisy=True)
            new_particles.append(new_particle)

    particles = new_particles

    print(str(len(particles)) + " new resampling particles: ")
    for i in range(5): print(particles[i])

    # ---------- Try to find current best estimate for display ----------
    m_x, m_y, m_confident = compute_mean_point(particles)
    print(m_x, m_y, m_confident)
    # ---------- Show current state ----------
    world.show_particles(particles)
    world.show_mean(m_x, m_y, m_confident)
    world.show_robot(robbie)

    plt.figure("particle distribution")
    hist, bin_edges = np.histogram([particle.x for particle in particles[:]],bins=100,range=(0,5))
    plt.plot(hist)
    hist, bin_edges = np.histogram([particle.y for particle in particles[:]],bins=100,range=(0,5))
    plt.plot(hist)
    plt.ylim((0,100))
    plt.legend(["x","y"])
    plt.pause(0.1)

    while time.time() - t < 1:
        time.sleep(0.1)
    t = time.time()
    plt.clf()

    

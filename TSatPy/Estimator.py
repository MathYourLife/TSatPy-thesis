
import time
from twisted.internet.task import LoopingCall
from TSatPy import State
from TSatPy import StateOperators

time_vary = True

class Estimator(object):
    def __init__(self, clock, **kwargs):
        self.x_hat = State.State()
        self.estimators = {
            'pid': PID(clock, **kwargs),
        }

    def update(self, x, M=None):

        for est in self.estimators.keys():
            self.estimators[est].update(x=x, M=M)
        pass


class EstimatorBase(object):

    def __init__(self, clock, propagate_every=None, plant=None, ic=None):
        self.clock = clock
        self.last_update = None
        self.I = [[4, 0, 0], [0, 4, 0], [0, 0, 4]]
        if ic is None:
            self.x_hat = State.State()
        else:
            self.x_hat = ic
        self.plant = plant
        self.propagate_every = propagate_every

        if self.propagate_every is not None:
            self.timers = {
                'propagate': LoopingCall(self.propagate)
            }
            self.start_propagation()

    def start_propagation(self):
        if self.propagate_every is not None:
            self.timers['propagate'].start(self.propagate_every)

    def propagate(self, M=None):
        pass

    def update(self, x, M=None):
        pass


class PID(EstimatorBase):

    def __init__(self, clock, **kwargs):
        EstimatorBase.__init__(self, clock, **kwargs)

        # Zero out state integrator
        self.x_i = State.State()
        self.last_err = None
        self.K = {
            'p': None,
            'i': None,
            'd': None,
        }

    def set_Kp(self, K):
        self.K['p'] = K

    def set_Ki(self, K):
        self.K['i'] = K

    def set_Kd(self, K):
        self.K['d'] = K

    def update(self, x, M=None):
        t = self.clock.tick()
        try:
            dt = t - self.last_update
        except TypeError:
            dt = 0

        # Use the plant dynamics to predict where the system's state
        # should be now.
        if self.plant:
            self.plant.propagate()
            x_hat_pre = self.plant.x
            self.x_hat.q.vector = x_hat_pre.q.vector
            self.x_hat.q.scalar = x_hat_pre.q.scalar
            self.x_hat.w.w = x_hat_pre.w.w


        x_err = State.StateError(self.x_hat, x)
        x_adj = State.State()

        if self.K['p'] is not None:
            x_kp = self.K['p'] * x_err
            x_adj += x_kp

        if dt and self.K['i'] is not None:
            Kq = StateOperators.QuaternionGain(dt)
            Kw = StateOperators.BodyRateGain(
                [[dt, 0, 0], [0, dt, 0], [0, 0, dt]])
            Kt = StateOperators.StateGain(Kq, Kw)

            x_i_err = Kt * x_err
            if time_vary:
                self.x_i += x_i_err
            else:
                self.x_i += x_err

            x_ki = self.K['i'] * self.x_i
            x_adj += x_ki

        if dt and self.K['d'] is not None:
            Kq = StateOperators.QuaternionGain(1 / dt)
            Kw = StateOperators.BodyRateGain(
                [[1 / dt, 0, 0], [0, 1 / dt, 0], [0, 0, 1 / dt]])
            Kt = StateOperators.StateGain(Kq, Kw)

            x_diff = x_err - self.last_err
            x_d_err = Kt * x_diff
            if time_vary:
                x_kd = self.K['d'] * x_d_err
            else:
                x_kd = self.K['d'] * x_diff
            x_adj += x_kd

        self.x_adj = x_adj
        self.x_hat -= x_adj
        if self.plant:
            self.plant.set_state(self.x_hat)
        self.last_update = t
        self.last_err = x_err
        return self.x_hat

    def __str__(self):
        gains = [self.__class__.__name__, ' x_hat %s' % self.x_hat]
        for G in self.K.iteritems():
            gains.append(' K%s %s' % G)
        return '\n'.join(gains)

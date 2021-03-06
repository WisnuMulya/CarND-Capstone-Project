import rospy

from pid import PID
from yaw_controller import YawController
from lowpass import LowPassFilter

GAS_DENSITY = 2.858
ONE_MPH = 0.44704


class Controller(object):
    def __init__(self, vehicle_mass, fuel_capacity, brake_deadband, decel_limit,
                 accel_limit, wheel_radius, wheel_base, steer_ratio, max_lat_accel, max_steer_angle):
        # Implement yaw controller
        self.yaw_controller = YawController(wheel_base, steer_ratio, 0.1, max_lat_accel, max_steer_angle)

        # Implement PID controller
        kp = 0.3
        ki = 0.1
        kd = 0.
        mn = 0 # minimum throttle value
        mx = 0.2 # maximum throttle value
        self.throttle_controller = PID(kp, ki, kd, mn, mx)

        # Implement low pass filter
        tau = 0.5 # 1/(2pi*tau) = cutoff frequency
        ts = 0.2 # Sample time
        self.vel_lpf = LowPassFilter(tau, ts)

        self.vehicle_mass = vehicle_mass
        self.fuel_capacity = fuel_capacity
        self.brake_deadband = brake_deadband
        self.decel_limit = decel_limit
        self.accel_limit = accel_limit
        self.wheel_radius = wheel_radius

        self.last_time = rospy.get_time()

    def control(self, linear_vel, angular_vel, current_vel, dbw_enabled):
        # Check if DBW is enabled
        if not dbw_enabled:
            self.throttle_controller.reset()
            return 0., 0., 0.

        # Pass current filter through the low pass filter
        current_vel = self.vel_lpf.filt(current_vel)

        # Debugging log
        # rospy.logwarn('Angular vel: {0}'.format(angular_vel))
        # rospy.logwarn('Target vel: {0}'.format(linear_vel))
        # rospy.logwarn('Target angular vel: {0}\n'.format(angular_vel))
        # rospy.logwarn('Current vel: {0}'.format(current_vel))
        # rospy.logwarn('Filtered vel: {0}'.format(self.vel_lpf.get()))

        # Get steering value
        steering = self.yaw_controller.get_steering(linear_vel, angular_vel, current_vel)

        # Get values for PID
        vel_error = linear_vel - current_vel
        self.last_vel = current_vel

        current_time = rospy.get_time()
        sample_time = current_time - self.last_time
        self.last_time = current_time

        # Get throttle value
        throttle = self.throttle_controller.step(vel_error, sample_time)
        brake = 0

        # Implement logic for brake
        if linear_vel == 0 and current_vel < 0.1:
            throttle = 0
            brake = 700 # holding car in place, e.g. when stop at a light
        elif throttle < .1 and vel_error < 0:
            throttle = 0 # since we're going faster than we wanna be
            decel = max(vel_error, self.decel_limit)
            brake = abs(decel) * self.vehicle_mass * self.wheel_radius # torque = N*m

        return throttle, brake, steering
        

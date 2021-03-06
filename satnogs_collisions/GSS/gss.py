import ephem
from satnogs_collisions.satellite import Satellite
from satnogs_collisions.ground_station import GroundStation
from datetime import datetime

C = 299792458.0                                         # Define speed of light

def _time_range_intersection(sat1_rise, sat1_set, sat2_rise, sat2_set):
    """Computes the intersection of the rise and set time intervals of the 2 satellites.

    :param sat1_rise: Rise time of Satellite 1
    :type sat1_rise: datetime/Ephem.Date instance
    :param sat1_set: Set time of Satellite 1
    :type sat1_set: datetime/Ephem.Date instance
    :param sat2_rise: Rise time of Satellite 2
    :type sat2_rise: datetime/ephem.Date instance
    :param sat2_set: Set time of Satellite 2
    :type sat2_set: datetime/ephem.Date instance
    :return: time range intersection
    :rtype: tuple
    """
    low = max(sat1_rise, sat2_rise)
    high = min(sat1_set, sat2_set)
    if (low <= high):
        return [low.datetime(), high.datetime()]
    return

def _compute_doppler_shift(sat, observer, freq, rise_time, set_time):
    """Computes the Maximum Doppler shift in the frequency at the ground station.
    Returns the Max and min doppler shifted frequencies for each frequency received at the GroundStation.

    :param sat: Satellite
    :type sat: instance of ephem satellite
    :param observer: Ground Station / Observer
    :type observer: Instance of ephem ground station
    :param freq: Satellite transmitting frequencies
    :type freq: list
    :param rise_time: Rise time of Satellite
    :type rise_time: datetime/ephem.Date instance
    :param set_time: Set time of Satellite
    :type set_time: datetime/ephem.Date instance
    """
    freq_low_high = {}                                          # Append max and min frequencies shift to the list
    for elem in freq:   
        freq_low_high[elem] = []                                # Maximum shift observed at Rise time
        observer.date = rise_time
        sat.compute(observer)
        rel_vel = sat.range_velocity
        shift_r = (rel_vel/C)*(elem)
        observer.date = set_time                                # Maximum shift observed at Set time
        sat.compute(observer)
        rel_vel = sat.range_velocity
        shift_s = (rel_vel/C)*(elem)
        freq_low_high[elem].append(elem + shift_r)
        freq_low_high[elem].append(elem + shift_s)
    return freq_low_high

def _in_freq_range(frequencies1, frequencies2, f_range):
    """Checks if the frequencies of both the satellites fall under the given range.
    """    
    freq_list = []                                              # compare all the frequencies
    for key1, val1 in frequencies1.items():
        for key2, val2 in frequencies2.items():
            if (abs(val1[0] - val2[0]) <= f_range) or (abs(val1[0] - val2[1]) <= f_range) or (abs(val1[1] - val2[0]) <= f_range) or (abs(val1[1] - val2[1]) <= f_range):
                freq_list.append((key1, key2))
    if len(freq_list):
        return freq_list
    return False

def _check_collision(ground_station, sat1, sat2, date_time_range, frequency_range, time_period=False):
    """Checks and computes the possible collision between Sat1 and Sat2

    :param ground_station: Ground Station object
    :type ground_station: Instance of `GroundStation`
    :param sat1: Satellite 1
    :type sat1: Instance of `Satellite`
    :param sat2: Satellite 2
    :type sat2: Instance of `Satellite`
    :param date_time_range: User specified Time interval
    :type date_time_range: datetime
    :param frequency_range: frequency in Hz
    :type frequency_range: int
    :param time_period: , defaults to False
    :type time_period: bool, optional
    :return: bool/ Array of time periods if there is a collision
    :rtype: bool/list
    """
    ground_coordinates = ground_station.get_coordinates()           # Extract ground coordinates  
    observer = ephem.Observer()                                     # Define an Epem Observer
    observer.elevation = ground_station.get_elevation()
    observer.lat = str(ground_coordinates[0])
    observer.lon = str(ground_coordinates[1])

    line1, line2, line3 = sat1.get_tle()                            # Read TLE of both the sateellites and create an instance
    satA = ephem.readtle(line1, line2, line3)
    line1, line2, line3 = sat2.get_tle()
    satB = ephem.readtle(line1, line2, line3)

    # This stores an array of intervals as there could be multiple RF collisions 
    # between the  satellites at the given time interval. 
    collisions = []

    e_low = ephem.Date(date_time_range[0])                          # Convert the date_time interval to ephem Date instances
    e_high = ephem.Date(date_time_range[1])
    e = e_low - ephem.hour                                          # Decrement e by an hour to record the collisions that start slightly before e_low
    while (e <= e_high):
        observer.date = e                                           # Set the date and time of the oberserver

        # `next_pass` computes the rise_time, Rise azimuth ,maximum_atlitude,
        # max_altitude_time, set_time and set Azimuth of the Satellite.
        infoA = observer.next_pass(satA)
        infoB = observer.next_pass(satB)

        # Check if the satellites' have a period of intersection
        intersection_range = _time_range_intersection(infoA[0], infoA[4], infoB[0], infoB[4])

        # Check the brackets of intersection range with the defined datetime range
        if intersection_range:
            if (intersection_range[0] > e_high.datetime() or intersection_range[1] < e_low.datetime()):
                intersection_range = None
            else:
                if (intersection_range[0] < e_low.datetime()):
                    intersection_range[0] = e_low.datetime()
                if (intersection_range[1] > e_high.datetime()):
                    intersection_range[1] = e_high.datetime()

        if intersection_range is not None:
            # Compute the Maximum and minimum Doppler frequencies
            # for all the frequencies for both the satellites
            freq1_low_high = _compute_doppler_shift(satA, observer, sat1.get_frequencies(), infoA[0], infoA[4])
            freq2_low_high = _compute_doppler_shift(satB, observer, sat2.get_frequencies(), infoB[0], infoB[4])
            freq_list = _in_freq_range(freq1_low_high, freq2_low_high, frequency_range)
            if (freq_list):
                if not time_period:
                    return True
                temp = {}
                temp["ground_station"] = {}                                         # Add Ground Station Meta data to the dictionary
                temp["ground_station"]["id"] = ground_station.get_id()
                temp["ground_station"]["latitude"] = ground_coordinates[0]
                temp["ground_station"]["longitude"] = ground_coordinates[1]
                temp["ground_station"]["elevation"] = ground_station.get_elevation()
                temp["satellites"] = []
                sat_dict = {}                                                       # Add Satellites' Meta data to the dictionary
                sat_dict["norad_id"] = sat1.get_name().split(' ')[0]
                sat_dict["name"] = sat1.get_name().split(' ')[1]
                sat_dict["tle"] = sat1.get_tle()
                sat_dict["frequencies"] = sat1.get_frequencies()
                sat_dict["collision_frequencies"] = []
                for elem in freq_list:
                    sat_dict["collision_frequencies"].append(elem[0])
                temp["satellites"].append(sat_dict)
                sat_dict = {}
                sat_dict["norad_id"] = sat2.get_name().split(' ')[0]
                sat_dict["name"] = sat2.get_name().split(' ')[1]
                sat_dict["tle"] = sat2.get_tle()
                sat_dict["frequencies"] = sat2.get_frequencies()
                sat_dict["collision_frequencies"] = []
                for elem in freq_list:
                    sat_dict["collision_frequencies"].append(elem[1])
                temp["satellites"].append(sat_dict)
                temp["time_period"] = intersection_range                            # Add time period of the collision
                collisions.append(temp)

        e = ephem.Date(min(infoA[4], infoB[4]) + ephem.minute)                      # Check for every increment after the minimum `set_time`

    if (len(collisions) == 0):                                                      # Return True or time_periods depending on the passed argument `time_period`
        return collisions if time_period else False
    return collisions


def detect_RF_collision_of_satellite_over_groundstation(ground_station, 
                    satellites, main_sat, date_time_range, frequency_range=30000, time_period=False):
    """Detects RF collisions that main satellite will have with 
    other satellites over a ground station

    :param ground_station: Ground Station
    :type ground_station: Instance of `GroundStation`
    :param satellites: List of Satellites
    :type satellites: list
    :param main_sat: Satellite
    :type main_sat: Instance of `Satellite`
    :param date_time_range: User defined date-time range
    :type date_time_range: datetime
    :param frequency_range: Frequency in Hz, defaults to 30000
    :type frequency_range: int, optional
    :param time_period: Set to True if desired to compute the time periods of intersection, defaults to False
    :type time_period: bool, optional
    :return: list of all collisions
    :rtype: list
    """
    rf_collisions = []
    for sat in satellites:
            rf_collisions.append(_check_collision(ground_station, main_sat, sat, 
                    date_time_range, frequency_range, time_period=time_period))
    return rf_collisions

def detect_RF_collision_of_satellite_over_groundstations(ground_stations, 
                    satellites, main_sat, date_time_range, frequency_range=30000, time_period=False):
    """Detects RF collisions that main satellite will have with 
    other satellites over every ground station

    :param ground_station: List of `GroundStation`s
    :return: ditcionary contaning all collisions
    :rtype: dictionary
    """
    all_rf_collisions = {}
    id = 1                                                      # Ground Station index for the dictionary.
    for ground_station in ground_stations:
        rf_collisions = []
        for sat in satellites:
                rf_collisions.append(_check_collision(ground_station, main_sat, sat, 
                        date_time_range, frequency_range=frequency_range, time_period=time_period))
        all_rf_collisions[id] = rf_collisions
        id += 1
    return all_rf_collisions

def detect_RF_collision_of_satellites_over_groundstation(ground_station, 
                    satellites, date_time_range, frequency_range=30000, time_period=False):
    """Detects RF collisions that every pair of satellites will have with 
    each other over a ground station

    :param ground_station: `GroundStation`s
    :param satellites: List of `Satellites`s
    :return: ditcionary contaning all collisions
    :rtype: dictionary
    """
    all_rf_collisions = {}
    for main_sat in satellites:
        # Create a satellite list to pass to `detect_RF_collision_of_satellite_over_groundstation`
        sat_list  = []
        for sat in satellites:
            if (sat != main_sat):
                sat_list.append(sat)
        all_rf_collisions[main_sat.get_name()] = (detect_RF_collision_of_satellite_over_groundstation(ground_station, sat_list, main_sat,
                                               date_time_range, frequency_range=frequency_range, time_period=time_period))
    return all_rf_collisions

def detect_RF_collision_of_satellites_over_groundstations(ground_stations, 
                    satellites, date_time_range, frequency_range=30000, time_period=False):
    """Detects RF collisions that every pair of satellites will have with 
    each other over every ground station

    :param ground_station: List of `GroundStation`s
    :param satellites: List of `Satellites`s
    :return: ditcionary contaning all collisions
    :rtype: dictionary
    """
    all_rf_collisions = {}
    id = 1
    for ground_station in ground_stations:
        all_rf_collisions[id] = (detect_RF_collision_of_satellites_over_groundstation(ground_station, satellites, date_time_range,
                         frequency_range=frequency_range, time_period=time_period))
        id += 1
    return all_rf_collisions

def compute_RF_collision_of_satellite_over_groundstation(ground_station, 
                    satellites, main_sat, date_time_range, frequency_range=30000):
    """Computes RF collisions that main satellite will have with 
    other satellites over a ground station

    :param ground_station: Ground Station
    :type ground_station: Instance of `GroundStation`
    :param satellites: List of Satellites
    :type satellites: list
    :param main_sat: Satellite
    :type main_sat: Instance of `Satellite`
    :param date_time_range: User defined date-time range
    :type date_time_range: datetime
    :param frequency_range: Frequency in Hz, defaults to 30000
    :type frequency_range: int, optional
    :return: list of all collisions
    :rtype: list
    """
    return detect_RF_collision_of_satellite_over_groundstation(ground_station, 
                    satellites, main_sat, date_time_range, frequency_range=frequency_range, time_period=True)

def compute_RF_collision_of_satellite_over_groundstations(ground_stations, 
                    satellites, main_sat, date_time_range, frequency_range=30000):
    """Computes the time periods of the RF collisions that every pair of satellite will
    have with each other over the ground station.
    """
    return detect_RF_collision_of_satellite_over_groundstations(ground_stations, 
                    satellites, main_sat, date_time_range, frequency_range=frequency_range, time_period=True)

def compute_RF_collision_of_satellites_over_groundstation(ground_station, 
                    satellites, date_time_range, frequency_range=30000, time_period=False):
    """Computes the time periods of the RF collisions that every pair of satellite will
    have with each other over the ground station. 
    """
    return detect_RF_collision_of_satellites_over_groundstation(ground_station, 
                    satellites, date_time_range, frequency_range=frequency_range, time_period=True)

def compute_RF_collision_of_satellites_over_groundstations(ground_stations, 
                    satellites, date_time_range, frequency_range=30000, time_period=False):
    """Computes the time periods of the RF collisions that every pair of satellite will
    have with each other over every ground station. 
    """
    return detect_RF_collision_of_satellites_over_groundstations(ground_stations, 
                    satellites, date_time_range, frequency_range=frequency_range, time_period=True)